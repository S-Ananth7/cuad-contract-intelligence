import random


def clause_name(qa_id: str) -> str:
    """The clause name is the part of the id after the last double underscore."""
    return qa_id.rsplit("__", 1)[-1]


def company(title: str) -> str:
    return title.split("_")[0]


def clause_questions(contracts: list[dict]) -> dict[str, str]:
    """Clause name -> the dataset's own question text, read from the first contract."""
    return {clause_name(qa["id"]): qa["question"] for qa in contracts[0]["paragraphs"][0]["qas"]}


def make_clause_prompt(template: str, clause: str, question: str) -> str:
    """Fill the template. Uses replace, so the braces in the JSON example are safe."""
    return template.replace("[CLAUSE]", clause).replace("[QUESTION]", question)


def positives_by_clause(contracts: list[dict]) -> dict[str, set]:
    """Clause name -> titles of contracts where the lawyers marked it."""
    found = {}
    for contract in contracts:
        for qa in contract["paragraphs"][0]["qas"]:
            titles = found.setdefault(clause_name(qa["id"]), set())
            if not qa["is_impossible"]:
                titles.add(contract["title"])
    return found


def coverage_sample(contracts, exclude_titles, per_clause=5, total=60, seed=7) -> list[str]:
    """Pick contracts so every clause has about `per_clause` examples. Rarest clauses first.
    Never picks an excluded title, or a contract from the same company as one."""
    banned = {company(t) for t in exclude_titles}
    pool = {c["title"] for c in contracts if c["title"] not in exclude_titles and company(c["title"]) not in banned}
    positives = {clause: titles & pool for clause, titles in positives_by_clause(contracts).items()}
    rng = random.Random(seed)
    chosen, chosen_set = [], set()
    for clause in sorted(positives, key=lambda name: len(positives[name])):
        have = len(positives[clause] & chosen_set)
        candidates = sorted(positives[clause] - chosen_set)
        rng.shuffle(candidates)
        for title in candidates[: max(0, per_clause - have)]:
            chosen.append(title)
            chosen_set.add(title)
    rest = sorted(pool - chosen_set)
    rng.shuffle(rest)
    for title in rest:
        if len(chosen) >= total:
            break
        chosen.append(title)
    return chosen
