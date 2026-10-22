## Problem
Lawyers read hundreds of contracts. Slow and costly. 
Build a system that finds key clauses and shows the exact quote.

## User
In-house lawyer doing due diligence

## Flow
contract text - > LLM -> backend validation -> result -> score against answer key

## First clause: Governing Law
Form (boxes the answer must fill):
- found: yes or no
- quotes: list of exact sentences from the contract
- value: state or country, like "Delaware"

# Rules:
- Not found: found = no, quotes empty, value empty
- Several sentences: put all of item in the quotes list.
- Every quote must appear word for word in the contract. If not, reject.
- Value must come from a quote. No quote, no value.

## Open questions
- What if the contract names two states?
- What if the quote check fails twice?

Governing Law: 437 present, 73 absent, total 510.
464 quotes, 0 mismatches, labels clean for Governing Law.