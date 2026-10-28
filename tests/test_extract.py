import pytest
from cuad_ai.extract import build_prompt, load_prompt, parse_reply, \
    extract_governing_law

INSTRUCTIONS = "Find the governing law sentence. Return JSON."
CONTRACT = "This Agreement is governed by the laws of Texas."

FENCE = "`" * 3
GOOD = '{"found": true, "quotes": ["governed by Swiss law."], "value": "Switzerland"}'

ROW_CONTRACT = "This Agreement is governed by Swiss law."
REAL = '{"found": true, "quotes":["governed by Swiss law."], "value": "Switzerland"}'
INVENTED = '{"found": true, "quotes": ["governed by Mars law."], "value":"Mars"}'
FOUND_NO_QUOTES = '{"found": true, "quotes": [], "value": "Switzerland"}'
NOT_FOUND = '{"found": false, "quotes": [], "value": null}'


def fake_call(text):

    def call(prompt):
        return {"text": text, "tokens_in": 10, "tokens_out": 5, "seconds": 0.1, "attempts": 1}

    return call


def broken_call(prompt):
    raise RuntimeError("down")

#--- build_prompt and load_prompt ---


def test_prompt_contains_instructions():
    assert INSTRUCTIONS in build_prompt(INSTRUCTIONS, CONTRACT)


def test_prompt_contains_contract():
    assert CONTRACT in build_prompt(INSTRUCTIONS, CONTRACT)

    
def test_instructions_come_before_contract():
    prompt = build_prompt(INSTRUCTIONS, CONTRACT)
    assert prompt.index(INSTRUCTIONS) < prompt.index(CONTRACT)

    
def test_load_prompt_read_file(tmp_path):
    file = tmp_path / "prompt.txt"
    file.write_text("hello prompt", encoding="utf-8")
    assert load_prompt(str(file)) == "hello prompt"

# ---parse_reply---


def test_parse_plain_json():
    assert parse_reply(GOOD).value == "Switzerland"


def test_parse_fenced_json():
    assert parse_reply(FENCE + "json\n" + GOOD + "\n" + FENCE).value == "Switzerland"

    
def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_reply("sorry, I cannot help with that")


def test_parse_with_text_around():
    assert parse_reply("Here is the answer: " + GOOD + " Hope that helps!").value == "Switzerland"


def test_parse_wrong_shape_raises():
    with pytest.raises(ValueError):
        parse_reply('{"found": "banana", "quotes" :[]}')
        
# --- extract_governing_law ---


def test_real_quote_is_accepted():
    row = extract_governing_law(ROW_CONTRACT, "instructions", call=fake_call(REAL))
    assert row["found"] is True
    assert row["value"] == "Switzerland"
    assert row["quotes_real"] is True
    assert row["error"] is None
    assert row["tokens_in"] == 10

   
def test_invented_quote_is_rejected():
    row = extract_governing_law(ROW_CONTRACT, "instructions", call=fake_call(INVENTED))
    assert row["quotes_real"] is False


def test_found_without_has_no_proof():
    row = extract_governing_law(ROW_CONTRACT, "instructions", call=fake_call(FOUND_NO_QUOTES))
    assert row["quotes_real"] is False


def test_not_found_is_fine():
    row = extract_governing_law(ROW_CONTRACT, "instructions", call=fake_call(NOT_FOUND))
    assert row["found"] is False
    assert row["quotes_real"] is True


def test_garbage_reply_is_recorded_not_crashed():
    row = extract_governing_law(ROW_CONTRACT, "instructions", call=fake_call("sorry, no"))
    assert row["error"] == "parse failed"
    assert row["found"] is None

    
def test_failed_call_is_recorded_not_crashed():
    row = extract_governing_law(ROW_CONTRACT, "instructions", call=broken_call)
    assert row["error"] == "call failed: RuntimeError"
