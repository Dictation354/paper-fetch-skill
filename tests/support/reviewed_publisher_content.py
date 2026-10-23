"""Shared test support; contains no collected tests."""

import re
import unicodedata


def _words(text):
    """Coarse text locator only; scientific fidelity needs independent checks."""
    from tests.support.scientific_content import without_latex_spacing

    text = without_latex_spacing(text)
    text = re.sub(
        r"\\(?:mathrm|mathit|mathbf|mathsf|mathcal|operatorname|text|textit|textbf|textsf|texttt)\{([^{}]*)\}",
        r"\1",
        text,
    )
    from markdown_it import MarkdownIt

    tokens = MarkdownIt().parseInline(text)[0].children or []
    text = "".join(
        t.content
        for t in tokens
        if t.type in {"text", "code_inline", "html_inline", "image"}
    )
    text = re.sub(r"</?(?:sub|sup|br|em|strong|i|b|span)(?:\s[^<>]*?)?\s*/?>", "", text)
    text = unicodedata.normalize("NFKC", text).replace("π", "pi")
    return "".join(c for c in text.casefold() if c.isalnum())
