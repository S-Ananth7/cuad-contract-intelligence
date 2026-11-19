import pytest

from cuad_ai.pipeline import finalize as fa
from cuad_ai.pipeline import judge_examples, judge_quote
from cuad_ai.pipeline.judge_quote import parse_verdict

NOT_A_BOOLEAN = ['"false"', '"true"', '"yes"', "0", "1", "null"]


def reply(value):
    return '{"is_this_clause": %s, "looks_like": "Governing Law"}' % value


def fake_call(text):
    return lambda prompt: {"text": text, "tokens_in": 5}


def test_real_booleans_are_read_as_they_are():
    assert parse_verdict(reply("true")) == (True, "Governing Law")
    assert parse_verdict(reply("false")) == (False, "Governing Law")


@pytest.mark.parametrize("value", NOT_A_BOOLEAN)
def test_a_value_that_is_not_a_real_boolean_is_unreadable_not_a_yes(value):
    assert parse_verdict(reply(value))[0] is None


@pytest.mark.parametrize("value", NOT_A_BOOLEAN)
def test_judge_one_returns_none_for_a_non_boolean(value):
    verdict, _, _ = judge_quote.ask("[CLAUSE] [QUESTION] [QUOTE]", "Governing Law", "Which law?", "q", fake_call(reply(value)))
    assert verdict is None


@pytest.mark.parametrize("value", NOT_A_BOOLEAN)
def test_judge_two_returns_none_for_a_non_boolean(value):
    verdict, _, _ = judge_examples.ask(
        "[CLAUSE] [QUESTION] [EXAMPLES] [QUOTE]", "Governing Law", "Which law?", "q", "- e", fake_call(reply(value))
    )
    assert verdict is None


@pytest.mark.parametrize("text", ['{"looks_like": "x"}', "no json here", ""])
def test_a_reply_without_a_verdict_is_unreadable(text):
    assert judge_quote.ask("[CLAUSE] [QUESTION] [QUOTE]", "c", "q", "q", fake_call(text)) == (None, "none", 0)


ROW = {"error": None, "unsolved": False, "found": True}


@pytest.mark.parametrize("bad", ["false", "true", "yes", 0, 1])
def test_a_stored_non_boolean_verdict_never_accepts(bad):
    answer = {"route": "review", "verdict": bad, "verdict2": True}
    assert fa.decide(ROW, answer) == ("queue", "judge_missing")
