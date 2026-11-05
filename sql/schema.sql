CREATE TABLE IF NOT EXISTS contracts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    company TEXT NOT NULL,
    n_chars INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clauses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    question TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS highlights (
    id SERIAL PRIMARY KEY,
    contract_id INT NOT NULL REFERENCES contracts(id),
    clause_id INT NOT NULL REFERENCES clauses(id),
    start_char INT NOT NULL,
    end_char INT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    contract_id INT NOT NULL REFERENCES contracts(id),
    start_char INT NOT NULL,
    end_char INT NOT NULL,
    text TEXT NOT NULL,
    UNIQUE (contract_id, start_char)
);

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_model TEXT;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);

ALTER TABLE contracts ADD COLUMN IF NOT EXISTS official_split TEXT;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS shares_company_with_test BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE highlights ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS embedding_model TEXT;