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


def page_text(page):
    parts = [m.value for m in page.markdown] + [c.value for c in page.caption] + [s.value for s in page.subheader]
    parts += [str(o) for box in page.selectbox for o in box.options]
    parts += [d.value.to_csv() for d in page.dataframe]
    return " ".join(parts)


def test_a_signed_in_client_never_sees_another_clients_contracts(live_db, monkeypatch):
    """The page itself, not only the store: the client comes from the sign-in, and a guessed upload id is no way in."""
    from cuad_ai.live import tenants

    monkeypatch.setenv("DATABASE_URL", live_db.url)
    sid = seed(live_db)  # an upload by client 'acme'
    with live_db() as conn:
        tenants.create_tenant(conn, "beta", "Beta Legal")

    other = AppTest.from_file(PAGE, default_timeout=60)
    other.session_state["tenant"], other.session_state["email"] = "beta", "b@beta.example"
    other.session_state["current"] = sid  # even if it knows the other client's upload id
    other.run()
    assert not other.exception
    assert "Gamma_2020.txt" not in page_text(other) and "Governing Law" not in page_text(other)
    assert "Welcome, Beta Legal" in page_text(other)

    owner = AppTest.from_file(PAGE, default_timeout=60)
    owner.session_state["tenant"], owner.session_state["email"] = "acme", "a@acme.example"
    owner.run()
    assert not owner.exception
    assert "Gamma_2020.txt" in page_text(owner)


def test_a_session_for_a_client_that_does_not_exist_gets_nothing(live_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", live_db.url)
    seed(live_db)
    page = AppTest.from_file(PAGE, default_timeout=60)
    page.session_state["tenant"], page.session_state["email"] = "ghost", "g@ghost.example"
    page.run()
    assert not page.exception
    assert "not set up" in page.error[0].value and "Gamma_2020.txt" not in page_text(page)
