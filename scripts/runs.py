import json
import sys
from pathlib import Path

from cuad_ai.runlog import RUNS_DIR, load_report

KEYS = ["tp", "fp", "fn", "tn", "errors", "recall", "recall_errors_as_misses", "precision",
        "invented_quotes", "quote_matches_lawyers", "avg_tokens_in", "avg_tokens_out", "avg_seconds"]


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "list":
        for folder in sorted(Path(RUNS_DIR).iterdir()):
            s = json.loads((folder / "report.json").read_text(encoding="utf-8"))["summary"]
            print(f"{folder.name:<72} n={s['contracts']:<3} recall={s['recall']} precision={s['precision']} "
                  f"invented={s['invented_quotes']} errors={s['errors']}")
    elif command == "compare" and len(sys.argv) >= 4:
        try:
            a, b = load_report(sys.argv[2]), load_report(sys.argv[3])
        except FileNotFoundError as error:
            raise SystemExit(str(error))
        print(f"{'':<26}{'A':>12}{'B':>12}")
        for key in KEYS:
            print(f"{key:<26}{str(a['summary'][key]):>12}{str(b['summary'][key]):>12}")
        rows_a = {row["title"]: row for row in a["rows"]}
        print("ROWS THAT DIFFER (found, number of quotes, value):")
        for row in b["rows"]:
            other = rows_a.get(row["title"])
            if other and (other["found"], len(other["quotes"]), other["value"]) != (row["found"], len(row["quotes"]), row["value"]):
                print(row["title"][:48], "| A:", other["found"], len(other["quotes"]), other["value"],
                      "| B:", row["found"], len(row["quotes"]), row["value"])
    else:
        raise SystemExit("usage: python scripts\\runs.py list | compare <key A> <key B>")


if __name__ == "__main__":
    main()
