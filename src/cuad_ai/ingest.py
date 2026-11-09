from cuad_ai.clauses import clause_name, clause_questions


def contract_row(contract) -> dict:
    title = contract["title"]
    text = contract["paragraphs"][0]["context"]
    company = title.split("_")[0]
    return {
        "title": title,
        "company": company,
        "n_chars": len(text),
    }

    
def insert_contracts(conn, rows):
    sql = "INSERT INTO contracts (title, company, n_chars) VALUES (%s, %s, %s)"
    for row in rows:
        conn.execute(sql, (row["title"], row["company"], row["n_chars"]))


def clause_rows(contracts):
    questions = clause_questions(contracts)
    return [{"name": name, "question": question} for name, question in questions.items()]


def insert_clauses(conn, rows):
    sql = "INSERT INTO clauses (name, question) VALUES (%s, %s)"
    for row in rows:
        conn.execute(sql, (row["name"], row["question"]))


def highlight_rows(contract):
    rows = []
    title = contract["title"]
    for qa in contract["paragraphs"][0]["qas"]:
        clause = clause_name(qa["id"])
        for answer in qa["answers"]:
            start = answer["answer_start"]
            end = start + len(answer["text"])
            rows.append({
                "title": title,
                "clause": clause,
                "start_char": start,
                "end_char": end,
                "text": answer["text"]
            })
    return rows


def insert_highlights(conn, rows):
    sql = (
    "INSERT INTO highlights (contract_id, clause_id, start_char, end_char, text) "
    "VALUES ((SELECT id FROM contracts WHERE title = %s), "
    "(SELECT id FROM clauses WHERE name = %s), %s, %s, %s)"
)
    for row in rows:
        conn.execute(sql, (row["title"], row["clause"], row["start_char"], row["end_char"], row["text"]))  


def chunk_spans(text, size=1000, overlap=200):
    """cut text into (start, end) spans of about `size` characters, overlapping by `overlap`."""
    spans = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            cut = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if cut > start + size // 2:
                end = cut
        spans.append((start, end))
        if end >= n:
            break
        start = end - overlap
    return spans


def chunk_rows(contract, size=1000, overlap=200):
    title = contract["title"]
    text = contract["paragraphs"][0]["context"]
    return [
        {"title": title, "start_char": s, "end_char": e, "text": text[s:e]}
        for s, e in chunk_spans(text, size, overlap)
    ]

    
def insert_chunks(conn, rows):
    sql = (
        "INSERT INTO chunks (contract_id, start_char, end_char, text) "
        "VALUES ((SELECT id FROM contracts WHERE title = %s), %s, %s, %s)"
    )
    params = [(r["title"], r["start_char"], r["end_char"], r["text"]) for r in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, params)
