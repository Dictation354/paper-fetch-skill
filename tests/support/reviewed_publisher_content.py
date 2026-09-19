"""Shared test support; contains no collected tests."""

import re
import unicodedata


def _words(text):
    """Coarse text locator only; scientific fidelity needs independent checks."""
    from tests.support.scientific_content import without_latex_spacing

    text = without_latex_spacing(text)
    text = re.sub(r"\[([^\]]+)\]\([^\n]*?\)", r"\1", text)
    text = re.sub(r"</?(?:sub|sup|br|em|strong|i|b|span)(?:\s[^<>]*?)?\s*/?>", "", text)
    text = unicodedata.normalize("NFKC", text).replace("π", "pi")
    return "".join(c for c in text.casefold() if c.isalnum())
