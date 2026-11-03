from cuad_ai.extract import extract_governing_law, load_prompt
from cuad_ai.loader import (
    get_contract,
    get_gold_quotes,
    get_text,
    load_contracts,
    load_splits,
)

# 1. Pick one contract from the dev pile. Never from test.
contracts = load_contracts()
title = load_splits()["dev"][0]
contract = get_contract(contracts, title)

row = extract_governing_law(
    get_text(contract),
    load_prompt("prompts/governing_law.txt")
)

print("TITLE:", title)
for key, value in row.items():
    print(f"{key}: {value}")
print("LAWYERS' QUOTES:", get_gold_quotes(contract, "Governing Law"))

