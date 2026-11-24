import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from contextlib import contextmanager  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from cuad_ai.api import create_app  # noqa: E402
from cuad_ai.live import store  # noqa: E402

KEY = {"X-API-Key": "secret-key"}


@pytest.fixture
def client(live_db, monkeypatch):
    monkeypatch.setenv("LIVE_API_KEY", "secret-key")

    @contextmanager
    def connect():
        with live_db() as conn:
            yield conn

    return TestClient(create_app(connect)), live_db


def test_the_live_endpoints_do_not_exist_until_a_key_is_configured(monkeypatch):
    monkeypatch.delenv("LIVE_API_KEY", raising=False)
    assert TestClient(create_app()).post("/submissions", json={"filename": "a", "text": "b"}).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}, {"X-API-Key": ""}])
def test_every_live_endpoint_needs_the_key(client, headers):
    api, _ = client
    for call in (lambda: api.get("/submissions", headers=headers),
                 lambda: api.post("/submissions", json={"filename": "a", "text": "b"}, headers=headers),
                 lambda: api.get("/submissions/1", headers=headers),
                 lambda: api.delete("/submissions/1", headers=headers)):
        assert call().status_code == 401


def test_upload_then_read_review_and_delete(client):
    api, connect = client
    created = api.post("/submissions", json={"filename": "a.txt", "text": "This is a contract."}, headers=KEY)
    assert created.status_code == 202 and created.json()["status"] == "queued"
    sid = created.json()["id"]
    with connect() as conn:
        store.save_answer(conn, sid, {"clause": "Parties", "decision": "queue", "reason": "judges_disagree",
                                      "quotes": ["q"], "spans": [[0, 4]], "risk": 0.2, "rank_asked": 3,
                                      "verdict": True, "verdict2": False, "looks_like": [], "retried": False,
                                      "tokens_in": 1, "tokens_out": 1})
    detail = api.get(f"/submissions/{sid}", headers=KEY).json()
    answer = detail["answers"][0]
    assert answer["clause"] == "Parties" and answer["spans"] == [[0, 4]]

    url = f"/submissions/{sid}/answers/{answer['id']}/review"
    assert api.put(url, json={"reviewer": "Priya", "action": "maybe"}, headers=KEY).status_code == 422
    assert api.put(url, json={"reviewer": "Priya", "action": "confirm"}, headers=KEY).status_code == 200
    assert api.get(f"/submissions/{sid}", headers=KEY).json()["answers"][0]["review_action"] == "confirm"
    assert api.put(f"/submissions/{sid}/answers/99999/review", json={"reviewer": "P", "action": "confirm"},
                   headers=KEY).status_code == 404
    assert api.delete(url, headers=KEY).status_code == 200
    assert api.get(f"/submissions/{sid}", headers=KEY).json()["answers"][0]["review_action"] is None

    assert api.delete(f"/submissions/{sid}", headers=KEY).status_code == 200
    assert api.get(f"/submissions/{sid}", headers=KEY).status_code == 404
    assert api.delete(f"/submissions/{sid}", headers=KEY).status_code == 404


def test_a_bad_upload_is_a_422_and_the_daily_limit_is_a_429(client, monkeypatch):
    api, _ = client
    assert api.post("/submissions", json={"filename": "a.txt", "text": "  "}, headers=KEY).status_code == 422
    monkeypatch.setenv("LIVE_DAILY_CAP", "1")
    assert api.post("/submissions", json={"filename": "a.txt", "text": "one"}, headers=KEY).status_code == 202
    assert api.post("/submissions", json={"filename": "b.txt", "text": "two"}, headers=KEY).status_code == 429
