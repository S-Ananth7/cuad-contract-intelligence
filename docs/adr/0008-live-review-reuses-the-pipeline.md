# 0008. Live review runs the same pipeline on uploads, in separate tables, behind a queue

Status: accepted

## Context

The saved test run shows what the system does on 102 known contracts. A user also needs to try it on a contract of their own, see where each answer comes from, and confirm or reject it. A web request cannot run 41 questions with up to three model calls each, and uploads must never be able to change the example bank that answers are judged against.

## Decision

- **Same code, not a copy.** An upload goes through the functions the test run uses: `search.fuse` (retrieval), `extract_with_retry`, the gate and `route.decide`, both judges, and `finalize.decide`. A test checks that live retrieval picks the same excerpts as `search_hybrid`.
- **Separate tables** (`live_submissions`, `live_chunks`, `live_answers`, `live_reviews` in `sql/live.sql`). Nothing writes to `contracts`, `highlights` or `chunks`.
- **Leakage guard.** If the file name starts with the name of a CUAD company, that company's examples are left out of retrieval, the gate, judge 2 and the learned keywords, as for the test contracts.
- **A Postgres job queue.** The upload is stored and queued; a worker claims it with `FOR UPDATE SKIP LOCKED`. A job whose worker stopped (no heartbeat for 10 minutes) goes back in the queue. Questions of one upload run in parallel, each with its own connection.
- **Limits and a key.** File size, uploads per day and tokens per upload are capped. The HTTP endpoints exist only when `LIVE_API_KEY` is set and every call must send it. The model key stays in the environment.
- **A person's decision is stored next to the machine's**, never over it: `live_reviews` is a separate row, one per answer, replaced when the reviewer changes their mind.
- **No on-disk response cache** for live calls, so contract text is not copied into cache files.

## Consequences

- Live answers have the same checks as the measured run, but **no accuracy number applies to a user's contract**: the 0.757 / 0.916 figures are for the 102 CUAD test contracts only.
- Uploaded text is stored in Postgres and sent to the model provider. Delete removes the upload and everything derived from it, but not what the provider keeps. Do not upload confidential contracts to a provider you have not vetted.
- Matching a CUAD company by file name is a heuristic: a renamed copy of a CUAD contract would not be excluded.
- Duplicate uploads (same text) reuse the earlier result, so they cost nothing.
- Plain text only (`.txt`). PDF and Word extraction is not included.

## Alternatives considered

- **Run the pipeline inside the web request:** times out and has no recovery.
- **A broker such as Celery or Redis:** another service to run; Postgres already gives a safe queue at this size.
- **Write uploads into the CUAD tables:** would let a user's contract change retrieval and the risk of later answers.
