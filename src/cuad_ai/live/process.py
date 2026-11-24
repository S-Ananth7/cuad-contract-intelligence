"""Run the pipeline on one uploaded contract.

Same stages, same code as the saved test run: retrieve -> extract (with the verified-quote retry) -> gate ->
two judges -> finalize.decide. Only the source of the contract changes (an upload, not the CUAD file).
Questions run in parallel; each worker thread uses its own database connection. The model and the embedding model
are passed in, so tests run the whole thing with fakes and no key.
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from cuad_ai.clauses import make_clause_prompt
from cuad_ai.context import excerpts
from cuad_ai.embed import embed_texts, vector_literal
from cuad_ai.extract import load_prompt
from cuad_ai.ingest import chunk_spans
from cuad_ai.live import config, store
from cuad_ai.live.locate import Locator
from cuad_ai.live.retrieve import retrieve_spans
from cuad_ai.pipeline import judge_examples, judge_quote
from cuad_ai.pipeline.extraction import extract_with_retry
from cuad_ai.pipeline.finalize import decide
from cuad_ai.pipeline.gate import SQL as GATE_SQL
from cuad_ai.pipeline.route import decide as route_decide
from cuad_ai.pipeline.route import frozen_risk
from cuad_ai.terms import learn_terms

EXTRACT_PROMPT = "prompts/clause_rag.txt"
JUDGE1_PROMPT = "prompts/verify_quote.txt"
JUDGE2_PROMPT = "prompts/verify_quote_examples.txt"
RISK_TABLE = "evals/risk_table.json"
EMBED_BATCH = 64
EARLY_STOP_ERRORS = 5  # this many failures before any success means the model is unreachable: stop spending time


class LockedEmbedder:
    """Wraps an embedding model so several threads can share it safely."""

    def __init__(self, model):
        self.model, self.lock = model, threading.Lock()

    def embed(self, texts):
        with self.lock:
            return list(self.model.embed(texts))


@dataclass
class Bank:
    """What every upload shares. Built once per worker process; read-only afterwards."""
    clause_ids: dict
    questions: dict
    terms: dict
    risk: object
    extract_prompt: str
    judge1_prompt: str
    judge2_prompt: str


def load_bank(conn, excluded_company=""):
    """Read the clause list, learn the keyword stems from the example bank, and load the frozen risk table.

    When an upload is a CUAD contract, its own examples are left out of the learned stems, as for the test set.
    """
    rows = conn.execute("SELECT id, name, question FROM clauses ORDER BY name").fetchall()
    holdout = None
    if excluded_company:
        ids = [i for (i,) in conn.execute("SELECT id FROM contracts WHERE company = %s", (excluded_company,))]
        holdout = "c.id IN (" + ",".join(str(i) for i in ids) + ")" if ids else None
    return Bank(
        clause_ids={name: i for i, name, _ in rows},
        questions={name: question for _, name, question in rows},
        terms=learn_terms(conn, holdout=holdout),
        risk=frozen_risk(RISK_TABLE),
        extract_prompt=load_prompt(EXTRACT_PROMPT),
        judge1_prompt=load_prompt(JUDGE1_PROMPT),
        judge2_prompt=load_prompt(JUDGE2_PROMPT),
    )


def rank_clauses(conn, embedder, quotes, company):
    """Clause name -> how close the quotes are to its lawyer examples, best first (the gate's measure)."""
    best = {}
    for quote in quotes:
        vector = vector_literal(embed_texts(embedder, [quote])[0])
        for name, sim in conn.execute(GATE_SQL, (vector, company)):
            best[name] = max(best.get(name, 0.0), sim)
    return best


def answer_clause(conn, sub, clause, bank, text, locator, call, embedder):
    """Everything for one question. Returns the dict that store.save_answer writes. Does not write."""
    company = sub["excluded_company"] or ""
    stems = [t for t, _ in bank.terms.get(clause, [])]
    spans = retrieve_spans(conn, sub["id"], clause, bank.clause_ids[clause], stems, company)
    prompt = make_clause_prompt(bank.extract_prompt, clause, bank.questions[clause])
    row = extract_with_retry(excerpts(text, spans), prompt, call)

    out = {"clause": clause, "quotes": row["quotes"], "spans": [], "risk": None, "rank_asked": None,
           "verdict": None, "verdict2": None, "looks_like": [], "retried": row["retried"],
           "tokens_in": row["tokens_in"], "tokens_out": row["tokens_out"], "error": row["error"]}

    answer = None
    if row["found"] and row["quotes"]:
        best = rank_clauses(conn, embedder, row["quotes"], company)
        ranked = sorted(best, key=best.get, reverse=True)
        rank = ranked.index(clause) + 1 if clause in best else None
        risk = round(bank.risk(clause), 3)
        answer = {"route": route_decide({"rank_asked": rank, "risk": risk, "clause": clause})}
        out["risk"], out["rank_asked"] = risk, rank
        if answer["route"] == "review":
            quote = " ... ".join(row["quotes"])
            question = bank.questions[clause]
            answer["verdict"], looks1, used1 = judge_quote.ask(bank.judge1_prompt, clause, question, quote, call)
            examples = judge_examples.get_examples(conn, embedder, clause, company, quote)
            answer["verdict2"], looks2, used2 = judge_examples.ask(
                bank.judge2_prompt, clause, question, quote, examples, call)
            out.update(verdict=answer["verdict"], verdict2=answer["verdict2"],
                       looks_like=[name for name in (looks1, looks2) if name and name != "none"])
            out["tokens_in"] += used1 + used2

    out["decision"], out["reason"] = decide(row, answer)
    if row["quotes_real"]:
        found = (locator.find(q) for q in row["quotes"])
        out["spans"] = [list(span) for span in found if span]
    return out


def process(connect, sub, call, embedder, bank, workers=None):
    """Run one claimed submission to the end. Marks it done, or failed with a reason. Never raises for a bad model."""
    sid, text = sub["id"], sub["text"]
    workers = workers or config.workers()
    embedder = embedder if isinstance(embedder, LockedEmbedder) else LockedEmbedder(embedder)
    clauses = sorted(bank.clause_ids)
    locator = Locator(text)

    with connect() as conn:
        store.clear_results(conn, sid)
        spans = chunk_spans(text)
        for i in range(0, len(spans), EMBED_BATCH):
            batch = spans[i:i + EMBED_BATCH]
            vectors = embed_texts(embedder, [text[s:e] for s, e in batch])
            store.save_chunks(conn, sid, [(s, e, text[s:e], v) for (s, e), v in zip(batch, vectors)])
        store.heartbeat(conn, sid, 0, len(clauses), 0, 0)

    def work(clause):
        with connect() as conn:
            return answer_clause(conn, sub, clause, bank, text, locator, call, embedder)

    done = errors = good = tokens_in = tokens_out = 0
    stop = None
    with connect() as conn, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, clause) for clause in clauses]
        try:
            for future in as_completed(futures):
                result = future.result()
                store.save_answer(conn, sid, result)
                done += 1
                tokens_in += result["tokens_in"]
                tokens_out += result["tokens_out"]
                errors += bool(result["error"])
                good += not result["error"]
                store.heartbeat(conn, sid, done, len(clauses), tokens_in, tokens_out)
                if good == 0 and errors >= EARLY_STOP_ERRORS:
                    stop = "The model could not be reached. Check the model settings and try again."
                elif tokens_in + tokens_out > config.token_cap():
                    stop = "The token limit for one upload was reached."
                if stop:
                    break
        finally:
            for future in futures:
                future.cancel()

    with connect() as conn:
        if stop:
            store.fail(conn, sid, stop)
        else:
            store.finish(conn, sid)
    return stop is None
