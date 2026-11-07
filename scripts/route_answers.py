"""Stage 1 of routing: split found answers into ACCEPT and REVIEW. No model calls.

Confidence = the asked clause is the closest of all 41 clauses to the quote
(from gate_features.json).
Risk = how often this clause was a false alarm in the OTHER half of the contracts
(two halves, so a clause's risk never comes from the contract being routed).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

RISK_LIMIT = 0.5  # clauses above this false-alarm rate always go to review
PRIOR_WEIGHT = 3  # how strongly a rare clause is pulled toward the overall rate


def risk_function(train_rows):
    """Return clause -> smoothed false-alarm rate, learned from train_rows only."""
    seen = defaultdict(lambda: [0, 0])
    for row in train_rows:
        seen[row["clause"]][0] += 1
        seen[row["clause"]][1] += not row["gold_found"]
    overall = sum(v[1] for v in seen.values()) / sum(v[0] for v in seen.values())
    return lambda clause: (seen[clause][1] + overall * PRIOR_WEIGHT) / (seen[clause][0] + PRIOR_WEIGHT)


def route(rows):
    """Add 'risk' and 'route' to every row. Contracts are split into two halves."""
    titles = sorted({r["title"] for r in rows})
    half = {title: i % 2 for i, title in enumerate(titles)}
    for k in (0, 1):
        risk = risk_function([r for r in rows if half[r["title"]] != k])
        for r in (r for r in rows if half[r["title"]] == k):
            r["risk"] = round(risk(r["clause"]), 3)
            confident = r["rank_asked"] == 1
            r["route"] = "accept" if confident and r["risk"] <= RISK_LIMIT else "review"
    return rows


def main():
    folder = Path(sys.argv[1])
    rows = route(json.loads((folder / "gate_features.json").read_text(encoding="utf-8")))
    (folder / "routing.json").write_text(json.dumps(rows), encoding="utf-8")

    print(f"{'route':8}{'answers':>9}{'real':>7}{'false':>7}{'precision':>11}")
    for name in ("accept", "review"):
        part = [r for r in rows if r["route"] == name]
        real = sum(r["gold_found"] for r in part)
        print(f"{name:8}{len(part):>9}{real:>7}{len(part) - real:>7}{real / max(len(part), 1):>11.3f}")
    print("saved:", folder / "routing.json")


if __name__ == "__main__":
    main()
