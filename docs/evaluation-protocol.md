# Evaluation protocol

How the numbers were produced, what each one means, and the rules that keep the final score honest. The result itself is in [`notes/final_test_result.md`](../notes/final_test_result.md) and the committed evidence in [`evals/final_test/`](../evals/final_test/README.md).

## Data splits

| Set | Contracts | Used for |
|---|---|---|
| Official train | 408 | The example bank, learned keywords, and everything below |
| Official test | 102 | The final score, run once |
| Development | 30 (`evals/eval_set.json`) | Early development |
| Validation | every fifth bank-eligible train contract by id, about 80; 30 were used to tune and 30 more to confirm | Tuning the gate and settings, then confirming them on fresh contracts |

Ten companies appear in both train and test. Their 16 train contracts are flagged `shares_company_with_test` and never enter the example bank.

## Rules that prevent leakage

| Rule | Where it is enforced |
|---|---|
| The example bank holds only train highlights from companies that share nothing with the test set | `embed_highlights` embeds only bank-eligible highlights; a missing embedding keeps a contract out of the bank |
| Examples from the same company as the scored contract are never used | `hc.company <> company` in the gate and judge 2 queries |
| Learned keywords leave out the contracts being scored | `learn_terms(..., holdout=...)` in the extraction stage |
| The risk table is frozen from validation runs and never learned from the contracts being scored | `python -m cuad_ai freeze-risk`, read from `evals/risk_table.json` |
| The test set runs only on purpose | `SET=test` needs `CONFIRM_TEST=yes`; `tests/test_leakage_guards.py` checks the lock |
| Settings are frozen before the test run | listed in `notes/final_test_result.md` |

## Metrics

A question is one contract and one clause. The lawyers' label for a question, `gold_found`, is true when they marked that clause anywhere in the contract.

| Metric | Definition |
|---|---|
| Precision (headline, clause level) | accepted answers where `gold_found` is true, divided by all accepted answers |
| Recall (headline, clause level) | accepted answers where `gold_found` is true, divided by all questions where `gold_found` is true |
| Span-level precision and recall | the same, but the model's quote must also contain, or be contained in, a lawyer's highlighted passage (spacing ignored): `quote_match` |
| Retrieval recall@k | for each lawyer-marked clause, the share where the top k chunks cover at least half of a marked passage |
| Invented quote | a found answer whose quote is not in the contract |
| Queue rate | queued answers divided by all questions |

The headline counts an answer as right when the clause is present, even if the quote is a different passage from the one the lawyers marked. The span-level numbers are the stricter check. Both are committed and recomputed by `tests/test_final_test_result.py`.

## Results on the 102 test contracts

| Stage | Precision | Recall |
|---|---|---|
| Retrieval and model only | 0.603 | 0.949 |
| Plus one judge | 0.726 | 0.922 |
| Full pipeline, clause level | 0.757 | 0.916 |
| Full pipeline, span level | 0.703 | 0.850 |
| Perfect human on the queue (upper bound, computed, not measured) | 0.762 | 0.943 |

Of 4,182 questions: 1,505 accepted (1,139 real clauses, 1,058 also overlapping a lawyer's passage), 273 rejected (12 real), 184 queued (34 real), 2,220 not found. The margin on clause-level precision is about plus or minus 0.02. The confirmation run on 30 fresh validation contracts gave 0.747 and 0.911 before the test run.

## What is measured and what is not

| Claim | Status |
|---|---|
| Precision and recall | Evaluated against lawyer labels on held-out contracts |
| Retrieval recall@k | Evaluated on validation and test |
| Tokens per question (about 2,160 for extraction, about 2,430 with judges) | Measured on the test run |
| Whole-contract baseline (about 12,770 tokens) and the 81% saving | Observed on 9 contracts only |
| Invented quotes (3) and unresolved replies (7) | Counts from one run, not rates with intervals |
| Latency in use, reviewer time, other datasets | Not measured |

## Changing the system without spoiling the result

- Develop and tune on validation contracts only.
- The test set has been used once for this design. A new headline number needs contracts that no tuning has seen: carve a new held-out set from train and rebuild the example bank without it.
- Re-freeze the risk table when the model or the prompt changes.
- Record every run: the report stores the model, the prompt hash and the code commit, and `scripts/load_run.py` keeps runs in Postgres for comparison.

## Known limits of the measurement

- CUAD labels are not exhaustive, so some false alarms may be real clauses the lawyers did not mark.
- Rare clauses have few cases, so single-clause scores are noisy; judge changes on the pooled numbers.
- The judges share one model, so agreement between them is weaker evidence than it looks.
