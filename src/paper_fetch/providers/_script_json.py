"""Shared JSON extraction helpers for provider-owned script payloads."""

from __future__ import annotations

import json
import re
from typing import Any, Pattern

from ..extraction.html.parsing import choose_parser
from ..utils import normalize_text

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

_JSON_CLOSERS = {"{": "}", "[": "]"}


def loads_json(value: str | None) -> Any | None:
    if not normalize_text(value):
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def extract_balanced_json(text: str, *, start_index: int = 0) -> str | None:
    open_index = min(
        (index for index in (text.find("{", start_index), text.find("[", start_index)) if index >= 0),
        default=-1,
    )
    if open_index < 0:
        return None

    stack: list[str] = []
    string_quote: str | None = None
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if string_quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == string_quote:
                string_quote = None
            continue

        if char in {'"', "'"}:
            string_quote = char
            continue
        if char in _JSON_CLOSERS:
            stack.append(_JSON_CLOSERS[char])
            continue
        if stack and char == stack[-1]:
            stack.pop()
            if not stack:
                return text[open_index : index + 1]
    return None


def _pattern_search(pattern: str | Pattern[str], text: str):
    if isinstance(pattern, str):
        return re.search(rf"\b{re.escape(pattern)}\s*=", text)
    return pattern.search(text)


def _group_payload(match) -> str | None:
    group_dict = match.groupdict()
    if "json" in group_dict:
        return group_dict["json"]
    if match.lastindex:
        for index in range(1, match.lastindex + 1):
            candidate = match.group(index)
            if normalize_text(candidate) and normalize_text(candidate)[0] in _JSON_CLOSERS:
                return candidate
    return None


def extract_assignment_json(text: str, assignment: str | Pattern[str]) -> Any | None:
    match = _pattern_search(assignment, text)
    if not match:
        return None
    grouped_payload = _group_payload(match)
    if grouped_payload is not None:
        parsed = loads_json(grouped_payload)
        if parsed is not None:
            return parsed
    balanced_payload = extract_balanced_json(text, start_index=match.end())
    return loads_json(balanced_payload)


def extract_function_call_json(text: str, function_name: str | Pattern[str]) -> Any | None:
    if isinstance(function_name, str):
        match = re.search(rf"\b{re.escape(function_name)}\s*\(", text)
    else:
        match = function_name.search(text)
    if not match:
        return None
    balanced_payload = extract_balanced_json(text, start_index=match.end())
    return loads_json(balanced_payload)


def _matches_filter(value: str, pattern: str | Pattern[str] | None) -> bool:
    if pattern is None:
        return True
    if isinstance(pattern, str):
        return pattern.lower() in value.lower()
    return bool(pattern.search(value))


def extract_script_json(
    html_text: str,
    *,
    type_pattern: str | Pattern[str] | None = None,
    id_pattern: str | Pattern[str] | None = None,
) -> list[Any]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, choose_parser())
    payloads: list[Any] = []
    for script in soup.find_all("script"):
        if Tag is not None and not isinstance(script, Tag):
            continue
        script_type = normalize_text(str(script.get("type") or ""))
        script_id = normalize_text(str(script.get("id") or ""))
        if not _matches_filter(script_type, type_pattern):
            continue
        if not _matches_filter(script_id, id_pattern):
            continue
        payload_text = script.string if script.string is not None else script.get_text()
        payload = loads_json(payload_text)
        if payload is not None:
            payloads.append(payload)
    return payloads
