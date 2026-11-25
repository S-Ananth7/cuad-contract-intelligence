import pytest
from live_fakes import FakeEmbedder, T, load_bank_rows, submit

from cuad_ai.live import store
from cuad_ai.live.store import RejectedUpload


def test_an_empty_or_too_long_file_is_refused(live_db, monkeypatch):
    monkeypatch.setenv("LIVE_MAX_CHARS", "50")
    with live_db() as conn:
        with pytest.raises(RejectedUpload, match="empty"):
            submit(conn, "a.txt", "   \n")
        with pytest.raises(RejectedUpload, match="limit"):
            submit(conn, "a.txt", "x" * 51)


def test_the_same_text_twice_is_stored_once(live_db):
    with live_db() as conn:
        first = submit(conn, "a.txt", "some contract text")
        assert submit(conn, "b.txt", "some contract text") == first


def test_the_daily_limit_stops_new_uploads(live_db, monkeypatch):
    monkeypatch.setenv("LIVE_DAILY_CAP", "2")
    with live_db() as conn:
        submit(conn, "a.txt", "one")
        submit(conn, "b.txt", "two")
        with pytest.raises(RejectedUpload, match="daily"):
            submit(conn, "c.txt", "three")


def test_a_known_company_in_the_file_name_is_excluded_with_the_banks_spelling(live_db):
    with live_db() as conn:
        load_bank_rows(conn, FakeEmbedder())
        a = submit(conn, "ACME_2020_contract.txt", "text one")
        b = submit(conn, "unknown_2020.txt", "text two")
        c = submit(conn, "x.txt", "text three", company="beta")
        assert [store.get_submission(conn, T, i)["excluded_company"] for i in (a, b, c)] == ["Acme", None, "Beta"]


def test_workers_never_take_the_same_job_and_take_the_oldest_first(live_db):
    with live_db() as setup:
        ids = [submit(setup, f"{n}.txt", f"text {n}") for n in "abc"]
    with live_db() as one, live_db() as two:
        first, second = store.claim(one), store.claim(two)
        assert (first["id"], second["id"]) == (ids[0], ids[1])
        third, nothing = store.claim(one), store.claim(two)
        assert third["id"] == ids[2] and nothing is None


def test_a_job_whose_worker_stopped_goes_back_in_the_queue(live_db):
    with live_db() as conn:
        sid = submit(conn, "a.txt", "text")
        store.claim(conn)
        assert store.requeue_stale(conn) == 0  # just claimed: heartbeat is fresh
        conn.execute("UPDATE live_submissions SET heartbeat_at = now() - interval '1 hour'")
        conn.commit()
        assert store.claim(conn)["id"] == sid  # claim() puts it back and takes it again


def answer(clause="Governing Law", decision="queue"):
    return {"clause": clause, "decision": decision, "reason": "judges_disagree", "quotes": ["q"], "spans": [[0, 1]],
            "risk": 0.1, "rank_asked": 2, "verdict": True, "verdict2": False, "looks_like": ["Parties"],
            "retried": False, "tokens_in": 5, "tokens_out": 1}


def test_a_review_is_saved_replaced_and_validated(live_db):
    with live_db() as conn:
        sid = submit(conn, "a.txt", "text")
        store.save_answer(conn, sid, answer())
        answer_id = store.get_answers(conn, T, sid)[0]["id"]
        store.review_answer(conn, T, sid, answer_id, "Priya", "confirm")
        store.review_answer(conn, T, sid, answer_id, "Priya", "reject", "wrong clause")
        saved = store.get_answers(conn, T, sid)[0]
        assert (saved["review_action"], saved["review_note"], saved["reviewer"]) == ("reject", "wrong clause", "Priya")
        with pytest.raises(ValueError):
            store.review_answer(conn, T, sid, answer_id, "Priya", "maybe")
        with pytest.raises(ValueError):
            store.review_answer(conn, T, sid, answer_id, "  ", "confirm")
        store.clear_review(conn, T, sid, answer_id)
        assert store.get_answers(conn, T, sid)[0]["review_action"] is None


def test_an_answer_of_another_upload_cannot_be_reviewed(live_db):
    with live_db() as conn:
        one, two = submit(conn, "a.txt", "text a"), submit(conn, "b.txt", "text b")
        store.save_answer(conn, one, answer())
        answer_id = store.get_answers(conn, T, one)[0]["id"]
        with pytest.raises(LookupError):
            store.review_answer(conn, T, two, answer_id, "Priya", "confirm")


def test_saving_an_answer_twice_keeps_one_and_deleting_an_upload_removes_everything(live_db):
    with live_db() as conn:
        sid = submit(conn, "a.txt", "text")
        store.save_answer(conn, sid, answer())
        store.save_answer(conn, sid, answer(decision="accept"))
        rows = store.get_answers(conn, T, sid)
        assert [r["decision"] for r in rows] == ["accept"]
        store.review_answer(conn, T, sid, rows[0]["id"], "Priya", "confirm")
        assert store.delete_submission(conn, T, sid) is True
        assert store.delete_submission(conn, T, sid) is False
        assert conn.execute("SELECT count(*) FROM live_answers").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM live_reviews").fetchone()[0] == 0
