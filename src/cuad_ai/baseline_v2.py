import re
import time

from cuad_ai.baseline import split_sentences
from cuad_ai.validate import quote_in_contract

# Phrases that state a rule. Headings and boilerplate do not contain them.
STRONG_PHRASES = (
    "shall be governed",
    "governed by",
    "governed, interpreted",
    "construed in accordance with",
    "interpreted in accordance with",
)
MAX_SECTION_NUMBERS = 2


def is_clause_like(sentence: str) -> bool:
    """True if the sentence states a governing-law rule, not a heading, a contents line, or a pointer."""
    lowered = sentence.lower()
    if len(re.findall(r"\b\d+\.\d+\b", sentence)) > MAX_SECTION_NUMBERS:
        return False
    if not re.search(r"\blaws?\b", lowered):
        return False
    return any(phrase in lowered for phrase in STRONG_PHRASES)


def keyword_governing_law_v2(contract_text: str, max_quotes: int = 3) -> dict:
    """Free baseline v2: only sentences that state a governing-law rule. No model."""
    start = time.perf_counter()
    quotes = [s for s in split_sentences(contract_text) if is_clause_like(s)][:max_quotes]
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