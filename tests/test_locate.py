import pytest

from cuad_ai.live.locate import Locator, locate
from cuad_ai.validate import quote_in_contract

TEXT = "  First line.\n\nThis   Agreement is\ngoverned by Delaware law.   Last bit. "


def test_a_quote_is_found_where_it_really_is():
    start, end = locate(TEXT, "Agreement is governed by Delaware law.")
    assert TEXT[start:end] == "Agreement is\ngoverned by Delaware law."


def test_spaces_and_line_breaks_in_the_quote_do_not_matter():
    assert locate(TEXT, "Agreement   is governed\nby Delaware law.") == locate(TEXT, "Agreement is governed by Delaware law.")


def test_the_span_starts_and_ends_on_visible_characters():
    start, end = locate(TEXT, "First line.")
    assert TEXT[start:end] == "First line." and start == 2


def test_a_quote_that_is_not_there_is_none():
    assert locate(TEXT, "Texas law") is None


@pytest.mark.parametrize("quote", ["", "   ", "\n"])
def test_an_empty_quote_is_none(quote):
    assert locate(TEXT, quote) is None


def test_a_quote_inside_a_word_is_found_like_the_verifier_does():
    assert quote_in_contract(TEXT, "verned by")
    start, end = locate(TEXT, "verned by")
    assert TEXT[start:end] == "verned by"


def test_the_first_of_two_matches_is_used():
    text = "alpha beta. alpha beta."
    assert locate(text, "alpha beta") == (0, 10)


def test_it_agrees_with_the_verifier_on_every_substring():
    locator = Locator(TEXT)
    for start in range(0, len(TEXT) - 3, 3):
        for length in (4, 9, 20):
            quote = TEXT[start:start + length]
            if quote.strip():
                assert (locator.find(quote) is not None) == quote_in_contract(TEXT, quote)


def test_an_empty_contract_finds_nothing():
    assert locate("", "x") is None
