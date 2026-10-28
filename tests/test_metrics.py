from cuad_ai.metrics import summarize


def row(found, gold, error=None):
    return {"found": found, "gold_found": gold, "error": error}


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
    assert summary["tp"] == 1
