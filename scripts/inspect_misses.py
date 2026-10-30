import json
import sys
from pathlib import Path

from cuad_ai.baseline_v2 import is_clause_like
from cuad_ai.loader import get_contract, get_gold_quotes, load_contracts

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contracts = load_contracts()

for number, row in enumerate(report["rows"], start=1):
    if row["gold_found"] and not row["found"]:
        contract = get_contract(contracts, row["title"])
        print("ROW", number, "MISS")
        print("TITLE:", row["title"])
        for quote in get_gold_quotes(contract, "Governing Law"):
            print("LAWYERS' QUOTE:", quote)
            print("PASSES v2 RULES ON ITS OWN:", is_clause_like(quote))
        print()
