import json
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cuad_ai.embed import embed_texts, load_model, vector_literal
from cuad_ai.settings import database_url

SQL = """
SELECT cl.name, MAX(1 - (h.embedding <=> %s::vector)) AS sim
FROM highlights h
JOIN clauses cl ON cl.id = h.clause_id
JOIN contracts hc ON hc.id = h.contract_id
WHERE h.embedding IS NOT NULL AND hc.company <> %s
GROUP BY cl.name
"""


def main():
    load_dotenv()
    report = Path(sys.argv[1])
    rows = json.loads(report.read_text(encoding="utf-8"))["rows"]
    model = load_model()
    out = []
    with psycopg.connect(database_url()) as conn:
        for r in rows:
            if not r["found"] or not r["quotes"]:
                continue
            company = r["title"].split("_")[0]
            best = {}
            for quote in r["quotes"]:
                vector = vector_literal(embed_texts(model, [quote])[0])
                for name, sim in conn.execute(SQL, (vector, company)):
                    best[name] = max(best.get(name, 0.0), sim)
            ranked = sorted(best, key=best.get, reverse=True)
            out.append({
                "title": r["title"],
                "clause": r["clause"],
                "gold_found": r["gold_found"],
                "sim_asked": best.get(r["clause"], 0.0),
                "sim_best_other": max((s for n, s in best.items() if n != r["clause"]), default=0.0),
                "rank_asked": ranked.index(r["clause"]) + 1 if r["clause"] in best else None,
                "best_clause": ranked[0],
            })
    path = report.with_name("gate_features.json")
    path.write_text(json.dumps(out), encoding="utf-8")
    print("answers:", len(out), "| saved:", path)


if __name__ == "__main__":
    main()
