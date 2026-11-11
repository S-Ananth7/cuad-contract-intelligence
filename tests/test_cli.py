import importlib
import json

import pytest

from cuad_ai import cli


def test_help_lists_every_stage(capsys):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert all(name in out for name in cli.STAGES)


def test_an_unknown_stage_is_refused():
    with pytest.raises(SystemExit, match="unknown stage"):
        cli.main(["nope"])


@pytest.mark.parametrize("name", list(cli.STAGES))
def test_every_stage_module_can_be_imported_and_has_a_main(name):
    module = importlib.import_module(cli.STAGES[name][0])
    assert callable(module.main)


def test_route_stage_runs_through_the_cli(tmp_path):
    rows = [
        {"title": "A_x", "clause": "Governing Law", "gold_found": True, "rank_asked": 1},
        {"title": "A_x", "clause": "Price Restrictions", "gold_found": False, "rank_asked": 3},
    ]
    (tmp_path / "gate_features.json").write_text(json.dumps(rows))
    table = tmp_path / "risk.json"
    table.write_text(json.dumps({"Governing Law": [10, 1], "Price Restrictions": [10, 9]}))
    cli.main(["route", str(tmp_path), str(table)])
    routed = json.loads((tmp_path / "routing.json").read_text())
    assert {r["clause"]: r["route"] for r in routed} == {"Governing Law": "accept", "Price Restrictions": "review"}


def test_finalize_stage_runs_through_the_cli(tmp_path):
    row = {"title": "A_x", "clause": "Governing Law", "error": None, "unsolved": False, "found": True,
           "quotes": ["q"], "retried": False, "gold_found": True}
    (tmp_path / "report.json").write_text(json.dumps({"rows": [row]}))
    (tmp_path / "verified_examples.json").write_text(
        json.dumps([{"title": "A_x", "clause": "Governing Law", "route": "accept"}]))
    cli.main(["finalize", str(tmp_path)])
    final = json.loads((tmp_path / "final.json").read_text())
    assert [r["decision"] for r in final] == ["accept"]
    assert json.loads((tmp_path / "queue.json").read_text()) == []


def test_freeze_risk_stage_writes_the_table(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    (run / "gate_features.json").write_text(
        json.dumps([{"clause": "Parties", "gold_found": True}, {"clause": "Parties", "gold_found": False}]))
    (tmp_path / "evals").mkdir()
    monkeypatch.chdir(tmp_path)
    cli.main(["freeze-risk", str(run)])
    assert json.loads((tmp_path / "evals" / "risk_table.json").read_text()) == {"Parties": [2, 1]}
