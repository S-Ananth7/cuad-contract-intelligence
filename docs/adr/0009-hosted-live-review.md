# 0009. Host the live review on Streamlit Cloud with a hosted Postgres and an in-page worker

Status: accepted. The access decision (one shared code) is replaced by [ADR 0010](0010-clients-sign-in-and-audit.md).

## Context

A client needs to upload their own contracts without installing anything. [ADR 0008](0008-live-review-reuses-the-pipeline.md) built the live review for a local machine: Postgres, a separate worker and a model key. Streamlit Community Cloud only runs the page: it has no database and no background process.

## Decision

- **Database:** a hosted Postgres with pgvector (Neon). Only the example bank is copied to it (`contracts`, `clauses`, `highlights` with vectors, by `scripts/copy_bank.py`), not the 510 contracts' text or chunks, because the live pipeline needs nothing else.
- **Worker:** the same loop as `cuad worker` (`worker.run_loop`) runs in a background thread started by the hosted page. It asks the database for work only while the page was used in the last 30 minutes, so an idle deployment does not keep a free database awake. The queue already survives restarts and recovers stuck jobs, so a sleeping app loses nothing.
- **Access:** one shared access code in the app's secrets, compared in constant time. With no code configured the page stays closed. The code gates the page; it is not per-person authentication.
- **Cost and privacy limits:** the owner's model key with the daily upload cap, per-upload token cap and file-size cap already in the live review.
- **A separate Streamlit app and requirements file** (`deploy/live/`), so the public read-only demo keeps its small dependency list and cannot be affected by this one.

## Consequences

- The client can use the pipeline from a URL, and the owner pays for model tokens, bounded by the caps.
- A shared code means no record of which person did what; reviewer names are typed, not verified. Fine for one client, not for several.
- Processing speed depends on Streamlit Cloud's small machine and the embedding model download on first start.
- The client's contract text reaches the model provider and the hosted database. This needs the client's agreement.
- A production rollout for several customers should move the worker to its own service and add real sign-in.

## Alternatives considered

- **Docker on Render, Fly or Railway:** more robust, costs money and needs more setup; the right next step if this becomes a product.
- **The client brings their own model key:** removes the owner's cost, adds friction and key handling.
- **A public link with no login:** anyone could spend the owner's tokens.
