# Final Test Result: Official CUAD Test Set

Run date: 2026-11-08. The 102 official test contracts were scored once, after the design was frozen.

## 1. Result

| Stage | Precision | Recall |
|---|---|---|
| Retrieval only | 0.603 | 0.949 |
| One review judge | 0.726 | 0.922 |
| **Final, automatic only** | **0.757** | **0.916** |
| If a human resolved the queue perfectly (upper bound, not measured) | 0.762 | 0.943 |

4,182 questions (102 contracts times 41 clauses). The lawyers marked 1,244 clause instances.

| Final decision | Answers | Real | False alarms |
|---|---|---|---|
| Accept | 1,505 | 1,139 | 366 |
| Reject | 273 | 12 | 261 |
| Queue for a human | 184 | 34 | 150 |

- Precision is the share of accepted answers that match a lawyer label. Recall is the share of lawyer-marked clauses that ended up accepted.
- Margin of error on precision is about plus or minus 0.02 (95%) at 1,505 accepted answers.
- The automatic rejections are reliable: 12 of 273 rejected answers (4%) were real clauses.
- The queue holds 184 items, about 1.8 per contract. 177 are cases where the two judges disagree, 3 are quotes that could not be verified after a retry, and 4 are replies that could not be parsed after a retry. Only 34 of the 184 are real clauses.

## 2. How it was measured

| Control | What it does |
|---|---|
| Official split | 408 training and 102 test contracts, as published with CUAD |
| Example bank | Only training contracts that share no company with the test set. Examples from the same company as the scored contract are never used |
| Learned keywords | Learned from training highlights only. Test contracts have no embedded highlights, so test labels cannot reach them |
| Risk table | Built once from the 60 validation contracts (`scripts/freeze_risk.py`) and read from `evals/risk_table.json`. It is never learned from the contracts being scored |
| Frozen settings | Fixed before the test run and not changed afterwards (listed below) |
| One run | The test run is guarded by `CONFIRM_TEST=yes`. It was run once |

Frozen settings: `deepseek-v4-flash`, thinking off, output limit 800 tokens, 10 excerpts per question, hybrid retrieval with pool 50 and RRF constant 60, prompt `prompts/clause_rag.txt`, routing rule (asked clause is the closest of the 41 and risk is 0.5 or lower, plus Document Name and Agreement Date always accepted), both review judges must say yes, one retry for unusable replies.

The report in `evals/runs/` records the model, the prompt hash and the commit it was run from.

## 3. The pipeline in one paragraph

For each contract and clause: retrieve 10 excerpts (header clauses also get the first 4 chunks), ask the model for the clause and exact quotes, check that every quote appears word for word in the contract (retry once if not), compare the quote with the lawyers' examples of all 41 clauses, route it to accept or review using confidence and per-clause risk, review the doubtful ones with two judges, and send disagreements and unsolved retries to a human queue. Details are in `notes/routing_and_review.md` and `notes/production_design.md`.

## 4. Cost

| | Input tokens |
|---|---|
| Extraction | about 2,160 per question (9.0M in total) |
| Review, both judges | about 1.1M in total (about 12% on top) |
| **Per question, all steps** | **about 2,430** |
| Whole-contract baseline | about 12,770 per question (measured on 9 contracts) |

That is about 81% fewer input tokens than sending the whole contract. The baseline figure comes from a small sample, so treat the percentage as approximate.

## 5. Where it is strong and weak (accepted answers)

Weakest by precision:

| Clause | Accepted | Real | Precision |
|---|---|---|---|
| Price Restrictions | 24 | 0 | 0.00 |
| Third Party Beneficiary | 37 | 6 | 0.16 |
| Post-Termination Services | 69 | 27 | 0.39 |
| Uncapped Liability | 25 | 10 | 0.40 |
| Volume Restriction | 17 | 7 | 0.41 |

Weakest by recall (clauses with at least 10 lawyer-marked instances): Volume Restriction 0.41, Warranty Duration 0.50, Liquidated Damages 0.64, Rofr/Rofo/Rofn 0.76.

The overall precision hides a split. Common clauses with clear wording (dates, parties, governing law) are accurate. A handful of vague, rare clauses carry most of the false alarms, and the two judges still accept many of them. These are the clauses to work on next.

## 6. What this result does not say

- About one in four accepted answers (366 of 1,505) has no matching lawyer label. Some of those are real clauses the lawyers did not mark, so true precision is somewhat higher than 0.757. How much higher is not known.
- Recall of 0.916 means about 8% of lawyer-marked clauses are still missed or rejected.
- The human queue figure (0.762 / 0.943) is an upper bound that assumes a perfect reviewer. It was not measured.
- The two judges use the same model, so their mistakes are partly correlated.
- Results are for CUAD, which is US commercial contracts in English. Other contract types and languages are untested.
- The 800-token output limit cut off 7 long answers (3 unverified quotes and 4 parse failures after a retry). This was left in place so the test measures the validated system.
- The cheaper-by-81% figure rests on a 9-contract baseline.

## 7. Next steps (development, not evaluation)

Any change from here is development. The test set has been used once and is not reused for tuning.

1. A higher output limit on the retry call only, to fix truncated replies.
2. A stricter treatment of the weakest clauses (Price Restrictions, Third Party Beneficiary, Post-Termination Services): a stronger model as second judge, or a per-clause threshold.
3. Per-clause number of excerpts, and a whole-contract fallback for clauses that stay uncertain.
4. Store runs and answers in Postgres with the full decision path, and one command for the whole pipeline.
5. Tests for the routing, retry and final decision logic.
6. A further held-out set for the next round of changes.

## 8. Reproduce

```powershell
$env:SET="test"; $env:CONFIRM_TEST="yes"; $env:K="10"; $env:LIMIT="102"; $env:OFFSET="0"; python evals\run_rag.py
$F = "<run folder printed by run_rag.py>"
python scripts\gate_features.py $F\report.json
python scripts\route_answers.py $F evals\risk_table.json
python scripts\verify_answers.py $F
python scripts\verify_with_examples.py $F
python scripts\final_answers.py $F
```
