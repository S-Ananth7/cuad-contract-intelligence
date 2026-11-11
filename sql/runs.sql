-- Run history: one row per finished run, one row per answer.
-- Titles and clause names are stored as text, not as ids, so a run stays readable
-- even if the contracts table is reloaded and its ids change.

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    run_date DATE,
    model TEXT,
    template TEXT,
    k INT,
    contracts INT,
    git_commit TEXT,
    prompt_hash TEXT,
    meta JSONB NOT NULL,
    summary JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS answers (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    clause TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accept', 'reject', 'queue', 'not_found')),
    reason TEXT NOT NULL DEFAULT '',
    gold_found BOOLEAN NOT NULL,
    retried BOOLEAN NOT NULL DEFAULT FALSE,
    quotes JSONB NOT NULL DEFAULT '[]',
    looks_like JSONB NOT NULL DEFAULT '[]',
    PRIMARY KEY (run_id, title, clause)
);

CREATE INDEX IF NOT EXISTS answers_decision_idx ON answers (run_id, decision);

-- The headline numbers, computed from the rows. gold_found is the lawyers' label.
CREATE OR REPLACE VIEW run_scores AS
SELECT
    run_id,
    count(*) AS questions,
    count(*) FILTER (WHERE decision = 'accept') AS accepted,
    count(*) FILTER (WHERE decision = 'accept' AND gold_found) AS accepted_real,
    count(*) FILTER (WHERE decision = 'reject') AS rejected,
    count(*) FILTER (WHERE decision = 'reject' AND gold_found) AS rejected_real,
    count(*) FILTER (WHERE decision = 'queue') AS queued,
    count(*) FILTER (WHERE decision = 'queue' AND gold_found) AS queued_real,
    count(*) FILTER (WHERE decision = 'not_found') AS not_found,
    count(*) FILTER (WHERE gold_found) AS lawyer_marked,
    round(count(*) FILTER (WHERE decision = 'accept' AND gold_found)::numeric
          / nullif(count(*) FILTER (WHERE decision = 'accept'), 0), 3) AS accept_precision,
    round(count(*) FILTER (WHERE decision = 'accept' AND gold_found)::numeric
          / nullif(count(*) FILTER (WHERE gold_found), 0), 3) AS accept_recall
FROM answers
GROUP BY run_id;
