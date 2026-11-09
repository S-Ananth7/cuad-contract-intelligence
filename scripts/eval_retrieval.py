import os
from collections import defaultdict

import psycopg
from dotenv import load_dotenv

from cuad_ai.embed import embed_texts, load_model, vector_literal
from cuad_ai.settings import HEADER_CHUNKS, HEADER_CLAUSES, database_url

KS = (3, 5, 10)
MIN_COVER = 0.5


def covered(highlight, chunks):
    """Share of the highlight's characters that lie inside the chunks."""
    start, end = highlight
    total = 0
    last = start
    for chunk_start, chunk_end in sorted(chunks):
        s = max(chunk_start, last)
        e = min(chunk_end, end)
        if e > s:
            total += e - s
            last = e
    return total / (end - start)


def main():
    load_dotenv()
    model = load_model()
    with psycopg.connect(database_url()) as conn:
        clauses = conn.execute("select id, name, question from clauses order by id").fetchall()
        by_clause = defaultdict(lambda: defaultdict(list))
        for contract_id, clause_id, start, end in conn.execute(
            "select contract_id, clause_id, start_char, end_char from highlights"
        ):
            by_clause[clause_id][contract_id].append((start, end))

        print(f"{'clause':38} {'n':>5} " + " ".join(f"r@{k:<3}" for k in KS))
        all_hits = {k: 0 for k in KS}
        all_total = 0
        for clause_id, name, question in clauses:
            text = name if os.environ.get("QUERY_MODE") == "name" else question
            query = vector_literal(embed_texts(model, [text])[0])
            hits = {k: 0 for k in KS}
            cases = by_clause[clause_id]
            for contract_id, spans in cases.items():
                chunks = conn.execute(
                    "select start_char, end_char from chunks "
                    "where contract_id = %s and embedding is not null "
                    "order by embedding <=> %s::vector limit %s",
                    (contract_id, query, max(KS)),
                ).fetchall()
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
