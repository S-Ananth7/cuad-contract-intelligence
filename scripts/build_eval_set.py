import json
from pathlib import Path

from cuad_ai.clauses import coverage_sample, positives_by_clause
from cuad_ai.loader import load_contracts, load_splits

contracts = load_contracts()
old_test = set(load_splits()["test"])

eval_titles = coverage_sample(contracts, old_test, per_clause=5, total=60, seed=7)
test2_titles = coverage_sample(contracts, old_test | set(eval_titles), per_clause=5, total=60, seed=11)

Path("evals/eval_set.json").write_text(json.dumps({"titles": eval_titles, "seed": 7}, indent=2), encoding="utf-8")
Path("evals/test_set_multi.json").write_text(json.dumps({"titles": test2_titles, "seed": 11}, indent=2), encoding="utf-8")

positives = positives_by_clause(contracts)
a, b = set(eval_titles), set(test2_titles)
print("eval set:", len(eval_titles), "| locked test set 2:", len(test2_titles))
print(f"{'CLAUSE':<42}{'IN EVAL':>8}{'IN TEST2':>10}")
for clause, found in sorted(positives.items(), key=lambda item: len(item[1] & a)):
    print(f"{clause[:41]:<42}{len(found & a):>8}{len(found & b):>10}")
