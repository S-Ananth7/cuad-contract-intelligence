import sys

import psycopg
from dotenv import load_dotenv

from cuad_ai.embed import embed_pending, load_model
from cuad_ai.settings import database_url


def main():
    load_dotenv()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    model = load_model()
    with psycopg.connect(database_url()) as conn:
        done = embed_pending(conn, model, limit=limit)
        with_vector = conn.execute("select count(embedding) from chunks").fetchone()[0]
    print("embedded this run:", done, "| total with vector:", with_vector)


if __name__ == "__main__":
    main()
