"""Shared browser-workflow DOM and Markdown post-processing helpers."""

from __future__ import annotations

import re

from ..extraction.html.provider_rules import MarkdownHooks
from ..markdown.citations import (
    clean_citation_markers,
    normalize_inline_citation_markdown,
)

EQUATION_HEADING_JOIN_PATTERN = re.compile(r"(\S)(\*\*Equation\s+\d+[A-Za-z]?\.\*\*)")
DISPLAY_MATH_BLOCK_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)\$\$[ \t]*\n(?P<body>.+?)\n[ \t]*\$\$[ \t]*$",
    flags=re.DOTALL | re.MULTILINE,
)


def is_display_math_markdown_block(markdown_text: str) -> bool:
    return bool(DISPLAY_MATH_BLOCK_PATTERN.fullmatch(str(markdown_text or "").strip()))


def normalize_equation_markdown_blocks(markdown_text: str) -> str:
    text = EQUATION_HEADING_JOIN_PATTERN.sub(r"\1\n\n\2", markdown_text)

    def normalize_display_math(match: re.Match[str]) -> str:
        lines = match["body"].splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        body = "\n".join(lines)
        indent = match["indent"]
        return f"{indent}$$\n{body}\n{indent}$$"

    # Only line-delimited fences establish display math. Same-line $$…$$ is
    # valid inline remark-math, including TeX containing its own dollar signs.
    return DISPLAY_MATH_BLOCK_PATTERN.sub(normalize_display_math, text)


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
