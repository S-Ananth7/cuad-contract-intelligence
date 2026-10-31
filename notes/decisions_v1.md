# Decisions: CUAD contract intelligence

Last updated: 2026-10-31

## Problem and scope
Find key clauses in contracts, quote the exact sentence, prove it is real. First clause: Governing Law. More clauses after the first one works end to end.

## Answer form and rules
- found (true or false), quotes (list of exact sentences), value (state or country, or null).
- Not found means found false, quotes empty, value null.
- Quote must appear word for word. Extra spaces and line breaks are ignored. Empty quote is rejected. found true with no quotes counts as no proof.
- Value must come from a quote. Not enforced in code yet.

## Data
- CUAD v1: 510 contracts. Governing Law: 437 present, 73 absent. 464 quotes, all at the recorded positions.
- License CC BY 4.0. Cite the authors.
- The JSON key has quotes only. The original master CSV may hold a state or country answer. Not checked yet.

## Split
- Dev 30 and test 30, each 22 with the clause and 8 without. Test is locked.
- Seed: TODO (copy from scripts/make_split.py). Seed 42 leaked twin contracts (Bellring, NETGEAR, Gridiron). The final split has no company in both piles.

## Eval targets (set before seeing any model score)
- Recall at least 0.90, because a miss costs a lawyer more than a false alarm.
- Invented quotes 0, because a made-up quote breaks the tool.
- Failed calls at most 10%, because a flaky tool is not usable.
TODO: write your own reason beside each.

## Results on dev (30 contracts)
| Method | Recall | Precision | Quote matches | Invented | Failed | Avg s |
|---|---|---|---|---|---|---|
| Baseline v1 | 1.00 | 0.957 | 20/22 | 0 | 0 | 0 |
| Baseline v2 (tuned on dev) | 0.864 | 1.00 | 19/22 | 0 | 0 | 0 |
| DeepSeek V4 Flash, thinking off | 1.00 | 0.957 | 22/22 | 0 | 0 | 1.58 |
- All three targets met by the model.
- The one false alarm (row 29) quotes a sentence that points to another document. Baseline v1 made the same mistake. The labels are debatable. Saved as a hard case.
- Baseline v2 misses: two wording gaps ("controlled by", "in accordance with the laws of") and one venue sentence labeled as Governing Law (label noise).

## Provider history
- Oxion: 503 outage. Mistral free tier: 429. Google Gemini: calls took 56 to 63 seconds, thinking on by default.
- DeepSeek V4 Flash: about 1.6 s per call. Thinking off cut output tokens on a tiny test from 81 to 6.
- Free and hosted tiers may train on prompts. Hosted DeepSeek routes data to servers in China. Public contracts only.

## Choices and why
- One clause first, so the whole recipe works before copying it.
- Whole contract in the prompt, no chunking. The longest dev contract is about 40,000 tokens.
- Retries only on 429 and 5xx, with backoff. 401 and 404 stop at once.
- Parser takes the first { to the last }. It does not trust a code-fence wrapper.
- Recall reported twice, because a failing model must not look perfect.
- Eval built by hand, not MLflow, so every number is understood. MLflow tracking is a later step.
- Baselines are yardsticks, not to be tuned further on dev.

## Open questions
- Two states in one contract: value is the state whose law governs, not the court's state.
- Quote check fails twice: mark the contract for human review.

## To do
1. Quote precision and value check on the DeepSeek report.
2. Repeat the dev run to see variation. Thinking on versus off on the same contract.
3. Four more clauses. Bigger dev sets for the rare ones.
4. Official CUAD matching (Jaccard 0.5). Second model. Test pile once.