def merge_spans(spans):
    """Merge overlapping or touching (start, end) spans. Returns a sorted list."""
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def excerpts(text, spans, separator="\n[...]\n"):
    """Text of the merged spans in contract order, with a marker where text was skipped."""
    return separator.join(text[start:end] for start, end in merge_spans(spans))
