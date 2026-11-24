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
