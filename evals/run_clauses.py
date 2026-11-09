import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from cuad_ai.cache import cached
from cuad_ai.clauses import clause_questions, make_clause_prompt
from cuad_ai.extract import extract_governing_law, load_prompt
from cuad_ai.llm import call_model
from cuad_ai.loader import get_contract, get_gold_quotes, get_text, load_contracts, load_splits
from cuad_ai.metrics import quotes_overlap, summarize
from cuad_ai.runlog import RUNS_DIR, find_run, load_report, log_run, new_run_id, run_info, write_report
from cuad_ai.settings import env_flag, env_float, env_text

TEMPLATE_PATH = env_text("TEMPLATE_PATH", "prompts/clause.txt")
CORE = ["Governing Law", "Effective Date", "Anti-Assignment", "Termination For Convenience", "Cap On Liability"]
PAUSE_SECONDS = env_float("PAUSE_SECONDS", 0.2)
SECONDS_PER_CALL = env_float("SECONDS_PER_CALL", 1.6)


def choose_clauses(choice, available):
    """'core' = five clauses, 'all' = every clause, or a comma-separated list of names."""
    if choice == "core":
        names = CORE
    elif choice == "all":
        names = list(available)
    else:
        names = [name.strip() for name in choice.split(",")]
    unknown = [name for name in names if name not in available]
    if unknown:
        raise SystemExit(f"unknown clause: {unknown}")
    return names


def clause_table(rows, clauses):
    lines = [
        "| clause | n | positives | prevalence | tp | fn | fp | tn | recall | precision | invented | errors |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    stats = []
    for clause in clauses:
        part = [r for r in rows if r["clause"] == clause]
        if part:
            stats.append((sum(1 for r in part if r["gold_found"]), clause, len(part), summarize(part)))
    for positives, clause, n, s in sorted(stats, key=lambda item:-item[0]):
        few = " (few)" if positives < 5 else ""
        lines.append(
            f"| {clause}{few} | {n} | {positives} | {round(positives / n, 2)} | {s['tp']} | {s['fn']} | "
            f"{s['fp']} | {s['tn']} | {s['recall']} | {s['precision']} | {s['invented_quotes']} | {s['errors']} |"
        )
    return "\n".join(lines)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    choice = sys.argv[2] if len(sys.argv) > 2 else "core"
    dry = len(sys.argv) > 3 and sys.argv[3] == "dry"

    contracts = load_contracts()
    questions = clause_questions(contracts)
    clauses = choose_clauses(choice, questions)

    eval_path = Path("evals/eval_set.json")
    if not eval_path.exists():
        raise SystemExit("run scripts\\build_eval_set.py first")
    titles = json.loads(eval_path.read_text(encoding="utf-8"))["titles"][:limit]

    locked = set(load_splits()["test"])
    test2 = Path("evals/test_set_multi.json")
    if test2.exists():
        locked |= set(json.loads(test2.read_text(encoding="utf-8"))["titles"])
    if set(titles) & locked:
        raise SystemExit("the eval set contains locked test contracts. Stopping.")

    total = len(titles) * len(clauses)
    if dry:
        chars = sum(len(get_text(get_contract(contracts, t))) for t in titles)
        tokens = chars // 4 * len(clauses)
        print("contracts:", len(titles), "| clauses:", len(clauses), "| calls:", total)
        print("rough input tokens:", tokens)
        print(f"rough time: {total * (SECONDS_PER_CALL + PAUSE_SECONDS) / 3600:.1f} hours")
        if os.environ.get("PRICE_IN"):
            print(f"rough input cost: ${tokens / 1e6 * float(os.environ['PRICE_IN']):.2f}")
        return

    template = load_prompt(TEMPLATE_PATH)
    call = cached(call_model, enabled=not env_flag("NO_CACHE"))
    model = os.environ.get("LLM_MODEL", "unknown")
    info = run_info(template)
    label = choice if choice in ("core", "all") else "custom"
    resume = os.environ.get("RESUME")
    if resume:
        run_id = find_run(resume).name
        rows = [r for r in load_report(resume)["rows"] if not r["error"]]
    else:
        run_id = new_run_id(f"clauses_{Path(TEMPLATE_PATH).stem}_{model}_{label}_{limit}")
        rows = []
    done = {(r["title"], r["clause"]) for r in rows}

    meta = {
        "model": model, "template": TEMPLATE_PATH, "clauses": clauses, "contracts": len(titles),
        "date": date.today().isoformat(), "eval_set": str(eval_path), "run_info": info,
    }

    def save():
        return write_report(run_id, meta, summarize(rows), rows)

    stopped = False
    try:
        for title in titles:
            contract = get_contract(contracts, title)
            text = get_text(contract)
            for clause in clauses:
                if (title, clause) in done:
                    continue
                gold = get_gold_quotes(contract, clause)
                row = extract_governing_law(text, make_clause_prompt(template, clause, questions[clause]), call=call)
                row["title"], row["clause"] = title, clause
                row["gold_found"] = len(gold) > 0
                row["quote_match"] = quotes_overlap(row["quotes"], gold)
                rows.append(row)
                print(f"{len(rows)}/{total} {clause[:26]:<26} found={row['found']} gold={row['gold_found']} "
                      f"real={row['quotes_real']} sec={row['seconds']:.1f} err={row['error']}")
                if len(rows) % 10 == 0:
                    save()
                if len(rows) >= 3 and all(r["error"] for r in rows[-3:]):
                    print("3 failures in a row: stopping. The model is down or too slow.")
                    stopped = True
                    break
                time.sleep(PAUSE_SECONDS)
            if stopped:
                break
    finally:
        path = save()

    table = clause_table(rows, clauses)
    (Path(RUNS_DIR) / run_id / "clauses.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    print("run saved:", path)
    if not stopped:
        log_run(run_id, summarize(rows), info)


if __name__ == "__main__":
    main()
