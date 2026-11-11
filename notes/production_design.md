# Production Design: Contract Clause Extraction with Verification

Last updated: 2026-11-08

## 1. Purpose and scope

Given a contract, find the clauses a lawyer would look for (41 types from CUAD v1), quote the exact sentences, prove each quote exists in the contract, and say how much each answer can be trusted. The system must be cheap enough to run on every contract, honest about what it is unsure of, and measurable against the lawyers' answer key.

In scope: ingestion, indexing, retrieval, extraction, validation, routing, review, storage, evaluation, monitoring.
Out of scope for now: a user interface, authentication, multi-tenant isolation, OCR of scanned contracts, non-English contracts.

## 2. Status legend

| Mark | Meaning |
|---|---|
| BUILT | Implemented and measured in this repository |
| PARTIAL | Works, but runs as separate scripts or without full automation |
| PLANNED | Designed here, not built |

## 3. Architecture

```
                      ONE-TIME / BATCH                                   PER CONTRACT
 contracts + lawyer labels                                    contract text
        |                                                          |
  [1 Ingest] ---> Postgres: contracts, clauses, highlights         |
        |                                                          v
  [2 Chunk + embed] ---> chunks (text, vector, tsvector)    [4 Retrieve] per clause:
        |                                                      header rule + example search
  [3 Example bank] ---> embedded lawyer highlights ---------->  + learned keywords + RRF merge
                         (train only, never same company)           |
                                                                    v
                                                          [5 Extract] LLM on ~10 excerpts
                                                                    |  found? + quotes
                                                                    v
                                                          [6 Validate] quote word for word in contract
                                                                    |  fail -> retry once -> else reject
                                                                    v
                                                          [7 Route] confidence + risk
                                                              |                 |
                                                           ACCEPT            REVIEW
                                                              |                 |
                                                              |        [8 Two judges] both must say yes
                                                              |                 |
                                                              v                 v
                                                          [9 Store answer + evidence + route + run id]
```

## 4. Components

| # | Component | Responsibility | Status |
|---|---|---|---|
| 1 | Ingest | Load contracts, clause names and questions, lawyer highlights into Postgres. Official CUAD split: 408 train, 102 test | BUILT |
| 2 | Chunk and embed | 1000-character chunks, 200 overlap (33,809 chunks). Embeddings `BAAI/bge-small-en-v1.5`, 384 dimensions, plus a text-search column | BUILT |
| 3 | Example bank | 10,848 embedded lawyer highlights from training contracts that share no company with the test set | BUILT |
| 4 | Retrieve | Per clause: first 4 chunks for header clauses (name, parties, dates); otherwise example search (best match to bank examples) merged with learned keywords by reciprocal rank fusion. 10 chunks go to the model | BUILT |
| 5 | Extract | One model call per clause on the merged excerpts. Returns found, quotes. Prompt file `prompts/clause_rag.txt` | BUILT |
| 6 | Validate | Deterministic: reply parses, schema valid, every quote appears word for word in the excerpts and contract. One retry with a stricter prompt; still bad goes to the queue | PARTIAL: in `cuad_ai/pipeline/extraction.py`, not yet run live |
| 7 | Route | Confidence = asked clause is the closest of 41 to the quote. Risk = per-clause false alarm rate from other contracts. Accept or review | PARTIAL (script) |
| 8 | Review | Two cheap model calls on the quote only: one plain, one with 3 lawyer examples. Keep only if both say yes | PARTIAL (script) |
| 9 | Decide and store | `final_answers.py` applies the policy and writes `final.json` and `queue.json` per run. A database table is still planned | PARTIAL |

## 5. Data model

Existing tables: `contracts` (title, company, split, shares_company_with_test), `clauses` (name, question), `highlights` (lawyer spans, embedding), `chunks` (text, embedding, tsvector).

Planned tables:

| Table | Columns | Purpose |
|---|---|---|
| `runs` | id, started_at, model, prompt versions, k, settings, git commit | Reproduce any result |
| `answers` | run_id, contract_id, clause, found, quotes, quote_verified, rank_asked, similarity, risk, route, judge1, judge2, final, tokens, seconds | One row per question, with the full decision path |

