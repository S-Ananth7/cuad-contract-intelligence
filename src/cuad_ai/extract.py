def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
        return content

def build_prompt(prompt_text: str, contract_text: str) -> str:
    """Join the instructions and the contract into one prompt string."""
    return f"{prompt_text}\n\nContract:\n{contract_text}"

    