from cuad_ai.clauses import clause_questions


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
