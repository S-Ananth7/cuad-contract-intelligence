"""The worker: takes queued uploads one at a time and runs them. Start it with `cuad worker`."""
import time

import psycopg

from cuad_ai.embed import load_model
from cuad_ai.live import store
from cuad_ai.live.process import LockedEmbedder, load_bank, process
from cuad_ai.llm import call_model
from cuad_ai.settings import database_url


def run_once(connect, call, embedder, bank_for):
    """Claim and process one upload. Returns the submission id, or None when the queue is empty.

    bank_for(excluded_company) returns the Bank to use (cached per company by the caller).
    """
    with connect() as conn:
        sub = store.claim(conn)
    if sub is None:
        return None
    try:
        process(connect, sub, call, embedder, bank_for(sub["excluded_company"] or ""))
    except Exception as error:  # a bug or a database problem must not leave the job 'running' forever
        with connect() as conn:
            store.fail(conn, sub["id"], f"internal error: {type(error).__name__}")
    return sub["id"]


def main(argv=None, poll_seconds=3.0):
    url = database_url()

    def connect():
        return psycopg.connect(url)

    with connect() as conn:
        store.ensure_schema(conn)
    embedder = LockedEmbedder(load_model())
    banks = {}

    def bank_for(company):
        if company not in banks:
            with connect() as conn:
                banks[company] = load_bank(conn, company)
        return banks[company]

    print("worker ready; waiting for uploads")
    while True:
        if run_once(connect, call_model, embedder, bank_for) is None:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
