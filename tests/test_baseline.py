from cuad_ai.baseline import STRONG_PHRASES, keyword_governing_law

TEXT = "The parties agree to terms.\nThis Agreement shall be governed by the laws of Texas. Payment is due in 30 days."


def test_finds_governing_sentence():
    row = keyword_governing_law(TEXT)
    assert row["found"] is True
    assert row["quotes"] == ["This Agreement shall be governed by the laws of Texas."]
    assert row["quotes_real"] is True


def test_line_break_inside_sentence_is_handled():
    row = keyword_governing_law("This Agreement is governed\nby the laws of Ohio.")
    assert row["found"] is True
    assert row["quotes_real"] is True


def test_quotes_are_capped():
    text = " ".join(f"Clause {i} is governed by the laws of State {i}." for i in range(10))
    assert len(keyword_governing_law(text)["quotes"]) == 3


HEADING = "MISCELLANEOUS 15.1 Governing Law; English Language."
CLAUSE = "This Agreement shall be governed, interpreted and construed in accordance with the substantive laws of Delaware."


def test_heading_is_skipped_and_clause_is_found():
    row = keyword_governing_law(HEADING + " " + CLAUSE)
    assert row["quotes"] == [CLAUSE]


def test_contents_line_is_skipped():
    contents = "22.1 Term 22.2 Fees 22.3 This Agreement shall be governed by law 22.4 Notices."
    row = keyword_governing_law(contents + " " + CLAUSE)
    assert row["quotes"] == [CLAUSE]


def test_real_clause_after_junk_is_not_cut_off():
    junk = " ".join(["Governing Law."] * 3)
    row = keyword_governing_law(junk + " " + CLAUSE)
    assert row["quotes"] == [CLAUSE]


def test_pointer_to_another_document_without_law_is_skipped():
    row = keyword_governing_law("Any liability shall be governed by the provisions of the Separation Agreement.")
    assert row["found"] is False


def test_boilerplate_about_incorporation_is_skipped():
    row = keyword_governing_law("It is a corporation validly existing under the laws of the State of its incorporation.")
    assert row["found"] is False


def test_short_real_clause_is_kept():
    row = keyword_governing_law("This Agreement is governed by the laws of Texas.")
    assert row["found"] is True
    assert row["quotes_real"] is True


def test_no_clause_means_not_found():
    row = keyword_governing_law("Payment is due in 30 days. Delivery is by truck.")
    assert row["found"] is False
    assert row["quotes"] == []


SAMPLE = (
    "This Agreement shall be governed by the laws of the State of Delaware. "
    "It shall be construed in accordance with those laws. "
    "Disputes are interpreted in accordance with the same laws."
).lower()


def test_every_phrase_is_real_english():
    """A typo in a phrase silently matches nothing. Each phrase must appear in real contract wording."""
    for phrase in STRONG_PHRASES:
        assert phrase in SAMPLE or phrase in ("governed, interpreted", "shall be governed"), phrase


def test_known_good_phrases_present():
    assert "construed in accordance with" in STRONG_PHRASES
