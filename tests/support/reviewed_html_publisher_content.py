"""Shared test support; contains no collected tests."""

import re
import unicodedata


def _table_cell(text):
    text = text.replace(r"\*", "*")
    text = re.sub(r"\[([^\]]+)\]\([^\n]*?\)", r"\1", text)
    text = re.sub(r"</?(?:sub|sup|br|em|strong|i|b|span)(?:\s[^<>]*?)?\s*/?>", "", text)
    text = unicodedata.normalize("NFKC", text).replace("−", "-").replace("–", "-")
    return re.sub(r"\s+", "", text.replace("*", ""))
