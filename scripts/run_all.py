"""Run the whole pipeline in order and print the final table.

  python scripts/run_all.py                 extract (using the SET/K/LIMIT/OFFSET settings), then everything after
  python scripts/run_all.py <run folder>    skip the extraction, start from an existing run

Needs evals/risk_table.json (made by freeze_risk.py from validation runs). Risk is never learned from the
contracts being scored.
"""
import subprocess
import sys
from pathlib import Path

RISK_TABLE = Path("evals/risk_table.json")
PY = sys.executable


def run(*command):
    print("\n$", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def extract():
    """Run evals/run_rag.py, show its output as it comes, return the run folder."""
    print("\n$ python evals/run_rag.py", flush=True)
    folder = None
    process = subprocess.Popen([PY, "evals/run_rag.py"], stdout=subprocess.PIPE, text=True, bufsize=1)
    for line in process.stdout:
        print(line, end="", flush=True)
        if line.startswith("run saved:"):
            folder = Path(line.split(":", 1)[1].strip()).parent
    if process.wait() != 0 or folder is None:
        raise SystemExit("extraction did not finish; fix that first (re-running resumes from the cache)")
    return folder


def main():
    if not RISK_TABLE.exists():
        raise SystemExit("evals/risk_table.json is missing. Run scripts/freeze_risk.py on validation runs first.")
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else extract()
    run(PY, "scripts/gate_features.py", str(folder / "report.json"))
    run(PY, "scripts/route_answers.py", str(folder), str(RISK_TABLE))
    run(PY, "scripts/verify_answers.py", str(folder))
    run(PY, "scripts/verify_with_examples.py", str(folder))
    run(PY, "scripts/final_answers.py", str(folder))


if __name__ == "__main__":
    main()
