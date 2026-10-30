from cuad_ai.baseline_v2 import keyword_governing_law_v2

HEADING = "MISCELLANEOUS 15.1 Governing Law; English Language."
CLAUSE = "This Agreement shall be governed, interpreted and construed in accordance with the substantive laws of Delaware."


def test_heading_is_skipped_and_clause_is_found():
    row = keyword_governing_law_v2(HEADING + " " + CLAUSE)
    assert row["quotes"] == [CLAUSE]


def test_contents_line_is_skipped():
    contents = "22.1 Term 22.2 Fees 22.3 This Agreement shall be governed by law 22.4 Notices."
    row = keyword_governing_law_v2(contents + " " + CLAUSE)
    assert row["quotes"] == [CLAUSE]


def test_real_clause_after_junk_is_not_cut_off():
    junk = " ".join(["Governing Law."] * 3)
    row = keyword_governing_law_v2(junk + " " + CLAUSE)
    assert row["quotes"] == [CLAUSE]


def test_pointer_to_another_document_without_law_is_skipped():
    row = keyword_governing_law_v2("Any liability shall be governed by the provisions of the Separation Agreement.")
    assert row["found"] is False


def test_boilerplate_about_incorporation_is_skipped():
    row = keyword_governing_law_v2("It is a corporation validly existing under the laws of the State of its incorporation.")
    assert row["found"] is False


def test_short_real_clause_is_kept():
    row = keyword_governing_law_v2("This Agreement is governed by the laws of Texas.")
    assert row["found"] is True
    assert row["quotes_real"] is True


def test_no_clause_means_not_found():
    row = keyword_governing_law_v2("Payment is due in 30 days. Delivery is by truck.")
    assert row["found"] is False
    assert row["quotes"] == []