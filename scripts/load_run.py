"""Load a saved run into Postgres.

    python scripts/load_run.py                        # the committed final test run (evals/final_test)
    python scripts/load_run.py evals/runs/<run>       # a fresh run folder written by the pipeline

A run folder is either the committed evidence (report_summary.json + decisions.json) or a pipeline run
(report.json + final.json). Loading the same run twice replaces it.
"""

import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cuad_ai.runstore import create_tables, read_run_folder, run_scores, save_run
from cuad_ai.settings import database_url


def main():
    load_dotenv()
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/final_test")
    report, decisions, queue = read_run_folder(folder)
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
