"""The published result, recomputed from the committed decisions file."""
import json
from pathlib import Path

DECISIONS = Path(__file__).parent.parent / "evals" / "final_test" / "decisions.json"


def rows():
    return json.loads(DECISIONS.read_text(encoding="utf-8"))


def test_headline_matches_the_published_result():
    data = rows()
    kept = [r for r in data if r["decision"] == "accept"]
    real_kept = sum(r["gold_found"] for r in kept)
    lawyer_marked = sum(r["gold_found"] for r in data)
    assert (len(data), len(kept), real_kept, lawyer_marked) == (4182, 1505, 1139, 1244)
    assert round(real_kept / len(kept), 3) == 0.757
    assert round(real_kept / lawyer_marked, 3) == 0.916


def test_rejections_and_queue_match_the_final_note():
    data = rows()
    rejected = [r for r in data if r["decision"] == "reject"]
    queued = [r for r in data if r["decision"] == "queue"]
    assert (len(rejected), sum(r["gold_found"] for r in rejected)) == (273, 12)
    assert (len(queued), sum(r["gold_found"] for r in queued)) == (184, 34)


def test_the_stricter_span_level_numbers_match_the_evaluation_note():
    """Headline numbers count the clause as found. These also need the quote to overlap a lawyer highlight."""
    data = rows()
    kept = [r for r in data if r["decision"] == "accept"]
    on_target = [r for r in kept if r["gold_found"] and r["quote_match"]]
    lawyer_marked = sum(r["gold_found"] for r in data)
    assert len(on_target) == 1058
    assert round(len(on_target) / len(kept), 3) == 0.703
    assert round(len(on_target) / lawyer_marked, 3) == 0.850
