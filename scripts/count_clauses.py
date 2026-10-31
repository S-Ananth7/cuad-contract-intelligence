from cuad_ai.loader import load_contracts, load_splits

contracts = load_contracts()
dev = set(load_splits()["dev"])

present = {}
present_dev = {}
lengths = {}

for contract in contracts:
    for qa in contract["paragraphs"][0]["qas"]:
        clause = qa["id"].rsplit("__", 1)[-1]
        present.setdefault(clause, 0)
        present_dev.setdefault(clause, 0)
        lengths.setdefault(clause, [])
        if not qa["is_impossible"]:
            present[clause] += 1
            if contract["title"] in dev:
                present_dev[clause] += 1
            lengths[clause].extend(len(a["text"]) for a in qa["answers"])

print(f"{'CLAUSE':<42}{'OF 510':>7}{'IN DEV':>8}{'AVG CHARS':>11}{'QUOTES':>8}")
for clause in sorted(present, key=present.get, reverse=True):
    chars = lengths[clause]
    avg = round(sum(chars) / len(chars)) if chars else 0
    per_contract = round(len(chars) / present[clause], 1) if present[clause] else 0
    print(f"{clause[:41]:<42}{present[clause]:>7}{present_dev[clause]:>8}{avg:>11}{per_contract:>8}")
