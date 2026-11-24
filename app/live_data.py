"""Pure helpers for the live-review page: no Streamlit, no database, so they are easy to test."""
from __future__ import annotations

import csv
import html
import io

LABELS = {"accept": "Accepted", "reject": "Rejected", "queue": "Needs review", "not_found": "Not found"}
REASONS = {
    "accept": "Passed the gate: the quote clearly matches this clause type",
    "both_judges_yes": "Both checkers said it is this clause",
    "both_judges_no": "Both checkers said it is not this clause",
    "judges_disagree": "The two checkers disagreed",
    "judge_missing": "A checker gave no usable answer",
    "quote_unverified": "The quote was not found word for word in the contract",
    "parse_failed": "The model's reply could not be used",
    "no_quote": "The model gave no quote",
    "": "",
}


def plain_reason(reason: str) -> str:
    return REASONS.get(reason or "", reason or "")


def summary(answers: list[dict]) -> dict:
    """Four headline numbers. A person's decision moves an answer: confirmed counts as accepted, rejected as rejected."""
    result = {"Accepted": 0, "Needs review": 0, "Rejected": 0, "Not found": 0, "reviewed": 0}
    for a in answers:
        action = a.get("review_action")
        if action:
            result["reviewed"] += 1
            result["Accepted" if action == "confirm" else "Rejected"] += 1
        else:
            result[LABELS[a["decision"]]] += 1
    return result


def final_status(answer: dict) -> str:
    """What the answer is now: a person's decision wins over the machine's."""
    if answer.get("review_action") == "confirm":
        return "Confirmed by reviewer"
    if answer.get("review_action") == "reject":
        return "Rejected by reviewer"
    return LABELS[answer["decision"]]


def merge_spans(spans):
    merged = []
    for start, end in sorted((int(s), int(e)) for s, e in spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def highlight_html(text: str, spans, context: int = 500) -> str:
    """The contract around the quoted passages, as safe HTML with each quote in <mark>.

    Everything from the contract is escaped. With no spans, the start of the contract is shown instead.
    """
    spans = merge_spans(spans)
    if not spans:
        return html.escape(text[: 2 * context]) + ("…" if len(text) > 2 * context else "")
    pieces, cursor = [], max(0, spans[0][0] - context)
    pieces.append("…" if cursor > 0 else "")
    for i, (start, end) in enumerate(spans):
        pieces.append(html.escape(text[cursor:start]))
        pieces.append(f"<mark>{html.escape(text[start:end])}</mark>")
        cursor = end
        next_start = spans[i + 1][0] if i + 1 < len(spans) else None
        if next_start is not None and next_start - end > 2 * context:  # a long gap: show both edges, skip the middle
            pieces.append(html.escape(text[end:end + context]) + "\n\n…\n\n")
            cursor = next_start - context
    stop = min(len(text), cursor + context)
    pieces.append(html.escape(text[cursor:stop]) + ("…" if stop < len(text) else ""))
    return "".join(pieces)


def export_csv(filename: str, answers: list[dict]) -> str:
    """One row per question with the quote(s) and the final status, for the reviewer to keep."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["file", "clause", "status", "machine_decision", "reason", "quotes", "reviewer", "note"])
    for a in answers:
        writer.writerow([filename, a["clause"], final_status(a), a["decision"], a["reason"],
                         " ... ".join(a["quotes"]), a.get("reviewer") or "", a.get("review_note") or ""])
    return out.getvalue()


def counts(answers: list[dict]) -> dict:
    result = {}
    for a in answers:
        status = final_status(a)
        result[status] = result.get(status, 0) + 1
    return result
