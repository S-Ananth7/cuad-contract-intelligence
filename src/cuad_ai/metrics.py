from cuad_ai.validate import normalize


def quotes_overlap(model_quotes, gold_quotes):
    """True if any model quote and any lawyer quote contain one another(ignoring spacing)."""
    for model_quote in model_quotes:
        for gold_quote in gold_quotes:
            a = normalize(model_quote)
            b = normalize(gold_quote)
            if a and b and (a in b or b in a):
                return True
    return False


def _ratio(top, bottom):
    return round(top / bottom, 3) if bottom else None


def _average(values):
    return round(sum(values) / len(values), 2) if values else None


def summarize(rows):
    """Turn one row per contract into counts and two main numbers."""
    done = [r for r in rows if r["error"] is None]
    tp = sum(1 for r in done if r["found"] and r["gold_found"])
    fp = sum(1 for r in done if r["found"] and not r["gold_found"])
    fn = sum(1 for r in done if not r["found"] and r["gold_found"])
    tn = sum(1 for r in done if not r["found"] and not r["gold_found"])
    gold_total = sum(1 for r in rows if r["gold_found"])
    return {
        "contracts": len(rows),
        "errors": len(rows) - len(done),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "recall": _ratio(tp, tp + fn),
        "recall_errors_as_misses": _ratio(tp, gold_total),
        "precision": _ratio(tp, tp + fp),
        "invented_quotes": sum(1 for r in done if r["found"] and r["quotes_real"] is False),
        "quote_matches_lawyers": sum(1 for r in done if r["found"] and r["gold_found"] and r["quote_match"]),
        "avg_tokens_in": _average([r["tokens_in"] for r in done]),
        "avg_tokens_out": _average([r["tokens_out"] for r in done]),
        "avg_seconds": _average([r["seconds"] for r in done]),
    }
