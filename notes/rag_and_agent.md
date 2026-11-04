# Retrieval and Agent: Why, How, Tradeoff

Last updated: 2026-11-02

## 1. Problem
Each extraction call sends the whole contract. One call per clause per contract means every contract is sent 41 times.

| Fact | Value |
|---|---|
| Median contract | 33,143 characters, about 8,300 tokens |
| Longest dev contract | about 40,000 tokens |
| Calls for 10 contracts x 41 clauses | 410 |
| Calls for 510 contracts x 41 clauses | 20,910 (about 170 million input tokens at median size) |
| Precision on the 41-clause run | 0.596 (neighbouring clauses taken for the asked one) |

Consequences:
- Cost grows with contract length and contract count.
- One prompt cannot hold the work as it grows.
- Most of each prompt is irrelevant to the clause. The noise also causes false alarms.

## 2. Approach
1. Split each contract into chunks and store them in Postgres with an embedding and a full-text index.
2. For a clause, search with the clause description and fetch the top few chunks.
3. The model reads only those chunks, picks the sentence and quotes it.
4. `validate.py` verifies that the quote exists in the contract.
5. A small agent handles clauses where one pass fails: it can search again, read another chunk, and re-verify, up to a fixed step limit.
6. Progress is stored in the database, not in the conversation.

Expected effect: input per call falls from about 8,000 tokens to roughly 1,000 to 2,000 and stays that size for any contract length. Fewer false alarms is expected but not measured yet.

## 3. Tradeoff
| Gain | Cost or risk |
|---|---|
| Much smaller input per call | If retrieval misses the right chunk, the clause cannot be found. The failure is silent. |
| Cost no longer grows with contract length | More system to build and run: chunking, embeddings, an index |
| Fewer false alarms from neighbouring clauses (to be measured) | A clause can be split across two chunks |
| Progress and results kept in the database | Retrieval must be measured on its own (recall at k per clause) |
| Fits an agent with a step limit | The agent adds calls, latency and unpredictability |

Measured so far: keyword retrieval was safe for only 11 of 41 clauses, a saving of about 22% of tokens. Vector and hybrid retrieval are not measured yet.

## 4. Decision
- Use retrieval to find candidates.
- Use the agent only for clauses where one pass fails.
- Keep the whole-contract call as the fallback for any clause where retrieval recall is not proven.
- The verifier is unchanged: no quote is accepted unless it appears in the contract.

## 5. Components
| # | Component | Note |
|---|---|---|
| 1 | Ingestion | Tables for contracts, clauses, chunks, highlights, filled with checked data. Built first. |
| 2 | Chunker | Keeps character offsets so every chunk maps back to the contract |
| 3 | Embeddings | Model not chosen. Vector size must match it. |
| 4 | Retriever | Vector search plus full-text search in one SQL query |
| 5 | Verifier | Existing `validate.py` |
| 6 | Agent | Search, read and verify tools. Fixed step limit. State in the database. |
| 7 | Fallback | Whole-contract call |
| 8 | Evaluation | Recall at k per clause, then total cost and accuracy against the 410-call baseline |

## 6. Success criteria
- Retrieval: for each clause, the chunks cover at least 50% of an annotated highlight at some k. Report recall at k per clause.
- End to end: recall at least 0.90, invented quotes 0, failed calls at most 10%.
- Cost: total tokens and calls lower than the 410-call baseline at equal or better recall.
