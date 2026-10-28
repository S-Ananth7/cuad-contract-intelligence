import json

from cuad_ai.llm import call_model
from cuad_ai.schema import GoverningLaw
from cuad_ai.validate import quote_in_contract


def load_prompt(path: str) -> str:
    """Read the prompt file and return its text."""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def build_prompt(prompt_text: str, contract_text: str) -> str:
    """Join the instructions and the contract into one prompt string."""
    return f"{prompt_text}\n\nContract:\n{contract_text}"


def extract_json(reply: str) -> str:
    """Return the text from the first '{' to the last '}'. Raise ValueError if there is none."""
    start = reply.find("{")
    end = reply.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return reply[start: end + 1]


def parse_reply(reply: str) -> GoverningLaw:
    """Turn the model's reply into a GoverningLaw form. Raises ValueError if it cannot."""
    data = json.loads(extract_json(reply))
    return GoverningLaw.model_validate(data)


def extract_governing_law(contract_text: str, prompt_text: str, call=call_model) -> dict:
    """Run one contract through the whole chain. Return one row of data. Never prints."""
    row = {
        "found": None,
        "value": None,
        "quotes": [],
        "quotes_real": None,
        "tokens_in": 0,
        "tokens_out": 0,
        "seconds": 0.0,
        "attempts": 0,
        "error": None,
    }

    try:
        result = call(build_prompt(prompt_text, contract_text))
    except Exception as error:
        row["error"] = f"call failed: {type(error).__name__}"
        return row

    row["tokens_in"] = result["tokens_in"]
    row["tokens_out"] = result["tokens_out"]
    row["seconds"] = result["seconds"]
    row["attempts"] = result["attempts"]

    try:
        answer = parse_reply(result["text"])
    except ValueError:
        row["error"] = "parse failed"
        return row

    row["found"] = answer.found
    row["value"] = answer.value
    row["quotes"] = answer.quotes
    if answer.quotes:
        row["quotes_real"] = all(quote_in_contract(contract_text, q) for q in answer.quotes)
    else:
        row["quotes_real"] = not answer.found
    return row
