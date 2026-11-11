# 0002. Retrieve with lawyer examples, learned keywords and rank fusion

Status: accepted

## Context

Retrieval decides what the model can see. Using the CUAD question as the search query reaches recall@10 of 0.64. Searching by clause name plus the header rule reaches 0.85.

## Decision

Score each chunk by similarity to the closest lawyer-marked example of the clause, and separately by learned keywords (word stems that are common in a clause's examples and rare in other clauses). Merge the two lists with reciprocal rank fusion (constant 60, 50 candidates each) and keep 10.

## Consequences

- Recall@10 rises to 0.93 on both validation and test, with 28 of 40 clauses at 0.90 or better.
- The system needs an example bank, which must never contain the contracts being scored. See the leakage rules in the [evaluation protocol](../evaluation-protocol.md).
- Keywords are learned per run with the scored contracts held out.
- Weak spots remain: Document Name (0.83), Non-Disparagement and Volume Restriction (0.71).

## Alternatives considered

- Question as the query: 0.64.
- Clause name and header rule only: 0.85.
- Examples only: 0.88.
- A reranker: not tried.
