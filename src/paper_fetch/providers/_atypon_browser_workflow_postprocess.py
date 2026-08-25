"""Shared browser-workflow DOM and Markdown post-processing helpers."""

from __future__ import annotations

import re

from ..extraction.html.provider_rules import MarkdownHooks
from ..markdown.citations import (
    clean_citation_markers,
    normalize_inline_citation_markdown,
)

EQUATION_HEADING_JOIN_PATTERN = re.compile(r"(\S)(\*\*Equation\s+\d+[A-Za-z]?\.\*\*)")
DISPLAY_MATH_OPEN_PATTERN = re.compile(r"(?<=\S)(\$\$)")
DISPLAY_MATH_BLOCK_PATTERN = re.compile(r"\$\$\s*(.+?)\s*\$\$", flags=re.DOTALL)
DISPLAY_MATH_TRAILING_PATTERN = re.compile(r"(?<=\$\$)(?=[^\s\n])")


def is_display_math_markdown_block(markdown_text: str) -> bool:
    return bool(DISPLAY_MATH_BLOCK_PATTERN.fullmatch(str(markdown_text or "").strip()))


def normalize_equation_markdown_blocks(markdown_text: str) -> str:
    text = EQUATION_HEADING_JOIN_PATTERN.sub(r"\1\n\n\2", markdown_text)
    text = DISPLAY_MATH_OPEN_PATTERN.sub(r"\n\n\1", text)

    def normalize_display_math(match: re.Match[str]) -> str:
        body = match.group(1).strip()
        return f"$$\n{body}\n$$"

    text = DISPLAY_MATH_BLOCK_PATTERN.sub(normalize_display_math, text)
    return DISPLAY_MATH_TRAILING_PATTERN.sub("\n\n", text)


def normalize_browser_workflow_markdown(
    markdown_text: str,
    *,
    markdown_hooks: MarkdownHooks | None = None,
) -> str:
    # Shared cleanup runs for every browser-workflow publisher before any
    # provider-specific markdown hook, such as Science citation italic repair.
    normalized = normalize_equation_markdown_blocks(markdown_text)
    normalized = clean_citation_markers(normalized)
    normalize_markdown = (
        markdown_hooks.normalize_markdown if markdown_hooks is not None else None
    )
    if normalize_markdown is not None:
        normalized = normalize_markdown(normalized)
    return normalize_inline_citation_markdown(normalized)
