# 0005. Two judges review doubtful answers; a split goes to a person

Status: accepted

## Context

After the gate, doubtful answers still contain many false alarms. One judge raised precision from 0.603 to 0.726 on test, with recall falling from 0.949 to 0.922.

## Decision

Two prompts review each doubtful answer. Judge 1 sees the quote and the clause question. Judge 2 also sees three lawyer examples of the clause, never from the same company. Both yes accepts, both no rejects, and a disagreement is queued for a person.

## Consequences

- Final clause-level precision 0.757 and recall 0.916 without any human.
- Automatic rejections are reliable: 12 of 273 were real clauses.
- 184 answers are queued (about 1.8 per contract), 177 of them judge disagreements, and only 34 of the 184 are real clauses.
- A perfect human on the queue would reach 0.762 precision, so most remaining errors are accepted answers, not queued ones.
- Both judges use the same model, so they can make the same mistake. The queue catches disagreement, not shared error.

## Alternatives considered

- One judge: lower precision.
- A different, independent model as the second judge: not tried; it would reduce shared error at extra cost.
