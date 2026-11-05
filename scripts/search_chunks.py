import os
import sys

import psycopg
from dotenv import load_dotenv

from cuad_ai.embed import load_model
from cuad_ai.search import search_chunks


def main():
    load_dotenv()
    query = sys.argv[1]
    model = load_model()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for chunk_id, contract_id, start, end, text, distance in search_chunks(conn, model, query):
            print(f"{distance:.3f} | contract {contract_id} | {start}-{end} | {text[:150]!r}")


if __name__ == "__main__":
    main()
