import os
from collections import defaultdict

import psycopg
from dotenv import load_dotenv

from cuad_ai.search import search_by_examples, search_hybrid
from cuad_ai.terms import learn_terms

KS = (3, 5, 10)
MIN_COVER = 0.5
HEADER_CLAUSES = {"Document Name", "Parties", "Agreement Date", "Effective Date"}
HEADER_CHUNKS = 4

SPLIT = os.environ.get("SPLIT", "test")
MODE = os.environ.get("MODE", "examples")
CONTRACTS = {
    "test": "c.official_split = 'test'",
    "validation": "c.official_split = 'train' AND NOT c.shares_company_with_test AND c.id % 5 = 0",
}[SPLIT]


def covered(highlight, chunks):
    start, end = highlight
    total, last = 0, start
    for chunk_start, chunk_end in sorted(chunks):
        s, e = max(chunk_start, last), min(chunk_end, end)
        if e > s:
            total += e - s
            last = e
    return total / (end - start)


def main():
    load_dotenv()
    print("scoring on:", SPLIT, "| mode:", MODE)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        terms = {}
        if MODE == "hybrid":
            holdout = CONTRACTS if SPLIT == "validation" else None
            terms = learn_terms(conn, holdout=holdout)

        clauses = conn.execute("select id, name from clauses order by id").fetchall()
        by_clause = defaultdict(lambda: defaultdict(list))
        for contract_id, clause_id, start, end in conn.execute(
            "select h.contract_id, h.clause_id, h.start_char, h.end_char "
            "from highlights h join contracts c on c.id = h.contract_id "
            "where " + CONTRACTS
        ):
            by_clause[clause_id][contract_id].append((start, end))

        print(f"{'clause':38} {'n':>5} " + " ".join(f"r@{k:<3}" for k in KS))
        all_hits = {k: 0 for k in KS}
        all_total = 0
        for clause_id, name in clauses:
            cases = by_clause[clause_id]
            hits = {k: 0 for k in KS}
            for contract_id, spans in cases.items():
                if MODE == "hybrid":
                    stems = [t for t, _ in terms.get(name, [])]
                    found = search_hybrid(conn, contract_id, clause_id, stems, max(KS))
                else:
                    found = search_by_examples(conn, contract_id, clause_id, max(KS))
                chunks = [(s, e) for s, e, _ in found]
                header = []
                if name in HEADER_CLAUSES:
                    header = conn.execute(
                        "select start_char, end_char from chunks "
                        "where contract_id = %s order by start_char limit %s",
                        (contract_id, HEADER_CHUNKS),
                    ).fetchall()
                for k in KS:
                    if any(covered(h, header + chunks[:k]) >= MIN_COVER for h in spans):
                        hits[k] += 1
            n = len(cases)
            for k in KS:
                all_hits[k] += hits[k]
            all_total += n
            if n:
                print(f"{name[:38]:38} {n:>5} " + " ".join(f"{hits[k] / n:5.2f}" for k in KS))
        print(f"{'ALL':38} {all_total:>5} " + " ".join(f"{all_hits[k] / all_total:5.2f}" for k in KS))


if __name__ == "__main__":
    main()
