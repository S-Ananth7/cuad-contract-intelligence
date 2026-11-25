"""Everything the live review reads and writes in Postgres. Plain functions that take an open connection.

Jobs are rows in live_submissions. A worker claims one with FOR UPDATE SKIP LOCKED, so two workers never take the
same upload, and a job whose worker died (no heartbeat) goes back in the queue.
"""
import hashlib
import json
from pathlib import Path

from cuad_ai.embed import vector_literal
from cuad_ai.live import config, tenants


class RejectedUpload(ValueError):
    """The upload is not accepted. The message is safe to show the person."""


class LimitReached(RejectedUpload):
    """Too many uploads today. A different answer for a web client: try again later, not fix the file."""


def ensure_schema(conn):
    conn.execute(Path(config.SQL_PATH).read_text(encoding="utf-8"))
    conn.commit()


def bank_company(conn, filename, company=None):
    """The CUAD company this upload may be a copy of, spelled as the bank spells it, or None.

    CUAD file names start with the company ("ACME_20200101_10-K_..."). If an upload matches one, that company's
    examples are left out of the search and the judges, exactly as they were for the test contracts.
    """
    guess = (company or Path(filename).stem.split("_")[0]).strip()
    if not guess:
        return None
    row = conn.execute("SELECT company FROM contracts WHERE lower(company) = lower(%s) LIMIT 1", (guess,)).fetchone()
    return row[0] if row else None


def submit(conn, tenant, filename, text, company=None, uploaded_by=""):
    """Store an upload for one client and queue it. Returns the submission id. Raises RejectedUpload with a reason.

    The same text from the same client is not stored twice; another client's identical file is a separate upload.
    """
    if tenants.get_tenant(conn, tenant) is None:
        raise RejectedUpload("This account is not set up for uploads.")
    text = text.replace("\x00", "")
    if not text.strip():
        raise RejectedUpload("The file is empty.")
    if len(text) > config.max_chars():
        raise RejectedUpload(f"The file has {len(text):,} characters; the limit is {config.max_chars():,}.")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    same = conn.execute(
        "SELECT id FROM live_submissions WHERE tenant = %s AND sha256 = %s AND status <> 'failed' "
        "ORDER BY id LIMIT 1", (tenant, digest)).fetchone()
    if same:  # the same text again costs nothing: show the answers already there
        return same[0]
    cap = conn.execute("SELECT daily_cap FROM live_tenants WHERE id = %s", (tenant,)).fetchone()[0]
    cap = config.daily_cap() if cap is None else cap
    mine, everyone = conn.execute(
        "SELECT count(*) FILTER (WHERE tenant = %s), count(*) FROM live_submissions "
        "WHERE created_at > now() - interval '24 hours'", (tenant,)).fetchone()
    if mine >= cap or everyone >= config.global_cap():
        raise LimitReached("The daily upload limit has been reached. Please try again tomorrow.")
    row = conn.execute(
        "INSERT INTO live_submissions (tenant, uploaded_by, filename, text, n_chars, sha256, excluded_company) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (tenant, uploaded_by[:200], Path(filename).name[:200], text, len(text), digest,
         bank_company(conn, filename, company))).fetchone()
    conn.commit()
    return row[0]


def requeue_stale(conn):
    """Put running jobs whose worker stopped reporting back in the queue. Returns how many."""
    rows = conn.execute(
        "UPDATE live_submissions SET status = 'queued', started_at = NULL "
        "WHERE status = 'running' AND heartbeat_at < now() - make_interval(mins => %s) RETURNING id",
        (config.stale_minutes(),)).fetchall()
    conn.commit()
    return len(rows)


def claim(conn):
    """Take the oldest queued upload and mark it running. Returns its row (a dict) or None."""
    requeue_stale(conn)
    row = conn.execute(
        "UPDATE live_submissions SET status = 'running', started_at = now(), heartbeat_at = now(), "
        "error = NULL, done_questions = 0 "
        "WHERE id = (SELECT id FROM live_submissions WHERE status = 'queued' ORDER BY id "
        "FOR UPDATE SKIP LOCKED LIMIT 1) "
        "RETURNING id, filename, text, excluded_company").fetchone()
    conn.commit()
    return dict(zip(("id", "filename", "text", "excluded_company"), row)) if row else None


def heartbeat(conn, submission_id, done, total, tokens_in, tokens_out):
    conn.execute(
        "UPDATE live_submissions SET heartbeat_at = now(), done_questions = %s, total_questions = %s, "
        "tokens_in = %s, tokens_out = %s WHERE id = %s",
        (done, total, tokens_in, tokens_out, submission_id))
    conn.commit()


def finish(conn, submission_id):
    conn.execute("UPDATE live_submissions SET status = 'done', finished_at = now() WHERE id = %s", (submission_id,))
    conn.commit()


def fail(conn, submission_id, reason):
    conn.execute(
        "UPDATE live_submissions SET status = 'failed', error = %s, finished_at = now() WHERE id = %s",
        (reason[:500], submission_id))
    conn.commit()


