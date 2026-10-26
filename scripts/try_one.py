from cuad_ai.extract import build_prompt, load_prompt, parse_reply
from cuad_ai.llm import call_model
from cuad_ai.loader import (
    get_contract,
    get_gold_quotes,
    get_text,
    load_contracts,
    load_splits,
)
from cuad_ai.validate import quote_in_contract

# 1. Pick one contract from the dev pile. Never from test.
contracts = load_contracts()
splits = load_splits()
title = splits["dev"][0]
contract = get_contract(contracts, title)
text = get_text(contract)

# 2. Build the prompt and send it.
prompt_text = load_prompt("prompts/governing_law_v1.txt")
prompt = build_prompt(prompt_text, text)
result = call_model(prompt)

print("TITLE:", title)
print("TOKENS IN:", result["tokens_in"])
print("TOKENS OUT:", result["tokens_out"])
print("SECONDS:", round(result["seconds"], 2))

# 3. Read the reply into the form.
try:
    answer = parse_reply(result["text"])
except ValueError as error:
    print("PARSE FAILED:", error)
    print("RAW REPLY:", result["text"])
    raise SystemExit(1)

print("FOUND:", answer.found)
print("VALUE:", answer.value)

# 4. Check every quote against the contract.
for quote in answer.quotes:
    print("QUOTE IN CONTRACT:", quote_in_contract(text, quote))

# 5. Compare with the lawyers.
print("MODEL QUOTES:", answer.quotes)
print("LAWYERS' QUOTES:", get_gold_quotes(contract, "Governing Law"))