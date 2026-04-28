"""Shared author extraction helpers for browser-workflow providers."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Pattern

from ..extraction.html.parsing import choose_parser
from ..utils import dedupe_authors, normalize_text
from ._script_json import extract_assignment_json, extract_script_json

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None


class AuthorExtractionPipeline:
    def __init__(self, *extractors: Callable[[str], list[str]]) -> None:
        self.extractors = tuple(extractors)

    def __call__(self, html_text: str) -> list[str]:
        for extractor in self.extractors:
            authors = dedupe_authors(extractor(html_text))
            if authors:
                return authors
        return []


def load_json_assignment(html_text: str, pattern: Pattern[str]) -> Mapping[str, Any] | None:
    payload = extract_assignment_json(html_text, pattern)
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


def jsonld_types(node: Mapping[str, Any]) -> set[str]:
    raw_types = node.get("@type")
    if isinstance(raw_types, str):
        values = [raw_types]
    elif isinstance(raw_types, list):
        values = [item for item in raw_types if isinstance(item, str)]
    else:
        values = []
    return {normalize_text(value).lower() for value in values if normalize_text(value)}


def iter_jsonld_nodes(payload: Any) -> list[Mapping[str, Any]]:
    nodes: list[Mapping[str, Any]] = []
    queue: list[Any] = [payload]
    while queue:
        current = queue.pop(0)
        if isinstance(current, list):
            queue.extend(current)
            continue
        if not isinstance(current, Mapping):
            continue
        nodes.append(current)
        graph = current.get("@graph")
        if isinstance(graph, list):
            queue.extend(graph)
        elif isinstance(graph, Mapping):
            queue.append(graph)
    return nodes


def _schema_name_from_mapping(value: Mapping[str, Any]) -> str:
    direct_name = normalize_text(str(value.get("name") or ""))
    if direct_name:
        return direct_name
    return normalize_text(
        " ".join(
            part
            for part in (
                normalize_text(str(value.get("givenName") or "")),
                normalize_text(str(value.get("familyName") or "")),
            )
            if part
        )
    )


def _schema_author_names(value: Any) -> list[str]:
    if isinstance(value, list):
        authors: list[str] = []
        for item in value:
            authors.extend(_schema_author_names(item))
        return authors
    if isinstance(value, Mapping):
        candidate = _schema_name_from_mapping(value)
    else:
        candidate = normalize_text(str(value or ""))
    return [candidate] if looks_like_author_name(candidate) else []


def _expand_path_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if value is None:
        return []
    return [value]


def _values_at_schema_path(node: Mapping[str, Any], path: str) -> list[Any]:
    values: list[Any] = [node]
    for key in path.split("."):
        next_values: list[Any] = []
        for value in values:
            if isinstance(value, Mapping):
                next_values.extend(_expand_path_value(value.get(key)))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Mapping):
                        next_values.extend(_expand_path_value(item.get(key)))
        values = next_values
    return values


def extract_schema_author_names(
    node: Mapping[str, Any],
    *,
    author_paths: tuple[str, ...] = ("author",),
) -> list[str]:
    authors: list[str] = []
    for path in author_paths:
        for value in _values_at_schema_path(node, path):
            authors.extend(_schema_author_names(value))
    return dedupe_authors(authors)


def extract_jsonld_authors(
    html_text: str,
    *,
    article_types: set[str] | frozenset[str],
    author_paths: tuple[str, ...] = ("author",),
) -> list[str]:
    if BeautifulSoup is None:
        return []
    authors: list[str] = []
    for payload in extract_script_json(html_text, type_pattern="ld+json"):
        for node in iter_jsonld_nodes(payload):
            if not (jsonld_types(node) & article_types):
                continue
            authors.extend(extract_schema_author_names(node, author_paths=author_paths))
    return dedupe_authors(authors)


def extract_meta_authors(html_text: str, *, keys: set[str]) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, choose_parser())
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
    soup = BeautifulSoup(html_text, choose_parser())
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
    count_pattern: Pattern[str] | None = None,
    reject_email: bool = False,
    reject_affiliation_prefixes: tuple[str, ...] = (),
) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, choose_parser())
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
                count_pattern=count_pattern,
                reject_email=reject_email,
                reject_affiliation_prefixes=reject_affiliation_prefixes,
            ):
                continue
            if looks_like_author_name(candidate):
                authors.append(candidate)
    return dedupe_authors(authors)
