from cuad_ai.loader import get_contract, get_text, load_contracts, load_splits
from cuad_ai.validate import normalize

contracts = load_contracts()
before = after = 0
for title in load_splits()["dev"]:
    text = get_text(get_contract(contracts, title))
    before += len(text)
    after += len(normalize(text))
print("characters before:", before, "after:", after, "saved:", round(100 * (1 - after / before), 1), "%")
