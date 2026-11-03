r"""Show, for one clause, what the model said next to what the lawyers marked.

Usage:
  python scripts\show_clause.py "Non-Compete"
  python scripts\show_clause.py "Non-Compete" fp        (only false alarms)
  python scripts\show_clause.py "Non-Compete" fp <run folder name>
Kinds: all, fp (model found, lawyers did not), fn (model missed), bad (invented quote).
Prints trimmed quotes only, never whole contracts.
"""
import json
import sys
from pathlib import Path

from cuad_ai.loader import get_contract, get_gold_quotes, load_contracts

RUNS = Path("evals/runs")
LIMIT = 260


def short(text):
    text = " ".join(text.split())
    return text if len(text) <= LIMIT else text[:LIMIT] + " ..."


def latest_clause_run():
    folders = sorted(p for p in RUNS.iterdir() if "_clauses_" in p.name)
    return folders[-1]


def main():
    clause = sys.argv[1]
    kind = sys.argv[2] if len(sys.argv) > 2 else "all"
    folder = RUNS / sys.argv[3] if len(sys.argv) > 3 else latest_clause_run()
    rows = json.loads((folder / "report.json").read_text(encoding="utf-8"))["rows"]
    contracts = load_contracts()
    print("run:", folder.name, "| clause:", clause, "| show:", kind)
    shown = 0
    for row in rows:
        if row["clause"] != clause:
            continue
        found, gold = bool(row["found"]), row["gold_found"]
        if kind == "fp" and not (found and not gold):
            continue
        if kind == "fn" and not (gold and not found):
            continue
        if kind == "bad" and row["quotes_real"] is not False:
            continue
        shown += 1
        verdict = "OK" if found == gold else ("FALSE ALARM" if found else "MISS")
        print("\n" + "=" * 70)
        print(f"{verdict} | model found={found} | lawyers found={gold} | quotes real={row['quotes_real']}")
        print("CONTRACT:", row["title"][:90])
        for q in row["quotes"][:3]:
            print("  MODEL  :", short(q))
        for q in get_gold_quotes(get_contract(contracts, row["title"]), clause)[:3]:
            print("  LAWYERS:", short(q))
    print(f"\n{shown} rows shown")


main()
