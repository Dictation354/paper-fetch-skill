"""Structured YAML front matter parsing for locally saved paper Markdown."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from ..publisher_identity import normalize_doi

_CONTENT_KINDS = frozenset({"fulltext", "abstract_only", "metadata_only"})


@dataclass(frozen=True)
class MarkdownFrontMatter:
    """Identity and quality fields required for cache-safe Markdown reuse."""

    doi: str
    source: str
    has_fulltext: bool
    content_kind: str
    completed_at: str | None = None

    @property
    def is_fulltext(self) -> bool:
        return self.has_fulltext and self.content_kind == "fulltext"


def _front_matter_mapping(markdown: str) -> Mapping[str, Any] | None:
    lines = markdown.splitlines()
    if not lines or lines[0].removeprefix("\ufeff").strip() != "---":
        return None

    closing_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in {"---", "..."}:
            closing_index = index
            break
    if closing_index is None:
        return None

    try:
        parsed = yaml.safe_load("\n".join(lines[1:closing_index]))
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _completed_at_text(value: Any) -> str | None:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip() or None
    return None


def parse_markdown_front_matter(markdown: str) -> MarkdownFrontMatter | None:
    """Parse the cache identity fields from a Markdown YAML front matter block."""

    parsed = _front_matter_mapping(markdown)
    if parsed is None:
        return None

    raw_doi = parsed.get("doi")
    raw_source = parsed.get("source")
    raw_has_fulltext = parsed.get("has_fulltext")
    raw_content_kind = parsed.get("content_kind")
    if not isinstance(raw_doi, str) or not isinstance(raw_source, str):
        return None
    if not isinstance(raw_has_fulltext, bool) or not isinstance(raw_content_kind, str):
        return None

    doi = normalize_doi(raw_doi)
    source = raw_source.strip()
    content_kind = raw_content_kind.strip().lower()
    if not doi or not source or content_kind not in _CONTENT_KINDS:
        return None
    return MarkdownFrontMatter(
        doi=doi,
        source=source,
        has_fulltext=raw_has_fulltext,
        content_kind=content_kind,
        completed_at=_completed_at_text(parsed.get("completed_at")),
    )


def read_markdown_front_matter(path: Path) -> MarkdownFrontMatter | None:
    """Read and parse YAML front matter without inferring identity from the filename."""

    try:
        markdown = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return parse_markdown_front_matter(markdown)


__all__ = [
    "MarkdownFrontMatter",
    "parse_markdown_front_matter",
    "read_markdown_front_matter",
]
