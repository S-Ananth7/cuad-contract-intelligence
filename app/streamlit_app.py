"""Read-only demo of a saved run. No model is called and no secrets are needed."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from demo_data import (
    contracts,
    evidence_for,
    for_contract,
    load_decisions,
    load_evidence,
    load_extraction_summary,
    load_queue,
    queue_reasons,
    score,
    verdict_text,
)

RUN = Path(__file__).resolve().parents[1] / "evals" / "final_test"
REPO = "https://github.com/S-Ananth7/cuad-contract-intelligence"
LABELS = {"accept": "Accepted", "reject": "Rejected", "queue": "Sent to review", "not_found": "Not found"}
TINT = {"Accepted": "#E6F4EA", "Rejected": "#FCE8E6", "Sent to review": "#FFF4E0", "Not found": "#F1F3F4"}
NAVY, LIGHT = "#1F4E79", "#9DB8D2"
GATE_RUNG = (0.726, 0.922)  # from evals/final_test/README.md; the other two rungs are computed from the files
STEPS = [
    ("1  Retrieve", "Pick the passages most likely to hold each of the 41 clause types."),
    ("2  Extract", "A model quotes the clause's exact words."),
    ("3  Verify", "Code checks every quote appears word for word. One retry if not."),
    ("4  Gate", "Doubtful answers and error-prone clause types are held back."),
    ("5  Judges", "Two separate checks must both agree."),
    ("6  Decide", "Accept, reject, or send to a person."),
]

st.set_page_config(page_title="CUAD Contract Intelligence", page_icon="📄", layout="wide")
st.markdown(
    "<style>.block-container{padding-top:2rem;max-width:1200px;} footer{visibility:hidden;}</style>",
    unsafe_allow_html=True,
)


@st.cache_data
def load_all():
    return load_decisions(RUN), load_queue(RUN), load_extraction_summary(RUN), load_evidence(RUN)


def show_passage(text: str) -> None:
    """Contract text as plain wrapped code, so symbols like $ are never read as formatting."""
    st.code(text, language=None, wrap_lines=True)


def tint(value: str) -> str:
    return f"background-color: {TINT[value]}; color: #1B2430"


try:
    rows, queue, extraction, evidence = load_all()
except (FileNotFoundError, ValueError) as err:
    st.error(f"Could not load the saved run: {err}")
    st.stop()

final = score(rows)
counts = Counter(r["decision"] for r in rows)

st.title("Contract clause extraction")
st.markdown(
    "Finds **41 types of clauses** in contracts, quotes the exact words, checks every quote, "
    "and sends doubtful answers to a person."
)
st.caption(
    "Saved final run on the 102 official CUAD test contracts, scored end to end once after the design was frozen. "
    f"No model is called live. [Source code]({REPO})"
)

st.info(
    "Want to try your own contract? The source includes a live review: upload a contract, see each quote highlighted "
    f"in the text, and confirm or reject answers. It runs on your own computer: see [Live review]({REPO}#live-review)."
)

with st.container(border=True):
    st.markdown("**How an answer is produced**")
    for col, (name, text) in zip(st.columns(len(STEPS)), STEPS):
        col.markdown(f"**{name}**")
        col.caption(text)

tab_results, tab_contracts, tab_queue = st.tabs(["Results", "Contracts", "Review queue"])

with tab_results:
    cards = [
        ("Precision", f"{final['precision']:.3f}", "Of the answers accepted, the share lawyers also marked."),
        ("Recall", f"{final['recall']:.3f}", "Of the clauses lawyers marked, the share we accepted."),
        ("Accepted answers", f"{final['accepted']:,}", "Answers that passed every check."),
        ("Sent to a person", f"{counts['queue']:,}", "Answers the system was not sure about."),
    ]
    for col, (label, value, help_text) in zip(st.columns(4), cards):
        with col.container(border=True):
            st.metric(label, value, help=help_text)

    st.caption(
        f"Precision {final['precision']:.3f} means about {round(final['precision'] * 100)} of every 100 accepted "
        "answers were also marked by the lawyers. The others are mistakes, which is why doubtful answers go to a "
        "person and why accepted answers are worth skimming."
    )

    left, right = st.columns(2)
    with left:
        st.subheader("How precision improved")
        ladder = pd.DataFrame(
            [
                ("1 Extract only", extraction["precision"], extraction["recall"]),
                ("2 + Gate", *GATE_RUNG),
                ("3 + Judges", final["precision"], final["recall"]),
            ],
            columns=["Stage", "Precision", "Recall"],
        )
        st.bar_chart(ladder.set_index("Stage"), stack=False, color=[NAVY, LIGHT], height=280)
        st.dataframe(ladder.style.format({"Precision": "{:.3f}", "Recall": "{:.3f}"}), hide_index=True, width="stretch")
        st.caption(
            "Stage 1: the model alone. Stage 2: plus the gate, which holds back doubtful answers. "
            "Stage 3: plus the two judges. Each stage trades a little recall for higher precision."
        )
    with right:
        st.subheader("What happened to the 4,182 questions")
        outcome = pd.Series({LABELS[k]: counts.get(k, 0) for k in LABELS})
        st.bar_chart(outcome, horizontal=True, color=NAVY, height=280)
        st.caption(" · ".join(f"{name}: {n:,}" for name, n in outcome.items()))
        st.caption("A question is one clause in one contract: 102 contracts × 41 clause types.")

    with st.expander("How to read these numbers"):
        st.markdown(
            "- **Precision**: when the system says a clause is there, how often lawyers agree.\n"
            "- **Recall**: of the clauses lawyers found, how many the system also found.\n"
            "- The system was built and tuned on other contracts. The 102 test contracts were scored end to end once, "
            "after the design was frozen. Early retrieval experiments, which only check whether the right passage is "
            "found, also looked at all 510 contracts."
        )

with tab_contracts:
    title = st.selectbox("Choose a contract", contracts(rows))
    mine = for_contract(rows, title)
    per = Counter(r["decision"] for r in mine)
    for col, key in zip(st.columns(4), LABELS):
        with col.container(border=True):
            st.metric(LABELS[key], per.get(key, 0))
    shown = st.multiselect("Show", list(LABELS.values()), default=["Accepted", "Rejected", "Sent to review"])
    table = pd.DataFrame(
        [
            {
                "Clause": r["clause"],
                "Decision": LABELS[r["decision"]],
                "Reason": r["reason"],
                "Lawyers marked it": "yes" if r["gold_found"] else "no",
                "Retried": "yes" if r["retried"] else "no",
            }
            for r in mine
            if LABELS[r["decision"]] in shown
        ],
        columns=["Clause", "Decision", "Reason", "Lawyers marked it", "Retried"],
    )
    st.caption(f"{len(table)} of {len(mine)} clauses shown. Pick a clause below to see the quote next to the lawyers' passage.")
    st.dataframe(table.style.map(tint, subset=["Decision"]), hide_index=True, width="stretch")

    inspectable = [r for r in mine if LABELS[r["decision"]] in shown]
    if inspectable:
        st.subheader("Inspect the evidence")
        clause = st.selectbox("Clause", [r["clause"] for r in inspectable])
        row = next(r for r in inspectable if r["clause"] == clause)
        item = evidence_for(evidence, title, clause)
        st.write(f"**{LABELS[row['decision']]}.** {verdict_text(row, item)}")
        quoted, marked = st.columns(2)
        with quoted:
            st.markdown("**What the system quoted**")
            for q in item["quotes"]:
                show_passage(q)
            if not item["quotes"]:
                st.caption("Nothing was quoted.")
        with marked:
            st.markdown("**What the lawyers marked**")
            for g in item["gold"]:
                show_passage(g)
            if not item["gold"]:
                st.caption("The lawyers did not mark this clause.")

with tab_queue:
    reasons = queue_reasons(queue)
    for col, (name, n) in zip(st.columns(max(len(reasons), 1)), reasons):
        with col.container(border=True):
            st.metric(name.replace("_", " ").capitalize(), n)
    choice = st.selectbox("Filter by reason", ["All"] + [name for name, _ in reasons])
    items = [r for r in queue if choice == "All" or r["reason"] == choice]
    real = sum(bool(r["gold_found"]) for r in items)
    st.write(f"**{len(items)} answers** a person would review. Lawyers had marked {real} of them.")
    for r in items[:25]:
        with st.expander(f"{r['clause']} — {r['title'][:70]}"):
            st.caption(f"Reason: {r['reason']} · Lawyers marked this clause: {'yes' if r['gold_found'] else 'no'}")
            if r["quotes"]:
                for q in r["quotes"]:
                    show_passage(q)
            else:
                st.write("No quote: the model's reply could not be read.")
            if r["looks_like"]:
                st.caption("Closest clause types: " + ", ".join(r["looks_like"]))
    if len(items) > 25:
        st.caption(f"Showing the first 25 of {len(items)}.")

st.divider()
st.caption("Contract text from CUAD (Hendrycks et al.), licensed CC BY 4.0.")
