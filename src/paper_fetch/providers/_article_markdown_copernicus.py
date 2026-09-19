"""Copernicus adapters around the shared NLM/JATS XML renderer."""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from typing import Any
from collections.abc import Mapping
import re
import xml.etree.ElementTree as ET

from ..reason_codes import OFFICIAL_FULL_SIZE_NOT_EXPOSED
from ..utils import normalize_text
from ..xml_security import XmlParseFailure, parse_xml
from ._article_markdown_common import child_text, iter_descendants
from ._retained_object_links import resolve_retained_object_links

from ._article_markdown_jats import (
    JatsExtraction,
    parse_jats_xml,
)

CopernicusExtraction = JatsExtraction


def _restore_empty_bibliography_xrefs(root: ET.Element, source_url: str) -> None:
    """Restore only empty citations from their explicitly identified bibliography."""
    references = {
        ref.get("id"): ref for ref in iter_descendants(root, "ref") if ref.get("id")
    }
    for node in iter_descendants(root, "xref"):
        if node.get("ref-type") != "bibr" or normalize_text("".join(node.itertext())):
            continue
        citations = []
        for rid in (node.get("rid") or "").split():
            ref = references.get(rid)
            if ref is None:
                citations.append(f"[Reference unavailable: {rid}]")
                continue
            label = normalize_text(child_text(ref, "label"))
            # Copernicus natbib labels can append the expanded author list
            # after the short author(year) label. Both parts are source data.
            short = re.match(r"^(.*?\(\d{4}[a-z]?\))", label)
            if short:
                label = re.sub(r"\s*\(", " (", short[1], count=1)
            label = label or f"Reference {rid}"
            citations.append(
                resolve_retained_object_links(
                    f"[{label}](#{rid})", source_url, {rid: rid}
                )
            )
        node.text = "; ".join(citations) or "[Reference unavailable]"


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


def _restore_empty_object_xrefs(root: ET.Element) -> None:
    parents = {child: parent for parent in root.iter() for child in parent}
    targets = {
        node.get("id"): normalize_text(child_text(node, "label"))
        for kind in ("fig", "table-wrap")
        for node in iter_descendants(root, kind)
        if node.get("id")
    }
    for node in iter_descendants(root, "xref"):
        if node.get("ref-type") not in {"fig", "table"} or normalize_text(
            "".join(node.itertext())
        ):
            continue
        labels = [targets.get(rid, "") for rid in (node.get("rid") or "").split()]
        if labels and all(labels):
            parent = parents[node]
            index = list(parent).index(node)
            preceding = parent[index - 1].tail if index else parent.text
            # Avoid "Fig. Figure 1" when the publisher puts the object type
            # outside an empty xref but includes it in the target's label.
            if re.search(r"(?:Figs?\.?|Figures?|Tables?)\s*$", preceding or "", re.I):
                labels = [
                    re.sub(r"^(?:Figures?|Figs?\.?|Tables?)\s+", "", label, flags=re.I)
                    for label in labels
                ]
            node.text = ", ".join(labels)


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
    try:
        root = (
            deepcopy(xml_root)
            if xml_root is not None
            else parse_xml(
                xml_body, source="Copernicus JATS XML", allow_external_doctype=True
            )
        )
    except XmlParseFailure:
        return None
    _restore_empty_bibliography_xrefs(root, source_url)
    _restore_empty_object_xrefs(root)
    extraction = parse_jats_xml(
        xml_body,
        source_url=source_url,
        base_metadata=base_metadata,
        xml_root=root,
    )
    return (
        _promote_copernicus_official_graphics(extraction)
        if extraction is not None
        else None
    )


__all__ = [
    "CopernicusExtraction",
    "parse_copernicus_xml",
]
