"""Stage 1 of routing: split found answers into ACCEPT and REVIEW. No model calls.

Confidence = the asked clause is the closest of all 41 clauses to the quote
(from gate_features.json).
Risk = how often this clause was a false alarm.
  - No table given: learned from the OTHER half of the contracts (two halves).
  - Table given (from freeze_risk.py): taken from that file, so the contracts
    being routed never supply their own risk.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from cuad_ai.settings import ALWAYS_ACCEPT, PRIOR_WEIGHT, RISK_LIMIT


def smoothed(counts):
    """counts: clause -> [answers, false alarms]. Return clause -> smoothed false-alarm rate."""
    overall = sum(v[1] for v in counts.values()) / sum(v[0] for v in counts.values())

    def risk(clause):
        answers, false_alarms = counts.get(clause, [0, 0])
        return (false_alarms + overall * PRIOR_WEIGHT) / (answers + PRIOR_WEIGHT)

    return risk


def risk_function(train_rows):
    """Return clause -> risk, learned from train_rows only."""
    counts = defaultdict(lambda: [0, 0])
    for row in train_rows:
        counts[row["clause"]][0] += 1
        counts[row["clause"]][1] += not row["gold_found"]
    return smoothed(counts)


def frozen_risk(path):
    """Return clause -> risk, from the counts saved by freeze_risk.py."""
    return smoothed(json.loads(Path(path).read_text(encoding="utf-8")))


def decide(row):
    """The routing rule. Needs row['risk'] to be set."""
    sure = row["rank_asked"] == 1 and row["risk"] <= RISK_LIMIT
    return "accept" if sure or row["clause"] in ALWAYS_ACCEPT else "review"


def route(rows):
    """Half-split routing: a clause's risk comes from the other half of the contracts."""
    titles = sorted({r["title"] for r in rows})
    half = {title: i % 2 for i, title in enumerate(titles)}
    for k in (0, 1):
        risk = risk_function([r for r in rows if half[r["title"]] != k])
        for r in (r for r in rows if half[r["title"]] == k):
            r["risk"] = round(risk(r["clause"]), 3)
            r["route"] = decide(r)
    return rows


def main():
    folder = Path(sys.argv[1])
    rows = json.loads((folder / "gate_features.json").read_text(encoding="utf-8"))
    if len(sys.argv) > 2:
        risk = frozen_risk(sys.argv[2])
        for r in rows:
            r["risk"] = round(risk(r["clause"]), 3)
            r["route"] = decide(r)
    else:
        rows = route(rows)
    (folder / "routing.json").write_text(json.dumps(rows), encoding="utf-8")

    print(f"{'route':8}{'answers':>9}{'real':>7}{'false':>7}{'precision':>11}")
    for name in ("accept", "review"):
        part = [r for r in rows if r["route"] == name]
        real = sum(r["gold_found"] for r in part)
        print(f"{name:8}{len(part):>9}{real:>7}{len(part) - real:>7}{real / max(len(part), 1):>11.3f}")
    print("saved:", folder / "routing.json")


if __name__ == "__main__":
    main()
