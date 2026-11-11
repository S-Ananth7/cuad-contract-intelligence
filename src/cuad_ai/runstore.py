"""Keep a finished run in Postgres, so runs can be listed and compared with SQL."""

from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SQL_PATH = Path(__file__).resolve().parents[2] / "sql" / "runs.sql"
DECISIONS = ("accept", "reject", "queue", "not_found")


def create_tables(conn):
    """Create the runs and answers tables and the run_scores view if they are missing."""
    conn.execute(SQL_PATH.read_text(encoding="utf-8"))


def run_fields(report):
    """The columns of one run, taken from a report summary (report_summary.json)."""
    meta = report["meta"]
    info = meta.get("run_info", {})
    return {
        "run_id": report["run_id"],
        "run_date": meta.get("date"),
        "model": meta.get("model"),
        "template": meta.get("template"),
        "k": meta.get("k"),
        "contracts": meta.get("contracts"),
        "git_commit": info.get("git_commit"),
        "prompt_hash": info.get("prompt_hash"),
        "meta": meta,
        "summary": report["summary"],
    }


def answer_rows(decisions, queue=()):
    """One row per question. Quotes and 'looks like' come from the queue file, where there are any."""
    queued = {(row["title"], row["clause"]): row for row in queue}
    rows = []
    for row in decisions:
        if row["decision"] not in DECISIONS:
            raise ValueError(f"unknown decision: {row['decision']!r}")
        extra = queued.get((row["title"], row["clause"]), {})
        rows.append(
            {
                "title": row["title"],
                "clause": row["clause"],
                "decision": row["decision"],
                "reason": row.get("reason", ""),
                "gold_found": bool(row["gold_found"]),
                "retried": bool(row.get("retried", False)),
                "quotes": extra.get("quotes", []),
                "looks_like": extra.get("looks_like", []),
            }
        )
    return rows


def score_rows(rows):
    """The same numbers as the run_scores view, computed in Python (used to check the SQL)."""
    accepted = [r for r in rows if r["decision"] == "accept"]
    accepted_real = sum(r["gold_found"] for r in accepted)
    lawyer_marked = sum(r["gold_found"] for r in rows)
    return {
        "questions": len(rows),
        "accepted": len(accepted),
        "accepted_real": accepted_real,
        "lawyer_marked": lawyer_marked,
        "accept_precision": round(accepted_real / len(accepted), 3) if accepted else None,
        "accept_recall": round(accepted_real / lawyer_marked, 3) if lawyer_marked else None,
    }


def save_run(conn, report, decisions, queue=()):
    """Store a run. Saving the same run id again replaces it, so loading twice is safe."""
    fields = run_fields(report)
    rows = answer_rows(decisions, queue)
    conn.execute(
        """
        INSERT INTO runs (run_id, run_date, model, template, k, contracts, git_commit, prompt_hash, meta, summary)
        VALUES (%(run_id)s, %(run_date)s, %(model)s, %(template)s, %(k)s, %(contracts)s,
                %(git_commit)s, %(prompt_hash)s, %(meta)s, %(summary)s)
        ON CONFLICT (run_id) DO UPDATE SET
            run_date = EXCLUDED.run_date, model = EXCLUDED.model, template = EXCLUDED.template,
            k = EXCLUDED.k, contracts = EXCLUDED.contracts, git_commit = EXCLUDED.git_commit,
            prompt_hash = EXCLUDED.prompt_hash, meta = EXCLUDED.meta, summary = EXCLUDED.summary,
            loaded_at = now()
        """,
        {**fields, "meta": Jsonb(fields["meta"]), "summary": Jsonb(fields["summary"])},
    )
    conn.execute("DELETE FROM answers WHERE run_id = %s", (fields["run_id"],))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO answers (run_id, title, clause, decision, reason, gold_found, retried, quotes, looks_like)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    fields["run_id"], r["title"], r["clause"], r["decision"], r["reason"],
                    r["gold_found"], r["retried"], Jsonb(r["quotes"]), Jsonb(r["looks_like"]),
                )
                for r in rows
            ],
        )
    return len(rows)


def run_scores(conn, run_id=None):
    """Headline numbers per run from the run_scores view, newest run id last."""
    sql = "SELECT * FROM run_scores"
    params = ()
    if run_id is not None:
        sql += " WHERE run_id = %s"
        params = (run_id,)
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(sql + " ORDER BY run_id", params).fetchall()
