from collections import Counter
from pathlib import Path

import pytest

from demo_data import (
    contracts,
    for_contract,
    load_decisions,
    load_extraction_summary,
    load_queue,
    queue_reasons,
    score,
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