def save_chunks(conn, submission_id, rows):
    """rows: (start, end, text, embedding vector as a list of floats)."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO live_chunks (submission_id, start_char, end_char, text, embedding) "
            "VALUES (%s, %s, %s, %s, %s::vector) ON CONFLICT (submission_id, start_char) DO NOTHING",
            [(submission_id, s, e, t, vector_literal(v)) for s, e, t, v in rows])
    conn.commit()


def save_answer(conn, submission_id, a):
    """Insert or replace the answer for one clause. `a` is the dict made by process.answer_clause."""
    conn.execute(
        "INSERT INTO live_answers (submission_id, clause, decision, reason, quotes, spans, risk, rank_asked, "
        "verdict, verdict2, looks_like, retried, tokens_in, tokens_out) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (submission_id, clause) DO UPDATE SET decision = EXCLUDED.decision, reason = EXCLUDED.reason, "
        "quotes = EXCLUDED.quotes, spans = EXCLUDED.spans, risk = EXCLUDED.risk, rank_asked = EXCLUDED.rank_asked, "
        "verdict = EXCLUDED.verdict, verdict2 = EXCLUDED.verdict2, looks_like = EXCLUDED.looks_like, "
        "retried = EXCLUDED.retried, tokens_in = EXCLUDED.tokens_in, tokens_out = EXCLUDED.tokens_out",
        (submission_id, a["clause"], a["decision"], a["reason"], json.dumps(a["quotes"]), json.dumps(a["spans"]),
         a["risk"], a["rank_asked"], a["verdict"], a["verdict2"], json.dumps(a["looks_like"]),
         a["retried"], a["tokens_in"], a["tokens_out"]))
    conn.commit()


def clear_results(conn, submission_id):
    """Start a run from nothing, so a restarted job never shows answers from an earlier attempt."""
    conn.execute("DELETE FROM live_answers WHERE submission_id = %s", (submission_id,))
    conn.execute("DELETE FROM live_chunks WHERE submission_id = %s", (submission_id,))
    conn.commit()


SUBMISSION_COLUMNS = ("id", "filename", "n_chars", "status", "error", "done_questions", "total_questions",
                      "tokens_in", "tokens_out", "excluded_company", "created_at", "finished_at")


def get_submission(conn, tenant, submission_id):
    """One of this client's uploads, or None. An id that belongs to another client is simply not found."""
    row = conn.execute(f"SELECT {', '.join(SUBMISSION_COLUMNS)} FROM live_submissions WHERE id = %s AND tenant = %s",
                       (submission_id, tenant)).fetchone()
    return dict(zip(SUBMISSION_COLUMNS, row)) if row else None


def list_submissions(conn, tenant, limit=50):
    rows = conn.execute(
        f"SELECT {', '.join(SUBMISSION_COLUMNS)} FROM live_submissions WHERE tenant = %s ORDER BY id DESC LIMIT %s",
        (tenant, limit)).fetchall()
    return [dict(zip(SUBMISSION_COLUMNS, row)) for row in rows]


def get_text(conn, tenant, submission_id):
    row = conn.execute("SELECT text FROM live_submissions WHERE id = %s AND tenant = %s",
                       (submission_id, tenant)).fetchone()
    return row[0] if row else None


ANSWER_COLUMNS = ("id", "clause", "decision", "reason", "quotes", "spans", "risk", "rank_asked", "verdict",
                  "verdict2", "looks_like", "retried", "review_action", "review_note", "reviewer")


def get_answers(conn, tenant, submission_id):
    """Every answer of one upload, with the person's decision when there is one, in clause order."""
    rows = conn.execute(
        "SELECT a.id, a.clause, a.decision, a.reason, a.quotes, a.spans, a.risk, a.rank_asked, a.verdict, "
        "a.verdict2, a.looks_like, a.retried, r.action, r.note, r.reviewer "
        "FROM live_answers a LEFT JOIN live_reviews r ON r.answer_id = a.id "
        "WHERE a.submission_id = %s AND a.submission_id IN (SELECT id FROM live_submissions WHERE tenant = %s) "
        "ORDER BY a.clause", (submission_id, tenant)).fetchall()
    return [dict(zip(ANSWER_COLUMNS, row)) for row in rows]


def review_answer(conn, tenant, submission_id, answer_id, reviewer, action, note=""):
    """Record a person's confirm or reject. Raises LookupError if the answer is not part of this upload."""
    if action not in ("confirm", "reject"):
        raise ValueError("action must be 'confirm' or 'reject'")
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("a reviewer name is required")
    found = conn.execute(
        "SELECT 1 FROM live_answers a JOIN live_submissions s ON s.id = a.submission_id "
        "WHERE a.id = %s AND a.submission_id = %s AND s.tenant = %s", (answer_id, submission_id, tenant)).fetchone()
    if not found:
        raise LookupError("no such answer")
    conn.execute(
        "INSERT INTO live_reviews (answer_id, reviewer, action, note) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (answer_id) DO UPDATE SET reviewer = EXCLUDED.reviewer, action = EXCLUDED.action, "
        "note = EXCLUDED.note, reviewed_at = now()",
        (answer_id, reviewer[:100], action, note[:1000]))
    conn.commit()


def clear_review(conn, tenant, submission_id, answer_id):
    """Take a review back. Returns True if there was one to remove (False for another client's answer too)."""
    row = conn.execute(
        "DELETE FROM live_reviews WHERE answer_id = %s AND answer_id IN "
        "(SELECT a.id FROM live_answers a JOIN live_submissions s ON s.id = a.submission_id "
        "WHERE a.submission_id = %s AND s.tenant = %s) RETURNING answer_id",
        (answer_id, submission_id, tenant)).fetchone()
    conn.commit()
    return row is not None


def delete_submission(conn, tenant, submission_id):
    """Remove one of this client's uploads and everything derived from it. Returns True if it existed."""
    row = conn.execute("DELETE FROM live_submissions WHERE id = %s AND tenant = %s RETURNING id",
                       (submission_id, tenant)).fetchone()
    conn.commit()
    return row is not None
