# Ingestion and Retrieval

Last updated: 2026-11-05

How CUAD is stored in Postgres, how contracts are chunked and embedded, how the retrieval works, and how it is measured. The final numbers are in section 9.

## 1. Why
Sending the whole contract to the model once per clause costs too much and does not scale. Contracts are stored in Postgres, only the relevant chunks are retrieved per clause, and every quote is verified against the contract. The reasoning and tradeoff are in `notes/rag_and_agent.md`.

## 2. Conventions
- No version suffixes in file names. Git is the history.
- Pattern for every table: SQL table, pure row builder (tested with fake data), insert function (tested in a rolled-back transaction), loader script, count check.
- Tune on validation contracts only. The test set is run once per design.

## 3. Database
- Postgres 17 with pgvector 0.8.7 in Docker: container `cuad-db`, host port 5433, volume `cuad-db-data`.
- Connection string in `.env` as `DATABASE_URL` (never committed). Docker Desktop must be running; start the container with `docker start cuad-db`.
- Schema is in `sql/schema.sql` and is safe to re-run (`IF NOT EXISTS`). Applying it to the database is a separate step from editing the file.

| Table | Rows | Content |
|---|---|---|
| contracts | 510 | title, company, n_chars, `official_split` (train/test), `shares_company_with_test` |
| clauses | 41 | name, CUAD question |
| highlights | 13,823 | lawyer-marked passages: contract, clause, start, end, text; `embedding` for the example bank only |
| chunks | 33,809 | contract pieces: start, end, text, `embedding` vector(384), `embedding_model`, `tsv` full-text column with GIN index |

## 4. Data split and leak rules
- `official_split` comes from the CUAD authors: 408 train, 102 test (`data/test.json`).
- 10 companies appear in both train and test. The 16 train contracts of those companies are flagged `shares_company_with_test` and never enter the example bank.
- **Example bank:** the 10,848 highlights of train contracts that do not share a company with test. Only these rows have a highlight embedding. A missing embedding is what keeps a contract out of the bank.
- Example search never uses highlights from the same company as the contract being searched.
- **Validation:** every fifth bank-eligible train contract by id, about 80 contracts. Words learned for keyword search leave these contracts out while they are scored.
- **Test:** the 102 official test contracts, scored once with frozen settings.

## 5. Code
| File | Role |
|---|---|
| `src/cuad_ai/ingest.py` | Row builders and inserts for contracts, clauses, highlights, chunks |
| `src/cuad_ai/embed.py` | Local embedding model, resumable batch embedding of chunks |
| `src/cuad_ai/embed_highlights.py` | Resumable embedding of bank highlights (train, no shared company) |
| `src/cuad_ai/terms.py` | `learn_terms`: distinctive word stems per clause from the bank, with a hold-out option |
| `src/cuad_ai/search.py` | `search_chunks`, `search_by_examples`, `search_by_terms`, `search_hybrid` |
| `scripts/load_*.py` | One-time loaders |
| `scripts/embed_chunks.py`, `embed_highlights.py` | Fill the embedding columns |
| `scripts/set_splits.py` | Sets `official_split` and `shares_company_with_test` (idempotent) |
| `scripts/learn_terms.py` | Prints the learned words per clause |
| `scripts/eval_retrieval.py` | First evaluation: query by clause text, all contracts |
| `scripts/eval_examples.py` | Current evaluation: `SPLIT` test or validation, `MODE` examples or hybrid |
| `tests/test_ingest.py`, `tests/test_embed.py` | Unit tests; database tests roll back |

## 6. Chunking and embeddings
- About 1,000 characters per chunk, 200 overlap, cut at a space or line break when possible. 33,809 chunks, lengths 207 to 1,000.
- Model `BAAI/bge-small-en-v1.5` through `fastembed` (quantized ONNX, 384 numbers per vector). It runs locally, so contract text stays on the machine. The model name is stored per row.
- Vector search only (cosine distance, bi-encoder). No reranker.

