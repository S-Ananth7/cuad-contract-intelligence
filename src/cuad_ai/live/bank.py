"""Copy the example bank (the lawyer-marked passages the pipeline compares against) into another database.

The hosted live review needs only three tables, not the 510 contracts' text or chunks:
contracts (names and companies), clauses (the 41 questions) and highlights (the marked passages and their vectors).
"""
from pathlib import Path

BATCH = 500


def ensure_tables(conn):
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(Path("sql/schema.sql").read_text(encoding="utf-8"))
    conn.execute(Path("sql/live.sql").read_text(encoding="utf-8"))
    conn.commit()


def _insert(dst, sql, rows):
    with dst.cursor() as cur:
        for i in range(0, len(rows), BATCH):
            cur.executemany(sql, rows[i:i + BATCH])
    dst.commit()


def copy_bank(src, dst):
    """Copy contracts, clauses and highlights from src to dst, keeping their ids. Safe to run again.
    Returns {table: rows now in dst}."""
    ensure_tables(dst)
    contracts = src.execute("SELECT id, title, company, n_chars FROM contracts ORDER BY id").fetchall()
    clauses = src.execute("SELECT id, name, question FROM clauses ORDER BY id").fetchall()
    highlights = src.execute(
        "SELECT id, contract_id, clause_id, start_char, end_char, text, embedding::text, embedding_model "
        "FROM highlights WHERE embedding IS NOT NULL ORDER BY id").fetchall()
    if not (contracts and clauses and highlights):
        raise RuntimeError("The source database has no example bank to copy. Load and embed CUAD there first.")

    _insert(dst, "INSERT INTO contracts (id, title, company, n_chars) VALUES (%s, %s, %s, %s) "
                 "ON CONFLICT (id) DO NOTHING", contracts)
    _insert(dst, "INSERT INTO clauses (id, name, question) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING", clauses)
    _insert(dst, "INSERT INTO highlights (id, contract_id, clause_id, start_char, end_char, text, embedding, "
                 "embedding_model) VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s) ON CONFLICT (id) DO NOTHING",
            highlights)
    for table in ("contracts", "clauses", "highlights"):  # new rows added later must not reuse a copied id
        dst.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT max(id) FROM {table}))")
    dst.commit()
    return {t: dst.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("contracts", "clauses", "highlights")}
