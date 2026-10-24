from cuad_ai.loader import load_contracts, load_splits

contracts = load_contracts()
splits = load_splits()
print(len(contracts), len(splits["dev"]), len(splits["test"]))
