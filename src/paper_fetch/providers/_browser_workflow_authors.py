"""Shared author extraction helpers for browser-workflow providers."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Pattern

from ..utils import dedupe_authors, normalize_text

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None


def load_json_assignment(html_text: str, pattern: Pattern[str]) -> Mapping[str, Any] | None:
    match = pattern.search(html_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def normalized_author_tokens(value: str | None) -> list[str]:
    return [
        normalize_text(token)
        for token in str(value or "").split("|")
        if normalize_text(token)
    ]


def looks_like_author_name(text: str) -> bool:
    normalized = normalize_text(text)
    return bool(normalized) and any(character.isalpha() for character in normalized)


def is_ignored_author_text(
    text: str,
    *,
    ignored_text: set[str],
    count_pattern: Pattern[str] | None = None,
    reject_email: bool = False,
    reject_affiliation_prefixes: tuple[str, ...] = (),
) -> bool:
    normalized = normalize_text(text).lower()
    if not normalized:
        return True
    if normalized in ignored_text:
        return True
    if normalized.startswith(("http://", "https://")) or "orcid.org" in normalized:
        return True
    if count_pattern is not None and count_pattern.fullmatch(normalized):
        return True
    if reject_email and ("@" in normalized or normalized.startswith("mailto:")):
        return True
    return any(normalized.startswith(prefix) for prefix in reject_affiliation_prefixes)


def extract_meta_authors(html_text: str, *, keys: set[str]) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    for meta in soup.find_all("meta"):
        if Tag is not None and not isinstance(meta, Tag):
            continue
        key = normalize_text(str(meta.get("name") or meta.get("property") or "")).lower()
        if key not in keys:
            continue
        candidate = normalize_text(str(meta.get("content") or ""))
        if looks_like_author_name(candidate):
            authors.append(candidate)
    return dedupe_authors(authors)


def extract_property_authors(
    html_text: str,
    *,
    selectors: str,
    ignored_text: set[str],
    count_pattern: Pattern[str] | None = None,
    reject_email: bool = False,
) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    for node in soup.select(selectors):
        if Tag is not None and not isinstance(node, Tag):
            continue
        given_node = node.select_one("[property='givenName']")
        family_node = node.select_one("[property='familyName']")
        name = normalize_text(
            " ".join(
                part
                for part in (
                    given_node.get_text(" ", strip=True) if isinstance(given_node, Tag) else "",
                    family_node.get_text(" ", strip=True) if isinstance(family_node, Tag) else "",
                )
                if normalize_text(part)
            )
        )
        if not name:
            name_node = node.select_one("[property='name']")
            if isinstance(name_node, Tag):
                name = normalize_text(name_node.get_text(" ", strip=True))
        if not name:
            fragments = [
                fragment
                for fragment in (normalize_text(item) for item in node.stripped_strings)
                if fragment
                and not is_ignored_author_text(
                    fragment,
                    ignored_text=ignored_text,
                    count_pattern=count_pattern,
                    reject_email=reject_email,
                )
            ]
            name = normalize_text(" ".join(fragments))
        if looks_like_author_name(name):
            authors.append(name)
    return dedupe_authors(authors)


def extract_selector_authors(
    html_text: str,
    *,
    selectors: tuple[str, ...],
    ignored_text: set[str],
    node_text: Callable[[Any], str],
    reject_email: bool = False,
    reject_affiliation_prefixes: tuple[str, ...] = (),
) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    seen_nodes: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            if Tag is not None and not isinstance(node, Tag):
                continue
            if id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))
            candidate = node_text(node)
            if is_ignored_author_text(
                candidate,
                ignored_text=ignored_text,
                reject_email=reject_email,
                reject_affiliation_prefixes=reject_affiliation_prefixes,
            ):
                continue
            if looks_like_author_name(candidate):
                authors.append(candidate)
    return dedupe_authors(authors)
