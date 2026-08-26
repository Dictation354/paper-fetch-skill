"""Structured YAML front matter parsing for locally saved paper Markdown."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from pathlib import Path
from typing import Any

import yaml

from ..models import AcquisitionProvenance, coerce_acquisition_provenance
from ..publisher_identity import normalize_doi

_CONTENT_KINDS = frozenset({"fulltext", "abstract_only", "metadata_only"})
MAX_FRONT_MATTER_BYTES = 256 * 1024


@dataclass(frozen=True)
class MarkdownFrontMatter:
    """Identity and quality fields required for cache-safe Markdown reuse."""

    doi: str
    source: str
    has_fulltext: bool
    content_kind: str
    completed_at: str | None = None
    acquisition: AcquisitionProvenance | None = None

    @property
    def is_fulltext(self) -> bool:
        return self.has_fulltext and self.content_kind == "fulltext"


@dataclass(frozen=True)
class MarkdownFrontMatterFile:
    """One-pass identity parse and whole-file digest for an index refresh."""

    front_matter: MarkdownFrontMatter | None
    content_sha256: str
    front_matter_sha256: str | None


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
    raw_acquisition = parsed.get("acquisition")
    acquisition = coerce_acquisition_provenance(raw_acquisition)
    if raw_acquisition is not None and acquisition is None:
        return None
    return MarkdownFrontMatter(
        doi=doi,
        source=source,
        has_fulltext=raw_has_fulltext,
        content_kind=content_kind,
        acquisition=acquisition,
        completed_at=_completed_at_text(parsed.get("completed_at")),
    )


def read_markdown_front_matter(path: Path) -> MarkdownFrontMatter | None:
    """Read only a bounded prefix; paper body size cannot inflate identity parsing."""

    try:
        with path.open("rb") as handle:
            prefix = handle.read(MAX_FRONT_MATTER_BYTES + 1)
    except (OSError, UnicodeError):
        return None
    if len(prefix) > MAX_FRONT_MATTER_BYTES:
        prefix = prefix[:MAX_FRONT_MATTER_BYTES]
    try:
        markdown = prefix.decode("utf-8")
    except UnicodeError:
        return None
    return parse_markdown_front_matter(markdown)


def read_markdown_front_matter_file(path: Path) -> MarkdownFrontMatterFile | None:
    """Parse the bounded front matter while hashing a changed file in one pass."""

    digest = hashlib.sha256()
    prefix = bytearray()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                if len(prefix) < MAX_FRONT_MATTER_BYTES:
                    remaining = MAX_FRONT_MATTER_BYTES - len(prefix)
                    prefix.extend(block[:remaining])
    except OSError:
        return None
    try:
        markdown = bytes(prefix).decode("utf-8")
    except UnicodeError:
        front_matter = None
    else:
        front_matter = parse_markdown_front_matter(markdown)
    front_matter_digest = None
    if front_matter is not None:
        lines = markdown.splitlines()
        closing_index = next(
            (
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() in {"---", "..."}
            ),
            None,
        )
        if closing_index is not None:
            front_matter_digest = hashlib.sha256(
                "\n".join(lines[: closing_index + 1]).encode("utf-8")
            ).hexdigest()
    return MarkdownFrontMatterFile(
        front_matter=front_matter,
        content_sha256=digest.hexdigest(),
        front_matter_sha256=front_matter_digest,
    )


__all__ = [
    "MAX_FRONT_MATTER_BYTES",
    "MarkdownFrontMatter",
    "MarkdownFrontMatterFile",
    "parse_markdown_front_matter",
    "read_markdown_front_matter",
    "read_markdown_front_matter_file",
]
