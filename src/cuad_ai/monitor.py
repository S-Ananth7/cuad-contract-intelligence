"""Numbers to watch on a run that need no lawyer labels.

Labels exist only in evaluation. In use you cannot compute precision, so you watch signals you can always see:
how much goes to a person, how often a quote is invented, how often a retry is needed, and what a question costs.
A sudden change in one of them is the first sign that the model, the prompt or the documents have changed.
"""


def metrics_from(meta, summary, decision_counts, retried, queue_reasons):
    """Label-free numbers for one run. Rates are shares of all questions."""
    questions = sum(decision_counts.values())
    contracts = meta.get("contracts")
    queued = decision_counts.get("queue", 0)

    def rate(count):
        return round(count / questions, 4) if questions else None

    return {
        "questions": questions,
        "accept_rate": rate(decision_counts.get("accept", 0)),
        "reject_rate": rate(decision_counts.get("reject", 0)),
        "queue_rate": rate(queued),
        "not_found_rate": rate(decision_counts.get("not_found", 0)),
        "queue_per_contract": round(queued / contracts, 2) if contracts else None,
        "retried_rate": rate(retried),
        "invented_quote_rate": rate(summary.get("invented_quotes", 0)),
        # Extraction calls only. The judge calls are not stored with the run.
        "avg_extraction_tokens_in": summary.get("avg_tokens_in"),
        "avg_extraction_tokens_out": summary.get("avg_tokens_out"),
        "avg_seconds": summary.get("avg_seconds"),
        "queue_reasons": dict(queue_reasons),
    }


def run_metrics(conn, run_id):
    """The label-free numbers for a stored run, or None when there is no such run."""
    run = conn.execute("SELECT meta, summary FROM runs WHERE run_id = %s", (run_id,)).fetchone()
    if run is None:
        return None
    counts = dict(conn.execute(
        "SELECT decision, count(*) FROM answers WHERE run_id = %s GROUP BY decision", (run_id,)).fetchall())
    retried = conn.execute(
        "SELECT count(*) FROM answers WHERE run_id = %s AND retried", (run_id,)).fetchone()[0]
    reasons = conn.execute(
        "SELECT reason, count(*) FROM answers WHERE run_id = %s AND decision = 'queue' "
        "GROUP BY reason ORDER BY 2 DESC", (run_id,)).fetchall()
    return metrics_from(run[0], run[1], counts, retried, reasons)


def prometheus_text(run_id, metrics):
    """The numbers in the plain-text format that Prometheus and similar tools scrape."""
    lines = []
    for name, value in metrics.items():
        if name == "queue_reasons":
            for reason, count in value.items():
                lines.append(f'cuad_queue_reason_total{{run_id="{run_id}",reason="{reason}"}} {count}')
        elif value is not None:
            lines.append(f'cuad_{name}{{run_id="{run_id}"}} {value}')
    return "\n".join(lines) + "\n"
