"""Keep opaque TeX payloads out of Markdown prose normalization."""

from __future__ import annotations

import re
from collections.abc import Callable

# Dollar fences are chosen by the formula renderer to exceed every internal
# dollar run, including escaped dollars and math embedded in text arguments.
_INLINE_DOLLAR_MATH_PATTERN = (
    r"(?<![\\$])(?P<math_dollars>\$+)(?!\$)(?:(?!\n[ \t]*\n).)*?"
    r"(?<![\\$])(?P=math_dollars)(?!\$)"
)
DOLLAR_MATH_MARKDOWN_PATTERN = (
    r"^[ \t]*(?P<display_dollars>\${2,})[ \t]*\r?\n.*?"
    r"^[ \t]*(?P=display_dollars)[ \t]*\r?$" + "|" + _INLINE_DOLLAR_MATH_PATTERN
)
MATH_MARKDOWN_PATTERN = (
    DOLLAR_MATH_MARKDOWN_PATTERN + r"|(?<!\\)\\\((?:(?!\n[ \t]*\n).)*?(?<!\\)\\\)"
    r"|(?<!\\)\\\[(?:(?!\n[ \t]*\n).)*?(?<!\\)\\\]"
)
_CODE_OR_MATH = re.compile(
    r"(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[ \t]*$"
    r"|(?P<code>`+)(?:(?!(?P=code)).)*?(?P=code)"
    r"|(?P<math>" + MATH_MARKDOWN_PATTERN + ")",
    re.M | re.S,
)


def protect_markdown_math(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        if match.group("math") is None:
            return match[0]
        marker = f"PAPERFETCHMATHTEX{len(protected)}TOKEN"
        while marker in text:
            marker += "X"
        protected[marker] = match[0]
        return marker

    return _CODE_OR_MATH.sub(replace, text), protected


def restore_markdown_math(text: str, protected: dict[str, str]) -> str:
    for marker, original in protected.items():
        text = text.replace(marker, original)
    return text


def normalize_prose_preserving_math(text: str, normalize: Callable[[str], str]) -> str:
    prose, protected = protect_markdown_math(text)
    return restore_markdown_math(normalize(prose), protected)