## 7. Retrieval design
For one contract and one clause:
1. **Header rule.** For Document Name, Parties, Agreement Date and Effective Date, the first 4 chunks are added. These facts sit at the start of a contract.
2. **Example search.** Each chunk is scored by its similarity to the closest bank highlight of the clause. Real wording from lawyer-marked passages replaces the long generic CUAD question.
3. **Keyword search.** For each clause, `learn_terms` takes the word stems that appear in at least 10% of its bank examples and in at least 5 different contracts, and that are at least 3 times more common there than in other clauses. The top 10 are used as an OR query on the `tsv` index, ranked by `ts_rank_cd`. Stemmed words are matched with the `simple` configuration so they are not stemmed twice. Hyphenated stems are skipped (their parts are separate stems).
4. **Merge.** Reciprocal rank fusion: each chunk gets `1 / (60 + rank)` from each list, the points are added, and the best chunks are kept. Each list contributes its top 50.

Settings are frozen: top 10 words, pool 50, RRF constant 60. On validation, 5, 15 and 20 words gave the same pooled result (single clauses moved by 10 to 25 points in both directions, which is sample noise), and a pool of 20 or 100 gave no gain of 0.01 at both k=5 and k=10.

## 8. Evaluation method
For each clause and each contract where lawyers marked it, search inside that contract, take the top k chunks (plus the header chunks for the four header clauses), and count a hit if they cover at least 50% of a marked passage. Recall@k is hits divided by cases. Test: 102 contracts, 1,244 cases. Validation: about 80 contracts, 1,068 cases. This measures whether the right passage is among the retrieved chunks, not whether the model then quotes it correctly.

## 9. Results
Overall recall (r@3 / r@5 / r@10):

| Search | Contracts scored | r@3 | r@5 | r@10 |
|---|---|---|---|---|
| CUAD question as query | all 510 | 0.43 | 0.51 | 0.64 |
| Clause name + header rule | all 510 | 0.71 | 0.77 | 0.85 |
| Examples only | test | 0.73 | 0.80 | 0.88 |
| Examples only | validation | 0.73 | 0.79 | 0.88 |
| Hybrid (examples + keywords) | validation | 0.84 | 0.89 | 0.93 |
| **Hybrid, frozen settings** | **test** | **0.85** | **0.89** | **0.93** |

The first two rows were scored on all contracts, before any learning from data, so they are not directly comparable with the held-out rows. Validation and test agree to within 0.01. 28 of 40 clauses reach 0.90 at k=10 on test.

Final test result per clause (hybrid, n = cases):

| Clause | n | r@3 | r@5 | r@10 |
|---|---|---|---|---|
| Document Name | 102 | 0.79 | 0.80 | 0.83 |
| Parties | 102 | 1.00 | 1.00 | 1.00 |
| Agreement Date | 93 | 0.86 | 0.89 | 0.89 |
| Effective Date | 70 | 0.87 | 0.89 | 0.93 |
| Expiration Date | 78 | 0.90 | 0.91 | 0.99 |
| Renewal Term | 26 | 1.00 | 1.00 | 1.00 |
| Notice Period To Terminate Renewal | 16 | 0.88 | 0.94 | 0.94 |
| Governing Law | 83 | 0.98 | 0.99 | 0.99 |
| Most Favored Nation | 3 | 0.00 | 0.67 | 0.67 |
| Non-Compete | 23 | 0.83 | 0.91 | 0.91 |
| Exclusivity | 33 | 0.70 | 0.85 | 0.91 |
| No-Solicit Of Customers | 7 | 0.57 | 0.71 | 0.71 |
| Competitive Restriction Exception | 16 | 0.62 | 0.81 | 0.88 |
| No-Solicit Of Employees | 10 | 1.00 | 1.00 | 1.00 |
| Non-Disparagement | 7 | 0.57 | 0.71 | 0.71 |
| Termination For Convenience | 29 | 0.97 | 1.00 | 1.00 |
| Rofr/Rofo/Rofn | 17 | 0.59 | 0.76 | 0.88 |
| Change Of Control | 26 | 0.81 | 0.85 | 0.92 |
| Anti-Assignment | 72 | 0.94 | 0.94 | 1.00 |
| Revenue/Profit Sharing | 35 | 0.77 | 0.86 | 0.91 |
| Minimum Commitment | 32 | 0.59 | 0.66 | 0.81 |
| Volume Restriction | 17 | 0.65 | 0.71 | 0.71 |
| Ip Ownership Assignment | 23 | 0.74 | 0.78 | 0.91 |
| Joint Ip Ownership | 7 | 0.86 | 0.86 | 1.00 |
| License Grant | 50 | 0.82 | 0.84 | 0.94 |
| Non-Transferable License | 22 | 0.73 | 0.86 | 1.00 |
| Affiliate License-Licensor | 6 | 1.00 | 1.00 | 1.00 |
| Affiliate License-Licensee | 12 | 0.75 | 0.92 | 1.00 |
| Unlimited/All-You-Can-Eat-License | 3 | 0.67 | 0.67 | 0.67 |
| Irrevocable Or Perpetual License | 13 | 0.85 | 0.85 | 0.85 |
| Source Code Escrow | 1 | 1.00 | 1.00 | 1.00 |
| Post-Termination Services | 29 | 0.76 | 0.86 | 0.90 |
| Audit Rights | 38 | 0.84 | 0.87 | 0.95 |
| Uncapped Liability | 13 | 0.92 | 1.00 | 1.00 |
| Cap On Liability | 44 | 0.93 | 0.95 | 0.98 |
| Liquidated Damages | 14 | 0.64 | 0.71 | 0.86 |
| Warranty Duration | 10 | 0.80 | 0.90 | 1.00 |
| Insurance | 32 | 0.97 | 0.97 | 1.00 |
| Covenant Not To Sue | 24 | 0.62 | 0.79 | 0.92 |
| Third Party Beneficiary | 6 | 0.83 | 0.83 | 1.00 |
| ALL | 1,244 | 0.85 | 0.89 | 0.93 |

