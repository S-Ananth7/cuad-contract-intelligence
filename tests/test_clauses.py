from cuad_ai.clauses import (
    clause_questions, company, coverage_sample, make_clause_prompt, positives_by_clause,
)


def fake(title, present, names=("Common", "Rare")):
    return {"title": title, "paragraphs": [{"context": "x", "qas": [
        {"id": f"{title}__{name}", "question": f"Q about {name}",
         "is_impossible": name not in present, "answers": []}
        for name in names]}]}


CONTRACTS = [
    fake("A_1", {"Common", "Rare"}),
    fake("B_1", {"Common"}),
    fake("C_1", {"Common"}),
    fake("D_1", {"Common"}),
    fake("T_1", {"Common", "Rare"}),
    fake("T_2", {"Common", "Rare"}),
]


def test_clause_questions_reads_names_and_questions():
    assert clause_questions(CONTRACTS) == {"Common": "Q about Common", "Rare": "Q about Rare"}


def test_prompt_is_filled_and_json_braces_survive():
    template = 'Clause: [CLAUSE]. Look for: [QUESTION]. Return {"found": false}'
    assert make_clause_prompt(template, "Cap On Liability", "Is it capped?") == (
        'Clause: Cap On Liability. Look for: Is it capped?. Return {"found": false}'
    )


def test_company_is_the_part_before_the_first_underscore():
    assert company("ABCINC_20200101_8-K_EX-10") == "ABCINC"


def test_positives_by_clause():
    assert positives_by_clause(CONTRACTS)["Rare"] == {"A_1", "T_1", "T_2"}


def test_coverage_sample_keeps_rare_examples_and_avoids_excluded_companies():
    chosen = coverage_sample(CONTRACTS, {"T_1"}, per_clause=1, total=3, seed=1)
    assert "A_1" in chosen
    assert not any(company(title) == "T" for title in chosen)
    assert len(chosen) == 3 and len(set(chosen)) == 3
