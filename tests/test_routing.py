import json
import sys

import pytest

import route_answers as ra


def row(clause="Governing Law", rank=1, risk=0.1):
    return {"clause": clause, "rank_asked": rank, "risk": risk}


def test_closest_clause_with_low_risk_is_accepted():
    assert ra.decide(row(rank=1, risk=0.2)) == "accept"


def test_closest_clause_at_the_risk_limit_is_still_accepted():
    assert ra.decide(row(rank=1, risk=ra.RISK_LIMIT)) == "accept"


def test_closest_clause_with_high_risk_goes_to_review():
    assert ra.decide(row(rank=1, risk=0.51)) == "review"


def test_a_clause_that_is_not_the_closest_goes_to_review_even_if_low_risk():
    assert ra.decide(row(rank=2, risk=0.0)) == "review"


def test_a_missing_rank_goes_to_review():
    assert ra.decide(row(rank=None, risk=0.0)) == "review"


@pytest.mark.parametrize("clause", ["Document Name", "Agreement Date"])
def test_titles_and_dates_are_always_accepted(clause):
    assert ra.decide(row(clause=clause, rank=15, risk=0.99)) == "accept"


def test_risk_of_a_rare_clause_is_pulled_toward_the_overall_rate():
    risk = ra.smoothed({"A": [1, 1], "B": [99, 0]})
    assert risk("A") == pytest.approx((1 + 0.01 * 3) / (1 + 3))


def test_an_unseen_clause_gets_the_overall_rate():
    risk = ra.smoothed({"A": [10, 5], "B": [10, 1]})
    assert risk("never seen") == pytest.approx(0.3)


def test_risk_function_counts_false_alarms_in_the_rows_it_is_given():
    rows = [{"clause": "A", "gold_found": False}, {"clause": "A", "gold_found": True},
            {"clause": "B", "gold_found": True}]
    risk = ra.risk_function(rows)
    assert risk("A") == pytest.approx((1 + (1 / 3) * 3) / (2 + 3))


def test_half_split_routing_never_uses_a_contracts_own_answers():
    rows = [{"title": "a", "clause": "X", "gold_found": False, "rank_asked": 1},
            {"title": "b", "clause": "X", "gold_found": True, "rank_asked": 1}]
    by_title = {r["title"]: r for r in ra.route(rows)}
    assert by_title["a"]["risk"] == 0.0
    assert by_title["b"]["risk"] == 1.0


def test_frozen_risk_reads_counts_from_a_file(tmp_path):
    path = tmp_path / "risk_table.json"
    path.write_text(json.dumps({"A": [10, 5], "B": [10, 1]}), encoding="utf-8")
    risk = ra.frozen_risk(path)
    assert risk("A") == pytest.approx((5 + 0.3 * 3) / (10 + 3))


def test_frozen_routing_does_not_look_at_the_lawyer_labels(tmp_path, monkeypatch):
    table = tmp_path / "risk.json"
    table.write_text(json.dumps({"X": [10, 5]}), encoding="utf-8")

    def routed(name, gold):
        folder = tmp_path / name
        folder.mkdir()
        rows = [{"title": "t", "clause": "X", "rank_asked": 1, "gold_found": gold}]
        (folder / "gate_features.json").write_text(json.dumps(rows), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["route_answers.py", str(folder), str(table)])
        ra.main()
        return json.loads((folder / "routing.json").read_text(encoding="utf-8"))[0]

    real, false = routed("real", True), routed("false", False)
    assert real["risk"] == false["risk"]
    assert real["route"] == false["route"]
