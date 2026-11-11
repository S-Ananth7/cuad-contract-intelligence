# 0004. Gate answers with the clause rank and a frozen per-clause risk table

Status: accepted

## Context

Sending every answer to two judges costs model calls, and some clauses produce many false alarms while others almost none.

## Decision

Embed the quote and compare it with the lawyer examples of all 41 clauses. Accept without review when the asked clause is the closest one and that clause's smoothed false-alarm rate is at most 0.5 (prior weight 3). Document Name and Agreement Date are always accepted, because a title or a date is not a sentence to second-guess. Everything else goes to the judges. The risk table is built once from 60 validation contracts and saved to `evals/risk_table.json`.

## Consequences

- The contracts being scored never supply their own risk.
- Risk for rare clauses rests on few examples and is noisy.
- The table must be frozen again when the model or the prompt changes.

## Alternatives considered

- Judge every answer: more calls for the same decisions.
- Learn risk from the contracts being routed (half-split): useful for tuning, but not clean enough for the final run.
