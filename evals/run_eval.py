from datetime import date
from pathlib import Path
import json
import sys
import os
import time

from cuad_ai.extract import extract_governing_law, load_prompt
from cuad_ai.loader import get_contract, get_gold_quotes, get_text, load_contracts, load_splits
from cuad_ai.metrics import summarize

CLAUSE = "Governing Law"
PROMPT_PATH = "prompts/governing_law_v1.txt"
PAUSE_SECONDS = 3


def pick_titles(dev, limit):
    """Dev list has clause-present contracts first and absent last. Take some from each end."""
    extra = limit // 3
    return dev[: limit - extra] + dev[len(dev) - extra:]


def save_report(rows, model, limit):
    """Write every row plus the summary to a file. Called after each contract."""
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
    path = Path("evals/reports") / f"dev_{model.replace('/', '-')}_{limit}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    contracts = load_contracts()
    dev = load_splits()["dev"]
    prompt_text = load_prompt(PROMPT_PATH)
    model = os.environ.get("LLM_MODEL", "unknown")
    
    rows = []
    report = None
    for number, title in enumerate(pick_titles(dev, limit), start=1):
        contract = get_contract(contracts, title)
        row = extract_governing_law(get_text(contract), prompt_text)
        row["title"] = title
        row["gold_found"] = len(get_gold_quotes(contract, CLAUSE)) > 0
        rows.append(row)
        
        print(
            number, "found:", row["found"], row["gold_found"],
            "real: ", row["quotes_real"], "sec:", round(row["seconds"], 1),
            "error:", row["error"],
        )
        report = save_report(rows, report, limit)
        time.sleep(PAUSE_SECONDS)
    
    print(json.dumps(report["summary"], indent=2))
    
    
if __name__ == "__main__":
    main()
