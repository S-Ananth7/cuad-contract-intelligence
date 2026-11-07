from cuad_ai.context import excerpts, merge_spans


def test_merge_spans_joins_overlapping_and_touching():
    assert merge_spans([(10, 20), (0, 5), (18, 30), (30, 40)]) == [(0, 5), (10, 40)]


def test_merge_spans_keeps_gaps():
    assert merge_spans([(0, 5), (7, 9)]) == [(0, 5), (7, 9)]


def test_excerpts_marks_skipped_text():
    assert excerpts("abcdefghij", [(6, 9), (0, 3)]) == "abc\n[...]\nghi"
