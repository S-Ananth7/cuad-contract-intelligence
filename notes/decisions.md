# Architecture and Decisions: CUAD Contract Intelligence

Last updated: 2026-11-02

## 1. Purpose
Extract key clauses from commercial contracts, quote the exact sentence, and verify that each quote exists in the source text. Output supports first-pass review by an in-house lawyer during due diligence.

## 2. Scope
| In scope | Out of scope (for now) |
|---|---|
| 41 CUAD clause types | Legal advice or interpretation |
| Exact-quote extraction with verification | Contracts outside CUAD |
| Offline evaluation against the CUAD answer key | Production serving, authentication, UI |
| Postgres + pgvector storage and retrieval | Fine-tuning |

## 3. System flow
```
contract text -> prompt -> model -> parse reply -> validate form -> verify quotes -> result row -> score against answer key
```

## 4. Output contract
| Field | Type | Rule |
|---|---|---|
| found | bool | false means quotes empty and value null |
| quotes | list of string | each quote must appear verbatim in the contract (whitespace-insensitive); empty quotes rejected |
| value | string or null | state or country; must be derived from a quote (not yet enforced) |

`found = true` with no quotes counts as no proof. The model never receives the answer key.

## 5. Data
- CUAD v1: 510 contracts, 41 clause types, 20,910 questions (6,702 present, 14,208 absent), 13,823 highlights.
- Official split: 408 train, 102 test, disjoint.
- Governing Law: 437 present, 73 absent, 464 annotated quotes, all at recorded offsets. The key has quotes only, no value.
- License CC BY 4.0 (cite the authors). Contracts are public SEC filings.

## 6. Evaluation protocol
- Dev set of 30 contracts and test set of 30 (22 positive, 8 negative each). No company appears in both. The test set is locked until the final run.
- Known defect: `evals/test_set_multi.json` overlaps dev by 5 contracts. Resolve before use.
- Acceptance targets (fixed before any score was seen):

| Metric | Target | Rationale |
|---|---|---|
| Recall | >= 0.90 | A miss costs a reviewer more than a false alarm |
| Invented quotes | 0 | A fabricated quote defeats the purpose of the tool |
| Failed calls | <= 10% | An unreliable tool is not usable |

- Recall is reported both excluding and including failed calls.
- Limitation: at 10 to 30 contracts, one miss moves recall by several points.

## 7. Results
**Governing Law, dev (30 contracts)**

| Method | Recall | Precision | Invented | Failed |
|---|---|---|---|---|
| Keyword baseline | 1.00 | 0.957 | 0 | 0 |
| DeepSeek V4 Flash, thinking off | 1.00 | 0.957 | 0 | 0 |

The model returned the right sentence for 22 of 22 positives. A free keyword search is a strong baseline for this clause.

**All 41 clauses (10 contracts, 410 calls)**

| Recall | Precision | Invented quotes | Errors | Avg latency |
|---|---|---|---|---|
| 0.994 | 0.596 | 7 | 0 | 2.07 s |

- Most false alarms are neighbouring clauses returned for the asked clause. The official clause Group predicts which.
- The 7 invented quotes are near copies of real sentences with one word changed.
- Recall and failed-call targets are met. The invented-quote target is not.

## 8. Decision log
| # | Decision | Reason | Consequence |
|---|---|---|---|
| 1 | Verify every quote against the contract | The core guarantee of the product | Model output is never trusted as-is |
| 2 | Parse from first `{` to last `}` | Models wrap JSON in prose or code fences | Pydantic validates the shape afterwards |
| 3 | Retry only on 429 and 5xx, with backoff | Auth and request errors will not heal | 400, 401, 403 and 404 fail immediately |
| 4 | Whole contract in the prompt for now | Chunking adds a way to miss a clause | Cost grows with contract size (see section 9) |
| 5 | Evaluation built by hand, not MLflow | Every number is understood | Experiment tracking is a later step |
| 6 | Provider: DeepSeek V4 Flash, thinking off, max 1500 output tokens | About 2 s per call and low cost | Hosted tier sends prompts to servers in China: public contracts only |
| 7 | One Postgres with pgvector for contracts, clauses, chunks, highlights | Single store for metadata, vectors and full-text search | Vector size must match the chosen embedding model |
| 8 | Ingestion before retrieval | Retrieval quality can only be measured on stored, checked data | Embeddings, RAG and the agent come after ingestion |
| 9 | No version suffixes in file names | Git is the version history | One current file per purpose |

## 9. Cost plan
One call per clause per contract sends each contract 41 times. Levers, largest first:
1. Batch several clauses per call (about 8x less input).
2. Place the contract first so the provider can cache the prefix (price unverified).
3. Cheaper model or batch API.
4. Retrieval only for clauses where it measured safe (11 of 41 with keyword search, about 22% saving).
5. Cache identical prompts and skip work that cannot change the answer.

An agent adds cost and is reserved for failed cases.

## 10. Storage and ingestion plan
- Tables: `contracts`, `clauses`, `chunks` (text, embedding, full-text vector), `highlights` (text, embedding). A view of leak-free training contracts serves as the example bank.
- Ingestion order: create tables, load clauses, load contracts with split flags, chunk, load highlights, mark the example bank, run integrity checks.
- Integrity checks: 510 contracts, 41 clauses, about 13,823 highlights, chunk and highlight text equal the contract slice at their offsets, report split conflicts.
- The LLM response cache moves into Postgres, keyed by a hash of the full prompt and model.

## 11. Roadmap
1. Ingestion with tests.
2. Embeddings, then compare keyword and vector retrieval (recall at k per clause).
3. Clause prompt built from official descriptions and group neighbours.
4. Quote snapping: repair near-copy quotes while still rejecting a changed word.
5. Batched extraction, then hybrid retrieval, then the agent for failures.
6. Score `value` automatically and adopt the official Jaccard >= 0.5 match.
7. Run the locked test set once.

## 12. Security and privacy
- API keys live in `.env`, which is never committed. Any key exposed outside `.env` must be revoked.
- Use only public contracts with hosted providers that are not vetted for confidential data.
