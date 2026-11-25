-- Live review: contracts uploaded by users. Separate tables, so nothing here can touch the CUAD example bank
-- (contracts, highlights, chunks) that the answers are judged against.

CREATE TABLE IF NOT EXISTS live_submissions (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    text TEXT NOT NULL,
    n_chars INT NOT NULL,
    sha256 TEXT NOT NULL,
    excluded_company TEXT,                      -- a CUAD company whose examples are left out (see ADR 0008)
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error TEXT,
    done_questions INT NOT NULL DEFAULT 0,
    total_questions INT NOT NULL DEFAULT 0,
    tokens_in INT NOT NULL DEFAULT 0,
    tokens_out INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS live_submissions_status_idx ON live_submissions (status, id);
CREATE INDEX IF NOT EXISTS live_submissions_sha_idx ON live_submissions (sha256);

CREATE TABLE IF NOT EXISTS live_chunks (
    id SERIAL PRIMARY KEY,
    submission_id INT NOT NULL REFERENCES live_submissions(id) ON DELETE CASCADE,
    start_char INT NOT NULL,
    end_char INT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(384),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    UNIQUE (submission_id, start_char)
);
CREATE INDEX IF NOT EXISTS live_chunks_tsv_idx ON live_chunks USING GIN (tsv);

CREATE TABLE IF NOT EXISTS live_answers (
    id SERIAL PRIMARY KEY,
    submission_id INT NOT NULL REFERENCES live_submissions(id) ON DELETE CASCADE,
    clause TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accept', 'reject', 'queue', 'not_found')),
    reason TEXT NOT NULL DEFAULT '',
    quotes JSONB NOT NULL DEFAULT '[]',
    spans JSONB NOT NULL DEFAULT '[]',          -- [[start, end], ...] where each verified quote sits in the contract
    risk REAL,
    rank_asked INT,
    verdict BOOLEAN,
    verdict2 BOOLEAN,
    looks_like JSONB NOT NULL DEFAULT '[]',
    retried BOOLEAN NOT NULL DEFAULT FALSE,
    tokens_in INT NOT NULL DEFAULT 0,
    tokens_out INT NOT NULL DEFAULT 0,
    UNIQUE (submission_id, clause)
);

-- A person's decision on one answer. One row per answer: changing your mind replaces it.
CREATE TABLE IF NOT EXISTS live_reviews (
    answer_id INT PRIMARY KEY REFERENCES live_answers(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('confirm', 'reject')),
    note TEXT NOT NULL DEFAULT '',
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- Clients (tenants), sign-in allow-list and audit trail. Added in ADR 0010; every statement is additive. ----

-- A client of the service. Its people can only ever see its own uploads.
CREATE TABLE IF NOT EXISTS live_tenants (
    id TEXT PRIMARY KEY CHECK (id ~ '^[a-z0-9][a-z0-9_-]{0,39}$'),
    name TEXT NOT NULL,
    retention_days INT NOT NULL DEFAULT 30 CHECK (retention_days >= 1),   -- uploads older than this are deleted
    daily_cap INT CHECK (daily_cap >= 0),                                  -- NULL = the global default
    api_key_sha256 TEXT UNIQUE,                                            -- only the hash of the key is kept
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Who may sign in, and for which client. One email belongs to exactly one client.
CREATE TABLE IF NOT EXISTS live_users (
    email TEXT PRIMARY KEY CHECK (email = lower(email)),
    tenant TEXT NOT NULL REFERENCES live_tenants(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uploads made before clients existed fall under 'legacy'. Nobody can sign in to it.
ALTER TABLE live_submissions ADD COLUMN IF NOT EXISTS tenant TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE live_submissions ADD COLUMN IF NOT EXISTS uploaded_by TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS live_submissions_tenant_idx ON live_submissions (tenant, id DESC);
CREATE INDEX IF NOT EXISTS live_submissions_tenant_sha_idx ON live_submissions (tenant, sha256);

-- Who did what, when. Keeps the file name, never the contract text. Survives deleting the upload.
CREATE TABLE IF NOT EXISTS live_audit (
    id BIGSERIAL PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tenant TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    submission_id INT,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS live_audit_tenant_idx ON live_audit (tenant, id DESC);
