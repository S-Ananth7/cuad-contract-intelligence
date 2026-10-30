# Decisions: CUAD contract intelligence

Last updated: 2026-10-29

## Problem
Lawyers read hundreds of contracts by hand. Slow and costly.
Build a tool that finds key clauses and shows the exact quote.

## User
In-house lawyer doing due diligence.

## Scope
First clause: Governing Law. Four more clauses after the first one works end to end.

## Flow
contract text -> prompt -> model -> parse reply -> check form -> check quotes -> row -> score against the lawyers' key

## Answer form
- found: true or false
- quotes: list of exact sentences from the contract
- value: state or country, for example "Delaware", or null

## Rules
- Not found: found is false, quotes is empty, value is null.
- Several governing law sentences: put all of them in quotes.
- Every quote must appear word for word in the contract. Extra spaces and line breaks are ignored. An empty quote is rejected.
- found true with no quotes counts as no proof (quotes_real is false).
- Value must come from a quote. Not enforced in code yet. Only quotes_real is checked.

## Data (CUAD v1)
- 510 contracts. Governing Law: 437 present, 73 absent.
- 464 lawyer quotes, 0 position mismatches. The key is clean for this clause.
- The key has quotes only, no value. Check about 10 values by eye.
- The files are public SEC filings. Check the license before sharing.

## Split
- Dev 30 (22 present, 8 absent). Test 30 (22 present, 8 absent). Test is locked until the final run.
- Seed: TODO (write the final seed from scripts/make_split.py).
- Seed 42 leaked twin contracts across piles (Bellring, NETGEAR, Gridiron). Final split has no company in both.

## Eval v1: Governing Law, dev pile
Question: can the model find the clause, with a real quote?
Measures: recall (with and without counting failed calls), precision, invented quotes, failed calls, tokens, seconds.
Targets, set before seeing any score (proposed, change if you disagree):
- Recall >= 0.90, because a miss costs a lawyer more than a false alarm.
- Invented quotes = 0, because a made-up quote breaks the point of the tool.
- Failed calls <= 10%, because a flaky tool is not usable.
TODO: write your own reason beside each target.
Limits: 30 contracts is noisy. One miss moves recall about 4.5 points. A small gap between two prompts or models is noise.

## Model and provider
- Provider: Google AI Studio via the OpenAI-compatible endpoint. Model: gemini-3.8-flash.
- Confirmed working: TODO (yes or no). Earlier calls timed out.
- History: Oxion gave 503 (outage). Mistral gave 429 (free-tier limit). Google calls took about 56 to 63 seconds.
- Free-tier prompts may be used for training. Public contracts only. A real client needs a provider with proper data terms.

## Measured so far
- One contract call (LECLANCHE, 4,371 tokens in): 56.3 s, correct answer, quote matched the lawyers.
- Call times seen: 61.4 s, 63.0 s, 56.3 s.
- Dev contract length in characters: 645 shortest, 37,031 median, 159,187 longest. About 4 characters per token.
- Tests: 32 passed (loader, validate, llm, extract, metrics).

## Choices and why
- One clause first, so the whole recipe works before I copy it.
- Whole contract in the prompt, no chunking. The longest dev contract is about 40,000 tokens, and chunking adds a way to miss the clause.
- Retries only on 429 and 5xx, with backoff. 401 and 404 stop at once.
- Parser takes the first { to the last }. It does not trust a code-fence wrapper.
- The model never sees the lawyers' answers.
- Recall is reported twice, because a failing model must not look perfect.
- Eval built by hand, not MLflow or Databricks. Reason: I wanted to understand every number. MLflow tracking is a later step.
- Quote match today: one quote inside the other. Planned: the CUAD evaluator's Jaccard rule, threshold 0.5.

## Open questions (proposed answers, confirm)
- Contract names two states: value is the state whose law governs, not the court's state.
- Quote check fails twice: mark the contract "needs human review".

## To do
1. Confirm the model answers in seconds. Switch model or provider if not.
2. Run the eval on 3 contracts, then 30. Read every wrong answer.
3. Switch quote match to Jaccard 0.5.
4. Prompt v2 from real mistakes (exact not-found JSON, two examples). One change per run.
5. Keyword baseline. Two-model comparison. Test pile once.
6. Four more clauses. README. CLI or small API.


Baseline v1 on dev: recall 1.0, precision 0.957, right sentence 20 of 22.
Baseline v2 on dev (rules tightened after seeing v1 errors): recall 0.864, precision 1.0, right sentence 19 of 22.
Trade-off: stricter rules fixed 2 wrong quotes and 1 false alarm, but lost 3 clauses.
Both scores are optimistic because the rules were tuned on dev. Honest numbers come from the locked test pile.