from collections import Counter
from pathlib import Path

import pytest

from demo_data import (
    contracts,
    evidence_for,
    for_contract,
    load_decisions,
    load_evidence,
    load_extraction_summary,
    load_queue,
    queue_reasons,
    score,
    verdict_text,
)

RUN = Path(__file__).resolve().parents[1] / "evals" / "final_test"


@pytest.fixture(scope="module")
def rows():
    return load_decisions(RUN)


def test_shape_of_the_final_run(rows):
    assert len(rows) == 4182
    assert len(contracts(rows)) == 102
    sizes = Counter(len(for_contract(rows, t)) for t in contracts(rows))
    assert sizes == {41: 102}  # every contract has all 41 clauses


def test_score_matches_the_readme(rows):
    assert score(rows) == {
        "accepted": 1505,
        "accepted_real": 1139,
        "lawyer_marked": 1244,
        "precision": 0.757,
        "recall": 0.916,
    }


def test_review_queue():
    queue = load_queue(RUN)
    assert len(queue) == 184
    assert queue_reasons(queue) == [("judges_disagree", 177), ("parse_failed", 4), ("quote_unverified", 3)]


def test_queue_rows_always_have_lists():
    queue = load_queue(RUN)
    assert all(isinstance(r["quotes"], list) and isinstance(r["looks_like"], list) for r in queue)
    assert all(isinstance(name, str) for r in queue for name in r["looks_like"])  # no empty entries to join
    assert sum(1 for r in queue if not r["quotes"]) == 4  # the parse failures


def test_extraction_only_rung():
    assert load_extraction_summary(RUN) == {"precision": 0.603, "recall": 0.949}


def test_empty_run_does_not_divide_by_zero():
    assert score([]) == {"accepted": 0, "accepted_real": 0, "lawyer_marked": 0, "precision": 0.0, "recall": 0.0}


def test_missing_file_names_the_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="decisions.json"):
        load_decisions(tmp_path)


def test_bad_json_is_a_clear_error(tmp_path):
    (tmp_path / "decisions.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_decisions(tmp_path)


def test_missing_key_names_the_row_and_key(tmp_path):
    (tmp_path / "decisions.json").write_text('[{"title": "a"}]', encoding="utf-8")
    with pytest.raises(ValueError, match=r"row 0 is missing.*clause"):
        load_decisions(tmp_path)


def test_evidence_covers_every_accepted_answer_and_every_lawyer_passage(rows):
    evidence = load_evidence(RUN)
    accepted = [r for r in rows if r["decision"] == "accept"]
    assert all(evidence_for(evidence, r["title"], r["clause"])["quotes"] for r in accepted)
    with_gold = sum(bool(evidence_for(evidence, r["title"], r["clause"])["gold"]) for r in rows)
    assert with_gold == 1244  # the lawyer-marked count


def test_the_page_comparison_sentences(rows):
    quoted = {"quotes": ["q"], "gold": ["g"]}
    assert verdict_text({"decision": "accept", "quote_match": True}, quoted) == "The quote matches one of the lawyers' passages."
    assert "different passage" in verdict_text({"decision": "accept", "quote_match": False}, quoted)
    assert "did not mark" in verdict_text({"decision": "accept", "quote_match": False}, {"quotes": ["q"], "gold": []})
    assert verdict_text({"decision": "not_found", "quote_match": False}, {"quotes": [], "gold": ["g"]}).startswith("Missed")
    assert verdict_text({"decision": "not_found", "quote_match": False}, {"quotes": [], "gold": []}) == "Correctly not found."
    assert verdict_text({"decision": "queue", "quote_match": False}, {"quotes": [], "gold": []}) == "No quote was produced."


def test_unknown_clause_has_empty_evidence():
    assert evidence_for({}, "nope", "nope") == {"quotes": [], "gold": []}


def test_missing_evidence_file_names_the_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="evidence.json.gz"):
        load_evidence(tmp_path)


def test_damaged_evidence_file_is_a_clear_error(tmp_path):
    (tmp_path / "evidence.json.gz").write_bytes(b"not gzip")
    with pytest.raises(ValueError, match="not valid gzip JSON"):
        load_evidence(tmp_path)
