from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from live_fakes import CONTRACT, DELAWARE, T, submit  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from cuad_ai.live import store  # noqa: E402

PAGE = str(Path(__file__).resolve().parents[1] / "app" / "live_app.py")


def test_without_a_database_the_page_explains_instead_of_crashing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none")
    page = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not page.exception
    assert "did not answer" in page.error[0].value


def seed(connect):
    with connect() as conn:
        sid = submit(conn, "Gamma_2020.txt", CONTRACT)
        from cuad_ai.live.locate import locate
        span = list(locate(CONTRACT, DELAWARE))
        base = {"reason": "", "quotes": [], "spans": [], "risk": None, "rank_asked": None, "verdict": None,
                "verdict2": None, "looks_like": [], "retried": False, "tokens_in": 1, "tokens_out": 1}
        store.save_answer(conn, sid, {**base, "clause": "Governing Law", "decision": "queue", "reason": "judges_disagree",
                                      "quotes": [DELAWARE], "spans": [span], "verdict": True, "verdict2": False})
        store.save_answer(conn, sid, {**base, "clause": "Parties", "decision": "not_found"})
        conn.execute("UPDATE live_submissions SET status = 'done'")
        conn.commit()
    return sid


def test_the_page_shows_answers_highlights_the_quote_and_records_a_review(live_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", live_db.url)
    monkeypatch.setenv("LIVE_LOCAL_TENANT", T)
    sid = seed(live_db)
    page = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not page.exception
    assert {m.label: m.value for m in page.metric} == {"Accepted": "0", "Needs review": "1", "Rejected": "0", "Not found": "1"}
    assert "<mark>" in " ".join(m.value for m in page.markdown)

    page.sidebar.text_input(key="reviewer").set_value("Priya").run()
    next(b for b in page.button if b.label == "Confirm").click().run()
    assert not page.exception
    with live_db() as conn:
        answers = {a["clause"]: a for a in store.get_answers(conn, T, sid)}
    assert (answers["Governing Law"]["review_action"], answers["Governing Law"]["reviewer"]) == ("confirm", "Priya")
