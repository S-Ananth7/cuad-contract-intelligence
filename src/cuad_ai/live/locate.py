"""Find where a verified quote sits in the original contract text, so the page can highlight it.

Verification (validate.quote_in_contract) ignores extra spaces and line breaks. This does the same, then maps the
match back to positions in the untouched text. If a quote occurs twice, the first occurrence is used.
"""
import re

_TOKEN = re.compile(r"\S+")


class Locator:
    """Builds the whitespace-normalised text once, then finds any number of quotes in it."""

    def __init__(self, text):
        chars, origin, previous_end = [], [], None
        for match in _TOKEN.finditer(text):
            if previous_end is not None:
                chars.append(" ")
                origin.append(previous_end)
            chars.extend(match.group())
            origin.extend(range(match.start(), match.end()))
            previous_end = match.end()
        self.clean = "".join(chars)
        self.origin = origin

    def find(self, quote):
        """(start, end) in the original text, or None when the quote is not there."""
        clean_quote = " ".join(quote.split())
        if not clean_quote:
            return None
        at = self.clean.find(clean_quote)
        if at == -1:
            return None
        return self.origin[at], self.origin[at + len(clean_quote) - 1] + 1


def locate(text, quote):
    return Locator(text).find(quote)
