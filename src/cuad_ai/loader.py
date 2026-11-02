import json


def load_contracts(path: str="data/CUADv1.json") -> list[dict]:
    """Return the list of 510 contracts from the CUAD json file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)["data"]

    
def load_splits(path: str="evals/splits.json") -> dict:
    """Return {'dev': [titles], 'test':[titles]}."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_contract(contracts: list[dict], title: str) -> dict | None:
    """Return the contract with this title, or None if missing."""
    for contract in contracts:
        if contract["title"] == title:
            return contract
    return None


def get_text(contract: dict) -> str:
    """Return the full contract text."""
    return contract["paragraphs"][0]["context"]


def find_question(contract: dict, clause: str) -> dict | None:
    """Return the question for this clause, like 'Governing Law', or None."""
    for qa in contract["paragraphs"][0]["qas"]:
        if qa["id"].endswith("__" + clause):
            return qa
    return None


def get_gold_quotes(contract: dict, clause: str) -> list[str]:
    """Return the lawyer's quotes (answer key). Empty list if clause is absent."""
    qa = find_question(contract, clause)
    if qa is None:
        return []
    return [answer["text"] for answer in qa["answers"]]
            
