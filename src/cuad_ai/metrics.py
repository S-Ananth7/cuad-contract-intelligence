def summarize(rows):
    """Turn one row per contract into counts and two main numbers."""
    done = [r for r in rows if r["error"] is None]
    tp = sum(1 for r in done if r["found"] and r["gold_found"])
    fp = sum(1 for r in done if r["found"] and not r["gold_found"])
    fn = sum(1 for r in done if not r["found"] and r["gold_found"])
    tn = sum(1 for r in done if not r["found"] and not r["gold_found"])
    return {
        "contracts": len(rows),
        "errors": len(rows) - len(done),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
    }
