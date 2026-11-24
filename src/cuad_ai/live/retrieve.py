"""Retrieval for an uploaded contract: the same two searches and the same fusion as the saved run (search.fuse),
pointed at the upload's own chunks. Examples from the excluded company are never used.

`company` is "" when nothing is excluded: no bank company has an empty name, so the filter then removes nothing.
"""
from cuad_ai.search import fuse, term_query
from cuad_ai.settings import HEADER_CHUNKS, HEADER_CLAUSES, RETRIEVE_K

EXAMPLES_SQL = (
    "SELECT c.start_char, c.end_char, MAX(1 - (c.embedding <=> h.embedding)) AS score "
    "FROM live_chunks c "
    "JOIN highlights h ON h.clause_id = %s AND h.embedding IS NOT NULL "
    "JOIN contracts hc ON hc.id = h.contract_id AND hc.company <> %s "
    "WHERE c.submission_id = %s AND c.embedding IS NOT NULL "
    "GROUP BY c.id, c.start_char, c.end_char "
    "ORDER BY score DESC LIMIT %s"
)
TERMS_SQL = (
    "SELECT start_char, end_char, ts_rank_cd(tsv, to_tsquery('simple', %s)) AS score "
    "FROM live_chunks WHERE submission_id = %s AND tsv @@ to_tsquery('simple', %s) "
    "ORDER BY score DESC LIMIT %s"
)


def retrieve_spans(conn, submission_id, clause, clause_id, stems, company, k=RETRIEVE_K, pool=50):
    """The (start, end) spans to show the model for one clause, in the order the saved run would pick them."""
    by_examples = conn.execute(EXAMPLES_SQL, (clause_id, company, submission_id, pool)).fetchall()
    query = term_query(stems)
    by_terms = conn.execute(TERMS_SQL, (query, submission_id, query, pool)).fetchall() if query else []
    spans = [(start, end) for start, end, _ in fuse((by_examples, by_terms), k)]
    if clause in HEADER_CLAUSES:
        spans += conn.execute(
            "SELECT start_char, end_char FROM live_chunks WHERE submission_id = %s ORDER BY start_char LIMIT %s",
            (submission_id, HEADER_CHUNKS)).fetchall()
    return spans
