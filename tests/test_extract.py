from cuad_ai.extract import build_prompt, load_prompt

INSTRUCTIONS = "Find the governing law sentence. Return JSON."
CONTRACT = "This Agreement is governed by the laws of Texas."

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