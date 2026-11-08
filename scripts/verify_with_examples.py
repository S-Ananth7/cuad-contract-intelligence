"""Stage 2b: like verify_answers.py, but the model also sees 3 lawyer-marked examples of the clause.

Reads verified.json (from verify_answers.py) and report.json in the same run folder.
Examples are the 3 bank highlights of the asked clause closest to the quote,
never from the same company as the contract. Replies are cached.
"""
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cuad_ai.cache import cached
from cuad_ai.clauses import clause_questions, make_clause_prompt
from cuad_ai.embed import embed_texts, load_model, vector_literal
from cuad_ai.extract import extract_json, load_prompt
from cuad_ai.llm import call_model
from cuad_ai.loader import load_contracts
from verify_answers import score

TEMPLATE = "prompts/verify_quote_examples.txt"
N_EXAMPLES = 3
EXAMPLE_CHARS = 400

EXAMPLES_SQL = """
SELECT h.text
FROM highlights h
JOIN clauses cl ON cl.id = h.clause_id
JOIN contracts hc ON hc.id = h.contract_id
WHERE cl.name = %s AND h.embedding IS NOT NULL AND hc.company <> %s
ORDER BY h.embedding <=> %s::vector
LIMIT %s
"""


def get_examples(conn, model, clause, company, quote):
    vector = vector_literal(embed_texts(model, [quote])[0])
    rows = conn.execute(EXAMPLES_SQL, (clause, company, vector, N_EXAMPLES)).fetchall()
    return "\n".join(f"- {text[:EXAMPLE_CHARS]}" for (text,) in rows)


def ask(prompt_text, clause, question, quote, examples, call):
    """One judgement. Returns (is_this_clause, looks_like, tokens_in); None if unreadable."""
    prompt = make_clause_prompt(prompt_text, clause, question)
    prompt = prompt.replace("[EXAMPLES]", examples).replace("[QUOTE]", quote)
    try:
        result = call(prompt)
        data = json.loads(extract_json(result["text"]))
        return bool(data["is_this_clause"]), str(data.get("looks_like", "none")), result["tokens_in"]
    except Exception:
        return None, "none", 0


def main():
    load_dotenv()
    folder = Path(sys.argv[1])
    rows = json.loads((folder / "verified.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))["rows"]
    quotes = {(r["title"], r["clause"]): " ... ".join(r["quotes"]) for r in report}
    gold_total = sum(1 for r in report if r["gold_found"])
    questions = clause_questions(load_contracts())
    prompt_text = load_prompt(TEMPLATE)
    call = cached(call_model, enabled=not os.environ.get("NO_CACHE"))
    model = load_model()

    review = [r for r in rows if r["route"] == "review"]
    tokens = unreadable = 0
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for i, r in enumerate(review, 1):
            quote = quotes[(r["title"], r["clause"])]
            examples = get_examples(conn, model, r["clause"], r["title"].split("_")[0], quote)
            r["verdict2"], r["looks_like2"], used = ask(
                prompt_text, r["clause"], questions[r["clause"]], quote, examples, call)
            tokens += used
            unreadable += r["verdict2"] is None
            if i % 50 == 0:
                print(f"{i}/{len(review)} done")
    (folder / "verified_examples.json").write_text(json.dumps(rows), encoding="utf-8")

    accepted = [r for r in rows if r["route"] == "accept"]
    old_yes = [r for r in review if r["verdict"] is not False]
    new_yes = [r for r in review if r["verdict2"] is not False]
    rejected = [r for r in review if r["verdict2"] is False]
    print(f"\nreview calls: {len(review)} | unreadable: {unreadable} | tokens in: {tokens}")
    print(f"new review rejected {len(rejected)}: real {sum(r['gold_found'] for r in rejected)}, "
          f"false {sum(not r['gold_found'] for r in rejected)}")
    print(f"\n{'version':34}{'tp':>5}{'fp':>6}{'fn':>6}{'precision':>11}{'recall':>9}")
    score("today (all answers)", rows, gold_total)
    score("accept only", accepted, gold_total)
    score("accept + old review (no examples)", accepted + old_yes, gold_total)
    score("accept + new review (examples)", accepted + new_yes, gold_total)
    print("saved:", folder / "verified_examples.json")


if __name__ == "__main__":
    main()
