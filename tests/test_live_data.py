import csv
import io

from live_data import counts, export_csv, final_status, highlight_html, merge_spans, plain_reason, summary

TEXT = "Intro text. " + "filler " * 200 + "The law of <Delaware> & more. " + "tail " * 200


def answer(**changes):
    base = {"clause": "Governing Law", "decision": "queue", "reason": "judges_disagree", "quotes": ["q"],
            "review_action": None, "review_note": None, "reviewer": None}
    return {**base, **changes}


def test_a_person_overrides_the_machine():
    assert final_status(answer()) == "Needs review"
    assert final_status(answer(review_action="confirm")) == "Confirmed by reviewer"
    assert final_status(answer(decision="accept", review_action="reject")) == "Rejected by reviewer"
    assert final_status(answer(decision="not_found")) == "Not found"


def test_overlapping_spans_merge():
    assert merge_spans([(5, 9), (0, 6), (20, 30)]) == [(0, 9), (20, 30)]


def test_the_quote_is_marked_and_contract_text_is_escaped():
    start = TEXT.index("The law")
    end = TEXT.index("more.") + 5
    out = highlight_html(TEXT, [(start, end)])
    assert "<mark>The law of &lt;Delaware&gt; &amp; more.</mark>" in out
    assert "<Delaware>" not in out and out.startswith("…")


def test_no_spans_shows_the_start_of_the_contract():
    out = highlight_html(TEXT, [])
    assert out.startswith("Intro text.") and "<mark>" not in out


def test_two_far_apart_quotes_are_both_marked_with_the_gap_skipped():
    out = highlight_html(TEXT, [(0, 5), (len(TEXT) - 10, len(TEXT))], context=50)
    assert out.count("<mark>") == 2 and len(out) < 400


def test_csv_has_one_row_per_question_and_the_final_status():
    rows = list(csv.DictReader(io.StringIO(export_csv("a.txt", [answer(review_action="confirm", reviewer="Priya")]))))
    assert rows[0]["status"] == "Confirmed by reviewer" and rows[0]["reviewer"] == "Priya" and rows[0]["file"] == "a.txt"


def test_counts_use_the_final_status():
    assert counts([answer(), answer(), answer(review_action="reject")]) == {"Needs review": 2, "Rejected by reviewer": 1}


def test_the_headline_numbers_move_with_a_persons_decision():
    rows = [answer(decision="accept"), answer(), answer(review_action="confirm"), answer(review_action="reject"),
            answer(decision="not_found")]
    assert summary(rows) == {"Accepted": 2, "Needs review": 1, "Rejected": 1, "Not found": 1, "reviewed": 2}


def test_every_reason_the_pipeline_can_give_has_plain_words():
    for reason in ("accept", "both_judges_yes", "both_judges_no", "judges_disagree", "judge_missing",
                   "quote_unverified", "parse_failed", "no_quote", ""):
        assert "_" not in plain_reason(reason)


def test_access_needs_a_configured_code_and_an_exact_match():
    from live_data import access_ok

    assert access_ok("open-sesame", "open-sesame")
    assert not access_ok("open-sesame", "open-sesame ")
    assert not access_ok("open-sesame", "")
    assert not access_ok("", "")  # no code configured: closed, even for an empty guess
    assert not access_ok("", "anything")
