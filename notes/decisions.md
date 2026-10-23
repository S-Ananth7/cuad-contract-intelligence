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
split rule, seed 42, 22 present and 8 absent per pile, plus a line on twins. Test stays locked.

Story: a worker checks a contract and hands you a form. The form has three boxes: found, quotes, value.

Good form 1: worker says “yes, found”. The quotes box holds the sentence. The value box says Pennsylvania. Everything agrees.

Good form 2: worker says “no, not found”. The quotes box is empty. The value box is empty. Everything agrees.

Bad form A: worker says “no, not found”, but the quotes box holds a sentence. The boxes disagree. Which one is true? Nobody knows.

Bad form B: worker says “yes, found”, but the quotes box is empty. No proof. You cannot check it, so you cannot trust it.

Right now your form accepts A and B. It only checks that each box has the right kind of thing. It does not check that the boxes agree. A better clerk would refuse A and B. We add that rule later. Do not code it today.