"""Typed upstream publication dates without inferred or substituted dates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict


class PublicationDate(TypedDict):
    kind: str
    value: str
    source: str


def publication_date(kind: str, value: Any, source: str) -> list[PublicationDate]:
    if value is None or not str(value).strip():
        return []
    return [{"kind": kind, "value": str(value).strip(), "source": source}]


def normalize_publication_dates(value: Any) -> list[PublicationDate]:
    result: list[PublicationDate] = []
    for item in value if isinstance(value, (list, tuple)) else ():
        if not isinstance(item, Mapping):
            continue
        entry = publication_date(
            str(item.get("kind") or "unspecified"),
            item.get("value"),
            str(item.get("source") or ""),
        )
        if entry and entry[0] not in result:
            result.extend(entry)
    return result


def citation_date(value: Any) -> str | None:
    dates = normalize_publication_dates(value)
    for kind in ("print", "online", "issued", "unspecified", "created"):
        for item in dates:
            if item["kind"] == kind:
                return item["value"]
    return None


def publication_years(value: Any) -> set[int]:
    import re

    years = set()
    for item in normalize_publication_dates(value):
        if item["kind"] == "created":
            continue
        match = re.search(r"(?<!\d)([12]\d{3})(?!\d)", item["value"])
        if match:
            years.add(int(match[1]))
    return years