An answer without its decision path cannot be audited, so the path is part of the record.

## 6. Decision policy

| Situation | Automatic step | Outcome |
|---|---|---|
| Model says not found | none | Final: not found |
| Reply cannot be parsed | Retry once | Still bad: queue (`parse_failed`) |
| Quote not word for word in the contract | Retry once with a stricter prompt | Still bad: queue (`quote_unverified`) |
| Clause is Document Name or Agreement Date | none | Accept (a title or date is not a sentence; the review question does not fit) |
| Asked clause is the closest of 41 and frozen clause risk is 0.5 or lower | none | Accept |
| Anything else | Two judges | Both yes: accept. Both no: reject. Disagree: queue (`judges_disagree`) |

Nothing is dropped without a recorded reason. A plain reject of an invented quote is wrong: 5 of the 7 invented quotes on the second validation set belonged to real clauses (the model paraphrased). That is why the first response is a retry, not a reject.

### 6.1 The review queue

The queue holds answers the system cannot settle. The system never waits for it: every queued answer has an automatic default (not accepted), and the headline score counts it that way. A person may review the queue; the second score assumes a perfect reviewer and is only an upper bound.

| | First 30 validation contracts | New 30 |
|---|---|---|
| Queue size | 51 | 55 to 60 (about 2 per contract) |
| Share of the queue that is real | about 16% | about 16% |
| Recall, automatic only | 0.922 | 0.911 |
| Recall with a perfect reviewer | 0.943 | 0.932 |

The queue is mostly false alarms, so a reviewer mostly confirms rejections. The gain from review is about 2 points of recall and almost nothing in precision. It is worth it for high-stakes contracts, not for the system to work.

Each queue item stores the clause, quote, reason and both judge replies. Human decisions are saved in their own table and are never fed back into the example bank, the learned keywords or the risk table for the evaluation they came from.

### 6.2 Leakage controls

1. Example bank: training contracts only, none whose company appears in the test set. Same-company examples are never used for a contract.
2. Learned keywords: training contracts only, scored contracts held out.
3. Risk table: frozen from the 60 validation contracts (`evals/risk_table.json`). Never learned from the contracts being scored. Routing the second validation set with a table from the first gave the same result (precision 0.747, recall 0.911).
4. Rules (risk limit 0.5, rank 1, header exemption, both judges) are fixed before the test run and not changed after it.
5. Test labels are used only to score, after the run. `SET=test` refuses to run without `CONFIRM_TEST=yes`.
6. Human decisions never flow back into evaluation inputs.
7. The 102 official test contracts are scored once.

## 7. Quality gates

| Gate | Rule |
|---|---|
| No leakage | Example bank uses only training contracts with no company shared with the test set. Same-company examples are never used for a contract. Learned keywords hold out the contracts being scored |
| Validation first | Every design change is judged on validation contracts. Rules tuned on one validation set are confirmed on a second set that was never used for tuning |
| One test run | The 102 official test contracts are scored once, after the design is frozen. Nothing is tuned on them |
| Regression check | Before a release: rerun the validation set, compare precision, recall, invented quotes and cost with the last accepted run |

## 8. Measured performance

Two sets of 30 validation contracts, 1,230 questions each. The second set was untouched by tuning, so it is the honest estimate.

| Pipeline version | First 30: P / R | New 30: P / R |
|---|---|---|
| Whole contract (baseline, 9 contracts) | 0.60 / 0.99 | not run |
| Retrieval only | 0.59 / 0.95 | 0.62 / 0.94 |
| Retrieval + routing + one review | 0.73 / 0.92 | 0.72 / 0.92 |
| **Retrieval + routing + two judges** | **0.75 / 0.92** | **0.75 / 0.91** |

P is precision, R is recall (model errors counted as misses). Margin of error on precision is about plus or minus 0.04 at this size. The lawyers' labels are incomplete, so true precision is somewhat higher.

## 9. Cost and latency

