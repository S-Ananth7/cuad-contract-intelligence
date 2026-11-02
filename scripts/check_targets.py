import json
import sys
from pathlib import Path

from cuad_ai.runlog import load_report

targets = json.loads(Path("evals/targets.json").read_text(encoding="utf-8"))
try:
    summary = load_report(sys.argv[1])["summary"]
except (IndexError, FileNotFoundError) as error:
    raise SystemExit(f"usage: python scripts\\check_targets.py <run key>  ({error})")

recall = summary["recall_errors_as_misses"]
checks = {
    "recall counting failed calls as misses": recall is not None and recall >= targets["min_recall"],
    "invented quotes": summary["invented_quotes"] <= targets["max_invented_quotes"],
    "failed call rate": summary["errors"] / summary["contracts"] <= targets["max_error_rate"],
}
for name, ok in checks.items():
    print("PASS" if ok else "FAIL", name)
raise SystemExit(0 if all(checks.values()) else 1)
