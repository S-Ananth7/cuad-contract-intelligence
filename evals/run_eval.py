import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

from cuad_ai.baseline import keyword_governing_law
from cuad_ai.extract import extract_governing_law, load_prompt
from cuad_ai.loader import get_contract, get_gold_quotes, get_text, load_contracts, load_splits
from cuad_ai.metrics import quotes_overlap, summarize
from cuad_ai.settings import env_text

CLAUSE = "Governing Law"
PROMPT_PATH = env_text("PROMPT_PATH", "prompts/governing_law.txt")
PAUSE_SECONDS = 3


def pick_titles(dev, limit):
    """Dev list has clause-present contracts first and absent last. Take some from each end."""
    limit = min(limit, len(dev))
    extra = limit // 3
    return dev[: limit - extra] + dev[len(dev) - extra:]


def save_report(rows, model, limit, stamp):
    """Write every row plus the summary to a new file. Called after each contract."""
    report = {
        "meta": {
            "model": model,
            "prompt": PROMPT_PATH,
            "clause": CLAUSE,
            "date": date.today().isoformat(),
            "contracts": len(rows),
        },
        "summary": summarize(rows),
        "rows": rows,
    }
    name = f"dev_{Path(PROMPT_PATH).stem}_{model.replace('/', '-')}_{limit}_{stamp}.json"
    path = Path("evals/reports") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, path


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    contracts = load_contracts()
    dev = load_splits()["dev"]
    prompt_text = load_prompt(PROMPT_PATH)
    model = os.environ.get("LLM_MODEL", "unknown")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows = []
    report, path = None, None
    for number, title in enumerate(pick_titles(dev, limit), start=1):
        contract = get_contract(contracts, title)
        if contract is None:
            raise SystemExit(f"title not found in CUAD: {title}")
        gold = get_gold_quotes(contract, CLAUSE)

        row = extract_governing_law(get_text(contract), prompt_text)
        row["title"] = title
        row["gold_found"] = len(gold) > 0
        row["quote_match"] = quotes_overlap(row["quotes"], gold)
        rows.append(row)

        print(
            number, "found:", row["found"], "gold:", row["gold_found"],
            "real:", row["quotes_real"], "match:", row["quote_match"],
            "sec:", round(row["seconds"], 1), "error:", row["error"],
        )
        report, path = save_report(rows, model, limit, stamp)

        if len(rows) >= 3 and all(r["error"] for r in rows[-3:]):
            print("3 failures in a row: stopping. The model is down or too slow.")
            break

        time.sleep(PAUSE_SECONDS)

    print(json.dumps(report["summary"], indent=2))
    print("report saved:", path)


if __name__ == "__main__":
    main()
