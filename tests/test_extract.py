import pytest
from cuad_ai.extract import build_prompt, load_prompt, parse_reply

INSTRUCTIONS = "Find the governing law sentence. Return JSON."
CONTRACT = "This Agreement is governed by the laws of Texas."

FENCE = "`" * 3
GOOD = '{"found": true, "quotes": ["governed by Swiss law."], "value": "Switzerland"}'

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