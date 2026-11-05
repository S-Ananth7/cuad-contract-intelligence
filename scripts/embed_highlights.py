import os
import sys

import psycopg
from dotenv import load_dotenv

from cuad_ai.embed import load_model
from cuad_ai.embed_highlights import embed_pending_highlights


def main():
    load_dotenv()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    model = load_model()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        done = embed_pending_highlights(conn, model, limit=limit)
        total = conn.execute("select count(embedding) from highlights").fetchone()[0]
    print("embedded this run:", done, "| total with vector:", total)


if __name__ == "__main__":
    main()
