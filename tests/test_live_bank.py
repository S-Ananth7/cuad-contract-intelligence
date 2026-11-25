import pytest
from live_fakes import FakeEmbedder, load_bank_rows

from cuad_ai.live.bank import copy_bank

TABLES = ("contracts", "clauses", "highlights")


def test_the_bank_is_copied_with_ids_and_vectors_and_copying_twice_adds_nothing(live_db):
    hosted = live_db.empty_schema()
    with live_db() as src:
        load_bank_rows(src, FakeEmbedder())
        want = {t: src.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        before = src.execute("SELECT id, text, embedding::text FROM highlights ORDER BY id").fetchall()
        with hosted() as dst:
            first = copy_bank(src, dst)
            second = copy_bank(src, dst)
            after = dst.execute("SELECT id, text, embedding::text FROM highlights ORDER BY id").fetchall()
            new_id = dst.execute("INSERT INTO clauses (name, question) VALUES ('Extra', 'q') RETURNING id").fetchone()[0]
            top = dst.execute("SELECT max(id) FROM clauses WHERE name <> 'Extra'").fetchone()[0]
    assert first == second == want
    assert after == before
    assert new_id > top  # the id counter moved past the copied ids


def test_the_copied_bank_works_for_the_live_pipeline(live_db):
    from live_fakes import GOVERNING

    from cuad_ai.live.process import LockedEmbedder, load_bank, rank_clauses

    hosted = live_db.empty_schema()
    with live_db() as src, hosted() as dst:
        load_bank_rows(src, FakeEmbedder())
        copy_bank(src, dst)
        assert "Governing Law" in rank_clauses(dst, LockedEmbedder(FakeEmbedder()), [GOVERNING], "")
        assert set(load_bank(dst).clause_ids) == {"Governing Law", "Anti-Assignment", "Document Name", "Parties"}


def test_an_empty_source_is_refused_instead_of_copying_nothing(live_db):
    hosted = live_db.empty_schema()
    with live_db() as src, hosted() as dst, pytest.raises(RuntimeError, match="no example bank"):
        copy_bank(src, dst)
