# CUAD Contract Intelligence

Finds 41 types of clauses in commercial contracts, quotes the exact sentence, proves the quote exists word for word, and sends only the doubtful cases to a person. Built and scored on the lawyer-annotated [CUAD v1](https://www.atticusprojectai.org/cuad) dataset (510 contracts).

## Result

Scored once on the 102 official test contracts (4,182 questions), after the design was frozen. Details and the controls that keep it honest: [`notes/final_test_result.md`](notes/final_test_result.md). The decision behind every number is committed in [`evals/final_test/`](evals/final_test/) and recomputed by a test.

| Stage | Precision | Recall |
|---|---|---|
| Retrieval and model only | 0.603 | 0.949 |
| Plus one review judge | 0.726 | 0.922 |
| **Full pipeline, no human involved** | **0.757** | **0.916** |
| If a person resolved the queue perfectly (upper bound, not measured) | 0.762 | 0.943 |

- Precision is the share of accepted answers that match a lawyer label. Recall is the share of lawyer-marked clauses that were accepted.
- Of 4,182 questions, 1,505 were accepted automatically, 273 rejected, and 184 queued for a person (about 1.8 per contract). Only 12 of the 273 rejected answers were real clauses.
- Precision has a margin of error of about 0.02. Invented quotes in the whole test run: 3.
- Cost: about 2,430 input tokens per question, against about 12,770 when the whole contract is sent (roughly 81% less; the whole-contract figure comes from 9 contracts).
- Weakest clauses: Price Restrictions, Third Party Beneficiary, Post-Termination Services, Uncapped Liability, Volume Restriction.

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

1. **Retrieval.** Postgres with pgvector. Keyword search, a search by similarity to lawyers' examples, and reciprocal rank fusion pick 10 excerpts. Header clauses (title, parties, dates) also get the first chunks of the contract.
2. **Extraction.** One model call per clause returns a found flag, the value, and exact quotes. The reply is parsed and validated, never trusted.
3. **Deterministic quote check.** A quote must appear in the contract word for word (spacing and line breaks ignored). A found answer without a verified quote is retried once, then queued.
4. **Gate.** The quote is compared with the lawyers' examples of all 41 clauses. If the asked clause is the closest and its historical false-alarm rate is low, the answer is accepted.
5. **Two judges.** Doubtful answers are reviewed by two independent prompts. Both yes accepts, both no rejects, a split goes to the queue.
6. **Queue.** `queue.json` lists what a person should look at and why.

**Leakage controls.** Official train and test split; the example bank excludes any company that appears in the test set; learned keywords and the per-clause risk table use training and validation contracts only (`evals/risk_table.json` is frozen); the test run is behind `CONFIRM_TEST=yes` and was run once. Do not re-run it to tune: that would invalidate the result.

## Quick start

Requires Python 3.10 or newer and Docker (for Postgres with pgvector).

```
python -m venv venv
.\venv\Scripts\Activate.ps1        # Linux/macOS: source venv/bin/activate
pip install -e ".[dev]"
Copy-Item .env.example .env        # Linux/macOS: cp .env.example .env
```

1. **Settings.** Fill in `.env`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `DATABASE_URL`, `POSTGRES_PASSWORD`. Never commit `.env`.
2. **Data.** Download the CUAD v1 release and put `CUADv1.json` and `test.json` in `data/`. The data is not in this repo.
3. **Database.** `docker compose up -d db` starts Postgres 17 with pgvector and applies `sql/schema.sql` on first start. Compose uses port 5433 by default (`DB_PORT` changes it).
4. **Load and embed** (once; the embedding steps take a while):

```
python scripts/load_contracts.py
python scripts/load_clauses.py
python scripts/load_highlights.py
python scripts/load_chunks.py
python scripts/embed_chunks.py
python scripts/set_splits.py
python scripts/embed_highlights.py
```

5. **Run the pipeline** on a few validation contracts (this calls the model and costs a little):

```
$env:SET="validation"; $env:LIMIT="5"; $env:K="10"
python -m cuad_ai pipeline
```

`pipeline` runs extraction, the gate, both judges and the final decision, and prints the score table. Results land in `evals/runs/<run folder>/`. Identical model calls are cached in `evals/cache/`; set `NO_CACHE=1` to bypass it.

Every stage also runs alone, and `python -m cuad_ai --help` lists them:

| Command | Stage |
|---|---|
| `extract` | Retrieve excerpts, ask the model, verify and retry the quotes |
| `gate` | Compare each quote with the lawyers' examples of all 41 clauses |
| `route` | Split answers into accept and review using the frozen risk table |
| `judge1`, `judge2` | The two judges (the second also sees lawyer examples) |
| `finalize` | Accept, reject or queue every question and print the scores |
| `freeze-risk` | Write `evals/risk_table.json` from validation runs |

6. **Keep the run in Postgres** (optional). `python scripts/load_run.py evals/runs/<run folder>` stores the run so runs can be compared with SQL; with no argument it loads the committed final test run. The `run_scores` view recomputes accepted, rejected, queued, precision and recall from the stored answers.

## Development

| Task | Command |
|---|---|
| Install with dev tools | `pip install -e ".[dev]"` |
| Lint | `ruff check .` |
| Tests | `python -m pytest -q` |
| Both (what CI runs) | `make check` |

Database tests skip when no database is reachable, so the suite runs on a fresh clone. CI (`.github/workflows/ci.yml`) runs lint and the full suite against a pgvector service on every push. Optional: `pre-commit install` for a lint and secret check before each commit.

## Repository layout

```
src/cuad_ai/   package: data loading, ingestion, embeddings, search, extraction, validation, metrics, settings,
               run storage; pipeline/ holds the stages and cli.py the single command (python -m cuad_ai)
scripts/       data loaders, embedding jobs, run loader, analysis helpers
evals/         baseline and earlier experiment runners, frozen risk table, split files, run log (results.md);
               run output is git-ignored
prompts/       extraction and judge prompts
sql/           database schema (schema.sql) and run history tables (runs.sql)
docker/        database initialisation
tests/         unit tests with fake data; database tests roll back
notes/         design decisions, evaluation protocol, final test result
```

## Documentation

| Read | For |
|---|---|
| [`notes/final_test_result.md`](notes/final_test_result.md) | The result, the controls, the frozen settings |
| [`notes/production_design.md`](notes/production_design.md) | The production design and decision policy |
| [`notes/routing_and_review.md`](notes/routing_and_review.md) | Gate, risk table, two judges, queue |
| [`notes/ingestion_and_retrieval.md`](notes/ingestion_and_retrieval.md) | Database, split rules, retrieval |
| [`notes/decisions.md`](notes/decisions.md) | Earlier decisions and the reasoning behind them |

## Limitations

- **Truncated quotes.** An 800-token output cap cuts very long quotes, which show up as parse failures or unverified quotes (7 of 4,182 here, all queued).
- **Correlated judges.** Both judges use the same model, so they can make the same mistake. The queue only catches disagreement.
- **Incomplete labels.** CUAD labels are not exhaustive; some "false alarms" may be real clauses the lawyers did not mark, so true precision may be higher.
- **Narrow data.** US commercial contracts only. Other jurisdictions, languages and contract types are untested.
- **Margins.** Per-clause scores for rare clauses rest on few examples and are noisy.
- **Hosted model.** Prompts go to the model provider. CUAD is public, so that is fine here; do not send confidential contracts to a provider you have not vetted.

## Roadmap

Done: evaluation, retrieval, extraction, quote verification, routing, judges, retry, human queue, tests, one place for settings, CI, Docker, run history in Postgres, pipeline in the package behind one command. Next: a thin API and basic monitoring (queue rate, invented-quote rate, tokens per question).

## License and citation

MIT, see `LICENSE`. CUAD v1 is licensed CC BY 4.0. Hendrycks, Burns, Chen and Ball. *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review.* NeurIPS 2021.
