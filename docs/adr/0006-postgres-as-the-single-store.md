# 0006. Keep data, vectors, full text and run history in one Postgres

Status: accepted

## Context

The system needs contract text, lawyer highlights, chunk vectors, keyword search and a record of every run.

## Decision

Use Postgres 17 with pgvector. Chunks carry a 384-number vector and a generated full-text column with a GIN index. Run history lives in `runs` and `answers`, with a `run_scores` view that recomputes the headline numbers.

## Consequences

- One service to run locally (Docker) and in CI, and one query language for search and for comparing runs.
- Hybrid retrieval happens in the same database as the data, so a contract and its chunks cannot drift apart.
- Scale limits are untested beyond 33,809 chunks.

## Alternatives considered

- A separate vector database plus a search engine: more moving parts for this size of data.
- Files only: no queries over runs, and retrieval would need its own index.
