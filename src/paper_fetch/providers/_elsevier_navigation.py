"""Source-key navigation for Elsevier Markdown, resolved after output selection."""

from __future__ import annotations

import re
from urllib.parse import quote

from ..markdown.math import MATH_MARKDOWN_PATTERN

PREFIX = "elsevier-"
_ANCHOR = re.compile(r'<a id="(elsevier-[^"<>\s]+)"></a>')
# Protect literal content and whole external links before inspecting local links.
_LITERAL = re.compile(
    r"(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^(?P=fence)[ \t]*$"
    r"|(?P<code>`+)(?:(?!(?P=code)).)*?(?P=code)"
    r"|"
    + MATH_MARKDOWN_PATTERN
    + r"|!?\[(?:\\.|[^\[\]\\\n])*\]\((?!#)(?:[^()\n]|\([^()\n]*\))*\)",
    re.M | re.S,
)
_LINK = re.compile(
    r"(?<!!)\[((?:\\.|[^\[\]\\\n]|\[[^\[\]\n]*\])*)\]\(#(elsevier-[^()\s]+)\)"
)


def anchor_id(key: str) -> str:
    return PREFIX + quote(str(key), safe="-_.:")


def anchor_markup(key: str) -> str:
    return f'<a id="{anchor_id(key)}"></a>'


def finalize_markdown(markdown: str) -> str:
    """Only retained, unique source targets can remain clickable."""
    literals: dict[str, str] = {}

    def protect(match):
        token = f"ELSEVIERLITERAL{len(literals)}TOKEN"
        while token in markdown:
            token += "X"
        literals[token] = match[0]
        return token

    text = _LITERAL.sub(protect, markdown)
    # A budget may stop between an anchor and its content. No target survives
    # when only whitespace remains before the next heading or end of output.
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not re.fullmatch(r'(?:[ \t]*<a id="elsevier-[^"<>\s]+"></a>)+\s*', line):
            continue
        following = next(
            (
                value
                for value in lines[index + 1 :]
                if value.strip()
                and not re.fullmatch(
                    r'(?:[ \t]*<a id="elsevier-[^"<>\s]+"></a>)+\s*', value
                )
            ),
            "",
        )
        next_heading = re.match(r"[ \t]*(#{1,6}) ", following)
        previous = next(
            (
                value
                for value in reversed(lines[:index])
                if value.strip() and not _ANCHOR.fullmatch(value.strip())
            ),
            "",
        )
        previous_heading = re.match(r"[ \t]*(#{1,6}) ", previous)
        owns_subsections = (
            next_heading is not None
            and previous_heading is not None
            and len(next_heading[1]) > len(previous_heading[1])
        )
        if not following or (next_heading is not None and not owns_subsections):
            lines[index] = "\n" if line.endswith("\n") else ""
    text = "".join(lines)
    seen = set()

    def unique(match):
        target = match[1]
        if target in seen:
            return ""
        seen.add(target)
        return match[0]

    text = _ANCHOR.sub(unique, text)
    # Strip a generated opening tag cut short by a finite render budget.
    text = re.sub(
        r'<a(?: id="elsevier-[^<>\n]*(?:>(?:</a?)?)?)?(?:\.\.\.)?\s*\Z', "", text
    )
    text = _LINK.sub(lambda m: m[0] if m[2] in seen else m[1], text)
    for token, value in literals.items():
        text = text.replace(token, value)
    return text


def prepare_xml_navigation(root):
    """Annotate a private XML tree using source refids, never citation positions."""
    import xml.etree.ElementTree as ET
    from ._article_markdown_common import xml_local_name, render_inline_text

    targets = {node.get("id"): node for node in root.iter() if node.get("id")}
    linked_keys: set[str] = set()
    for node in list(root.iter()):
        if xml_local_name(node.tag) not in {"cross-ref", "cross-refs"}:
            continue
        refids = (node.get("refid") or "").split()
        # A range/multi-target label has no unique source destination.
        linked_keys.update(refids)
        if len(refids) == 1:
            label = render_inline_text(node)
            node.set("data-paper-fetch-markdown", "1")
            node.text = f"[{label}](#{anchor_id(refids[0])})"
    for key, node in targets.items():
        kind = xml_local_name(node.tag)
        if kind in {"section", "abstract-sec", "formula", "display"}:
            node.set("data-elsevier-anchor", anchor_markup(key))
            continue
        if kind in {"figure", "table"}:
            caption = next(
                (n for n in node if xml_local_name(n.tag) == "caption"), None
            )
            if caption is None:
                continue
            node = caption
        elif (
            kind
            not in {
                "para",
                "simple-para",
                "note-para",
                "table-footnote",
                "footnote",
                "article-footnote",
            }
            or key not in linked_keys
        ):
            continue
        marker = ET.Element("span", {"data-paper-fetch-markdown": "1"})
        marker.text = anchor_markup(key)
        marker.tail = node.text
        node.text = None
        node.insert(0, marker)
