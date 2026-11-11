"""Stage 1: ask the model about every clause of every contract in the chosen set (SET, K, LIMIT, OFFSET).

Excerpts come from hybrid retrieval, every quote is checked against the contract, and a reply that cannot be
used is retried once. Returns the run folder. SET=test needs CONFIRM_TEST=yes and should be run once.
"""
import json
import os
import time
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cuad_ai.cache import cached
from cuad_ai.clauses import clause_questions, make_clause_prompt
from cuad_ai.context import excerpts
from cuad_ai.extract import extract_clause, load_prompt
from cuad_ai.llm import call_model
from cuad_ai.loader import get_contract, get_gold_quotes, get_text, load_contracts
from cuad_ai.metrics import quotes_overlap, summarize
from cuad_ai.runlog import log_run, new_run_id, run_info, write_report
from cuad_ai.search import search_hybrid
from cuad_ai.settings import HEADER_CHUNKS, HEADER_CLAUSES, database_url, env_flag, env_float, env_int, env_text
from cuad_ai.terms import learn_terms

TEMPLATE_PATH = env_text("TEMPLATE_PATH", "prompts/clause_rag.txt")
K = env_int("K", 5)
LIMIT = env_int("LIMIT", 10)
SET = env_text("SET", "dev")
OFFSET = env_int("OFFSET", 0)
PAUSE_SECONDS = env_float("PAUSE_SECONDS", 0.2)

RETRY_NOTE = ("\n\nIMPORTANT: your last reply could not be used. Copy each quote exactly, character for "
              "character, from one single excerpt. Do not paraphrase, shorten, or join text across the [...] marker. "
              "Reply with one JSON object and nothing else.")


def needs_retry(row):
    """True when the reply could not be used: a call or parse error, or a quote not found word for word."""
    return bool(row["error"]) or (bool(row["found"]) and row["quotes_real"] is False)


def official_test_titles():
    data = json.loads(Path("data/test.json").read_text(encoding="utf-8"))["data"]
    return {contract["title"] for contract in data}


def main(argv=None):
    """Settings come from the environment, so extra arguments are ignored."""
    load_dotenv()
    contracts = load_contracts()
    questions = clause_questions(contracts)
    clauses = list(questions)

    if SET == "validation":
        with psycopg.connect(database_url()) as conn:
            eval_titles = [t for (t,) in conn.execute(
                "select title from contracts where official_split = 'train' "
                "and not shares_company_with_test and id %% 5 = 0 order by id limit %s offset %s", (LIMIT, OFFSET))]
    elif SET == "test":
        if os.environ.get("CONFIRM_TEST") != "yes":
            raise SystemExit("SET=test scores the official test contracts. Run it once, when the design is frozen. "
                             "Set CONFIRM_TEST=yes to go ahead.")
        eval_titles = sorted(official_test_titles())[OFFSET:OFFSET + LIMIT]
    else:
        eval_titles = json.loads(Path("evals/eval_set.json").read_text(encoding="utf-8"))["titles"][:LIMIT]
    test_titles = official_test_titles()
    titles = [t for t in eval_titles if SET == "test" or t not in test_titles]
    print(f"contracts: {len(titles)} (left out {len(eval_titles) - len(titles)} official test) "
          f"| clauses: {len(clauses)} | k={K}")

    template = load_prompt(TEMPLATE_PATH)
    call = cached(call_model, enabled=not env_flag("NO_CACHE"))
    info = run_info(template)
    model = os.environ.get("LLM_MODEL", "unknown")
    run_id = new_run_id(f"rag_{Path(TEMPLATE_PATH).stem}_{model}_k{K}_{len(titles)}")
    meta = {"model": model, "template": TEMPLATE_PATH, "k": K, "contracts": len(titles),
            "date": date.today().isoformat(), "run_info": info}
    rows, total = [], len(titles) * len(clauses)

    with psycopg.connect(database_url()) as conn:
        ids = {t: conn.execute("select id from contracts where title = %s", (t,)).fetchone()[0] for t in titles}
        clause_ids = dict(conn.execute("select name, id from clauses").fetchall())
        holdout = "c.id IN (" + ",".join(str(i) for i in ids.values()) + ")"
        terms = learn_terms(conn, holdout=holdout)  # words learned without these contracts

        try:
            for title in titles:
                contract = get_contract(contracts, title)
                text = get_text(contract)
                for clause in clauses:
                    stems = [t for t, _ in terms.get(clause, [])]
                    found = search_hybrid(conn, ids[title], clause_ids[clause], stems, K)
                    spans = [(s, e) for s, e, _ in found]
                    if clause in HEADER_CLAUSES:
                        spans += conn.execute(
                            "select start_char, end_char from chunks where contract_id = %s "
                            "order by start_char limit %s", (ids[title], HEADER_CHUNKS)).fetchall()
                    context = excerpts(text, spans)

                    gold = get_gold_quotes(contract, clause)
                    prompt = make_clause_prompt(template, clause, questions[clause])
                    row = extract_clause(context, prompt, call=call)
                    row["retried"], row["unsolved"] = False, False
                    if needs_retry(row):
                        again = extract_clause(context, prompt + RETRY_NOTE, call=call)
                        spent_in = row["tokens_in"] + again["tokens_in"]
                        spent_out = row["tokens_out"] + again["tokens_out"]
                        solved = not needs_retry(again)
                        if solved:
                            row = again
                        row["retried"], row["unsolved"] = True, not solved
                        row["tokens_in"], row["tokens_out"] = spent_in, spent_out
                    row["title"], row["clause"] = title, clause
                    row["gold_found"] = len(gold) > 0
                    row["quote_match"] = quotes_overlap(row["quotes"], gold)
                    row["excerpt_chars"] = len(context)
                    rows.append(row)
                    print(f"{len(rows)}/{total} {clause[:26]:<26} found={row['found']} gold={row['gold_found']} "
                          f"real={row['quotes_real']} in={row['tokens_in']} err={row['error']}")
                    if len(rows) % 10 == 0:
                        write_report(run_id, meta, summarize(rows), rows)
                    if len(rows) >= 3 and all(r["error"] for r in rows[-3:]):
                        raise SystemExit("3 failures in a row: stopping. The model is down or too slow.")
                    time.sleep(PAUSE_SECONDS)
        finally:
            path = write_report(run_id, meta, summarize(rows), rows)

    print(summarize(rows))
    print("run saved:", path)
    log_run(run_id, summarize(rows), info)
    return path.parent


if __name__ == "__main__":
    main()
