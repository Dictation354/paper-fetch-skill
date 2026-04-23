"""Leaf XML traversal helpers for article Markdown rendering."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..utils import normalize_text


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def normalize_compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def first_child(element: ET.Element | None, local_name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in list(element):
        if isinstance(child.tag, str) and xml_local_name(child.tag) == local_name:
            return child
    return None


def first_descendant(element: ET.Element | None, local_name: str) -> ET.Element | None:
    if element is None:
        return None
    for node in element.iter():
        if isinstance(node.tag, str) and xml_local_name(node.tag) == local_name:
            return node
    return None


def render_literal_inline_text(element: ET.Element | None, *, skip_local_names: set[str] | None = None) -> str:
    if element is None:
        return ""
    skip_names = skip_local_names or set()
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in list(node):
            if not isinstance(child.tag, str):
                if child.tail:
                    parts.append(child.tail)
                continue
            local_name = xml_local_name(child.tag)
            if local_name in skip_names:
                if child.tail:
                    parts.append(child.tail)
                continue
            if local_name == "sup":
                parts.append(f"<sup>{render_literal_inline_text(child, skip_local_names=skip_names)}</sup>")
            elif local_name == "sub":
                parts.append(f"<sub>{render_literal_inline_text(child, skip_local_names=skip_names)}</sub>")
            elif local_name == "bold":
                parts.append(f"**{render_literal_inline_text(child, skip_local_names=skip_names)}**")
            elif local_name == "italic":
                parts.append(f"*{render_literal_inline_text(child, skip_local_names=skip_names)}*")
            elif local_name in {"break", "br"}:
                parts.append("\n")
            else:
                visit(child)
            if child.tail:
                parts.append(child.tail)

    visit(element)
    return normalize_text("".join(parts))


def child_text(element: ET.Element | None, local_name: str) -> str:
    return render_literal_inline_text(first_child(element, local_name))
