# CUAD Contract Intelligence

[![CI](https://github.com/S-Ananth7/cuad-contract-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/S-Ananth7/cuad-contract-intelligence/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
[![Live demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://cuad-contract-intelligence.streamlit.app/)

**Finds 41 types of clauses in commercial contracts, quotes the exact sentence, proves the quote exists word for word, and sends only the doubtful cases to a person.**

Built and scored on the lawyer-annotated [CUAD v1](https://www.atticusprojectai.org/cuad) dataset (510 contracts). It targets three problems of using a language model on contracts:

| Problem | How it is handled |
|---|---|
| **Cost** | Retrieves 10 relevant excerpts per question instead of sending the whole contract: about 81% fewer input tokens |
| **Invented quotes** | Every quote is checked against the contract by plain code, retried once, then queued: 3 invented quotes in the test run, none accepted |
| **Knowing what to trust** | A gate and two judges decide accept, reject or queue, so a person reads about 1.8 answers per contract, not all of them |

## Try it

| | What it is | Where |
|---|---|---|
| **Results demo** | Read-only view of the saved test run: scores, every decision, the evidence next to the lawyers' passages, and the review queue. No setup. | [cuad-contract-intelligence.streamlit.app](https://cuad-contract-intelligence.streamlit.app/) |
| **Live review** | Upload your own contract, watch the pipeline run, see each quote highlighted in your text, and confirm or reject each answer. | [Run it locally](#live-review) or [host it for a client](docs/deploy-live.md) |

**Contents:** [Results](#results) · [How it works](#how-it-works) · [Quick start](#quick-start) · [Usage](#usage) · [Live review](#live-review) · [Keeping the result honest](#keeping-the-result-honest) · [Documentation](#documentation) · [Development](#development) · [Limitations](#limitations) · [Roadmap](#roadmap)

## Results

Scored once on the 102 official test contracts (4,182 questions), after the design was frozen.

| Stage | Precision | Recall |
|---|---|---|
| Retrieval and model only | 0.603 | 0.949 |
| Plus one review judge | 0.726 | 0.922 |
| **Full pipeline, no human involved** | **0.757** | **0.916** |
| Same, and the quote must also overlap the lawyers' highlighted passage | 0.703 | 0.850 |
| With a perfect human on the queue (upper bound, not measured) | 0.762 | 0.943 |

- **Decisions:** 1,505 accepted (1,139 real clauses), 273 rejected (12 real), 184 queued for a person (34 real).
- **Cost:** about 2,430 input tokens per question, against about 12,770 for the whole contract (the baseline comes from 9 contracts, so treat 81% as approximate).
- **Margin:** about plus or minus 0.02 on precision.
- **Scoring:** the headline counts an answer as right when the lawyers marked that clause in the contract; the stricter row also needs the quote to overlap their passage. Definitions and limits: [`docs/evaluation-protocol.md`](docs/evaluation-protocol.md). Every decision is committed in [`evals/final_test/`](evals/final_test/README.md) and recomputed by tests.

## How it works

```mermaid
flowchart LR
    Q[Contract and clause question] --> R[Hybrid retrieval: 10 excerpts]
    R --> M[Model extracts the clause and exact quotes]
    M --> V{Every quote word for word in the contract?}
    V -- no --> RT[Retry once]
    RT --> V2{Fixed?}
    V2 -- no --> H[(Human queue)]
    V -- yes --> G[Gate: closest of the 41 clauses, per-clause risk]
    V2 -- yes --> G
    G -- confident --> A[Accept]
    G -- doubtful --> J[Two judges]
    J -- both yes --> A
    J -- both no --> X[Reject]
    J -- disagree --> H
```

1. **Retrieval.** Postgres with pgvector: similarity to lawyers' examples plus learned keywords, merged by reciprocal rank fusion.
2. **Extraction.** One model call per clause returns a found flag, the value and exact quotes. The reply is parsed and validated, never trusted.
3. **Quote check.** A quote must appear in the contract word for word. A failure is retried once, then queued.
4. **Gate.** The quote is compared with lawyers' examples of all 41 clauses; a confident, low-risk answer is accepted.
5. **Two judges.** Doubtful answers go to two prompts. Both yes accepts, both no rejects, a split is queued.

The reasoning behind each choice is in the [decision records](docs/adr/README.md).

## Quick start

Requires Python 3.10 or newer and Docker.

```powershell
# 1. Install
python -m venv venv
.\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate
pip install -e ".[dev,api,demo]"

# 2. Configure: copy the template, then fill in LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DATABASE_URL, POSTGRES_PASSWORD
Copy-Item .env.example .env          # Linux/macOS: cp .env.example .env

# 3. Start Postgres 17 with pgvector (applies the schema on first start; port 5433 unless DB_PORT is set)
docker compose up -d db

# 4. Load and embed CUAD once (the embedding steps take a while)
python scripts/load_contracts.py
python scripts/load_clauses.py
python scripts/load_highlights.py
python scripts/load_chunks.py
python scripts/embed_chunks.py
python scripts/set_splits.py
python scripts/embed_highlights.py

# 5. Run the pipeline on a few validation contracts (calls the model, costs a little)
$env:SET="validation"; $env:LIMIT="5"; $env:K="10"
python -m cuad_ai pipeline
```

To open the results demo on your machine: `python -m streamlit run app/streamlit_app.py`.

The data is not in this repository: download CUAD v1 and put `CUADv1.json` and `test.json` in `data/`. Never commit `.env`.

## Usage

`python -m cuad_ai --help` lists the commands. `pipeline` runs every stage and prints the score table; each stage also runs alone.

| Command | What it does |
|---|---|
| `pipeline [run folder]` | All stages in order (extracts first when no folder is given) |
| `extract` | Retrieve excerpts, ask the model, verify and retry the quotes |
| `gate`, `route` | Compare quotes with the lawyers' examples; split into accept and review with the frozen risk table |
| `judge1`, `judge2` | The two judges (the second also sees lawyer examples) |
| `finalize` | Accept, reject or queue every question; writes `final.json` and `queue.json` |
| `freeze-risk` | Write `evals/risk_table.json` from validation runs |
| `serve` | Start the API (read-only unless `LIVE_API=1`; see Live review) |
| `live-admin` | Manage clients, who may sign in, API keys, the audit trail and expired uploads |
| `worker` | Process uploaded contracts from the live-review queue |

Runs land in `evals/runs/<run folder>/`. Identical model calls are cached in `evals/cache/` (set `NO_CACHE=1` to bypass).

**Run history and API.** `python scripts/load_run.py [run folder]` stores a run in Postgres, where the `run_scores` view recomputes precision and recall. `python -m cuad_ai serve` then exposes stored runs at `http://127.0.0.1:8000/docs`:

| Endpoint | Returns |
|---|---|
| `GET /health`, `GET /ready` | The process is up; the database answers |
| `GET /runs`, `GET /runs/{id}` | Stored runs with their scores and monitoring numbers |
| `GET /runs/{id}/queue` | The answers waiting for a person, with quotes and reasons |
| `GET /metrics` | Monitoring numbers of the latest run as Prometheus text |

Monitoring numbers need no lawyer labels: share accepted, rejected and queued, queue per contract, retry rate, invented-quote rate, and tokens and seconds per question.

## Live review

Upload a contract, watch the pipeline run on it, and confirm or reject each answer. It uses the same retrieval, quote check, gate, two judges and decision code as the saved run ([ADR 0008](docs/adr/0008-live-review-reuses-the-pipeline.md)). Uploads live in their own tables and never touch the example bank. If a file name starts with a CUAD company, that company's lawyer examples are left out, as they were for the test contracts.

**What the page shows:** a summary (accepted, needs review, rejected, not found), a color-coded table with the reason for each decision in plain words, the contract with the quote highlighted, both judges' verdicts, and Confirm / Reject buttons. A person's decision is stored next to the machine's, never over it. Results export to CSV, and each upload can be deleted with everything derived from it.

**Run it locally** (needs Postgres and the model settings from the quick start):

```powershell
docker compose up -d db                       # an older database gets the new tables automatically on first start of the page or worker
python -m cuad_ai worker                      # terminal 1: processes queued uploads (uses LLM_* from .env)
python -m streamlit run app/live_app.py       # terminal 2: upload, inspect, confirm or reject
```

Run directly like this, the page uses one private client named `local` and asks for your name. Sign-in and separate clients belong to the hosted version.

**Host it for clients** (Streamlit Community Cloud, a hosted Postgres, Google or Microsoft sign-in, your model key with daily caps): follow [`docs/deploy-live.md`](docs/deploy-live.md), [ADR 0009](docs/adr/0009-hosted-live-review.md) and [ADR 0010](docs/adr/0010-clients-sign-in-and-audit.md). Each client sees only its own contracts, only people on an allow-list can sign in, reviewer names are verified emails, and an audit trail records who did what. What is and is not protected is written down in [`docs/security.md`](docs/security.md). The hosted page has its own entry file, `deploy/live/streamlit_app.py`; the public demo stays read-only.

**Limits** (environment variables): `LIVE_MAX_CHARS` 400,000 characters per file, `LIVE_DAILY_CAP` 20 uploads per client per day, `LIVE_GLOBAL_DAILY_CAP` 100 across all clients, `LIVE_TOKEN_CAP` 400,000 tokens per upload, `LIVE_RETENTION_DAYS` 30 days before an upload is deleted (each client can have its own). Plain text only.

**From code:** set `LIVE_API=1`, make a key for a client with `python -m cuad_ai live-admin key CLIENT`, and start `python -m cuad_ai serve`. The endpoints `POST /submissions`, `GET /submissions/{id}`, `PUT /submissions/{id}/answers/{answer}/review` and `DELETE /submissions/{id}` then appear in `/docs` and need that key in an `X-API-Key` header. A key reaches only its own client's uploads.

> The 0.757 / 0.916 scores belong to the 102 CUAD test contracts. They do not describe how the system does on your contract. Skim accepted answers too: they are right about three times in four, not always.

## Keeping the result honest

Official train and test split. The example bank excludes every company that appears in the test set. Learned keywords and the per-clause risk table never use the contracts being scored (`evals/risk_table.json` is frozen). The test run needs `CONFIRM_TEST=yes` and was run once: do not re-run it to tune. Details: [`docs/evaluation-protocol.md`](docs/evaluation-protocol.md).

## Documentation

| Read | For |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Components, data model, data flow, operations |
| [`docs/evaluation-protocol.md`](docs/evaluation-protocol.md) | Splits, leakage rules, metric definitions, what is and is not measured |
| [`docs/security.md`](docs/security.md) | Who can see what, how clients are separated, what is recorded and what is not covered |
| [`docs/adr/`](docs/adr/README.md) | Ten decision records: what was chosen, why, and what it costs |
| [`notes/final_test_result.md`](notes/final_test_result.md) | The final result, controls and frozen settings |
| [`notes/`](notes/) | Design history: production design, routing, retrieval, earlier decisions |

## Development

```powershell
make check          # lint and tests, what CI runs (or: ruff check . ; python -m pytest -q)
pre-commit install  # optional: lint and secret check before each commit
```

Database tests skip when no database is reachable, so the suite runs on a fresh clone. CI runs lint and the full suite against a pgvector service on every push, on Python 3.10 and 3.12.

```
src/cuad_ai/   package: ingestion, search, extraction, validation, metrics, run storage, monitoring, API;
               pipeline/ holds the stages, live/ the upload review, cli.py the single command
app/           Streamlit pages: streamlit_app.py (results demo), live_app.py (live review)
deploy/live/   entry file, requirements and secrets template for the hosted live review
scripts/       data loaders, embedding jobs, run loader, analysis helpers
evals/         frozen risk table, split files, committed final-test evidence; run output is git-ignored
prompts/       extraction and judge prompts          sql/ docker/   schema, run tables, database init
tests/         unit tests with fake data; database tests roll back
docs/ notes/   current documentation; design history
```

## Limitations

- **Judges share a model,** so they can make the same mistake; the queue only catches disagreement. An informal check on one new, synthetic contract showed it: about 19 of 22 accepted answers were right, and the two clearly wrong ones had passed both judges. One contract is an anecdote, not a measurement.
- **Retrieval caps recall:** about 7% of lawyer-marked passages are not in the top 10 excerpts.
- **Labels are incomplete,** so some "false alarms" may be real clauses nobody marked.
- **Long quotes can be cut** by the 800-token output limit (7 of 4,182 here, all queued).
- **US commercial contracts only.** Other jurisdictions, languages and contract types are untested.
- **Hosted model:** prompts go to the provider. CUAD is public; do not send confidential contracts to a provider you have not vetted. Live uploads are also stored in your Postgres until deleted.

## Roadmap

Next: error analysis on the accepted-but-wrong answers, a different model for the second judge (measured on validation contracts only), comparing runs over time, and per-person sign-in for the hosted live review.

## License and citation

MIT, see [`LICENSE`](LICENSE). CUAD v1 is licensed CC BY 4.0. Hendrycks, Burns, Chen and Ball. *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review.* NeurIPS 2021.
