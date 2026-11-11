# 0003. Check every quote against the contract with plain code

Status: accepted

## Context

A model can invent a quote that sounds right. A reviewer needs to trust that a quoted sentence is really in the contract.

## Decision

A quote must appear in the contract word for word, ignoring spacing and line breaks. A found answer without a verified quote is retried once with a stricter instruction, then sent to the human queue. Replies that cannot be parsed follow the same path.

## Consequences

- In the test run 3 invented quotes were caught. 25 answers needed a retry, and 7 stayed unresolved (4 parse failures, 3 unverified), all queued.
- The check proves a quote exists, not that it answers the clause. A real quote can still be about the wrong clause, which is why a gate and judges follow ([0004](0004-gate-with-a-frozen-risk-table.md), [0005](0005-two-judges-must-agree.md)).
- Very long quotes can be cut by the 800-token output limit, which shows up as parse failures.

## Alternatives considered

- Ask another model to verify the quote: it can make the same kind of mistake.
- Accept the quote without a check: no protection against invention.
