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

ignore extra whitespace (formatting, not a lie), reject empty quotes (no proof), and tests prove both.

loader functions return values and never print. Tests use tiny fake data, so they never read the 40 MB file.

What you learned without noticing:

Count before you build.
Never print contract text. Print numbers.
The terminal beats the editor squiggle.
Autocomplete can add wrong imports. Read the top of your file.
Tests prove the code works. Evals measure whether the AI is good.

Root files

.env              done soon  your secret key. Never in Git.
.env.example      planned    same line, no key. Tells others what is needed.
.gitignore        done       tells Git to skip data/, venv/, .env.
requirements.txt  done       list of packages the project needs.
pytest.ini        done       tells pytest where src is.
README.md         planned    what the project does, how to run, your final numbers.

src/cuad_ai/: the real code. Reused and tested.

schema.py    done     the form: found, quotes, value.
validate.py  done     lie detector: is the quote really in the contract?
loader.py    done     reads contracts, piles, text, lawyers' answers.
config.py    planned  reads .env and settings: model name, timeout, retries.
llm.py       planned  the one wrapper for model calls. Timeout, retry, logs tokens, cost, seconds.
extract.py   planned  the pipeline: build prompt, call model, check form, check quotes, retry once, else human review.
baseline.py  planned  dumb keyword search for "governed by". Free. The model must beat it.
metrics.py   planned  turns results into recall, precision, cost, latency.

prompts/

governing_law_v1.txt  planned  instructions to the model. One file per version.

evals/: the exam

splits.json   done     the 30 dev and 30 test titles.
run_eval.py   planned  runs the pipeline on dev, scores against lawyers' answers, saves a report.
reports/      planned  one report per run: model, prompt version, scores, cost.

tests/: proof the code is correct. No real model, no cost.

test_validate.py  done     5 tests for the lie detector.
test_loader.py    done     4 tests with tiny fake data.
test_schema.py    planned  bad form is refused.
test_extract.py   planned  fake model gives a lie, pipeline rejects it.

scripts/: one-off helpers. Not part of the product.

explore.py       done  your learning notebook.
make_split.py    done  made the two piles. Rerun only if needed.
dump_one.py      done  saved one contract for by-hand testing.
check_loader.py  done  proved loader reads 510 / 30 / 30.
hello_model.py   planned  tiny model call to test key and connection.

data/ and notes/

data/CUADv1.json  the 510 contracts and lawyers' answers. Not in Git.
notes/decisions.md  your engineering diary: what you chose and why.