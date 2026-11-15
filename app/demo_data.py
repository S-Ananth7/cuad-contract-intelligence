"""Load and score a saved evaluation run for the demo.

No Streamlit in this file, so it can be tested on its own.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DECISION_KEYS = {"title", "clause", "decision", "reason", "gold_found", "quote_match", "retried"}
QUEUE_KEYS = {"title", "clause", "decision", "reason", "gold_found", "quotes", "retried", "looks_like"}


def _read_json(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ValueError(f"{path} is not valid JSON: {err}") from err


def _check_rows(rows, keys, source):
    if not isinstance(rows, list):
        raise ValueError(f"{source}: expected a list of rows")
    for i, row in enumerate(rows):
        missing = keys - row.keys()
        if missing:
            raise ValueError(f"{source}: row {i} is missing {sorted(missing)}")
    return rows


def load_decisions(folder):
    return _check_rows(_read_json(Path(folder) / "decisions.json"), DECISION_KEYS, "decisions.json")


def load_queue(folder):
    rows = _check_rows(_read_json(Path(folder) / "queue.json"), QUEUE_KEYS, "queue.json")
    for row in rows:  # parse failures have no quotes and no closest-clause list
        row["quotes"] = row["quotes"] or []
        row["looks_like"] = row["looks_like"] or []
    return rows


def load_extraction_summary(folder):
    """The first rung of the ladder: extraction alone, before the gate and judges."""
    s = _read_json(Path(folder) / "report_summary.json")["summary"]
    return {"precision": s["precision"], "recall": s["recall_errors_as_misses"]}


def contracts(rows):
    return sorted({r["title"] for r in rows})


def for_contract(rows, title):
    return sorted((r for r in rows if r["title"] == title), key=lambda r: r["clause"])


def score(rows):
    accepted = [r for r in rows if r["decision"] == "accept"]
    accepted_real = sum(bool(r["gold_found"]) for r in accepted)
    lawyer_marked = sum(bool(r["gold_found"]) for r in rows)
    return {
        "accepted": len(accepted),
        "accepted_real": accepted_real,
        "lawyer_marked": lawyer_marked,
        "precision": round(accepted_real / len(accepted), 3) if accepted else 0.0,
        "recall": round(accepted_real / lawyer_marked, 3) if lawyer_marked else 0.0,
    }


def queue_reasons(queue):
    return Counter(r["reason"] for r in queue).most_common()
