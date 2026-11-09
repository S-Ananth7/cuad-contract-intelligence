import json
import sys
from collections import Counter
from pathlib import Path


def main():
    folder = Path(sys.argv[1])
    rows = json.loads((folder / "verified_examples.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))["rows"]
    source = {(r["title"], r["clause"]): r for r in report}
    gold_total = sum(1 for r in report if r["gold_found"])

    final = []
    for r in rows:  # every answer where the model said "found"
        v1, v2 = r.get("verdict"), r.get("verdict2")
        if source[(r["title"], r["clause"])]["unsolved"]:
            decision, reason = "queue", "quote_unverified"
        elif r["route"] == "accept":
            decision, reason = "accept", "confident"
        elif v1 is False and v2 is False:
            decision, reason = "reject", "both_judges_no"
        elif v1 is not False and v2 is not False:
            decision, reason = "accept", "both_judges_yes"
        else:
            decision, reason = "queue", "judges_disagree"
        final.append({"title": r["title"], "clause": r["clause"], "decision": decision,
                      "reason": reason, "gold_found": r["gold_found"]})
    for s in report:  # replies that never parsed
        if s["error"]:
            final.append({"title": s["title"], "clause": s["clause"], "decision": "queue",
                          "reason": "parse_failed", "gold_found": s["gold_found"]})
    (folder / "final.json").write_text(json.dumps(final), encoding="utf-8")

    def count(decision):
        part = [f for f in final if f["decision"] == decision]
        return len(part), sum(f["gold_found"] for f in part)

    print(f"{'decision':10}{'answers':>9}{'real':>7}{'false':>7}")
    for name in ("accept", "reject", "queue"):
        n, real = count(name)
        print(f"{name:10}{n:>9}{real:>7}{n - real:>7}")
    print("queue reasons:", dict(Counter(f["reason"] for f in final if f["decision"] == "queue")))

    (acc, acc_real), (_, q_real) = count("accept"), count("queue")
    print(f"\nautomatic only: precision {acc_real / acc:.3f}  recall {acc_real / gold_total:.3f}")
    print(f"human resolves queue perfectly (upper bound): "
          f"precision {(acc_real + q_real) / (acc + q_real):.3f}  recall {(acc_real + q_real) / gold_total:.3f}")
    print("saved:", folder / "final.json")


if __name__ == "__main__":
    main()
