
import psycopg
from dotenv import load_dotenv

from cuad_ai.ingest import clause_rows, insert_clauses
from cuad_ai.loader import load_contracts
from cuad_ai.settings import database_url


def main():
    load_dotenv()
    contracts = load_contracts()
    rows = clause_rows(contracts)
    with psycopg.connect(database_url()) as conn:
        insert_clauses(conn, rows)
        conn.commit()
        count = conn.execute("select count(*) from clauses").fetchone()[0]
    print(count)

    
if __name__ == "__main__":
    main()
