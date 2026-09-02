"""Provider-neutral HTML helper utilities."""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

from ...utils import normalize_text
from ..image_payloads import image_mime_type_from_bytes

from bs4 import BeautifulSoup, Tag


def direct_child_tags(node: Tag) -> list[Tag]:
    return [child for child in node.find_all(recursive=False) if isinstance(child, Tag)]


def class_tokens(node: Any) -> set[str]:
    if not isinstance(node, Tag):
        return set()
    raw_value = (getattr(node, "attrs", None) or {}).get("class") or []
    if isinstance(raw_value, str):
        return {
            normalize_text(item).lower()
            for item in raw_value.split()
            if normalize_text(item)
        }
    return {
        normalize_text(str(item)).lower()
        for item in raw_value
        if normalize_text(str(item))
    }


def attr_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return normalize_text(" ".join(str(item) for item in value if item is not None))
    return normalize_text(str(value or ""))


def short_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def soup_root(node: Tag | None) -> BeautifulSoup | None:
    node_types = tuple(item for item in (Tag, BeautifulSoup) if item is not None)
    current: Any = node
    while current is not None:
        if isinstance(current, BeautifulSoup):
            return current
        parent = getattr(current, "parent", None)
        current = parent if node_types and isinstance(parent, node_types) else None
    return None


def append_text_block(
    parent: Tag, text: str, *, tag_name: str = "p", soup: BeautifulSoup | None = None
) -> None:
    root = soup or soup_root(parent)
    if root is None:
        return
    block = root.new_tag(tag_name)
    block.string = text
    parent.append(block)


def image_magic_type(body: bytes | bytearray | None) -> str:
    return image_mime_type_from_bytes(body)


def html_text_snippet(body: bytes | bytearray | None, *, limit: int = 240) -> str:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ""
    try:
        decoded = bytes(body[:4096]).decode("utf-8", errors="replace")
    except Exception:
        return ""
    text = re.sub(r"<[^>]+>", " ", decoded)
    return normalize_text(html_lib.unescape(text))[:limit]


def html_title_snippet(body: bytes | bytearray | None, *, limit: int = 160) -> str:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ""
    try:
        decoded = bytes(body[:8192]).decode("utf-8", errors="replace")
    except Exception:
        return ""
    match = re.search(
        r"<title\b[^>]*>(.*?)</title>", decoded, flags=re.IGNORECASE | re.DOTALL
    )
    if not match:
        return ""
    return normalize_text(html_lib.unescape(re.sub(r"<[^>]+>", " ", match.group(1))))[
        :limit
    ]
