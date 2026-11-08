# Routing and Review: Raising Precision Without a Human

Last updated: 2026-11-08

This note covers what comes after retrieval and the model's first answer: checking each answer, deciding which ones to trust, and reviewing the doubtful ones with a second, cheap model call. The earlier steps are in `notes/ingestion_and_retrieval.md` (finding the passages) and `notes/rag_pipeline_results.md` (sending only those passages to the model). This note is a new file and replaces nothing.

## 1. The problem

After retrieval the model finds almost every real clause (recall about 0.95) but also claims many clauses that are not there (precision about 0.60). Out of 100 "found" answers, about 40 are false alarms. The cause is mostly vague, rare clauses (Post-Termination Services, Price Restrictions, Renewal Term): the model sees text that touches the topic and says "found".

Goal: raise precision without losing much recall, without a person in the loop, and without sending the whole contract again.

## 2. The pipeline

```
1. Model answers from 10 retrieved excerpts      -> found? + quotes
2. Deterministic checks                          -> quote must appear word for word in the contract
3. Embedding check (no model call)               -> does the quote look like THIS clause's lawyer examples?
4. Confidence + risk routing                     -> ACCEPT or REVIEW
5. Review (second model call, quote only)        -> two judges; both must say yes
6. Final answer                                  -> kept answers; rejected ones are dropped
```

Five small scripts, run in this order:

| Script | What it does | Model calls |
|---|---|---|
| `scripts/gate_features.py` | For each found answer, how close is the quote to each clause's lawyer examples | none |
| `scripts/route_answers.py` | Sorts answers into accept or review | none |
| `scripts/verify_answers.py` | Judge 1: quote + clause question only | one per review answer |
| `scripts/verify_with_examples.py` | Judge 2: same, plus 3 lawyer examples (few-shot) | one per review answer |
| (final step, by hand for now) | Keep answer only if both judges say yes | none |

## 3. Step by step, with real examples

### 3.1 Embedding check (confidence)

The quote is turned into a vector and compared with the lawyers' examples of all 41 clause types. Examples from the same company as the contract are never used. Two numbers are saved: the similarity to the asked clause, and the rank of the asked clause among all 41.

Example, a good answer (Anti-Assignment, rank 1, similarity 0.80):

> "Neither NETTAXI or SpinRecords.com shall assign its respective rights or delegate its obligations hereunder ... without the prior written consent ..."

The quote looks most like Anti-Assignment examples, and the lawyers agree.

Example, a bad answer (asked clause: Notice Period To Terminate Renewal, rank 6, similarity 0.73):

> "8.2 Convenience. NETTAXI may terminate this Agreement at any time for its convenience ... upon sixty (60) days prior written notice to SpinRecords.com."

The quote looks most like Termination For Convenience, not renewal notice. The lawyers did not mark it as the asked clause either. This is a false alarm the vectors can see.

Why rank matters more than similarity: 55% of real answers had the asked clause as rank 1, against only 16% of false alarms. Similarity alone overlaps too much (median 0.80 for real, 0.76 for false).

### 3.2 Risk (per clause)

Risk is how often a clause was a false alarm in other contracts. Governing Law is low risk. Price Restrictions is high risk (in the first 30 contracts the model claimed it 15 times and it was real once). The 30 contracts are split into two halves, and a clause's risk is learned only from the other half, so a clause is never scored with its own answers.

### 3.3 Routing

| Case | Route |
|---|---|
| Asked clause is the closest of 41, and clause risk is 0.5 or lower | ACCEPT |
| Clause is Document Name or Agreement Date | ACCEPT (see 3.4) |
| Everything else | REVIEW |

Nothing is dropped at this step. "Accept" means trusted now, "review" means check again.

### 3.4 Why Document Name and Agreement Date skip the review

A title or a date is not a sentence. The review question "is this quote itself that kind of clause?" is unfair for them. In the first test the review wrongly rejected 6 real answers for these two clauses (3 each) and was never right to reject any. Exempting them returned all 6 and added no false alarms. This rule comes from what the clauses are, not from a threshold tuned on data.

### 3.5 Review: the two prompts

Judge 1 (`prompts/verify_quote.txt`) sees only the clause name, the dataset's question for that clause, and the quote. It never sees the contract. It answers with JSON:

```
{"is_this_clause": true, "looks_like": "none"}
```

Judge 2 (`prompts/verify_quote_examples.txt`) is the few-shot version. It sees the same things plus 3 real lawyer-marked examples of the clause, picked as the 3 closest to the quote (same-company examples excluded, each cut to 400 characters). A rendered example:

```
Clause type: Non-Compete
The question for this clause type: Is there a restriction on the ability of a party to compete with the counterparty ...?

Here are real examples of this clause type, marked by lawyers in other contracts:
- <example 1>
- <example 2>
- <example 3>

Now the quote taken from a new contract:
<the quote>

Is the new quote the same kind of text as the examples, and does it, by itself, contain what the question asks for?
Say true only if it is. ...
```

