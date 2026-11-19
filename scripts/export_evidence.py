"""Build evals/final_test/evidence.json.gz: each answer's quotes next to the lawyers' passages.

Needs the CUAD file (data/CUADv1.json, not in the repo) and the run folder with report.json.
Only the quoted passages are written, never whole contracts. CUAD is CC BY 4.0 (Hendrycks et al.).

Usage: python scripts/export_evidence.py [run folder] [CUAD json]
"""
import json
import sys
from pathlib import Path

from cuad_ai.evidence import build_evidence, save_evidence

RUN = "evals/runs/20261108_172552_rag_clause_rag_deepseek-v4-flash_k10_102"
OUT = Path("evals/final_test/evidence.json.gz")


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    run = Path(args[0] if args else RUN)
    cuad_path = Path(args[1] if len(args) > 1 else "data/CUADv1.json")
    decisions = json.loads(Path("evals/final_test/decisions.json").read_text(encoding="utf-8"))
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))["rows"]
    cuad = json.loads(cuad_path.read_text(encoding="utf-8"))

    evidence = build_evidence(decisions, report, cuad)
    save_evidence(evidence, OUT)

    rows = [c for clauses in evidence.values() for c in clauses.values()]
    marked = sum(bool(r["gold_found"]) for r in decisions)
    with_gold = sum(bool(r["gold"]) for r in rows)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB): {len(rows)} answers, {len(evidence)} contracts")
    print(f"answers with lawyer passages: {with_gold} (decisions say lawyers marked {marked})")
    if with_gold != marked:
        raise SystemExit("mismatch between the CUAD passages and the lawyer-marked count in decisions.json")


if __name__ == "__main__":
    main()
