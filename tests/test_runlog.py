import pytest

from cuad_ai.runlog import find_run, load_report, log_run, new_run_id, write_report

SUMMARY = {
    "contracts": 30, "recall": 1.0, "recall_errors_as_misses": 1.0, "precision": 0.957,
    "invented_quotes": 0, "errors": 0, "avg_seconds": 1.58,
}
INFO = {"git_commit": "abc1234", "thinking": "off"}


def test_run_ids_are_safe_and_start_with_a_timestamp():
    run_id = new_run_id("governing law v1 / deepseek")
    assert " " not in run_id and "/" not in run_id
    assert run_id[:8].isdigit()


def test_separate_runs_get_separate_folders(tmp_path):
    write_report("20260101_000000_a", {}, SUMMARY, [], runs_dir=tmp_path)
    write_report("20260101_000001_a", {}, SUMMARY, [], runs_dir=tmp_path)
    assert len(list(tmp_path.iterdir())) == 2


def test_find_run_returns_the_latest_match(tmp_path):
    write_report("20260101_000000_v1", {"x": 1}, SUMMARY, [], runs_dir=tmp_path)
    write_report("20260102_000000_v1", {"x": 2}, SUMMARY, [], runs_dir=tmp_path)
    assert load_report("v1", runs_dir=tmp_path)["meta"]["x"] == 2


def test_find_run_with_no_match_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_run("nothing", runs_dir=tmp_path)


def test_log_run_writes_header_once_and_appends(tmp_path):
    path = tmp_path / "results.md"
    log_run("run-a", SUMMARY, INFO, path=path)
    log_run("run-b", SUMMARY, INFO, path=path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("| run id |")
    assert len(lines) == 4
    assert "run-a" in lines[2] and "run-b" in lines[3]
