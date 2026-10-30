import json
import sys
from datetime import date, datetime
from pathlib import Path

from cuad_ai.baseline_v2 import keyword_governing_law_v2
from cuad_ai.loader import get_contract, get_gold_quotes, get_text, load_contracts, load_splits
from cuad_ai.metrics import quotes_overlap, summarize

CLAUSE = "Governing Law"


def pick_titles(dev, limit):
    """Dev list has clause-present contracts first and absent last. Take some from each end."""
    limit = min(limit, len(dev))
    extra = limit // 3
    return dev[: limit - extra] + dev[len(dev) - extra:]


def save_report(rows, limit, stamp):
    report = {
        "meta": {
            "method": "keyword-baseline-v2",
            "clause": CLAUSE,
            "date": date.today().isoformat(),
            "contracts": len(rows),
        },
        "summary": summarize(rows),
        "rows": rows,
    }
    path = Path("evals/reports") / f"dev_baseline_keyword_v2_{limit}_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, path


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    contracts = load_contracts()
    dev = load_splits()["dev"]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows = []
    for number, title in enumerate(pick_titles(dev, limit), start=1):
        contract = get_contract(contracts, title)
        if contract is None:
            raise SystemExit(f"title not found in CUAD: {title}")
        gold = get_gold_quotes(contract, CLAUSE)

        row = keyword_governing_law_v2(get_text(contract))
        row["title"] = title
        row["gold_found"] = len(gold) > 0
        row["quote_match"] = quotes_overlap(row["quotes"], gold)
        rows.append(row)

        print(
            number, "found:", row["found"], "gold:", row["gold_found"],
            "real:", row["quotes_real"], "match:", row["quote_match"],
        )

    report, path = save_report(rows, limit, stamp)
    print(json.dumps(report["summary"], indent=2))
    print("report saved:", path)


if __name__ == "__main__":
    main()
