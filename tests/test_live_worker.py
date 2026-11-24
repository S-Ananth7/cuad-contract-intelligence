from live_fakes import CONTRACT, DELAWARE, FakeEmbedder, FakeModel, load_bank_rows

from cuad_ai.live import store, worker
from cuad_ai.live.process import LockedEmbedder, load_bank


def setup(live_db):
    embedder = LockedEmbedder(FakeEmbedder())
    with live_db() as conn:
        load_bank_rows(conn, embedder)
        bank = load_bank(conn)
    return embedder, (lambda company: bank)


def test_the_worker_does_nothing_on_an_empty_queue_then_finishes_an_upload(live_db):
    embedder, bank_for = setup(live_db)
    assert worker.run_once(live_db, FakeModel(), embedder, bank_for) is None
    with live_db() as conn:
        sid = store.submit(conn, "a.txt", CONTRACT)
    assert worker.run_once(live_db, FakeModel({"Governing Law": DELAWARE}), embedder, bank_for) == sid
    with live_db() as conn:
        assert store.get_submission(conn, sid)["status"] == "done"


def test_a_crash_inside_a_job_marks_it_failed_instead_of_leaving_it_running(live_db):
    embedder, _ = setup(live_db)

    def broken(company):
        raise RuntimeError("boom")

    with live_db() as conn:
        sid = store.submit(conn, "a.txt", CONTRACT)
    assert worker.run_once(live_db, FakeModel(), embedder, broken) == sid
    with live_db() as conn:
        job = store.get_submission(conn, sid)
        assert job["status"] == "failed" and "RuntimeError" in job["error"]
