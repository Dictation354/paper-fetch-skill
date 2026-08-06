"""Elsevier object-resource indexing and formula locator helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET

from ..utils import normalize_text
from ._elsevier_xml_rules import (
    ELSEVIER_IMAGE_ASSET_TYPES,
    classify_elsevier_asset_kind,
    infer_elsevier_asset_group_key,
)


XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def elsevier_asset_priority(
    asset_kind: str,
    asset_type: str,
    category: str | None = None,
) -> int:
    """Rank official object variants from full-size to thumbnail."""

    normalized_type = asset_type.strip().upper()
    normalized_category = (category or "").strip().lower()
    if asset_kind not in ELSEVIER_IMAGE_ASSET_TYPES:
        return 0
    if normalized_type == "IMAGE-HIGH-RES":
        return 0
    if normalized_type == "IMAGE-DOWNSAMPLED":
        return 1
    if normalized_type == "IMAGE-THUMBNAIL" or normalized_category == "thumbnail":
        return 3
    return 2


def _normalized_locator(value: str | None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    return normalize_text(infer_elsevier_asset_group_key(normalized))


def resolve_elsevier_formula_locator(element: ET.Element | None) -> str:
    """Resolve a formula link locator, falling back to an href basename."""

    if element is None:
        return ""
    formula_nodes = [
        node
        for node in element.iter()
        if isinstance(node.tag, str)
        and _local_name(node.tag) in {"formula", "inline-formula"}
    ]
    for formula in formula_nodes:
        for node in formula.iter():
            if not isinstance(node.tag, str) or _local_name(node.tag) != "link":
                continue
            locator = _normalized_locator(node.get("locator"))
            if locator:
                return locator
            href = _normalized_locator(node.get(XLINK_HREF) or node.get("href"))
            if href:
                return href
    return ""


def elsevier_formula_locators(root: ET.Element) -> frozenset[str]:
    locators: set[str] = set()
    for element in root.iter():
        if not isinstance(element.tag, str) or _local_name(element.tag) not in {
            "formula",
            "inline-formula",
        }:
            continue
        locator = resolve_elsevier_formula_locator(element)
        if locator:
            locators.add(locator)
    return frozenset(locators)


def extract_elsevier_object_references(root: ET.Element) -> list[dict[str, Any]]:
    """Select the best official resource for each semantic object group."""

    formula_locators = elsevier_formula_locators(root)
    selected: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
    for element in root.iter():
        if not isinstance(element.tag, str) or _local_name(element.tag) != "object":
            continue

        source_url = normalize_text(element.text)
        if not source_url:
            continue
        object_type = normalize_text(element.get("type"))
        category = normalize_text(element.get("category"))
        object_mimetype = normalize_text(element.get("mimetype"))
        ref = normalize_text(element.get("ref")) or source_url
        group_key = _normalized_locator(ref)
        asset_kind = classify_elsevier_asset_kind(ref, object_type, category)
        if group_key in formula_locators and asset_kind in ELSEVIER_IMAGE_ASSET_TYPES:
            asset_kind = "image"

        reference: dict[str, Any] = {
            "asset_type": asset_kind,
            "source_kind": "object",
            "source_ref": ref,
            "source_url": source_url,
            "content_type": object_mimetype or None,
            "filename_hint": Path(urllib.parse.urlparse(source_url).path).name or ref,
            "object_type": object_type or None,
            "category": category or None,
        }
        priority = elsevier_asset_priority(asset_kind, object_type, category)
        key = (asset_kind, group_key)
        existing = selected.get(key)
        if existing is None or priority < existing[0]:
            selected[key] = (priority, reference)
    return [item[1] for item in selected.values()]


def build_elsevier_object_index(
    root: ET.Element,
    *,
    references: Iterable[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Index selected object resources by exact ref and semantic group key."""

    index: dict[str, dict[str, Any]] = {}
    object_references = (
        references
        if references is not None
        else extract_elsevier_object_references(root)
    )
    for reference in object_references:
        source_ref = normalize_text(str(reference.get("source_ref") or ""))
        group_key = _normalized_locator(source_ref)
        if source_ref:
            index[source_ref] = reference
        if group_key:
            index[group_key] = reference
    return index
