# CUAD Contract Intelligence

Finds key clauses in commercial contracts, quotes the exact sentence, and checks that the quote really exists in the contract. A learning project built from scratch: data checks, evals, a free baseline, and a model, all scored the same way.

**Status:** Governing Law works end to end on the dev set. The locked test set has not been run yet.

## The problem
Lawyers read hundreds of contracts by hand. It is slow and costly. This tool does a first pass and shows its proof, so a person only reviews what it flags.

## How it works
```
contract text -> prompt -> model -> parse reply -> check form -> check quotes -> one row -> score against the lawyers' key
```
- **The model never sees the answer key.** The lawyers' labels are used only for scoring.
- **Every quote is verified.** A quote must appear word for word in the contract. Extra spaces and line breaks are ignored. An empty quote is rejected, and "found" with no quote counts as no proof.
- **Replies are never trusted.** The parser takes the first `{` to the last `}`, then Pydantic checks the shape.
- **Failures are recorded, not hidden.** A failed call or an unreadable reply becomes an error row, and recall is reported both ignoring and counting failed calls.

## Results (dev set: 30 contracts, 22 with the clause and 8 without)

| Method | Recall | Precision | Quote matches lawyers | Invented quotes | Failed calls | Avg seconds |
|---|---|---|---|---|---|---|
| Keyword baseline v1 | 1.00 | 0.957 | 20 / 22 | 0 | 0 | about 0 |
| Keyword baseline v2 | 0.864 | 1.00 | 19 / 22 | 0 | 0 | about 0 |
| DeepSeek V4 Flash, thinking off, prompt v1 | 1.00 | 0.957 | 22 / 22 | 0 | 0 | 1.58 |

The model used on average 9,604 input tokens and 57 output tokens per call. At a published list price near $0.14 per million input tokens, 30 contracts cost a few cents. Check the provider's current price.

**Read these numbers carefully**
- 30 contracts is small. One miss moves recall by about 4.5 points.
- Baseline v2 was tuned after looking at dev errors, so its dev score is optimistic. The model prompt was written before any dev error was seen.
- For Governing Law, a free keyword search already finds the clause. The model's gain is in choosing the right sentence, and in extracting the value.
- The one false alarm on dev is a sentence that points to another document. Both the baseline and the model quote it. The labels are debatable there.
- Extra quotes that overlap no lawyer quote are not counted at contract level. `scripts/quote_precision.py` measures them.
- The state or country in `value` is not scored automatically. It is checked by eye.

## Quick start (Windows PowerShell)
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
Copy-Item .env.example .env
pytest
```
1. Download CUAD v1 from the Atticus Project (https://www.atticusprojectai.org/cuad). Put `CUADv1.json` in `data/`. The data is not in this repo.
2. Fill in `.env`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. Optional: `LLM_THINKING=off` and `LLM_MAX_TOKENS=800`.
3. Free baseline, no key needed: `python evals\run_baseline.py 30`
4. Model run: `python evals\run_eval.py 30`
5. Reports are saved in `evals/reports/`. Inspect wrong rows with `python scripts\inspect_baseline.py <report>`.

## Layout
- `src/cuad_ai/` is the library. `loader` reads the data, `schema` is the answer form, `validate` checks quotes, `llm` calls the model with retries and timing, `extract` builds the prompt and reads the reply, `metrics` scores, `baseline` and `baseline_v2` are the keyword readers.
- `evals/` holds the dev and test split (`splits.json`) and the eval runners.
- `prompts/` holds versioned prompt files.
- `tests/` has one test file per code file. They use fake data and never call a model.
- `scripts/` holds one-off helpers.
- `notes/decisions.md` records choices and the reasons for them.

## Design choices
- Dev (30) and test (30) piles were fixed up front. No company appears in both. The test pile is locked until the final run.
- The answer key was checked first: 464 lawyer quotes for Governing Law, and all of them sit at the recorded positions.
- Retries only on 429 and 5xx, with backoff. A 401 or 404 stops at once.
- Thinking mode off cut output tokens on a tiny test from 81 to 6.
- A free baseline is the yardstick. A model has to beat it to earn its cost.

## Limits and next steps
- Only one clause so far. Next: four more, chosen by how often they appear (Effective Date, Anti-Assignment, Termination For Convenience, Cap On Liability).
- Compare two or more models on the same dev set, then run the locked test set once.
- Score `value` automatically, and use the official CUAD matching rule (Jaccard at least 0.5).

## Data and privacy
CUAD v1 is licensed CC BY 4.0. Cite the authors (below). Hosted DeepSeek APIs send prompts to servers in China, according to several sources. CUAD is public, so that is fine here, but do not send confidential contracts to a provider you have not vetted.

## Citation
Hendrycks, Burns, Chen and Ball. *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review.* NeurIPS 2021.