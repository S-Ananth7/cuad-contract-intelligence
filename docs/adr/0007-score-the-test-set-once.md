# 0007. Score the official test set once, behind a lock, with frozen settings

Status: accepted

## Context

A score is only believable when the system was not tuned on the data it is scored on. The system learns from labelled contracts (examples, keywords, risk) and was tuned by hand, so leakage is easy.

## Decision

Develop and tune on validation contracts, then freeze the model, prompt, retrieval constants, routing rule and risk table. Run the 102 test contracts once. The run needs `CONFIRM_TEST=yes`, and tests check that nothing else unlocks it.

## Consequences

- The headline numbers are held-out numbers. The confirmation run on 30 fresh validation contracts (0.747 and 0.911) was close to the test result (0.757 and 0.916).
- The test set is spent for this design. A new headline needs a new held-out set, and further changes are judged on validation.
- The margin on precision is about plus or minus 0.02.

## Alternatives considered

- Tune on test: gives a better-looking number that means less.
- Cross-validation: not used; the official split already exists and is the shared benchmark.
