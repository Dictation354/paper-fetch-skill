"""Provider-neutral section hint normalization and matching helpers."""

from __future__ import annotations

from collections.abc import Container
from typing import Any, Mapping

from ..utils import normalize_text

SECTION_HINT_KINDS = frozenset({"body", "data_availability", "code_availability", "references"})


def normalize_section_hint_heading(value: Any) -> str:
    return normalize_text(value).lower().strip(" :")


def _coerce_int_field(value: Any, fallback: int) -> int:
    return int(value) if isinstance(value, int) or str(value).isdigit() else fallback


def _section_hint_value(hint: Any, key: str) -> Any:
    if isinstance(hint, Mapping):
        return hint.get(key)
    return getattr(hint, key, None)


def coerce_section_hint_dicts(
    section_hints: Any,
    *,
    allowed_kinds: Container[str] = SECTION_HINT_KINDS,
    default_level: int = 2,
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for index, hint in enumerate(section_hints or []):
        heading = normalize_text(_section_hint_value(hint, "heading"))
        kind = normalize_text(_section_hint_value(hint, "kind")).lower()
        if not heading or kind not in allowed_kinds:
            continue
        order = _coerce_int_field(_section_hint_value(hint, "order"), index)
        level = _coerce_int_field(_section_hint_value(hint, "level"), default_level)
        hints.append(
            {
                "heading": heading,
                "heading_key": normalize_section_hint_heading(heading),
                "level": level,
                "kind": kind,
                "order": order,
                "language": normalize_text(_section_hint_value(hint, "language")) or None,
                "source_selector": normalize_text(_section_hint_value(hint, "source_selector")) or None,
            }
        )
    hints.sort(key=lambda item: item["order"])
    return hints


def match_next_section_hint(
    section_hints: list[Mapping[str, Any]],
    hint_index: int,
    heading: str,
) -> tuple[Mapping[str, Any] | None, int]:
    heading_key = normalize_section_hint_heading(heading)
    if not heading_key:
        return None, hint_index
    for index in range(hint_index, len(section_hints)):
        hint = section_hints[index]
        candidate_key = normalize_text(hint.get("heading_key"))
        if not candidate_key:
            candidate_key = normalize_section_hint_heading(hint.get("heading"))
        if candidate_key == heading_key:
            return hint, index + 1
    return None, hint_index
