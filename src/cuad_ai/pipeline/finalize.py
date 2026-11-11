"""Last step: apply the decision policy to every answer, save final.json and queue.json, print the scores.

Reads verified_examples.json and report.json from a run folder.

Decision for each question:
  not found by the model                         -> not_found
  reply unusable after the retry                 -> queue (parse_failed)
  quote not word for word after the retry        -> queue (quote_unverified)
  routed accept                                  -> accept
  review, both judges yes                        -> accept
  review, both judges no                         -> reject
  review, judges disagree                        -> queue (judges_disagree)
Queue items are NOT accepted automatically. The headline score counts them as not kept.
A person can review the queue; the second score assumes a perfect reviewer and is only an upper bound.
"""
import json
import sys
from collections import Counter
from pathlib import Path


def decide(report_row, answer):
    """Return (decision, reason) for one question."""
    if report_row["error"]:
        return "queue", "parse_failed"
    if report_row.get("unsolved"):
        return "queue", "quote_unverified"
    if not report_row["found"]:
        return "not_found", ""
    if answer is None:
        return "reject", "no_quote"
    if answer["route"] == "accept":
        return "accept", answer["route"]
    first, second = answer.get("verdict"), answer.get("verdict2")
    if first is not False and second is not False:
        return "accept", "both_judges_yes"
    if first is False and second is False:
        return "reject", "both_judges_no"
    return "queue", "judges_disagree"


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    folder = Path(args[0])
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))["rows"]
    answers = {(r["title"], r["clause"]): r
               for r in json.loads((folder / "verified_examples.json").read_text(encoding="utf-8"))}

    final, queue = [], []
    for row in report:
        key = (row["title"], row["clause"])
        answer = answers.get(key)
        decision, reason = decide(row, answer)
        item = {"title": row["title"], "clause": row["clause"], "decision": decision, "reason": reason,
                "gold_found": row["gold_found"], "quotes": row.get("quotes", []), "retried": row.get("retried", False)}
        final.append(item)
        if decision == "queue":
            queue.append({**item, "looks_like": [answer.get("looks_like"), answer.get("looks_like2")] if answer else None})
    (folder / "final.json").write_text(json.dumps(final), encoding="utf-8")
    (folder / "queue.json").write_text(json.dumps(queue), encoding="utf-8")

    gold = sum(r["gold_found"] for r in final)
    kept = [r for r in final if r["decision"] == "accept"]
    real = sum(r["gold_found"] for r in kept)
    queued_real = sum(r["gold_found"] for r in queue)
    contracts = len({r["title"] for r in final})
    print(f"questions: {len(final)} | contracts: {contracts} | retried: {sum(r['retried'] for r in final)}")
    print(f"decisions: {dict(Counter(r['decision'] for r in final))}")
    print(f"queue reasons: {dict(Counter(r['reason'] for r in queue))} | queue per contract: {len(queue) / contracts:.1f}")
    print(f"\n{'version':40}{'kept':>6}{'tp':>6}{'fp':>6}{'fn':>6}{'precision':>11}{'recall':>9}")
    print(f"{'automatic only (headline)':40}{len(kept):>6}{real:>6}{len(kept) - real:>6}{gold - real:>6}"
          f"{real / max(len(kept), 1):>11.3f}{real / gold:>9.3f}")
    both = len(kept) + queued_real
    print(f"{'with a perfect human on the queue':40}{both:>6}{real + queued_real:>6}{len(kept) - real:>6}"
          f"{gold - real - queued_real:>6}{(real + queued_real) / both:>11.3f}{(real + queued_real) / gold:>9.3f}"
          "   (upper bound)")
    print("saved:", folder / "final.json", "and", folder / "queue.json")


if __name__ == "__main__":
    main()
