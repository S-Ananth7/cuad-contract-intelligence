from cuad_ai.pipeline.extraction import RETRY_NOTE, extract_with_retry

CONTEXT = "The laws of Delaware govern."
GOOD = '{"found": true, "quotes": ["laws of Delaware"], "value": "Delaware"}'
INVENTED = '{"found": true, "quotes": ["laws of Texas"], "value": "Texas"}'


def make_call(*replies):
    seen = []

    def call(prompt):
        seen.append(prompt)
        return {"text": replies[min(len(seen), len(replies)) - 1], "tokens_in": 10, "tokens_out": 2,
                "seconds": 0.0, "attempts": 1}

    call.seen = seen
    return call


def test_a_good_first_reply_is_not_retried():
    call = make_call(GOOD)
    row = extract_with_retry(CONTEXT, "ask", call)
    assert (row["retried"], row["unsolved"], len(call.seen)) == (False, False, 1)


def test_a_bad_reply_is_retried_once_with_the_note_and_tokens_are_added():
    call = make_call("not json", GOOD)
    row = extract_with_retry(CONTEXT, "ask", call)
    assert row["retried"] and not row["unsolved"] and row["found"]
    assert RETRY_NOTE in call.seen[1] and RETRY_NOTE not in call.seen[0]
    assert row["tokens_in"] == 20


def test_an_invented_quote_that_stays_invented_is_unsolved():
    call = make_call(INVENTED, INVENTED)
    row = extract_with_retry(CONTEXT, "ask", call)
    assert row["retried"] and row["unsolved"] and len(call.seen) == 2
