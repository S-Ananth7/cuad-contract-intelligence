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