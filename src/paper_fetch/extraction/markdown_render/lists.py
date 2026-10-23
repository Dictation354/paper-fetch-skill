"""List rendering helpers."""

from __future__ import annotations

from ._ir import MarkdownList


def render_list(lst: MarkdownList) -> list[str]:
    lines: list[str] = []
    index = 1
    for item in lst.items:
        text = item.strip()
        if not text:
            continue
        marker = f"{index}." if lst.ordered else "-"
        first, *continuation = text.splitlines()
        lines.append(f"{marker} {first}")
        indent = " " * (len(marker) + 1)
        lines.extend(indent + line if line else "" for line in continuation)
        index += 1
    if lines:
        lines.append("")
    return lines
