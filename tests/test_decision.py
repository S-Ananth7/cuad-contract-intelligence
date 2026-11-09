import json
import sys

import final_answers as fa
import pytest
import run_rag


def report_row(**changes):
    row = {"error": None, "unsolved": False, "found": True, "quotes": ["q"], "retried": False}
    row.update(changes)
    return row


def answer(route="review", verdict=True, verdict2=True):
    return {"route": route, "verdict": verdict, "verdict2": verdict2, "looks_like": None, "looks_like2": None}


def test_a_reply_that_never_parsed_goes_to_the_queue():
    row = report_row(error="parse failed", found=None)
    assert fa.decide(row, None) == ("queue", "parse_failed")


def test_a_quote_still_unverified_after_the_retry_goes_to_the_queue():
    assert fa.decide(report_row(unsolved=True), answer()) == ("queue", "quote_unverified")


def test_an_error_wins_over_everything_else():
    row = report_row(error="parse failed", unsolved=True, found=None)
    assert fa.decide(row, answer(route="accept")) == ("queue", "parse_failed")


def test_not_found_stays_not_found():
    assert fa.decide(report_row(found=False), None) == ("not_found", "")


def test_found_without_a_quote_is_rejected():
    assert fa.decide(report_row(), None) == ("reject", "no_quote")


def test_a_routed_accept_is_accepted_without_the_judges():
    assert fa.decide(report_row(), answer(route="accept", verdict=False, verdict2=False))[0] == "accept"


def test_both_judges_yes_is_accepted():
    assert fa.decide(report_row(), answer(verdict=True, verdict2=True)) == ("accept", "both_judges_yes")


def test_both_judges_no_is_rejected():
    assert fa.decide(report_row(), answer(verdict=False, verdict2=False)) == ("reject", "both_judges_no")


@pytest.mark.parametrize("first, second", [(True, False), (False, True)])
def test_judges_that_disagree_go_to_the_queue(first, second):
    assert fa.decide(report_row(), answer(verdict=first, verdict2=second)) == ("queue", "judges_disagree")


def test_an_unreadable_judge_reply_does_not_count_as_a_no():
    assert fa.decide(report_row(), answer(verdict=None, verdict2=True)) == ("accept", "both_judges_yes")


def test_final_step_counts_queued_answers_as_not_kept(tmp_path, capsys, monkeypatch):
    report = [
        {"title": "t", "clause": "A", "found": True, "error": None, "unsolved": False, "gold_found": True, "quotes": ["q"]},
        {"title": "t", "clause": "B", "found": True, "error": None, "unsolved": False, "gold_found": False, "quotes": ["q"]},
        {"title": "t", "clause": "C", "found": False, "error": None, "unsolved": False, "gold_found": False, "quotes": []},
        {"title": "t", "clause": "D", "found": None, "error": "parse failed", "unsolved": False, "gold_found": True, "quotes": []},
    ]
    answers = [
        {"title": "t", "clause": "A", "route": "accept"},
        {"title": "t", "clause": "B", "route": "review", "verdict": True, "verdict2": False,
         "looks_like": "x", "looks_like2": "y"},
    ]
    (tmp_path / "report.json").write_text(json.dumps({"rows": report}), encoding="utf-8")
    (tmp_path / "verified_examples.json").write_text(json.dumps(answers), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["final_answers.py", str(tmp_path)])

    fa.main()

    final = {r["clause"]: r["decision"] for r in json.loads((tmp_path / "final.json").read_text(encoding="utf-8"))}
    queue = json.loads((tmp_path / "queue.json").read_text(encoding="utf-8"))
    assert final == {"A": "accept", "B": "queue", "C": "not_found", "D": "queue"}
    assert sorted(item["clause"] for item in queue) == ["B", "D"]
    headline = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("automatic only"))
    assert headline.split()[-2:] == ["1.000", "0.500"]


def test_an_error_needs_a_retry():
    assert run_rag.needs_retry({"error": "parse failed", "found": None, "quotes_real": None})


def test_a_found_answer_with_an_invented_quote_needs_a_retry():
    assert run_rag.needs_retry({"error": None, "found": True, "quotes_real": False})


def test_a_found_answer_with_a_real_quote_needs_no_retry():
    assert not run_rag.needs_retry({"error": None, "found": True, "quotes_real": True})


def test_not_found_needs_no_retry():
    assert not run_rag.needs_retry({"error": None, "found": False, "quotes_real": True})