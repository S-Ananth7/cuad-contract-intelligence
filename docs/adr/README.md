# Decision records

Short records of the choices that shape the system: what was decided, why, what it costs, and what was rejected. Numbers come from the [evaluation protocol](../evaluation-protocol.md) and the committed test evidence.

| Record | Decision |
|---|---|
| [0001](0001-retrieve-excerpts-not-whole-contracts.md) | Send retrieved excerpts to the model, not the whole contract |
| [0002](0002-hybrid-retrieval.md) | Retrieve with lawyer examples, learned keywords and rank fusion |
| [0003](0003-verify-quotes-deterministically.md) | Check every quote against the contract with plain code |
| [0004](0004-gate-with-a-frozen-risk-table.md) | Gate answers with the clause rank and a frozen per-clause risk table |
| [0005](0005-two-judges-must-agree.md) | Two judges review doubtful answers; a split goes to a person |
| [0006](0006-postgres-as-the-single-store.md) | Keep data, vectors, full text and run history in one Postgres |
| [0007](0007-score-the-test-set-once.md) | Score the official test set once, behind a lock, with frozen settings |

Each record has a status. A record is replaced by a new one, never edited to hide a change of mind.
