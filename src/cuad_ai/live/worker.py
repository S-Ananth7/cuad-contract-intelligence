"""The worker: takes queued uploads one at a time and runs them. Start it with `cuad worker`.

The hosted page runs the same loop in a background thread (deploy/live/streamlit_app.py), polling the database only
while someone is using the page, so an idle deployment does not keep the database awake.
"""
import threading
import time

import psycopg

from cuad_ai.embed import load_model
from cuad_ai.live import store, tenants
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


def run_loop(connect, call, embedder, bank_for, should_poll=lambda: True, stop=None, poll_seconds=3.0,
             purge_seconds=6 * 3600):
    """Keep taking uploads until `stop` (a threading.Event) is set. Asks the database only when should_poll() is true.

    Each time it polls and the last clean-up was more than `purge_seconds` ago (the first poll counts), it also
    deletes uploads older than their client's retention period, so the retention promise does not depend on someone
    remembering to run `live-admin purge`.
    """
    stop = stop or threading.Event()
    last_purge = None
    while not stop.is_set():
        try:
            if should_poll():
                if last_purge is None or time.monotonic() - last_purge >= purge_seconds:
                    with connect() as conn:
                        tenants.purge_expired(conn)
                    last_purge = time.monotonic()
                if run_once(connect, call, embedder, bank_for) is not None:
                    continue  # more may be waiting: do not sleep
        except psycopg.Error:
            pass  # the database blinked (a hosted one wakes slowly); try again after the pause
        stop.wait(poll_seconds)


def make_bank_cache(connect):
    banks = {}

    def bank_for(company):
        if company not in banks:
            with connect() as conn:
                banks[company] = load_bank(conn, company)
        return banks[company]

    return bank_for


def main(argv=None, poll_seconds=3.0):
    url = database_url()

    def connect():
        return psycopg.connect(url)

    with connect() as conn:
        store.ensure_schema(conn)
    embedder = LockedEmbedder(load_model())
    print("worker ready; waiting for uploads")
    run_loop(connect, call_model, embedder, make_bank_cache(connect), poll_seconds=poll_seconds)


if __name__ == "__main__":
    main()
