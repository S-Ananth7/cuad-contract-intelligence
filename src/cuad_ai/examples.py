def search_by_examples(conn, contract_id, clause_id, k=10):
    """Top k chunks of one contract, scored by the closest bank example of the clause."""
    return conn.execute(
        "SELECT c.start_char, c.end_char, MAX(1 - (c.embedding <=> h.embedding)) AS score "
        "FROM chunks c "
        "JOIN highlights h ON h.clause_id = %s AND h.embedding IS NOT NULL "
        "WHERE c.contract_id = %s AND c.embedding IS NOT NULL "
        "GROUP BY c.id, c.start_char, c.end_char "
        "ORDER BY score DESC LIMIT %s",
        (clause_id, contract_id, k),
    ).fetchall()