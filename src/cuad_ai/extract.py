import json
from cuad_ai.schema import GoverningLaw

def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
        return content

def build_prompt(prompt_text: str, contract_text: str) -> str:
    """Join the instructions and the contract into one prompt string."""
    return f"{prompt_text}\n\nContract:\n{contract_text}"

def extract_json(reply: str) -> str:
    """Return the text from the first '{' to the last '}'. Raise ValueError if there is none."""
    start = reply.find("{")
    end = reply.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return reply[start : end + 1]

def parse_reply(reply: str) -> GoverningLaw:
    """Turn the model's reply into a GoverningLaw form. Raises ValueError if it cannot."""
    data = json.loads(extract_json(reply))
    return GoverningLaw.model_validate(data)
    
        