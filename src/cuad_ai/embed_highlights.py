from cuad_ai.embed import MODEL_NAME, embed_texts, vector_literal

ELIGIBLE = """
    SELECT h.id, h.text
    FROM highlights h
    JOIN contracts c ON c.id = h.contract_id
    WHERE h.embedding IS NULL
      AND c.official_split = 'train'
      AND NOT c.shares_company_with_test
    ORDER BY h.id
    LIMIT %s
"""


def embed_pending_highlights(conn, model, batch_size=64, limit=None):
    """Embed eligible train highlights that have no vector yet. Returns how many were done."""
    done = 0
    while True:
        rows = conn.execute(ELIGIBLE, (batch_size,)).fetchall()
        if not rows:
            break
        vectors = embed_texts(model, [text for _, text in rows])
        params = [(vector_literal(v), MODEL_NAME, hid) for v, (hid, _) in zip(vectors, rows)]
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE highlights SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
                params,
            )
        conn.commit()
        done += len(rows)
        print(done, flush=True)
        if limit and done >= limit:
            break
    return done
