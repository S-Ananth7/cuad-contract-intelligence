from cuad_ai.loader import load_contracts, load_splits, get_contract, get_text

contracts = load_contracts()
dev = load_splits()["dev"]

lengths = sorted(len(get_text(get_contract(contracts, title))) for title in dev)

print("shortest", lengths[0])
print("median", lengths[len(lengths) // 2])
print("longest", lengths[-1])
