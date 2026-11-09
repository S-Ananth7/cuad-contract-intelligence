
import psycopg
from dotenv import load_dotenv

from cuad_ai.ingest import chunk_rows, insert_chunks
from cuad_ai.loader import load_contracts
from cuad_ai.settings import database_url


def main():
    load_dotenv()
    contracts = load_contracts()
    with psycopg.connect(database_url()) as conn:
        for contract in contracts:
            insert_chunks(conn, chunk_rows(contract))
        conn.commit()
        count = conn.execute("select count(*) from chunks").fetchone()[0]
    print(count)


if __name__ == "__main__":
    main()
