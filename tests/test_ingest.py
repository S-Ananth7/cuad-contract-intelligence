import os
import psycopg
import pytest
from dotenv import load_dotenv

from cuad_ai.ingest import contract_row, insert_contracts, clause_rows, insert_clauses

load_dotenv()


@pytest.fixture
def conn():
    with psycopg.connect(os.environ["DATABASE_URL"]) as c:
        yield c
        c.rollback()


def fake_contract():
    return {
        "title": "ACMECORP_01_02_2020-EX-10-SUPPLY AGREEMENT",
        "paragraphs": [{"context": "This Agreement is made today.", "qas": []}]
    }


def test_contract_row_has_title_company_and_length():
    row = contract_row(fake_contract())
    assert row["title"] == "ACMECORP_01_02_2020-EX-10-SUPPLY AGREEMENT"
    assert row["company"] == "ACMECORP"
    assert row["n_chars"] == len("This Agreement is made today.")


def test_clause_rows_have_name_and_question():
    contracts = [{
        "title": "X",
        "paragraphs": [{"context": "text", "qas":[
            {"id": "X__Governing Law", "question": "Q1"},
            {"id": "X__Parties", "question": "Q2"}
        ]}],
    }]
    assert clause_rows(contracts) == [
        {"name": "Governing Law", "question": "Q1"},
        {"name": "Parties", "question": "Q2"}
    ]


def test_insert_clauses_adds_rows(conn):
    before = conn.execute("select count(*) from clauses").fetchone()[0]
    rows = [
        {"name": "TEST_A", "question": "Q1"},
        {"name": "TEST_B", "question": "Q2"},
    ]
    insert_clauses(conn, rows)
    after = conn.execute("select count(*)from clauses").fetchone()[0]
    assert after - before == 2
    
