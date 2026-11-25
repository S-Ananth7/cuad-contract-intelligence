import pytest
from live_fakes import submit

from cuad_ai.live import store, tenants
from cuad_ai.live.store import LimitReached, RejectedUpload

ANSWER = {"clause": "Governing Law", "decision": "queue", "reason": "judges_disagree", "quotes": ["q"],
          "spans": [[0, 1]], "risk": 0.1, "rank_asked": 2, "verdict": True, "verdict2": False,
          "looks_like": [], "retried": False, "tokens_in": 1, "tokens_out": 1}


def two_clients(conn):
    tenants.create_tenant(conn, "acme", "Acme")
    tenants.create_tenant(conn, "beta", "Beta")

# ---- one client can never reach another client's data ----


def test_one_client_cannot_read_review_or_delete_anothers_upload(live_db):
    with live_db() as conn:
        two_clients(conn)
        sid = store.submit(conn, "acme", "a.txt", "acme secret text")
        store.save_answer(conn, sid, ANSWER)
        aid = store.get_answers(conn, "acme", sid)[0]["id"]

        assert store.get_submission(conn, "beta", sid) is None
        assert store.get_text(conn, "beta", sid) is None
        assert store.get_answers(conn, "beta", sid) == []
        assert store.list_submissions(conn, "beta") == []
        with pytest.raises(LookupError):
            store.review_answer(conn, "beta", sid, aid, "Eve", "confirm")

        store.review_answer(conn, "acme", sid, aid, "Ann", "confirm")
        store.clear_review(conn, "beta", sid, aid)  # silently does nothing
        assert store.get_answers(conn, "acme", sid)[0]["review_action"] == "confirm"
        assert store.delete_submission(conn, "beta", sid) is False
        assert store.get_submission(conn, "acme", sid)["filename"] == "a.txt"


def test_the_same_file_from_two_clients_is_two_separate_uploads(live_db):
    with live_db() as conn:
        two_clients(conn)
        a = store.submit(conn, "acme", "a.txt", "same text")
        b = store.submit(conn, "beta", "a.txt", "same text")
        assert a != b
        assert store.submit(conn, "acme", "again.txt", "same text") == a


def test_an_unknown_client_cannot_upload(live_db):
    with live_db() as conn:
        with pytest.raises(RejectedUpload, match="not set up"):
            store.submit(conn, "ghost", "a.txt", "text")

# ---- limits are per client, plus one global ceiling ----


def test_the_daily_cap_is_per_client(live_db, monkeypatch):
    monkeypatch.setenv("LIVE_DAILY_CAP", "1")
    with live_db() as conn:
        two_clients(conn)
        store.submit(conn, "acme", "a.txt", "one")
        with pytest.raises(LimitReached):
            store.submit(conn, "acme", "b.txt", "two")
        store.submit(conn, "beta", "c.txt", "three")  # beta is not affected by acme's uploads


def test_a_clients_own_cap_overrides_the_default(live_db):
    with live_db() as conn:
        tenants.create_tenant(conn, "acme", "Acme", daily_cap=0)
        with pytest.raises(LimitReached):
            store.submit(conn, "acme", "a.txt", "one")


def test_the_global_cap_stops_everyone(live_db, monkeypatch):
    monkeypatch.setenv("LIVE_GLOBAL_DAILY_CAP", "2")
    with live_db() as conn:
        two_clients(conn)
        store.submit(conn, "acme", "a.txt", "one")
        store.submit(conn, "acme", "b.txt", "two")
        with pytest.raises(LimitReached):
            store.submit(conn, "beta", "c.txt", "three")

# ---- sign-in allow-list ----


