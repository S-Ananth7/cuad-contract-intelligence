import json
import sys
from pathlib import Path

from cuad_ai.loader import get_contract, get_gold_quotes, load_contracts

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contracts = load_contracts()

for number, row in enumerate(report["rows"], start=1):
    wrong_quote = row["found"] and row["gold_found"] and not row["quote_match"]
    false_alarm = row["found"] and not row["gold_found"]
    if wrong_quote or false_alarm:
        gold = get_gold_quotes(get_contract(contracts, row["title"]), "Governing Law")
        print("ROW", number, "FALSE ALARM" if false_alarm else "QUOTE MISMATCH")
        print("TITLE:", row["title"])
        print("BASELINE QUOTES:", row["quotes"])
        print("LAWYERS' QUOTES:", gold)
        print()
