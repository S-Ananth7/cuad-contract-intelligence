from cuad_ai.metrics import quotes_overlap, summarize


def row(found, gold, error=None):
    return {
        "found": found,
        "gold_found": gold,
        "error": error,
        "quotes_real": True,
        "quote_match": True,
        "tokens_in": 100,
        "tokens_out": 10,
        "seconds": 2.0,
    }


def test_recall_and_precision():
    rows = [row(True, True), row(True, True), row(False, True), row(True, False), row(False, False)]
    summary = summarize(rows)
    assert (summary["tp"], summary["fn"], summary["fp"], summary["tn"]) == (2, 1, 1, 1)
    assert summary["recall"] == 0.667
    assert summary["precision"] == 0.667


def test_errors_are_counted_not_hidden():
    rows = [row(True, True), row(None, True, error="call failed: X")]
    summary = summarize(rows)
    assert summary["errors"] == 1
    assert summary["recall"] == 1.0
    assert summary["recall_errors_as_misses"] == 0.5


def test_quotes_overlap_ignores_spacing():
    assert quotes_overlap(["governed by  Swiss\nlaw"], ["This Agreement is governed by Swiss law."])


def test_quotes_overlap_rejects_different_text():
    assert not quotes_overlap(["governed by Mars law"], ["governed by Swiss law"])
    assert not quotes_overlap([], ["governed by Swiss law"])
