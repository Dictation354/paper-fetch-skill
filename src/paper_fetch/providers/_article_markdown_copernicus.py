"""Copernicus adapters around the shared NLM/JATS XML renderer."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from collections.abc import Mapping
import xml.etree.ElementTree as ET

from ..reason_codes import OFFICIAL_FULL_SIZE_NOT_EXPOSED

from ._article_markdown_jats import (
    JatsExtraction,
    build_jats_markdown_document,
    extract_jats_authors,
    extract_jats_metadata,
    extract_jats_references,
    parse_jats_xml,
)

CopernicusExtraction = JatsExtraction
extract_copernicus_authors = extract_jats_authors
extract_copernicus_metadata = extract_jats_metadata
extract_copernicus_references = extract_jats_references


def _copernicus_full_size_score(alternative: Mapping[str, Any]) -> tuple[int, int]:
    specific_use = str(alternative.get("specific_use") or "").strip().lower()
    media_type = str(alternative.get("media_type") or "").strip().lower()
    score = 20 if media_type == "graphic" else 0
    if any(token in specific_use for token in ("original", "full", "high", "large")):
        score += 40
    if any(token in specific_use for token in ("preview", "thumb", "small", "low")):
        score -= 40
    try:
        panel_index = int(alternative.get("panel_index") or 0)
    except (TypeError, ValueError):
        panel_index = 0
    return score, -panel_index


def _promote_copernicus_official_graphics(
    extraction: CopernicusExtraction,
) -> CopernicusExtraction:
    promoted: list[dict[str, Any]] = []
    for raw_asset in extraction.assets:
        asset = dict(raw_asset)
        if str(asset.get("kind") or "").strip().lower() != "figure":
            promoted.append(asset)
            continue
        alternatives = [
            dict(item)
            for item in list(asset.get("alternatives") or [])
            if isinstance(item, Mapping) and str(item.get("url") or "").strip()
        ]
        if not alternatives:
            asset["provenance"] = [OFFICIAL_FULL_SIZE_NOT_EXPOSED]
            promoted.append(asset)
            continue
        selected = max(alternatives, key=_copernicus_full_size_score)
        selected_url = str(selected.get("url") or "").strip()
        specific_use = str(selected.get("specific_use") or "").strip().lower()
        official_graphic = str(selected.get("media_type") or "").lower() == "graphic"
        explicitly_preview = any(
            token in specific_use for token in ("preview", "thumb", "small", "low")
        )
        asset.update(
            {
                "link": selected_url,
                "url": selected_url,
                "original_url": selected_url,
            }
        )
        if official_graphic and not explicitly_preview:
            asset["full_size_url"] = selected_url
            asset["download_url"] = selected_url
        else:
            asset["preview_url"] = selected_url
            asset["provenance"] = [OFFICIAL_FULL_SIZE_NOT_EXPOSED]
        promoted.append(asset)
    return replace(extraction, assets=promoted)


def parse_copernicus_xml(
    xml_body: bytes,
    *,
    source_url: str,
    base_metadata: Mapping[str, Any] | None = None,
    xml_root: ET.Element | None = None,
) -> CopernicusExtraction | None:
    extraction = parse_jats_xml(
        xml_body,
        source_url=source_url,
        base_metadata=base_metadata,
        xml_root=xml_root,
    )
    return (
        _promote_copernicus_official_graphics(extraction)
        if extraction is not None
        else None
    )


def build_copernicus_markdown_document(
    extraction: CopernicusExtraction,
    *,
    xml_path: Path | None = None,
) -> str:
    return build_jats_markdown_document(
        extraction,
        xml_path=xml_path,
        provider_label="copernicus",
    )


__all__ = [
    "CopernicusExtraction",
    "build_copernicus_markdown_document",
    "extract_copernicus_authors",
    "extract_copernicus_metadata",
    "extract_copernicus_references",
    "parse_copernicus_xml",
]
