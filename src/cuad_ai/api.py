"""A thin, read-only API over stored runs: scores, label-free monitoring numbers and the human queue.

    python -m cuad_ai serve [host] [port]      (needs: pip install -e ".[api]")

It reads what `scripts/load_run.py` stored. It does not run extraction: that is a long, costly job and
belongs in a queue, not in a web request.
"""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from cuad_ai.monitor import prometheus_text, run_metrics
from cuad_ai.runstore import run_scores
from cuad_ai.settings import database_url, env_int, env_text


@contextmanager
def default_connect():
    with psycopg.connect(database_url()) as conn:
        yield conn


def create_app(connect=default_connect):
    """Build the app. `connect` gives a database connection; tests pass their own."""
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import PlainTextResponse

    app = FastAPI(title="CUAD contract intelligence", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
        except (psycopg.Error, RuntimeError):
            raise HTTPException(status_code=503, detail="database is not reachable") from None
        return {"status": "ready"}

    @app.get("/runs")
    def runs():
        with connect() as conn:
            return run_scores(conn)

    @app.get("/runs/{run_id}")
    def run(run_id: str):
        with connect() as conn:
            scores = run_scores(conn, run_id)
            if not scores:
                raise HTTPException(status_code=404, detail="no such run")
            return {"scores": scores[0], "monitoring": run_metrics(conn, run_id)}

    @app.get("/runs/{run_id}/queue")
    def queue(run_id: str, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        with connect() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE run_id = %s", (run_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="no such run")
            where = "run_id = %s AND decision = 'queue'"
            total = conn.execute(f"SELECT count(*) FROM answers WHERE {where}", (run_id,)).fetchone()[0]
            with conn.cursor(row_factory=dict_row) as cur:
                items = cur.execute(
                    f"SELECT title, clause, reason, quotes, looks_like, retried FROM answers WHERE {where} "
                    "ORDER BY title, clause LIMIT %s OFFSET %s", (run_id, limit, offset)).fetchall()
        return {"total": total, "items": items}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        with connect() as conn:
            latest = conn.execute("SELECT run_id FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
            return "" if latest is None else prometheus_text(latest[0], run_metrics(conn, latest[0]))

    return app


def main(argv=None):
    """Start the server. Host and port come from the arguments, then API_HOST and API_PORT."""
    import sys

    import uvicorn

    args = sys.argv[1:] if argv is None else list(argv)
    host = args[0] if args else env_text("API_HOST", "127.0.0.1")
    port = int(args[1]) if len(args) > 1 else env_int("API_PORT", 8000)
    uvicorn.run("cuad_ai.api:create_app", factory=True, host=host, port=port)
