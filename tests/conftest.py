"""Shared fixtures. Database tests skip cleanly when no database is reachable."""

import os

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def conn():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL is not set")
    try:
        c = psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("database is not reachable")
    with c:
        yield c
        c.rollback()


@pytest.fixture
def live_db(tmp_path):
    """A private schema holding the CUAD tables and the live-review tables, thrown away after the test.

    Uses DATABASE_URL when it is reachable (the schema keeps it from touching your data), otherwise a temporary
    server from the optional `pgserver` package, otherwise the test is skipped. Yields a connect() function.
    """
    import uuid
    from pathlib import Path

    url, server = os.environ.get("DATABASE_URL"), None
    if url:
        try:
            psycopg.connect(url, connect_timeout=3).close()
        except psycopg.OperationalError:
            url = None
    if not url:
        try:
            import pgserver
        except ImportError:
            pytest.skip("no database: set DATABASE_URL or install pgserver")
        server = pgserver.get_server(tmp_path / "pg")
        url = server.get_uri()

    schema = "live_test_" + uuid.uuid4().hex[:8]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute("CREATE EXTENSION IF NOT EXISTS vector")
        admin.execute(f"CREATE SCHEMA {schema}")

    def connect():
        return psycopg.connect(url, options=f"-c search_path={schema},public")

    with connect() as conn:
        conn.execute(Path("sql/schema.sql").read_text(encoding="utf-8"))
        conn.execute(Path("sql/live.sql").read_text(encoding="utf-8"))
        conn.commit()
    connect.url = f"{url}{'&' if '?' in url else '?'}options=-c%20search_path%3D{schema}%2Cpublic"
    try:
        yield connect
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f"DROP SCHEMA {schema} CASCADE")
        if server is not None:
            server.cleanup()
