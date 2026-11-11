"""Load a saved run (a folder with report_summary.json and decisions.json) into Postgres.

    python scripts/load_run.py                    # the committed final test run
    python scripts/load_run.py evals/final_test   # or any folder with the same files
"""

import json
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cuad_ai.runstore import create_tables, run_scores, save_run
from cuad_ai.settings import database_url


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    load_dotenv()
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/final_test")
    report = read_json(folder / "report_summary.json")
    decisions = read_json(folder / "decisions.json")
    queue_path = folder / "queue.json"
    queue = read_json(queue_path) if queue_path.exists() else []
    with psycopg.connect(database_url()) as conn:
        create_tables(conn)
        count = save_run(conn, report, decisions, queue)
        conn.commit()
        scores = run_scores(conn, report["run_id"])[0]
    print(f"loaded {count} answers for {report['run_id']}")
    print(
        f"accepted {scores['accepted']} ({scores['accepted_real']} real)  "
        f"precision {scores['accept_precision']}  recall {scores['accept_recall']}"
    )


if __name__ == "__main__":
    main()