| Item | Value |
|---|---|
| Whole-contract approach | about 12,800 input tokens per question |
| Retrieval approach | about 2,200 input tokens per question (about 83% less) |
| Review | about 340 tokens per call, on about 65% of answers, per judge |
| Latency | about 1.4 seconds per model call; a contract is 41 questions, so about 1 minute sequentially |
| Throughput today | 1,230 calls in about 40 minutes (sequential, one process) |

Levers: parallel calls per contract (the provider concurrency limit applies), response cache (identical prompts cost nothing), per-clause `k`, running the review only when confidence is low.

## 10. Reliability

| Mechanism | Status |
|---|---|
| Retry with backoff on busy-line errors (429, 5xx, network), 4 attempts | BUILT |
| Response cache keyed on model, settings and prompt, so a stopped run resumes at no cost | BUILT |
| Run stops after 3 consecutive errors | BUILT |
| Report written every 10 rows | BUILT |
| Retry once on invalid or invented quote, stricter prompt (`cuad_ai/pipeline/extraction.py`) | PARTIAL: written, not yet run live |
| Whole-contract fallback for clauses that stay uncertain | PLANNED |
| Idempotent job per contract (safe to re-run) | PLANNED |

## 11. Security and privacy

- API keys and the database password live in `.env`, which is not committed. They are never printed or logged. Any key that was ever pasted in a chat must be revoked.
- Contract text is sent to an external model provider. For real contracts this needs a data-processing agreement, or a model hosted inside the company's own network.
- Stored answers contain contract text. Apply the same access control as the contracts themselves.
- Model replies are treated as untrusted input: parsed against a schema, never executed, and quotes are verified against the source.
- A contract can contain text that tries to instruct the model. The model only extracts and judges; it has no tools and no side effects, which limits the damage.

## 12. Observability

Built: a report per run (counts, precision, recall, invented quotes, tokens, seconds), a run log, and the saved per-answer rows.

Planned dashboard and alerts:
- Daily precision and recall on a small fixed audit set.
- Invented-quote rate and parse-failure rate (alert above a threshold).
- Share of answers routed to review, and review rejection rate (a sudden change means the model or data drifted).
- Tokens and cost per contract.
- Provider error rate and latency.

## 13. Versioning and reproducibility

A result is only meaningful if it can be reproduced. Every run records the model name, the prompt files, `k`, the retrieval settings and the git commit. Prompts live in `prompts/` under version control. The provider's model name can change underneath us (the old `deepseek-v4-flash` name is retired and now served by a newer Flash model), so runs from different dates may differ; pin the model name and note the date.

## 14. Failure modes

| Failure | Effect | Defence |
|---|---|---|
| Retriever misses the passage | Real clause missed (recall about 0.93 at k=10) | Larger `k` for spread-out clauses; whole-contract fallback |
| Model claims a clause that is not there | False alarm | Embedding check, risk routing, two judges |
| Model invents a quote | Dishonest evidence | Word-for-word check; retry; reject |
| Judges reject a real clause | Silent miss (7 to 11 per 400 answers) | Header exemption; track the rate; stronger model on doubtful clauses |
| Provider outage or rate limit | Run fails | Backoff, cache, resume |
| Provider silently changes the model | Quality drifts | Pin the model; audit set; alert on drift |
| New contract type unlike the examples | Weak retrieval | Audit set per contract type; widen the example bank |
| Labels incomplete | Metrics understate quality | Report this; spot check false alarms |

## 15. Roadmap

1. Run the retry live on a small validation sample and confirm it fixes invented quotes (7 and 2 on the new set).
2. One command for the whole pipeline: `python -m cuad_ai pipeline` (written, to be run).
3. Parallel execution and a per-contract job queue.
4. Per-clause `k` and a stronger model (`deepseek-v4-pro`) on the doubtful clauses only.
5. Whole-contract fallback for clauses still uncertain after review.
6. Audit set and monitoring dashboard.
7. One final run on the 102 official test contracts, after the design is frozen.

## 16. Open risks

- Precision gains were tuned on 30 contracts and confirmed on 30 more. A third set, or the test run, may move the numbers by a couple of points.
- The two judges share the same underlying model, so their mistakes are partly correlated. A different model for the second judge may help more than examples do.
- The design is measured on CUAD, a US commercial contract set. Other contract types and languages are untested.
