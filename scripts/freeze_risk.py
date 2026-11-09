import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    counts = defaultdict(lambda: [0, 0])  # clause -> [found answers, false alarms]
    for folder in sys.argv[1:]:
        rows = json.loads((Path(folder) / "gate_features.json").read_text(encoding="utf-8"))
        for row in rows:
            counts[row["clause"]][0] += 1
            counts[row["clause"]][1] += not row["gold_found"]

    out = Path("evals/risk_table.json")
    out.write_text(json.dumps(counts), encoding="utf-8")
    print("clauses:", len(counts), "| answers:", sum(v[0] for v in counts.values()), "| saved:", out)


if __name__ == "__main__":
    main()