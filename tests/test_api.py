import json
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from cuad_ai.api import create_app  # noqa: E402
from cuad_ai.runstore import create_tables, save_run  # noqa: E402

FINAL = Path(__file__).parent.parent / "evals" / "final_test"
RUN_ID = "20261108_172552_rag_clause_rag_deepseek-v4-flash_k10_102"


def read(name):
    return json.loads((FINAL / name).read_text(encoding="utf-8"))


@contextmanager
def broken_database():
    raise psycopg.OperationalError("down")
    yield


@pytest.fixture
def client(conn):
    """An app that uses the test's own connection, with the final run stored and no other run."""
    create_tables(conn)
    conn.execute("DELETE FROM runs")  # rolled back at the end of the test
    save_run(conn, read("report_summary.json"), read("decisions.json"), read("queue.json"))

    @contextmanager
    def same_connection():
        yield conn

    return TestClient(create_app(connect=same_connection))


def test_health_needs_no_database():
    assert TestClient(create_app(connect=broken_database)).get("/health").json() == {"status": "ok"}


def test_ready_is_503_when_the_database_is_down():
    assert TestClient(create_app(connect=broken_database)).get("/ready").status_code == 503


def test_runs_lists_the_stored_run_with_its_scores(client):
    runs = client.get("/runs").json()
    assert [r["run_id"] for r in runs] == [RUN_ID]
    assert (runs[0]["accepted"], runs[0]["accepted_real"]) == (1505, 1139)


def test_one_run_returns_scores_and_monitoring(client):
    body = client.get(f"/runs/{RUN_ID}").json()
    assert (body["scores"]["accept_precision"], body["scores"]["accept_recall"]) == (0.757, 0.916)
    assert body["monitoring"]["queue_rate"] == round(184 / 4182, 4)


def test_the_queue_is_paged_and_leaves_out_the_lawyers_label(client):
    page = client.get(f"/runs/{RUN_ID}/queue", params={"limit": 5, "offset": 10}).json()
    assert page["total"] == 184 and len(page["items"]) == 5
    assert "gold_found" not in page["items"][0]
    assert {"title", "clause", "reason", "quotes", "looks_like"} <= set(page["items"][0])


def test_an_unknown_run_is_a_404(client):
    assert client.get("/runs/nope").status_code == 404
    assert client.get("/runs/nope/queue").status_code == 404


def test_the_queue_page_size_is_limited(client):
    assert client.get(f"/runs/{RUN_ID}/queue", params={"limit": 100000}).status_code == 422


def test_metrics_is_prometheus_text_for_the_latest_run(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert f'cuad_queue_rate{{run_id="{RUN_ID}"}} {round(184 / 4182, 4)}' in response.text
