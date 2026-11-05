import os
import psycopg
import pytest
from dotenv import load_dotenv

from cuad_ai.ingest import contract_row, insert_contracts, clause_rows, insert_clauses, highlight_rows, insert_highlights

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
    

def test_highlight_rows_flatten_the_lawyer_answers():
    contract = {
        "title": "X",
        "paragraphs": [{"context": "Hello law text here", "qas": [
            {"id": "X__Governing Law", "is_impossible": False,
             "answers": [{"text": "law text", "answer_start": 6}]},
            {"id": "X__Parties", "is_impossible": True, "answers": []},
        ]}],
    }
    assert highlight_rows(contract) == [
        {"title": "X", "clause": "Governing Law",
         "start_char": 6, "end_char": 14, "text": "law text"},
    ]


def test_insert_highlights_links_to_contract_and_clause(conn):
    insert_contracts(conn, [{"title": "T1", "company": "T", "n_chars": 10}])
    insert_clauses(conn, [{"name": "C1", "question": "Q"}])
    rows = [{"title": "T1", "clause": "C1", "start_char": 0, "end_char": 5, "text": "hello"}]
    insert_highlights(conn, rows)
    got = conn.execute(
    "select h.start_char, h.text, c.title, k.name from highlights h "
    "join contracts c on c.id = h.contract_id "
    "join clauses k on k.id = h.clause_id where c.title = %s", ("T1",)
).fetchall()
    assert got == [(0, "hello", "T1", "C1")]
