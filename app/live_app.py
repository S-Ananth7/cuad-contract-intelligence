"""Live review: upload a contract, watch the pipeline work, confirm or reject each answer.

Needs a database (DATABASE_URL) and a running worker (`python -m cuad_ai worker`) with the model settings in .env.
The hosted demo (streamlit_app.py) stays read-only; this page is the one that spends tokens, so it runs where
you control the keys.
"""
from __future__ import annotations

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

from cuad_ai.live import config, store
from live_data import export_csv, final_status, highlight_html, plain_reason, summary

NAVY = "#1F4E79"
TINT = {"Accepted": "#E6F4EA", "Confirmed by reviewer": "#E6F4EA", "Rejected": "#FCE8E6",
        "Rejected by reviewer": "#FCE8E6", "Needs review": "#FFF4E0", "Not found": "#F1F3F4"}
CARD = {"Accepted": "#1E7B34", "Needs review": "#B26A00", "Rejected": "#B3261E", "Not found": "#5F6368"}

load_dotenv()
try:  # the hosted wrapper has already set this
    st.set_page_config(page_title="Contract clause review", page_icon="📄", layout="wide")
except st.errors.StreamlitAPIException:
    pass
st.markdown(f"""<style>
.block-container{{padding-top:1.6rem;max-width:1250px;}} footer{{visibility:hidden;}}
.legend{{font-size:.88rem;color:#374151;line-height:1.7}} .dot{{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;margin-right:.4rem}}
.doc{{white-space:pre-wrap;font-family:Georgia,serif;font-size:.92rem;line-height:1.55;max-height:460px;overflow:auto;
 border:1px solid #E3E7EB;border-radius:8px;padding:1rem 1.2rem;background:#FCFCFD;color:#1B2430}}
mark{{background:#FFE08A;padding:0 2px;border-radius:2px}}
.badge{{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.8rem;font-weight:600;color:#1B2430}}
h1{{color:{NAVY};}}
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

st.title("Contract clause review")
st.markdown("Upload a contract. The system looks for **41 kinds of clauses**, quotes the exact words for each, "
            "and checks that every quote really appears in your contract. Doubtful answers come to you to confirm or reject.")

with st.expander("How to read the results", expanded=False):
    st.markdown(
        '<div class="legend">'
        f'<span class="dot" style="background:{CARD["Accepted"]}"></span><b>Accepted</b>: the checks passed. '
        "This is not a guarantee: on the 102 CUAD test contracts about 3 in 4 accepted answers were right, so skim them too.<br>"
        f'<span class="dot" style="background:{CARD["Needs review"]}"></span><b>Needs review</b>: the two checkers disagreed. '
        "This is where your decision matters most.<br>"
        f'<span class="dot" style="background:{CARD["Rejected"]}"></span><b>Rejected</b>: both checkers said the quote is not that clause.<br>'
        f'<span class="dot" style="background:{CARD["Not found"]}"></span><b>Not found</b>: no matching text in the contract.<br><br>'
        "Your confirm or reject is saved next to the machine's decision and never replaces it."
        "</div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Your review")
    reviewer = st.text_input("Your name", key="reviewer", help="Saved with each decision you make.")
    st.divider()
    st.subheader("Add a contract")
    upload = st.file_uploader("Plain text (.txt)", type=["txt"], label_visibility="collapsed")
    if upload and st.button("Review this contract", type="primary", width="stretch"):
        try:
            with connect() as conn:
                st.session_state["current"] = store.submit(
                    conn, upload.name, upload.getvalue().decode("utf-8", "replace"))
        except store.RejectedUpload as error:
            st.error(str(error))
    st.caption(f"Up to {config.max_chars():,} characters per file and {config.daily_cap()} uploads a day. "
               "Your text is sent to the model provider and stored here until you delete it.")

with connect() as conn:
    submissions = store.list_submissions(conn, 30)
if not submissions:
    st.info("No contracts yet. Add a .txt contract in the sidebar and it will appear here.")
    st.stop()

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
    return f"background-color: {TINT[value]}; color: #1B2430"


@st.fragment(run_every=3 if active else None)
def show(submission_id: int):
    with connect() as conn:
        sub = store.get_submission(conn, submission_id)
        answers = store.get_answers(conn, submission_id)
        text = store.get_text(conn, submission_id) or ""
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
        st.markdown(f"<span class='badge' style='background:{TINT[status]}'>{status}</span>", unsafe_allow_html=True)
        st.write(plain_reason(a["reason"]) or "No quote to check.")
        if a["verdict"] is not None or a["verdict2"] is not None:
            word = {True: "yes", False: "no", None: "no answer"}
            st.write(f"**Checker 1:** {word[a['verdict']]} · **Checker 2:** {word[a['verdict2']]}")
        if a["looks_like"]:
            st.write("The checkers thought it looks more like: " + ", ".join(a["looks_like"]))
        if a["review_action"]:
            st.caption(f"{a['reviewer']} {a['review_action']}ed this" + (f": {a['review_note']}" if a["review_note"] else ""))
        who = st.session_state.get("reviewer", "").strip()
        if a["quotes"]:
            note = st.text_input("Note (optional)", key=f"note{pick}")
            confirm, reject, undo = st.columns(3)
            if confirm.button("Confirm", key=f"c{pick}", disabled=not who, type="primary", width="stretch"):
                with connect() as conn:
                    store.review_answer(conn, submission_id, pick, who, "confirm", note)
                st.rerun()
            if reject.button("Reject", key=f"r{pick}", disabled=not who, width="stretch"):
                with connect() as conn:
                    store.review_answer(conn, submission_id, pick, who, "reject", note)
                st.rerun()
            if a["review_action"] and undo.button("Undo", key=f"u{pick}", width="stretch"):
                with connect() as conn:
                    store.clear_review(conn, submission_id, pick)
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
            store.delete_submission(conn, submission_id)
        st.session_state.pop("current", None)
        st.rerun()


show(chosen)
st.caption("Answers are suggestions from a language model plus automatic checks, not legal advice. "
           "Accuracy figures belong to the CUAD test set, not to your contract.")