Price Restrictions has no cases in the test set. Many clauses have fewer than 20 cases, so single-clause numbers are noisy; judge changes on the pooled row.

## 10. Findings and limits
- Learning from the lawyers' own examples and combining it with learned keywords raised held-out recall at k=10 from 0.85 to 0.93. Keywords help most where wording is fixed (Governing Law, IP Ownership Assignment, Covenant Not To Sue, Exclusivity).
- Still weak at k=10: Document Name 0.83, Non-Disparagement 0.71, No-Solicit Of Customers 0.71, Volume Restriction 0.71, Minimum Commitment 0.81.
- Recall measures retrieval only. End-to-end quality (quote correctness after the model reads the chunks) is the next measurement.
- The test set has been used once for this design. Further retrieval changes must be judged on validation.
- Affiliate License clauses share generic license words with other license clauses, which can pull keyword search the wrong way. They have few cases; revisit with more data.

## 11. Next steps
1. Connect retrieval to the model: top chunks in, quote out, `validate.py`, score against the lawyers' answers.
2. Compare cost and accuracy with the 410-call whole-contract baseline.
3. Bounded agent for clauses where retrieval or the model fails; optional router per clause.
4. Improve header clauses (Document Name) and the weak clauses above, judged on validation.

## 12. Open items
- Tests for `chunk_spans`, `chunk_rows`, `insert_chunks` and `embed_pending_highlights` if missing.
- Unique rule on highlights (contract, clause, start, end) so a loader cannot double-load.
- Fix the overlap between the dev set and `evals/test_set_multi.json` before using it.
- Revoke any API key that was ever pasted in chat.
- Line endings: working files are CRLF while the repo is LF, so `git status` shows many false modifications. A `.gitattributes` file would settle it.
- Scratch outputs (`tune.txt`, `top5.txt`, `top20.txt`, `test_hybrid.txt`) are not part of the repo.

## 13. Reproduce from scratch
```
docker start cuad-db
Get-Content sql\schema.sql | docker exec -i cuad-db psql -U cuad -d cuad
python scripts\load_contracts.py
python scripts\load_clauses.py
python scripts\load_highlights.py
python scripts\load_chunks.py
python scripts\embed_chunks.py
python scripts\set_splits.py
python scripts\embed_highlights.py
```
Evaluate:
```
$env:SPLIT="validation"; $env:MODE="hybrid"; python scripts\eval_examples.py
$env:MODE="hybrid"; python scripts\eval_examples.py     # test, once
```
Run each loader once. Contracts, clauses and chunks reject duplicates. Highlights does not yet, so a second load doubles it; empty a table first with `TRUNCATE <table> RESTART IDENTITY;`. `set_splits.py` and the embedding scripts are safe to repeat.
