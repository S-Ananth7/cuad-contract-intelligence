# Trust layer: checks that a quote the AI gave really exists in the contract.

def normalize(text: str) -> str:
    return " ".join(text.split())


def quote_in_contract(contract_text: str, quote: str) -> bool:
    """True if the quote appears in the contract. Ignores extra spaces and line breaks."""
    clean_quote = normalize(quote)
    if clean_quote == "":
        return False
    return clean_quote in normalize(contract_text)