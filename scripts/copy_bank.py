"""Copy the example bank from your local database to the hosted one (see docs/deploy-live.md).

    $env:HOSTED_DATABASE_URL = "postgresql://...neon..."     # the hosted database; never put it in a file
    python scripts/copy_bank.py                               # source = DATABASE_URL from .env

Safe to run again. It only adds rows; it never deletes. Connection strings are not printed.
"""
import os

import psycopg
from dotenv import load_dotenv

from cuad_ai.live.bank import copy_bank


def main():
    load_dotenv()
    source, target = os.environ.get("DATABASE_URL"), os.environ.get("HOSTED_DATABASE_URL")
    if not source or not target:
        raise SystemExit("Set DATABASE_URL (your local database, in .env) and HOSTED_DATABASE_URL (the hosted one).")
    if source == target:
        raise SystemExit("HOSTED_DATABASE_URL is the same as DATABASE_URL. Nothing to copy.")
    with psycopg.connect(source) as src, psycopg.connect(target) as dst:
        counts = copy_bank(src, dst)
    print("hosted database now holds:", counts)


if __name__ == "__main__":
    main()
