"""Run the whole pipeline in order and print the final table.

  python -m cuad_ai pipeline                 extract (using the SET/K/LIMIT/OFFSET settings), then everything after
  python -m cuad_ai pipeline <run folder>    skip the extraction, start from an existing run

Needs evals/risk_table.json (made by `cuad_ai freeze-risk` from validation runs). Risk is never learned from the
contracts being scored.
"""
import sys
from pathlib import Path

from cuad_ai.pipeline import extraction, finalize, gate, judge_examples, judge_quote, route

RISK_TABLE = Path("evals/risk_table.json")


def stage(name, module, *args):
    print(f"\n$ cuad_ai {name} {' '.join(args)}".rstrip(), flush=True)
    return module.main(list(args))


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if not RISK_TABLE.exists():
        raise SystemExit("evals/risk_table.json is missing. Run `python -m cuad_ai freeze-risk` on validation runs first.")
    if args:
        folder = Path(args[0])
    else:
        folder = stage("extract", extraction)
        if folder is None:
            raise SystemExit("extraction did not finish; fix that first (re-running resumes from the cache)")
    stage("gate", gate, str(folder / "report.json"))
    stage("route", route, str(folder), str(RISK_TABLE))
    stage("judge1", judge_quote, str(folder))
    stage("judge2", judge_examples, str(folder))
    stage("finalize", finalize, str(folder))


if __name__ == "__main__":
    main()
