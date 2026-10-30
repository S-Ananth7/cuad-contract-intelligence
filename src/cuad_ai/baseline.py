import re
import time

from cuad_ai.validate import normalize, quote_in_contract

PHRASES = ("governed by", "governing law", "contributed in accordinate with", "laws of the state of")

def split_sentences(text: str) -> list[str]:
    """Rough sentence split on . ! ? followed by a space. Abbreviations like 'Inc.' split wrongly."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalize(text)) if s.strip()] 

def keyword_governing_law(contract_text: str, max_quotes: int = 3) -> dict:
    """Free baseline: return the first sentences that contain a governing-law phrase. No model."""
    start = time.perf_counter()
    quotes = [
        sentence
        for sentence in split_sentences(contract_text)
        if any(phrase in sentence.lower() for phrase in PHRASES)
    ][:max_quotes]
    return {
        "found": len(quotes) > 0,
        "value": None,
        "quotes": quotes,
        "quotes_real": all(quote_in_contract(contract_text, q) for q in quotes),
        "tokens_in": 0,
        "tokens_out": 0,
        "seconds": time.perf_counter() - start,
        "attempts": 0,
        "error": None,
    }