from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"


def load_model():
    return TextEmbedding(MODEL_NAME)


def embed_texts(model, texts):
    return [v.tolist() for v in model.embed(texts)]


def vector_literal(vector):
    """pgvector reads a vector written as text, like [0.1,0.2,0.3]."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def embed_pending(conn, model, batch_size=64, limit=None):
    """Embed chunks that have no vector yet. Returns how many were done."""
    done = 0
    while True:
        rows = conn.execute(
            "SELECT id, text FROM chunks WHERE embedding IS NULL ORDER BY id LIMIT %s",
            (batch_size,),
        ).fetchall()
        if not rows:
            break
        vectors = embed_texts(model, [text for _, text in rows])
        params = [(vector_literal(v), MODEL_NAME, chunk_id) for v, (chunk_id, _) in zip(vectors, rows)]
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE chunks SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
                params,
            )
        conn.commit()
        done += len(rows)
        print(done, flush=True)
        if limit and done >= limit:
            break
    return done
