from cuad_ai.embed import embed_texts, vector_literal


def search_chunks(conn, model, query, k=50):
    vector = vector_literal(embed_texts(model, [query])[0])
    return conn.execute(
        "SELECT id, contract_id, start_char, end_char, text, embedding <=> %s::vector AS distance "
        "FROM chunks WHERE embedding IS NOT NULL ORDER BY distance LIMIT %s",
        (vector, k),
    ).fetchall()


def search_by_examples(conn, contract_id, clause_id, k=10):
    """Top k chunks of one contract, scored by the closest bank example of the clause.
    Examples from the same company as the contract are never used."""
    return conn.execute(
        "SELECT c.start_char, c.end_char, MAX(1 - (c.embedding <=> h.embedding)) AS score "
        "FROM chunks c "
        "JOIN contracts q ON q.id = c.contract_id "
        "JOIN highlights h ON h.clause_id = %s AND h.embedding IS NOT NULL "
        "JOIN contracts hc ON hc.id = h.contract_id AND hc.company <> q.company "
        "WHERE c.contract_id = %s AND c.embedding IS NOT NULL "
        "GROUP BY c.id, c.start_char, c.end_char "
        "ORDER BY score DESC LIMIT %s",
        (clause_id, contract_id, k),
    ).fetchall()
