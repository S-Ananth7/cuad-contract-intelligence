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