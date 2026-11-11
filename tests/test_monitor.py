import json
from pathlib import Path

from cuad_ai.monitor import metrics_from, prometheus_text, run_metrics
from cuad_ai.runstore import create_tables, save_run

FINAL = Path(__file__).parent.parent / "evals" / "final_test"


def read(name):
    return json.loads((FINAL / name).read_text(encoding="utf-8"))


def test_rates_are_shares_of_all_questions():
    counts = {"accept": 6, "reject": 2, "queue": 1, "not_found": 1}
    m = metrics_from({"contracts": 2}, {"invented_quotes": 1}, counts, retried=3, queue_reasons=[("judges_disagree", 1)])
    assert m["questions"] == 10
    assert (m["accept_rate"], m["reject_rate"], m["queue_rate"], m["not_found_rate"]) == (0.6, 0.2, 0.1, 0.1)
    assert (m["retried_rate"], m["invented_quote_rate"], m["queue_per_contract"]) == (0.3, 0.1, 0.5)
    assert m["queue_reasons"] == {"judges_disagree": 1}


def test_an_empty_run_gives_no_rates_instead_of_a_division_error():
    m = metrics_from({}, {}, {}, retried=0, queue_reasons=[])
    assert m["questions"] == 0
    assert m["queue_rate"] is None and m["queue_per_contract"] is None


def test_prometheus_text_has_one_line_per_number():
    m = metrics_from({"contracts": 1}, {}, {"accept": 1, "queue": 1}, 0, [("parse_failed", 1)])
    text = prometheus_text("r1", m)
    assert 'cuad_queue_rate{run_id="r1"} 0.5' in text
    assert 'cuad_queue_reason_total{run_id="r1",reason="parse_failed"} 1' in text
    assert "None" not in text


def test_the_final_run_numbers_come_out_of_the_database(conn):
    create_tables(conn)
    save_run(conn, read("report_summary.json"), read("decisions.json"), read("queue.json"))
    m = run_metrics(conn, read("report_summary.json")["run_id"])
    assert m["questions"] == 4182
    assert m["queue_rate"] == round(184 / 4182, 4)
    assert m["queue_per_contract"] == round(184 / 102, 2)
    assert m["retried_rate"] == round(25 / 4182, 4)
    assert m["invented_quote_rate"] == round(3 / 4182, 4)
    assert m["queue_reasons"] == {"judges_disagree": 177, "parse_failed": 4, "quote_unverified": 3}


def test_a_missing_run_has_no_metrics(conn):
    create_tables(conn)
    assert run_metrics(conn, "no_such_run") is None
