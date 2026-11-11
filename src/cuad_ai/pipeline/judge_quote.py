"""Stage 2: ask the model about each REVIEW answer (quote + clause question only), then score.

Reads routing.json (from `cuad_ai route`) and report.json in the same run folder.
Model replies are cached, so a stopped run resumes where it stopped at no cost.
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from cuad_ai.cache import cached
from cuad_ai.clauses import clause_questions, make_clause_prompt
from cuad_ai.extract import extract_json, load_prompt
from cuad_ai.llm import call_model
from cuad_ai.loader import load_contracts
from cuad_ai.settings import env_flag

TEMPLATE = "prompts/verify_quote.txt"


def ask(prompt_text, clause, question, quote, call):
    """One yes/no judgement. Returns (is_this_clause, looks_like, tokens_in); None if unreadable."""
    prompt = make_clause_prompt(prompt_text, clause, question).replace("[QUOTE]", quote)
    try:
        result = call(prompt)
        data = json.loads(extract_json(result["text"]))
        return bool(data["is_this_clause"]), str(data.get("looks_like", "none")), result["tokens_in"]
    except Exception:
        return None, "none", 0


def score(label, kept, gold_total):
    real = sum(r["gold_found"] for r in kept)
    false = len(kept) - real
    precision = real / max(len(kept), 1)
    print(f"{label:34}{real:>5}{false:>6}{gold_total - real:>6}{precision:>11.3f}{real / gold_total:>9.3f}")


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    load_dotenv()
    folder = Path(args[0])
    rows = json.loads((folder / "routing.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))["rows"]
    quotes = {(r["title"], r["clause"]): " ... ".join(r["quotes"]) for r in report}
    gold_total = sum(1 for r in report if r["gold_found"])
    questions = clause_questions(load_contracts())
    prompt_text = load_prompt(TEMPLATE)
    call = cached(call_model, enabled=not env_flag("NO_CACHE"))

    review = [r for r in rows if r["route"] == "review"]
    tokens = unreadable = 0
    for i, r in enumerate(review, 1):
        quote = quotes[(r["title"], r["clause"])]
        r["verdict"], r["looks_like"], used = ask(prompt_text, r["clause"], questions[r["clause"]], quote, call)
        tokens += used
        unreadable += r["verdict"] is None
        if i % 50 == 0:
            print(f"{i}/{len(review)} done")
    (folder / "verified.json").write_text(json.dumps(rows), encoding="utf-8")

    accepted = [r for r in rows if r["route"] == "accept"]
    yes = [r for r in review if r["verdict"] is not False]  # an unreadable reply keeps the answer
    rejected = [r for r in review if r["verdict"] is False]
    print(f"\nreview calls: {len(review)} | unreadable: {unreadable} | tokens in: {tokens}")
    print(f"review rejected {len(rejected)}: real {sum(r['gold_found'] for r in rejected)}, false {sum(not r['gold_found'] for r in rejected)}")
    print(f"\n{'version':34}{'tp':>5}{'fp':>6}{'fn':>6}{'precision':>11}{'recall':>9}")
    score("today (all answers)", rows, gold_total)
    score("accept only", accepted, gold_total)
    score("accept + review confirmed", accepted + yes, gold_total)
    print("saved:", folder / "verified.json")


if __name__ == "__main__":
    main()
