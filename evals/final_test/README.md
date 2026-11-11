# Final test run: evidence

The official CUAD test set (102 contracts, 4,182 questions), scored once after the design was frozen.
Run id: `20261108_172552_rag_clause_rag_deepseek-v4-flash_k10_102`.

| File | Content |
|---|---|
| `report_summary.json` | Model, prompt hash, code commit, settings and the run's summary counts |
| `decisions.json` | One row per question: the final decision, the reason, the lawyers' label (`gold_found`: the lawyers marked this clause in the contract) and `quote_match` (the model's quote contains, or is contained in, a lawyer's highlighted passage, ignoring spacing) |
| `queue.json` | The 184 answers sent to a person, with the quotes and which clause the judges thought they looked like |

`tests/test_final_test_result.py` recomputes the headline numbers from `decisions.json`
(1,505 accepted, 1,139 real, precision 0.757, recall 0.916), so the claim and the data cannot drift apart.
Those headline numbers are clause-level: an accepted answer is real when the lawyers marked that clause anywhere in the contract. The stricter span-level numbers, which also need `quote_match`, are 1,058 of 1,505 (precision 0.703, recall 0.850); a second test recomputes them.

Not committed: the raw per-question report (3.4 MB, contains every model reply). It stays in `evals/runs/` locally.
Anyone with the data can reproduce the run; the test set is guarded by `CONFIRM_TEST=yes` and should not be re-run to tune.
