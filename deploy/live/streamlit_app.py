"""Hosted entry point for the live review (Streamlit Community Cloud). Main file path: deploy/live/streamlit_app.py

What it adds to app/live_app.py:
  - Google / Microsoft sign-in (Streamlit's st.login, configured by the [auth] secrets). Only an email on the
    allow-list may enter, and it sees only its own client's contracts (see docs/security.md). Closed if not set up,
  - a background thread that runs the worker, because Streamlit Cloud has no separate worker process. The thread
    asks the database for work only while someone has used the page in the last 30 minutes, so an idle
    deployment does not keep a hosted database awake. Jobs wait in the database and are picked up on the next visit.

Settings come from the app's Secrets (see docs/deploy-live.md): DATABASE_URL, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
the [auth] sections, and optionally LIVE_SIGNIN_PROVIDERS, LIVE_TRUSTED_MS_TENANTS, LIVE_DAILY_CAP, LIVE_TOKEN_CAP,
LIVE_MAX_CHARS, LIVE_WORKERS.
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

from cuad_ai.live.signin import tenant_ids, verified_email  # noqa: E402

IDLE_SECONDS = 30 * 60

st.set_page_config(page_title="Contract clause review", layout="wide")

try:  # copy the app's secrets into the environment on every run, so a saved change is picked up without a reboot
    for key, value in st.secrets.items():
        if isinstance(value, str):
            os.environ[key] = value
except Exception:  # no secrets file: running locally with .env instead
    pass

RETRY_SECONDS = 30  # a stopped worker is started again after this long


def run_worker(state):
    """The worker thread: runs until the server stops. If it cannot start, it records why and ends."""
    state["error"] = None
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
    except Exception as error:  # shown on the page; the page starts a new thread after RETRY_SECONDS
        state["error"] = f"{type(error).__name__}: {error}"[:300]
    state["stopped_at"] = time.time()


def start_thread(state):
    state["thread"] = threading.Thread(target=run_worker, args=(state,), name="live-worker", daemon=True)
    state["thread"].start()


@st.cache_resource
def background_worker():
    """The worker's shared state, created once per server process. The page updates it, the thread reads it."""
    state = {"last_seen": time.time(), "error": None, "stopped_at": 0.0, "thread": None}
    start_thread(state)
    return state


SCREEN_CSS = """<style>
.block-container{max-width:940px;padding-top:14vh;} footer{visibility:hidden;}
[data-testid="stHeader"],[data-testid="stToolbar"]{display:none;}
.brand{background:linear-gradient(145deg,#EEF4FB 0%,#D2E3F5 100%);color:#17304F;border-radius:6px;
 padding:2.2rem 2rem;min-height:340px}
.brand .name{font-size:1.6rem;font-weight:700;line-height:1.25;margin-bottom:.8rem}
.brand .desc{line-height:1.6;margin-bottom:1.6rem;max-width:30ch}
.brand .point{border-left:3px solid #1F4E79;padding-left:.7rem;margin-bottom:.7rem;font-weight:600;font-size:.95rem}
.screen-title{font-size:1.5rem;font-weight:700;margin:3.2rem 0 .2rem}
.screen-hint{opacity:.7;margin-bottom:1.4rem}
</style>"""
BRAND = """<div class="brand"><div class="name">Contract clause review</div>
<div class="desc">Upload a contract and get the key clauses back with the exact wording quoted from your document, ready for a person to confirm.</div>
<div class="point">Clause extraction</div><div class="point">Quoted evidence</div>
<div class="point">Human review</div></div>"""


def shell(title, hint):
    """A single card for the sign-in and no-access screens: a light panel on the left, the form on the right."""
    st.markdown(SCREEN_CSS, unsafe_allow_html=True)
    left, right = st.container(border=True).columns([1.1, 1], gap="large")
    left.markdown(BRAND, unsafe_allow_html=True)
    right.markdown(f"<div class='screen-title'>{title}</div><div class='screen-hint'>{hint}</div>",
                   unsafe_allow_html=True)
    return right


def sign_in_screen():
    with shell("Sign in", "Sign in to continue."):
        try:
            configured = "auth" in st.secrets
        except Exception:
            configured = False
        if not configured:
            st.error("Sign-in is not set up on this deployment (the [auth] secrets are missing), so the page stays closed.")
            return
        providers = [p.strip() for p in os.environ.get("LIVE_SIGNIN_PROVIDERS", "google,microsoft").split(",")
                     if p.strip()]
        for provider in providers:
            if st.button(f"Sign in with {provider.replace('_', ' ').title()}", key=f"login-{provider}",
                         width="stretch"):
                st.login(provider)


def allowed_client(email):
    """The client this email may use, or None. Looked up on every run, so removing someone takes effect at once."""
    import psycopg

    from cuad_ai.live import store, tenants

    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
            store.ensure_schema(conn)
            tenant = tenants.tenant_for_email(conn, email) if email else None
            if tenant and not st.session_state.get("login_logged"):
                tenants.audit(conn, tenant, email, "login")
                st.session_state["login_logged"] = True
            return tenant
    except (KeyError, psycopg.Error):
        st.title("Contract clause review")
        st.error("The database did not answer, so nobody can be signed in right now. Please try again shortly.")
        st.stop()


if not getattr(st.user, "is_logged_in", False):  # missing means not signed in: stay closed
    for key in ("tenant", "email", "login_logged"):
        st.session_state.pop(key, None)
    sign_in_screen()
    st.stop()

email = verified_email(st.user.to_dict(), tenant_ids(os.environ.get("LIVE_TRUSTED_MS_TENANTS", "")))
tenant = allowed_client(email)
if tenant is None:
    for key in ("tenant", "email", "login_logged"):
        st.session_state.pop(key, None)
    with shell("No access", "This account does not have access."):
        st.button("Sign out", on_click=st.logout, width="stretch")
    st.stop()
st.session_state["tenant"], st.session_state["email"] = tenant, email
st.sidebar.button("Sign out", on_click=st.logout)

worker = background_worker()
worker["last_seen"] = time.time()
if not worker["thread"].is_alive() and time.time() - worker["stopped_at"] > RETRY_SECONDS:
    start_thread(worker)  # it stopped (for example a wrong secret that has since been fixed): try again
if worker["error"]:
    st.warning(f"The background worker is not running, so uploads will not be processed yet: {worker['error']}. "
               f"It retries by itself every {RETRY_SECONDS} seconds after you fix the setting; reload the page.")

runpy.run_path(str(ROOT / "app" / "live_app.py"), run_name="__main__")
