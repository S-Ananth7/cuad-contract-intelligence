# CUAD Contract Intelligence

Finds key clauses in commercial contracts, quotes the exact sentence, and verifies that every quote exists in the contract. Scored against the lawyer-annotated [CUAD](https://www.atticusprojectai.org/cuad) answer key.

**Status:** Governing Law works end to end. All 41 clause types have run on a small sample: recall is high, precision and invented quotes need work. Next: load the data into Postgres. The locked test set has not been run.

## Why
Lawyers read hundreds of contracts by hand. This tool does a first pass and shows its proof, so a person reviews only what it flags.

## How it works
```
contract text -> prompt -> model -> parse reply -> validate form -> verify quotes -> result row -> score
```
- The model never sees the answer key. Labels are used only for scoring.
- A quote must appear word for word in the contract (extra spaces and line breaks ignored). `found` with no quote counts as no proof.
- Replies are never trusted: the JSON is extracted, then validated with Pydantic.
- Failed calls are recorded as error rows. Recall is reported with and without them.

## Results

**Governing Law, dev set (30 contracts: 22 with the clause, 8 without)**

| Method | Recall | Precision | Invented quotes | Failed calls |
|---|---|---|---|---|
| Keyword baseline | 1.00 | 0.957 | 0 | 0 |
| DeepSeek V4 Flash, thinking off | 1.00 | 0.957 | 0 | 0 |

**All 41 clause types (10 contracts, 410 calls)**

| Recall | Precision | Invented quotes | Failed calls | Avg latency |
|---|---|---|---|---|
| 0.994 | 0.596 | 7 | 0 | 2.07 s |

Caveats:
- Samples are small. One miss moves recall by several points.
- The keyword rules were tuned on dev errors, so the baseline score is optimistic.
- Most false alarms are neighbouring clauses taken for the asked one. The 7 invented quotes are near copies of real sentences.
- `value` (state or country) is not scored automatically yet.

Details and reasoning: [`notes/decisions.md`](notes/decisions.md).

## Quick start (Windows PowerShell)
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
Copy-Item .env.example .env
python -m pytest
```
1. Download CUAD v1 from the [Atticus Project](https://www.atticusprojectai.org/cuad) and put `CUADv1.json` in `data/`. The data is not in this repo.
2. Fill in `.env`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. Optional: `LLM_THINKING=off`, `LLM_MAX_TOKENS=1500`.

## Usage
| Task | Command |
|---|---|
| Free keyword baseline (Governing Law) | `python evals\run_baseline.py 30` |
| Model run (Governing Law) | `python evals\run_eval.py 30` |
| Clause run: contracts, clauses | `python evals\run_clauses.py 10 core` (`core`, `all`, or comma-separated names; add `dry` as a third argument to estimate without calling the model) |
| Show one clause's results | `python scripts\show_clause.py "Non-Compete" fp` |

Reports go to `evals/reports/`. Identical prompts are cached in `evals/cache/`; set `NO_CACHE=1` to bypass it.

## Project layout
```
src/cuad_ai/   loader, schema, validate, llm, extract, clauses, metrics, baseline, cache, runlog
evals/         runners, dev/test split, reports
prompts/       governing_law.txt, clause.txt
tests/         one test file per module; fake data, no model calls
scripts/       data exploration and one-off helpers
notes/         decisions.md: architecture, results, decision log, roadmap
```

## Roadmap
1. Load contracts, clauses, chunks and highlights into Postgres with pgvector.
2. Compare keyword and vector retrieval per clause.
3. Better clause prompt and quote snapping to remove invented quotes.
4. Batched extraction to cut cost, then an agent for failed cases.
5. Run the locked test set once.

## Data and privacy
CUAD v1 is licensed CC BY 4.0. Hosted DeepSeek APIs send prompts to servers in China, according to several sources. CUAD is public, so that is fine here. Do not send confidential contracts to a provider you have not vetted. Never commit `.env`.

## Citation
Hendrycks, Burns, Chen and Ball. *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review.* NeurIPS 2021.
