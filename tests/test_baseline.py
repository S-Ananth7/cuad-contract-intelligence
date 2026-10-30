from cuad_ai.baseline import keyword_governing_law

TEXT = "The parties agree to terms.\nThis Agreement shall be governed by the laws of Texas. Payment is due in 30 days."


def test_finds_governing_sentence():
    row = keyword_governing_law(TEXT)
    assert row["found"] is True
    assert row["quotes"] == ["This Agreement shall be governed by the laws of Texas."]
    assert row["quotes_real"] is True


def test_no_clause_means_not_found():
    row = keyword_governing_law("Payment is due in 30 days. Delivery is by truck.")
    assert row["found"] is False
    assert row["quotes"] == []
    assert row["error"] is None


def test_line_break_inside_sentence_is_handled():
    row = keyword_governing_law("This Agreement is governed\nby the laws of Ohio.")
    assert row["found"] is True
    assert row["quotes_real"] is True


def test_quotes_are_capped():
    text = " ".join(f"Clause {i} is governed by rule {i}." for i in range(10))
    assert len(keyword_governing_law(text)["quotes"]) == 3
