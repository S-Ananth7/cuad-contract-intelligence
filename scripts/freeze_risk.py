"""Build evals/risk_table.json: how often each clause was a false alarm, from VALIDATION runs only.

Usage: python scripts/freeze_risk.py <run folder> [<run folder> ...]
Each folder must hold gate_features.json (from gate_features.py).
The table is frozen: routing the test set uses it, so risk is never learned from the contracts being scored.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path("evals/risk_table.json")


def main():
    folders = sys.argv[1:]
    if not folders:
        raise SystemExit("give at least one validation run folder")
    seen = defaultdict(lambda: [0, 0])  # clause -> [found answers, false alarms]
    for folder in folders:
        for row in json.loads((Path(folder) / "gate_features.json").read_text(encoding="utf-8")):
            seen[row["clause"]][0] += 1
            seen[row["clause"]][1] += not row["gold_found"]
    answers = sum(v[0] for v in seen.values())
    overall = sum(v[1] for v in seen.values()) / answers
    table = {"overall": overall, "answers": answers, "source_runs": [Path(f).name for f in folders],
             "clauses": dict(seen)}
    OUT.write_text(json.dumps(table, indent=1), encoding="utf-8")
    print(f"saved {OUT}: {answers} answers from {len(folders)} runs, overall false-alarm rate {overall:.3f}")


if __name__ == "__main__":
    main()
