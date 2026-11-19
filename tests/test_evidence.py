from cuad_ai.evidence import build_evidence, lawyer_passages, save_evidence
from demo_data import load_evidence

CUAD = {
    "data": [
        {
            "title": "T",
            "paragraphs": [
                {
                    "qas": [
                        {"id": "T__Governing Law", "answers": [{"text": "NY law"}, {"text": "NY law"}]},
                        {"id": "T__Document Name", "answers": []},
                        {"id": "T__Cap On Liability", "answers": [{"text": "capped"}]},
                    ]
                }
            ],
        },
        {"title": "A__B", "paragraphs": [{"qas": [{"id": "A__B__Governing Law", "answers": [{"text": "x"}]}]}]},
    ]
}


def test_passages_are_deduplicated_and_titles_may_contain_double_underscores():
    gold = lawyer_passages(CUAD)
    assert gold[("T", "Governing Law")] == ["NY law"]
    assert gold[("T", "Document Name")] == []
    assert gold[("A__B", "Governing Law")] == ["x"]


def test_build_keeps_answers_worth_comparing_and_drops_empty_ones():
    decisions = [
        {"title": "T", "clause": "Governing Law", "decision": "accept"},
        {"title": "T", "clause": "Document Name", "decision": "not_found"},  # nothing found, nothing marked: dropped
        {"title": "T", "clause": "Cap On Liability", "decision": "not_found"},  # missed: kept
    ]
    report = [
        {"title": "T", "clause": "Governing Law", "quotes": ["NY law"]},
        {"title": "T", "clause": "Document Name", "quotes": None},
        {"title": "T", "clause": "Cap On Liability", "quotes": []},
    ]
    assert build_evidence(decisions, report, CUAD) == {
        "T": {
            "Governing Law": {"quotes": ["NY law"], "gold": ["NY law"]},
            "Cap On Liability": {"quotes": [], "gold": ["capped"]},
        }
    }


def test_saved_evidence_loads_back_unchanged(tmp_path):
    evidence = {"T": {"Governing Law": {"quotes": ["a \u00a7 b $5"], "gold": ["g"]}}}
    save_evidence(evidence, tmp_path / "evidence.json.gz")
    assert load_evidence(tmp_path) == evidence
