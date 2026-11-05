from cuad_ai.embed import embed_texts, vector_literal


def search_chunks(conn, model, query, k=50):
    vector = vector_literal(embed_texts(model, [query])[0])
    return conn.execute(
        "SELECT id, contract_id, start_char, end_char, text, embedding <=> %s::vector AS distance "
        "FROM chunks WHERE embedding IS NOT NULL ORDER BY distance LIMIT %s",
        (vector, k),
    ).fetchall()
