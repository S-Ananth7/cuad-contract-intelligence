import os

import psycopg
from dotenv import load_dotenv

from cuad_ai.ingest import highlight_rows, insert_highlights
from cuad_ai.loader import load_contracts


def main():
    load_dotenv()
    contracts = load_contracts()
    rows = []
    for contract in contracts:
        rows.extend(highlight_rows(contract))
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        insert_highlights(conn, rows)
        conn.commit()
        count = conn.execute("select count(*) from highlights").fetchone()[0]
    print(count)


if __name__ == "__main__":
    main()        
        
