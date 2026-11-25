"""Live review: upload a contract, watch the pipeline work, confirm or reject each answer.

Needs a database (DATABASE_URL) and a running worker (`python -m cuad_ai worker`) with the model settings in .env.
The hosted demo (streamlit_app.py) stays read-only; this page is the one that spends tokens, so it runs where
you control the keys.
"""
from __future__ import annotations

import html
import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

from cuad_ai.live import config, store, tenants
from live_data import export_csv, final_status, highlight_html, plain_reason, summary

# One neutral palette (the app theme). The only status that asks for action, "Needs review", gets a quiet tint.
ACTION_FILL = "#EAF0F7"

load_dotenv()
try:  # the hosted wrapper has already set this
    st.set_page_config(page_title="Contract clause review", layout="wide")
except st.errors.StreamlitAPIException:
    pass
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1200px;} footer{visibility:hidden;}
.doc{white-space:pre-wrap;font-family:Georgia,serif;font-size:.92rem;line-height:1.6;max-height:460px;overflow:auto;
 border:1px solid #D5DAE1;border-radius:4px;padding:1rem 1.2rem;background:#FFFFFF}
mark{background:#FFF1B8;padding:0 2px}
.badge{display:inline-block;padding:.1rem .55rem;border:1px solid #AEB7C4;border-radius:4px;font-size:.8rem;font-weight:600}
.account{text-align:right;font-weight:600;padding-top:.6rem} .account span{font-weight:400;font-size:.85rem;opacity:.75}
</style>""", unsafe_allow_html=True)


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)


try:
    with connect() as conn:
        store.ensure_schema(conn)
except KeyError:
    st.title("Contract clause review")
    st.error("DATABASE_URL is not set. Add it to .env (see .env.example) and restart the page.")
    st.stop()
except psycopg.Error as error:
    st.title("Contract clause review")
    st.error("The database did not answer. Is Postgres running (docker compose up -d db) and does DATABASE_URL "
             f"point at it? ({type(error).__name__})")
    st.stop()

# Who is this? The hosted sign-in wrapper sets these after login. Run directly, it is a private local client.
tenant = st.session_state.get("tenant")
email = st.session_state.get("email")
if tenant is None:
    tenant = os.environ.get("LIVE_LOCAL_TENANT", "local")
    with connect() as conn:
        if tenants.get_tenant(conn, tenant) is None:
            tenants.create_tenant(conn, tenant, tenant.title())
with connect() as conn:
    client = tenants.get_tenant(conn, tenant)
if client is None:
    st.title("Contract clause review")
    st.error("Your account is not set up. Please contact the person who gave you access.")
    st.stop()
cap = client["daily_cap"] if client["daily_cap"] is not None else config.daily_cap()

head, who = st.columns([3, 2])
head.title("Contract clause review")
head.caption("Clause extraction with quoted evidence and a human review step.")
who.markdown(f"<div class='account'>{html.escape(client['name'])}<br>"
             f"<span>{html.escape(email or 'Local session')}</span></div>", unsafe_allow_html=True)


def welcome() -> None:
    with st.container(border=True):
        st.subheader(f"Welcome, {client['name']}")
        st.write("This workspace reads a contract, finds 41 kinds of clauses and quotes the exact words behind each "
                 "answer. Every quote is checked against your document, and anything doubtful is left for you to "
                 "confirm or reject.")
        one, two, three = st.columns(3)
        one.markdown("**1. Upload**  \nAdd a plain-text (.txt) contract in the sidebar.")
        two.markdown("**2. Wait**  \nA review takes a few minutes. You can leave this page open.")
        three.markdown("**3. Review**  \nStart with Needs review, then skim the accepted answers.")
        st.caption(f"Contracts are visible only to {client['name']}. They are deleted automatically after "
                   f"{client['retention_days']} days, or sooner if you delete them.")



with st.sidebar:
    st.subheader("Account")
    if email:
        st.caption(f"Signed in as {email}. Your decisions are saved under this address.")
    else:
        st.text_input("Your name", key="reviewer", help="Saved with each decision you make.")
    st.divider()
    st.subheader("Add a contract")
    upload = st.file_uploader("Plain text (.txt)", type=["txt"], label_visibility="collapsed")
    if upload and st.button("Review this contract", type="primary", width="stretch"):
        try:
            with connect() as conn:
                st.session_state["current"] = store.submit(
                    conn, tenant, upload.name, upload.getvalue().decode("utf-8", "replace"),
                    uploaded_by=email or st.session_state.get("reviewer", "") or "local")
                tenants.audit(conn, tenant, email or "local", "upload", st.session_state["current"], upload.name)
        except store.RejectedUpload as error:
            st.error(str(error))
    st.caption(f"Up to {config.max_chars():,} characters per file and {cap} uploads a day. Your text is sent to "
               f"the model provider and deleted automatically after {client['retention_days']} days, or sooner if you delete it.")

with connect() as conn:
    submissions = store.list_submissions(conn, tenant, 30)
if not submissions:
    welcome()
    st.stop()

with st.expander("How to read the results", expanded=False):
    st.markdown(
        "- **Accepted**: the automatic checks passed. This is not a guarantee: on the 102 CUAD test contracts "
        "about 3 in 4 accepted answers were right, so skim them too.\n"
        "- **Needs review**: the two checkers disagreed. This is where your decision matters most.\n"
        "- **Rejected**: both checkers said the quote is not that clause.\n"
        "- **Not found**: no matching text in the contract.\n\n"
        "Your confirm or reject is saved next to the machine's decision and never replaces it.")

ids = [s["id"] for s in submissions]
current = st.session_state.get("current", ids[0])
status_word = {"queued": "waiting", "running": "running", "done": "done", "failed": "failed"}
chosen = st.selectbox("Contract", ids, index=ids.index(current) if current in ids else 0,
                      format_func=lambda i: next(f"{s['filename']}  ·  {status_word[s['status']]}"
                                                 for s in submissions if s["id"] == i))
active = any(s["id"] == chosen and s["status"] in ("queued", "running") for s in submissions)


def cards(counts: dict) -> None:
    columns = st.columns(4)
    for column, label in zip(columns, ("Accepted", "Needs review", "Rejected", "Not found")):
        column.metric(label, counts[label])
    if counts["reviewed"]:
        st.caption(f"{counts['reviewed']} decided by a person.")


def color_status(value: str) -> str:
    return f"background-color: {ACTION_FILL}; font-weight: 600" if value == "Needs review" else ""


@st.fragment(run_every=3 if active else None)
def show(submission_id: int):
    with connect() as conn:
        sub = store.get_submission(conn, tenant, submission_id)
        answers = store.get_answers(conn, tenant, submission_id)
        text = store.get_text(conn, tenant, submission_id) or ""
    if sub is None:
        st.warning("That contract is no longer available.")
        return
    if sub["status"] in ("queued", "running"):
        st.session_state[f"poll{submission_id}"] = True
        total = sub["total_questions"] or 1
        st.progress(sub["done_questions"] / total,
                    text=f"Working: {sub['done_questions']} of {sub['total_questions'] or 41} questions")
        if sub["status"] == "queued":
            st.info("Waiting for the worker. Start it in another terminal with: python -m cuad_ai worker")
    elif st.session_state.pop(f"poll{submission_id}", False):
        st.rerun()  # the run just finished: redraw the whole page so the labels update
    if sub["status"] == "failed":
        st.error(sub["error"] or "The run failed.")
    if sub["excluded_company"]:
        st.caption(f"This looks like a CUAD contract from {sub['excluded_company']}, so that company's lawyer examples "
                   "are left out, as they were for the test contracts.")
    if not answers:
        return

    counts = summary(answers)
    cards(counts)
    st.markdown("<hr style='margin:.4rem 0 .8rem'>", unsafe_allow_html=True)

    options = ["All", "Needs review", "Accepted", "Rejected", "Not found"]
    shown = st.radio("Show", options, horizontal=True, key=f"filter{submission_id}",
                     index=1 if counts["Needs review"] else 0)

    def in_view(a):
        status = final_status(a)
        if shown == "All":
            return True
        if shown == "Needs review":
            return a["decision"] == "queue" and not a["review_action"]
        return status == shown or (shown == "Accepted" and status == "Confirmed by reviewer") or \
            (shown == "Rejected" and status == "Rejected by reviewer")

    keep = [a for a in answers if in_view(a)]
    if not keep:
        st.success("Nothing here. Switch the view above to see the other answers.")
        return
    table = pd.DataFrame([{"Clause": a["clause"], "Status": final_status(a), "Why": plain_reason(a["reason"]),
                           "Quote": (" ... ".join(a["quotes"]))[:110]} for a in keep])
    st.dataframe(table.style.map(color_status, subset=["Status"]), hide_index=True, width="stretch",
                 height=min(38 * len(table) + 40, 420))

    st.subheader("Inspect one answer")
    pick = st.selectbox("Clause", [a["id"] for a in keep], key=f"pick{submission_id}",
                        format_func=lambda i: next(a["clause"] for a in keep if a["id"] == i))
    a = next(x for x in keep if x["id"] == pick)
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("**Where it sits in your contract** (highlighted)")
        st.markdown(f"<div class='doc'>{highlight_html(text, a['spans'])}</div>", unsafe_allow_html=True)
        if a["quotes"] and not a["spans"]:
            st.warning("The model's quote could not be found word for word, so it is not highlighted.")
    with right:
        status = final_status(a)
        st.markdown(f"### {a['clause']}")
        st.markdown(f"<span class='badge'>{status}</span>", unsafe_allow_html=True)
        st.write(plain_reason(a["reason"]) or "No quote to check.")
        if a["verdict"] is not None or a["verdict2"] is not None:
            word = {True: "yes", False: "no", None: "no answer"}
            st.write(f"**Checker 1:** {word[a['verdict']]} · **Checker 2:** {word[a['verdict2']]}")
        if a["looks_like"]:
            st.write("The checkers thought it looks more like: " + ", ".join(a["looks_like"]))
        if a["review_action"]:
            st.caption(f"{a['reviewer']} {a['review_action']}ed this" + (f": {a['review_note']}" if a["review_note"] else ""))
        who = email or st.session_state.get("reviewer", "").strip()
        if a["quotes"]:
            note = st.text_input("Note (optional)", key=f"note{pick}")
            confirm, reject, undo = st.columns(3)
            if confirm.button("Confirm", key=f"c{pick}", disabled=not who, type="primary", width="stretch"):
                with connect() as conn:
                    store.review_answer(conn, tenant, submission_id, pick, who, "confirm", note)
                    tenants.audit(conn, tenant, who, "review:confirm", submission_id, a["clause"])
                st.rerun()
            if reject.button("Reject", key=f"r{pick}", disabled=not who, width="stretch"):
                with connect() as conn:
                    store.review_answer(conn, tenant, submission_id, pick, who, "reject", note)
                    tenants.audit(conn, tenant, who, "review:reject", submission_id, a["clause"])
                st.rerun()
            if a["review_action"] and undo.button("Undo", key=f"u{pick}", width="stretch"):
                with connect() as conn:
                    store.clear_review(conn, tenant, submission_id, pick)
                    tenants.audit(conn, tenant, who, "review:clear", submission_id, a["clause"])
                st.rerun()
            if not who:
                st.caption("Enter your name in the sidebar to record a decision.")
        else:
            st.caption("There is no quote to confirm.")

    st.divider()
    left, right = st.columns([1, 1])
    left.download_button("Download results (CSV)", export_csv(sub["filename"], answers),
                         file_name=f"{sub['filename']}.review.csv", mime="text/csv")
    if right.button("Delete this contract and its results", key=f"del{submission_id}"):
        with connect() as conn:
            if store.delete_submission(conn, tenant, submission_id):
                tenants.audit(conn, tenant, email or "local", "delete", submission_id, sub["filename"])
        st.session_state.pop("current", None)
        st.rerun()


if st.session_state.get("viewed") != (tenant, chosen):
    st.session_state["viewed"] = (tenant, chosen)
    with connect() as conn:
        tenants.audit(conn, tenant, email or "local", "view", chosen)
show(chosen)
st.caption("Answers are suggestions from a language model plus automatic checks, not legal advice. "
           "Accuracy figures belong to the CUAD test set, not to your contract.")
