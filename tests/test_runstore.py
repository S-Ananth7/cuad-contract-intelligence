import json
from pathlib import Path

import pytest

from cuad_ai.runstore import (
    answer_rows,
    create_tables,
    read_run_folder,
    run_fields,
    run_scores,
    save_run,
    score_rows,
)

FINAL = Path(__file__).parent.parent / "evals" / "final_test"


def read(name):
    return json.loads((FINAL / name).read_text(encoding="utf-8"))


def decision(title, clause, kind, found):
    return {"title": title, "clause": clause, "decision": kind, "reason": kind, "gold_found": found, "retried": False}


def test_run_fields_come_from_the_report_summary():
    fields = run_fields(read("report_summary.json"))
    assert fields["run_id"] == "20261108_172552_rag_clause_rag_deepseek-v4-flash_k10_102"
    assert (fields["model"], fields["k"], fields["contracts"]) == ("deepseek-v4-flash", 10, 102)
    assert (fields["git_commit"], fields["prompt_hash"]) == ("49948ef", "de44f61b")


def test_queue_quotes_are_attached_to_the_matching_question():
    decisions = [decision("A", "Parties", "queue", False), decision("A", "Governing Law", "accept", True)]
    queue = [{"title": "A", "clause": "Parties", "quotes": ["q1"], "looks_like": ["none"]}]
    rows = answer_rows(decisions, queue)
    assert rows[0]["quotes"] == ["q1"] and rows[0]["looks_like"] == ["none"]
    assert rows[1]["quotes"] == []


def test_an_unknown_decision_is_refused():
    with pytest.raises(ValueError, match="unknown decision"):
        answer_rows([decision("A", "Parties", "maybe", False)])


def test_score_rows_counts_precision_and_recall():
    rows = [
        decision("A", "c1", "accept", True),
        decision("A", "c2", "accept", False),
        decision("A", "c3", "reject", True),
        decision("A", "c4", "not_found", False),
    ]
    assert score_rows(rows) == {
        "questions": 4, "accepted": 2, "accepted_real": 1, "lawyer_marked": 2,
        "accept_precision": 0.5, "accept_recall": 0.5,
    }


def test_queued_answers_keep_their_quotes_except_parse_failures():
    rows = answer_rows(read("decisions.json"), read("queue.json"))
    queued = [r for r in rows if r["decision"] == "queue"]
    assert len(queued) == 184
    without_quote = [r for r in queued if not r["quotes"]]
    # A reply that could not be parsed has no quote to keep: the 4 parse failures of the final run.
    assert len(without_quote) == 4
    assert {r["reason"] for r in without_quote} == {"parse_failed"}


def test_final_run_scores_match_the_published_result():
    scores = score_rows(answer_rows(read("decisions.json")))
    assert (scores["accepted"], scores["accepted_real"], scores["lawyer_marked"]) == (1505, 1139, 1244)
    assert (scores["accept_precision"], scores["accept_recall"]) == (0.757, 0.916)


def save_final(conn):
    report = read("report_summary.json")
    count = save_run(conn, report, read("decisions.json"), read("queue.json"))
    return report["run_id"], count


def test_the_sql_view_gives_the_same_numbers_as_python(conn):
    create_tables(conn)
    run_id, count = save_final(conn)
    assert count == 4182
    row = run_scores(conn, run_id)[0]
    assert (row["accepted"], row["accepted_real"], row["rejected"], row["rejected_real"]) == (1505, 1139, 273, 12)
    assert (row["queued"], row["queued_real"], row["not_found"]) == (184, 34, 2220)
    assert (float(row["accept_precision"]), float(row["accept_recall"])) == (0.757, 0.916)


def test_loading_the_same_run_twice_does_not_duplicate_it(conn):
    create_tables(conn)
    run_id, _ = save_final(conn)
    save_final(conn)
    assert conn.execute("SELECT count(*) FROM answers WHERE run_id = %s", (run_id,)).fetchone()[0] == 4182
    assert conn.execute("SELECT count(*) FROM runs WHERE run_id = %s", (run_id,)).fetchone()[0] == 1


def test_the_database_refuses_an_unknown_decision(conn):
    import psycopg

    create_tables(conn)
    run_id, _ = save_final(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO answers (run_id, title, clause, decision, gold_found) VALUES (%s, 'x', 'y', 'maybe', false)",
            (run_id,),
        )


def test_a_fresh_pipeline_run_folder_can_be_read(tmp_path):
    folder = tmp_path / "20261111_120000_rag_demo"
    folder.mkdir()
    meta = {"model": "m", "k": 10, "contracts": 1, "date": "2026-11-11"}
    (folder / "report.json").write_text(json.dumps({"meta": meta, "summary": {"contracts": 1}, "rows": []}))
    (folder / "final.json").write_text(json.dumps([decision("A", "Parties", "accept", True)]))
    report, decisions, queue = read_run_folder(folder)
    assert report["run_id"] == "20261111_120000_rag_demo"
    assert report["meta"] == meta
    assert len(decisions) == 1 and queue == []


def test_the_committed_evidence_folder_can_be_read():
    report, decisions, queue = read_run_folder(FINAL)
    assert (report["run_id"], len(decisions), len(queue)) == (
        "20261108_172552_rag_clause_rag_deepseek-v4-flash_k10_102", 4182, 184)


def test_a_folder_with_no_run_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError, match="no saved run"):
        read_run_folder(tmp_path)
