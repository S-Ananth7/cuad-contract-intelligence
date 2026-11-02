from cuad_ai.validate import quote_in_contract

CONTRACT = "This Agreement is governed by the laws of Pennsylvania. \nAny dispute goes to court."


def test_exact_quote_is_found():
    assert quote_in_contract(CONTRACT, "governed by the laws of Pennsylvania") is True


def test_invented_quote_is_rejected():
    assert quote_in_contract(CONTRACT, "governed by the laws of Texas") is False


def test_line_break_difference_is_ignored():
    assert quote_in_contract(CONTRACT, "Pennsylvania. Any dispute") is True


def test_extra_spaces_are_ignored():
    assert quote_in_contract(CONTRACT, "governed   by  the    laws") is True


def test_changed_word_near_a_line_break_is_rejected():
    assert quote_in_contract(CONTRACT, "Pennsylvania. Any argument") is False


def test_empty_quote_is_rejected():
    assert quote_in_contract(CONTRACT, "") is False
    assert quote_in_contract(CONTRACT, "   ") is False
