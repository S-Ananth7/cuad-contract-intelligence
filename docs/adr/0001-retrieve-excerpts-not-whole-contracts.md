# 0001. Send retrieved excerpts to the model, not the whole contract

Status: accepted

## Context

There are 41 clauses per contract. Sending the whole contract once per clause costs about 12,770 input tokens per question (observed on 9 contracts) and does not scale to longer contracts.

## Decision

For each contract and clause, retrieve 10 excerpts and send only those. Header clauses (title, parties, dates) also get the first 4 chunks, because those facts sit at the start of a contract.

## Consequences

- About 2,160 input tokens per question for extraction, about 2,430 with the judges: roughly 81% fewer than the whole-contract baseline. The baseline is a small sample, so the percentage is approximate.
- The model can only find what retrieval hands it. Retrieval recall@10 is 0.93 on test, so about 7% of lawyer-marked clauses are never shown to the model.
- Retrieval quality becomes a measured part of the system: see [0002](0002-hybrid-retrieval.md).

## Alternatives considered

- Whole contract per clause: simplest, highest cost, no retrieval misses.
- One call per contract for all 41 clauses: cheaper, but long outputs get truncated and quotes are harder to verify.
