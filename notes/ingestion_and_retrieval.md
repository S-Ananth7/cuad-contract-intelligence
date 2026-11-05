# Ingestion and Retrieval: What We Built

Last updated: 2026-11-05

This note records the work after the repo cleanup: moving CUAD into Postgres, chunking, embedding, and the first retrieval measurement.

## 1. Why
Sending the whole contract to the model once per clause costs too much and does not scale. The plan is to store contracts in Postgres, retrieve only the relevant chunks per clause, and verify every quote against the contract. See `notes/rag_and_agent.md` for the reasoning and tradeoff.

## 2. Repo cleanup (done)
- Merged v1/v2 files into single current files: `baseline.py`, `run_baseline.py`, `test_baseline.py`, `prompts/governing_law.txt`, `prompts/clause.txt`.
- Removed unused one-off scripts and the old notes draft.
- Rewrote `README.md` and `notes/decisions.md`.
- Convention: no version suffixes in file names. Git is the history.

## 3. Database
- Postgres 17 with pgvector 0.8.7 in Docker, container `cuad-db`, host port 5433, data in volume `cuad-db-data`.
- Connection string in `.env` as `DATABASE_URL` (never committed).
- Docker Desktop must be running. Start the container with `docker start cuad-db`.
- Schema lives in `sql/schema.sql` and is safe to re-run (`IF NOT EXISTS`).

### Tables
| Table | Rows | Content |
|---|---|---|
| contracts | 510 | title, company, n_chars (unique title) |
| clauses | 41 | name, CUAD question (unique name) |
| highlights | 13,823 | lawyer-marked passages: contract, clause, start, end, text |
| chunks | 33,809 | contract pieces: contract, start, end, text, embedding vector(384), embedding_model |

## 4. Code
| File | Role |
|---|---|
| `src/cuad_ai/ingest.py` | Row builders and inserts: `contract_row`, `insert_contracts`, `clause_rows`, `insert_clauses`, `highlight_rows`, `insert_highlights`, `chunk_spans`, `chunk_rows`, `insert_chunks` |
| `src/cuad_ai/embed.py` | Local embedding model, batch embedding that resumes after a stop |
| `src/cuad_ai/search.py` | Vector search over chunks (cosine distance) |
| `scripts/load_contracts.py`, `load_clauses.py`, `load_highlights.py`, `load_chunks.py` | One-time loaders |
| `scripts/embed_chunks.py` | Fills the `embedding` column |
| `scripts/search_chunks.py` | Command-line search demo |
| `scripts/eval_retrieval.py` | Retrieval recall per clause against the highlights |
| `tests/test_ingest.py`, `tests/test_embed.py` | Unit tests; database tests roll back |

Pattern for every table: table, row builder (pure, tested with fake data), insert function (tested with a rolled-back transaction), loader script, count check.

## 5. Chunking
- About 1,000 characters per chunk, 200 characters of overlap, cut at a space or line break when possible.
- 33,809 chunks across all 510 contracts. Lengths 207 to 1,000.
- A chunk can end mid-sentence. The next chunk repeats the last 200 characters.

## 6. Embeddings
- Model: `BAAI/bge-small-en-v1.5` through `fastembed` (quantized ONNX build, 384 numbers per vector). Runs locally, so contract text stays on the machine.
- All 33,809 chunks embedded. The model name is stored in `embedding_model`.
- Search is bi-encoder retrieval only. No reranker yet.

## 7. First retrieval measurement
Method: for each clause and each contract where lawyers marked it, search inside that contract using the clause's CUAD question, take the top k chunks, and count a hit if they cover at least 50% of a marked passage. 6,702 cases.

Overall recall: **0.43 at k=3, 0.51 at k=5, 0.64 at k=10.** Below the 0.90 target.

| Group | Clauses (recall at k=10) |
|---|---|
| Safe (0.90 or more) | Termination For Convenience 0.95, Uncapped Liability 0.96, Anti-Assignment 0.94, Cap On Liability 0.93, Insurance 0.93, Renewal Term 0.92, Notice Period To Terminate Renewal 0.92, Source Code Escrow 0.92 |
| Middle (0.70 to 0.89) | Governing Law 0.87, Audit Rights 0.86, No-Solicit Of Employees 0.85, Warranty Duration 0.85, Expiration Date 0.84, Third Party Beneficiary 0.84, Change Of Control 0.83, Joint IP Ownership 0.80, Post-Termination Services 0.74, Affiliate License-Licensee 0.71 |
| Weak (below 0.70) | Document Name 0.25, Parties 0.22, Agreement Date 0.33, Volume Restriction 0.27, Effective Date 0.50, Exclusivity 0.47, Rofr/Rofo/Rofn 0.49, License Grant 0.57, and others |

Full table (n = cases, then recall at k=3 / 5 / 10):

