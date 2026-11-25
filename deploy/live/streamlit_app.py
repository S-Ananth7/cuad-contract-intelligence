"""Hosted entry point for the live review (Streamlit Community Cloud). Main file path: deploy/live/streamlit_app.py

What it adds to app/live_app.py:
  - an access code screen (secret LIVE_ACCESS_CODE; if it is not set the page stays closed),
  - a background thread that runs the worker, because Streamlit Cloud has no separate worker process. The thread
    asks the database for work only while someone has used the page in the last 30 minutes, so an idle
    deployment does not keep a hosted database awake. Jobs wait in the database and are picked up on the next visit.

Settings come from the app's Secrets (see docs/deploy-live.md): DATABASE_URL, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
LIVE_ACCESS_CODE, and optionally LIVE_DAILY_CAP, LIVE_TOKEN_CAP, LIVE_MAX_CHARS, LIVE_WORKERS.
"""
from __future__ import annotations

import os
import runpy
import sys
import threading
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]
os.chdir(ROOT)  # prompts, the risk table and sql/ are read relative to the repository root

from live_data import access_ok  # noqa: E402

IDLE_SECONDS = 30 * 60

st.set_page_config(page_title="Contract clause review", page_icon="📄", layout="wide")

try:  # Streamlit Cloud also exposes top-level secrets as environment variables; this covers the other cases
    for key, value in st.secrets.items():
        if isinstance(value, str):
            os.environ.setdefault(key, value)
except Exception:  # no secrets file: running locally with .env instead
    pass


@st.cache_resource
def background_worker():
    """Start the worker thread once per server process. Returns a dict the page updates and the thread reads."""
    state = {"last_seen": time.time(), "error": None}

    def run():
        try:
            import psycopg

            from cuad_ai.embed import load_model
            from cuad_ai.live import store
            from cuad_ai.live.process import LockedEmbedder
            from cuad_ai.live.worker import make_bank_cache, run_loop
            from cuad_ai.llm import call_model

            url = os.environ["DATABASE_URL"]

            def connect():
                return psycopg.connect(url, connect_timeout=10)

            with connect() as conn:
                store.ensure_schema(conn)
            embedder = LockedEmbedder(load_model())
            run_loop(connect, call_model, embedder, make_bank_cache(connect),
                     should_poll=lambda: time.time() - state["last_seen"] < IDLE_SECONDS)
        except Exception as error:  # shown on the page; the thread ends and a reboot restarts it
            state["error"] = f"{type(error).__name__}: {error}"[:300]

    threading.Thread(target=run, name="live-worker", daemon=True).start()
    return state


expected = os.environ.get("LIVE_ACCESS_CODE", "")
if not expected:
    st.title("Contract clause review")
    st.error("This deployment is not configured: the LIVE_ACCESS_CODE secret is missing, so the page stays closed.")
    st.stop()

if not st.session_state.get("granted"):
    st.title("Contract clause review")
    st.write("Enter the access code you were given.")
    code = st.text_input("Access code", type="password")
    if code:
        if access_ok(expected, code):
            st.session_state["granted"] = True
            st.rerun()
        time.sleep(1)  # slows down guessing
        st.error("That code is not right.")
    st.stop()

worker = background_worker()
worker["last_seen"] = time.time()
if worker["error"]:
    st.warning(f"The background worker stopped, so uploads will not be processed: {worker['error']}")

runpy.run_path(str(ROOT / "app" / "live_app.py"), run_name="__main__")
