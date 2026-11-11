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