| Clause | n | r@3 | r@5 | r@10 |
|---|---|---|---|---|
| Document Name | 510 | 0.11 | 0.15 | 0.25 |
| Parties | 509 | 0.10 | 0.14 | 0.22 |
| Agreement Date | 470 | 0.13 | 0.19 | 0.33 |
| Effective Date | 390 | 0.28 | 0.35 | 0.50 |
| Expiration Date | 413 | 0.61 | 0.72 | 0.84 |
| Renewal Term | 176 | 0.78 | 0.85 | 0.92 |
| Notice Period To Terminate Renewal | 111 | 0.77 | 0.83 | 0.92 |
| Governing Law | 437 | 0.65 | 0.77 | 0.87 |
| Most Favored Nation | 28 | 0.32 | 0.50 | 0.57 |
| Non-Compete | 119 | 0.35 | 0.45 | 0.60 |
| Exclusivity | 180 | 0.21 | 0.31 | 0.47 |
| No-Solicit Of Customers | 34 | 0.29 | 0.47 | 0.62 |
| Competitive Restriction Exception | 76 | 0.25 | 0.30 | 0.45 |
| No-Solicit Of Employees | 59 | 0.75 | 0.81 | 0.85 |
| Non-Disparagement | 38 | 0.21 | 0.37 | 0.50 |
| Termination For Convenience | 183 | 0.79 | 0.83 | 0.95 |
| Rofr/Rofo/Rofn | 85 | 0.22 | 0.31 | 0.49 |
| Change Of Control | 121 | 0.64 | 0.71 | 0.83 |
| Anti-Assignment | 374 | 0.75 | 0.84 | 0.94 |
| Revenue/Profit Sharing | 166 | 0.34 | 0.43 | 0.59 |
| Price Restrictions | 15 | 0.47 | 0.47 | 0.67 |
| Minimum Commitment | 165 | 0.34 | 0.43 | 0.57 |
| Volume Restriction | 82 | 0.10 | 0.12 | 0.27 |
| Ip Ownership Assignment | 124 | 0.40 | 0.52 | 0.67 |
| Joint Ip Ownership | 46 | 0.50 | 0.65 | 0.80 |
| License Grant | 255 | 0.27 | 0.38 | 0.57 |
| Non-Transferable License | 138 | 0.28 | 0.40 | 0.63 |
| Affiliate License-Licensor | 23 | 0.22 | 0.39 | 0.48 |
| Affiliate License-Licensee | 59 | 0.41 | 0.56 | 0.71 |
| Unlimited/All-You-Can-Eat-License | 17 | 0.06 | 0.29 | 0.53 |
| Irrevocable Or Perpetual License | 70 | 0.44 | 0.50 | 0.70 |
| Source Code Escrow | 13 | 0.77 | 0.85 | 0.92 |
| Post-Termination Services | 182 | 0.37 | 0.51 | 0.74 |
| Audit Rights | 214 | 0.70 | 0.77 | 0.86 |
| Uncapped Liability | 111 | 0.77 | 0.87 | 0.96 |
| Cap On Liability | 275 | 0.73 | 0.82 | 0.93 |
| Liquidated Damages | 61 | 0.51 | 0.61 | 0.70 |
| Warranty Duration | 75 | 0.67 | 0.76 | 0.85 |
| Insurance | 166 | 0.81 | 0.84 | 0.93 |
| Covenant Not To Sue | 100 | 0.25 | 0.35 | 0.55 |
| Third Party Beneficiary | 32 | 0.56 | 0.72 | 0.84 |
| ALL | 6,702 | 0.43 | 0.51 | 0.64 |

## 8. Findings
- Vector retrieval alone does not meet the recall target. Only 8 of 41 clauses reach 0.90 at k=10.
- Document Name, Parties, Agreement Date and Effective Date are the worst, and make up 28% of all cases (1,879 of 6,702). These facts sit at the start of a contract, so a position rule is likely better than semantic search. Hypothesis not yet checked: the share of their highlights that start in the first 3,000 characters.
- The query is the long generic CUAD question, which says little about the specific clause.
- The numbers are a baseline before any tuning.

## 9. Next steps (in order of cost)
1. Position rule for the four header clauses (send the first chunks).
2. Shorter, clause-specific queries.
3. Hybrid search: full-text plus vector in one SQL query.
4. Reranker on the top 20 candidates.
5. Per-clause router: retrieval for clauses measured safe, whole-contract call for the rest.
6. Then the bounded agent for failures, and the cost and accuracy comparison against the 410-call baseline.

Tune on dev contracts only. Keep the locked test set for one final run.

## 10. Open items
- Confirm tests exist for `chunk_spans`, `chunk_rows` and `insert_chunks`.
- Add a unique rule on highlights (contract, clause, start, end) so a loader cannot double-load.
- Commit the embedding, search and evaluation files (not yet committed at the time of writing).
- Fix the overlap between dev and `evals/test_set_multi.json` before using it.
- Revoke any API key that was ever pasted in chat.

## 11. Reproduce from scratch
```
docker start cuad-db
Get-Content sql\schema.sql | docker exec -i cuad-db psql -U cuad -d cuad
python scripts\load_contracts.py
python scripts\load_clauses.py
python scripts\load_highlights.py
python scripts\load_chunks.py
python scripts\embed_chunks.py
python scripts\eval_retrieval.py
```
Run each loader once. Contracts, clauses and chunks reject duplicates. Highlights does not yet, so a second load doubles it. Empty a table first with `TRUNCATE <table> RESTART IDENTITY;`.
