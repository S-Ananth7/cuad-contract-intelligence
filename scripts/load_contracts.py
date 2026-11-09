
import psycopg
from dotenv import load_dotenv

from cuad_ai.ingest import contract_row, insert_contracts
from cuad_ai.loader import load_contracts
from cuad_ai.settings import database_url


def main():
    load_dotenv()
    contracts = load_contracts()
    rows = [contract_row(c) for c in contracts]
    with psycopg.connect(database_url()) as conn:
        insert_contracts(conn, rows)
        conn.commit()
        count = conn.execute("select count(*) from contracts").fetchone()[0]
    print(count)


if __name__ == "__main__":
    main()
