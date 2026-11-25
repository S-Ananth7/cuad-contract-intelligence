import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from contextlib import contextmanager  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from cuad_ai.api import create_app  # noqa: E402
from cuad_ai.live import store, tenants  # noqa: E402

ROW = {"clause": "Parties", "decision": "queue", "reason": "judges_disagree", "quotes": ["q"], "spans": [[0, 4]],
       "risk": 0.2, "rank_asked": 3, "verdict": True, "verdict2": False, "looks_like": [], "retried": False,
       "tokens_in": 1, "tokens_out": 1}


@pytest.fixture
def client(live_db, monkeypatch):
    monkeypatch.setenv("LIVE_API", "1")
    with live_db() as conn:
        tenants.create_tenant(conn, "acme", "Acme")
        tenants.create_tenant(conn, "beta", "Beta")
        keys = {t: {"X-API-Key": tenants.new_api_key(conn, t)} for t in ("acme", "beta")}

    @contextmanager
    def connect():
        with live_db() as conn:
            yield conn

    return TestClient(create_app(connect)), live_db, keys


def test_the_live_endpoints_do_not_exist_until_switched_on(monkeypatch):
    monkeypatch.delenv("LIVE_API", raising=False)
    assert TestClient(create_app()).post("/submissions", json={"filename": "a", "text": "b"}).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}, {"X-API-Key": ""}])
def test_every_live_endpoint_needs_a_valid_key(client, headers):
    api, _, _ = client
    for call in (lambda: api.get("/submissions", headers=headers),
                 lambda: api.post("/submissions", json={"filename": "a", "text": "b"}, headers=headers),
                 lambda: api.get("/submissions/1", headers=headers),
                 lambda: api.put("/submissions/1/answers/1/review", json={"reviewer": "P", "action": "confirm"},
                                 headers=headers),
                 lambda: api.delete("/submissions/1/answers/1/review", headers=headers),
                 lambda: api.delete("/submissions/1", headers=headers)):
        assert call().status_code == 401


def test_upload_then_read_review_and_delete(client):
    api, connect, keys = client
    key = keys["acme"]
    created = api.post("/submissions", json={"filename": "a.txt", "text": "This is a contract."}, headers=key)
    assert created.status_code == 202 and created.json()["status"] == "queued"
    sid = created.json()["id"]
    with connect() as conn:
        store.save_answer(conn, sid, ROW)
    answer = api.get(f"/submissions/{sid}", headers=key).json()["answers"][0]
    assert answer["clause"] == "Parties" and answer["spans"] == [[0, 4]]

    url = f"/submissions/{sid}/answers/{answer['id']}/review"
    assert api.put(url, json={"reviewer": "Priya", "action": "maybe"}, headers=key).status_code == 422
    assert api.put(url, json={"reviewer": "Priya", "action": "confirm"}, headers=key).status_code == 200
    assert api.get(f"/submissions/{sid}", headers=key).json()["answers"][0]["review_action"] == "confirm"
    assert api.put(f"/submissions/{sid}/answers/99999/review", json={"reviewer": "P", "action": "confirm"},
                   headers=key).status_code == 404
    assert api.delete(url, headers=key).status_code == 200
    assert api.get(f"/submissions/{sid}", headers=key).json()["answers"][0]["review_action"] is None

    assert api.delete(f"/submissions/{sid}", headers=key).status_code == 200
    assert api.get(f"/submissions/{sid}", headers=key).status_code == 404
    assert api.delete(f"/submissions/{sid}", headers=key).status_code == 404


def test_another_clients_key_sees_nothing_of_it_and_can_change_nothing(client):
    api, connect, keys = client
    sid = api.post("/submissions", json={"filename": "a.txt", "text": "acme only"}, headers=keys["acme"]).json()["id"]
    with connect() as conn:
        store.save_answer(conn, sid, ROW)
    aid = api.get(f"/submissions/{sid}", headers=keys["acme"]).json()["answers"][0]["id"]
    beta = keys["beta"]

    assert api.get("/submissions", headers=beta).json() == []
    assert api.get(f"/submissions/{sid}", headers=beta).status_code == 404
    assert api.put(f"/submissions/{sid}/answers/{aid}/review", json={"reviewer": "Eve", "action": "reject"},
                   headers=beta).status_code == 404
    api.delete(f"/submissions/{sid}/answers/{aid}/review", headers=beta)
    assert api.delete(f"/submissions/{sid}", headers=beta).status_code == 404

    detail = api.get(f"/submissions/{sid}", headers=keys["acme"]).json()  # untouched
    assert detail["filename"] == "a.txt" and detail["answers"][0]["review_action"] is None
    with connect() as conn:
        assert tenants.list_audit(conn, "beta") == []  # nothing happened, so nothing is logged for beta


def test_actions_are_written_to_the_audit_trail(client):
    api, connect, keys = client
    sid = api.post("/submissions", json={"filename": "a.txt", "text": "text"}, headers=keys["acme"]).json()["id"]
    api.get(f"/submissions/{sid}", headers=keys["acme"])
    api.delete(f"/submissions/{sid}", headers=keys["acme"])
    with connect() as conn:
        assert [r["action"] for r in tenants.list_audit(conn, "acme")] == ["delete", "view", "upload"]


def test_a_bad_upload_is_a_422_and_the_daily_limit_is_a_429(client, monkeypatch):
    api, _, keys = client
    key = keys["acme"]
    assert api.post("/submissions", json={"filename": "a.txt", "text": "  "}, headers=key).status_code == 422
    monkeypatch.setenv("LIVE_DAILY_CAP", "1")
    assert api.post("/submissions", json={"filename": "a.txt", "text": "one"}, headers=key).status_code == 202
    assert api.post("/submissions", json={"filename": "b.txt", "text": "two"}, headers=key).status_code == 429