def test_the_allow_list_maps_an_email_to_one_client(live_db):
    with live_db() as conn:
        two_clients(conn)
        tenants.add_user(conn, "acme", "  Ann@Acme.COM ")
        assert tenants.tenant_for_email(conn, "ann@acme.com") == "acme"
        assert tenants.tenant_for_email(conn, "ANN@acme.com") == "acme"
        assert tenants.tenant_for_email(conn, "stranger@x.com") is None
        assert tenants.tenant_for_email(conn, "") is None
        tenants.add_user(conn, "acme", "ann@acme.com")  # adding twice is harmless
        with pytest.raises(ValueError, match="another client"):
            tenants.add_user(conn, "beta", "ann@acme.com")
        assert tenants.tenant_for_email(conn, "ann@acme.com") == "acme"  # not moved
        assert tenants.remove_user(conn, "ann@acme.com") is True
        assert tenants.remove_user(conn, "ann@acme.com") is False
        assert tenants.tenant_for_email(conn, "ann@acme.com") is None


def test_bad_emails_clients_and_ids_are_refused(live_db):
    with live_db() as conn:
        tenants.create_tenant(conn, "acme", "Acme")
        with pytest.raises(ValueError):
            tenants.add_user(conn, "acme", "not-an-email")
        with pytest.raises(LookupError):
            tenants.add_user(conn, "nobody", "a@b.com")
        for bad in ("legacy", "Bad Id", "", "-x", "a" * 41):
            with pytest.raises(ValueError):
                tenants.create_tenant(conn, bad, "x")
        with pytest.raises(ValueError):
            tenants.create_tenant(conn, "okay", "x", retention_days=0)

# ---- API keys ----


def test_an_api_key_finds_its_client_and_only_its_hash_is_stored(live_db):
    with live_db() as conn:
        two_clients(conn)
        key = tenants.new_api_key(conn, "acme")
        assert key.startswith("lk_") and tenants.tenant_for_key(conn, key) == "acme"
        assert tenants.tenant_for_key(conn, "wrong") is None
        assert tenants.tenant_for_key(conn, "") is None
        stored = [r[0] for r in conn.execute("SELECT api_key_sha256 FROM live_tenants").fetchall()]
        assert key not in stored
        newer = tenants.new_api_key(conn, "acme")
        assert tenants.tenant_for_key(conn, key) is None  # the old key stops working
        assert tenants.tenant_for_key(conn, newer) == "acme"
        with pytest.raises(LookupError):
            tenants.new_api_key(conn, "nobody")

# ---- audit trail ----


def test_the_audit_trail_is_per_client_and_cut_to_size(live_db):
    with live_db() as conn:
        two_clients(conn)
        tenants.audit(conn, "acme", "ann@acme.com", "upload", 1, "a.txt")
        tenants.audit(conn, "acme", "ann@acme.com", "x" * 500, 1, "y" * 500)
        assert [r["action"][:1] for r in tenants.list_audit(conn, "acme")] == ["x", "u"]  # newest first
        assert len(tenants.list_audit(conn, "acme")[0]["detail"]) == 300
        assert tenants.list_audit(conn, "beta") == []

# ---- retention ----


def age(conn, days):
    conn.execute("UPDATE live_submissions SET created_at = now() - make_interval(days => %s)", (days,))
    conn.commit()


def test_purge_deletes_only_uploads_older_than_their_clients_retention(live_db):
    with live_db() as conn:
        tenants.create_tenant(conn, "short", "Short", retention_days=7)
        tenants.create_tenant(conn, "long", "Long", retention_days=365)
        a = store.submit(conn, "short", "a.txt", "text a")
        b = store.submit(conn, "long", "b.txt", "text b")
        age(conn, 10)
        assert tenants.purge_expired(conn) == 1
        assert store.get_submission(conn, "short", a) is None
        assert store.get_submission(conn, "long", b) is not None
        entry = tenants.list_audit(conn, "short")[0]
        assert (entry["actor"], entry["action"], entry["detail"]) == ("system", "purged", "a.txt")


def test_purge_leaves_a_running_job_and_uses_the_default_for_legacy(live_db):
    with live_db() as conn:
        submit(conn, "a.txt", "running text")
        store.claim(conn)  # now running
        conn.execute("INSERT INTO live_submissions (filename, text, n_chars, sha256) VALUES ('old.txt', 't', 1, 'x')")
        conn.commit()
        age(conn, 40)
        assert tenants.purge_expired(conn) == 1  # only the legacy one; the default retention is 30 days
        assert conn.execute("SELECT count(*) FROM live_submissions").fetchone()[0] == 1