Example of a correct rejection (asked clause: Joint Ip Ownership):

> "FCE will assign, and hereby assigns, to ExxonMobil ownership of Program Results ... Program Inventions shall be owned by ExxonMobil and its Affiliates."

Both judges said no and "looks like IP Ownership Assignment". One party owns everything, so it is not joint ownership.

Example of a wrong rejection, a real clause lost (asked clause: Non-Compete):

> "... any Major Competitor is or becomes the beneficial owner ... ten percent (10%) or greater of the voting power ... or the sale to any Major Competitor of all or substantially all ..."

Both judges said "this is change of control". The lawyers marked it as Non-Compete too, because it is about competitors. This is the kind of loss the review costs: 7 to 11 real clauses out of about 400.

Example where the judges disagree (false alarm for Notice Period To Terminate Renewal):

> "12.02 Early Termination ... either Party may terminate this Agreement ... for any reason and at any time upon giving ..."

Judge 1 said yes, Judge 2 (seeing real examples) said no. This is why two judges beat one.

### 3.6 Both must say yes

An answer survives only if neither judge rejected it. Judge 2 alone was no better than Judge 1 (it is more lenient: it rejects fewer real answers and fewer false ones). Requiring both removes about 17 to 21 more false alarms and loses almost no real clauses.

## 4. Results

Two sets of 30 validation contracts, 1,230 questions each. Rules were designed while looking at the first set. The second set was never used for tuning, so it is the honest estimate.

| Version | First 30: P / R | New 30: P / R |
|---|---|---|
| Retrieval only | 0.592 / 0.951 | 0.619 / 0.939 |
| Accept only (no review) | 0.931 / 0.508 | 0.938 / 0.527 |
| One review (no examples) | 0.726 / 0.922 | 0.719 / 0.916 |
| One review (with examples) | 0.714 / 0.932 | 0.715 / 0.923 |
| **Both must say yes** | **0.753 / 0.922** | **0.747 / 0.911** |

P = precision, R = recall (counting model errors as misses). On the new set: 389 real kept, 132 false alarms kept, 38 missed.

Input tokens: about 2,100 to 2,200 per question for retrieval (the whole-contract approach was about 12,770), plus about 340 per call for the 400 or so review calls per judge.

## 5. What to keep in mind

- The first-set numbers are slightly optimistic because the rules were tuned on them. The new-set numbers are the ones to quote.
- The margin of error on precision is about plus or minus 0.04 (95%) at this sample size. The gain from retrieval-only (0.62) to both-judges (0.75) is well beyond that. The gap between one judge and two (0.719 vs 0.747) is not.
- The lawyers' labels are incomplete. Some false alarms are real clauses nobody marked, so true precision is somewhat higher.
- The examples alone did not help. The improvement comes from two different judges agreeing, not from the examples.
- My early estimate of review cost was too low: it is about 340 tokens per call, not about 200.
- Accepting answers by confidence only (no review) gives precision 0.93, but recall falls to about 0.52, so the review step is needed.
- The model name `deepseek-v4-flash` is retired by DeepSeek and now served by its newer Flash model. Results across dates may differ slightly for that reason.

## 6. Not done yet

- Retry rule: an answer whose quote is not word for word in the excerpts (7 on the new set) or whose reply cannot be parsed (2) should be retried once, then rejected.
- A single command that runs the whole pipeline end to end (today it is five scripts).
- A stronger model (`deepseek-v4-pro`) on the doubtful clauses only. Parked for later.
- Per-clause number of excerpts (k), and a whole-contract fallback for clauses that stay uncertain.
- One final run on the 102 official test contracts, only after the design is frozen.

## 7. Reproduce

```powershell
$env:SET="validation"; $env:K="10"; $env:LIMIT="30"; $env:OFFSET="30"; python evals\run_rag.py
python scripts\gate_features.py <run folder>\report.json
python scripts\route_answers.py <run folder>
python scripts\verify_answers.py <run folder>
python scripts\verify_with_examples.py <run folder>
```

`OFFSET=0` gives the first 30 validation contracts, `OFFSET=30` the next 30.

## 8. Words used

| Word | Meaning |
|---|---|
| found | the model said the clause exists |
| gold | the lawyers marked it |
| real | found and gold agree |
| false alarm | found but not gold |
| miss | gold but not kept |
| precision | of the answers kept, how many are real |
| recall | of the real clauses, how many were kept |
| confidence | the asked clause is the closest of the 41 to the quote |
| risk | how often this clause was a false alarm in other contracts |
| judge | one review model call that says yes or no to a quote |
| few-shot | giving the model a few real examples inside the prompt |
