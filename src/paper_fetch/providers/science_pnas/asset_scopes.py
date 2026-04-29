"""Asset scope selection and scoped asset extraction for Science/PNAS pages."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from ...extraction.html import assets as _html_asset_impl
from ...extraction.html.parsing import choose_parser
from ...extraction.html.semantics import node_identity_text, normalize_heading
from ...extraction.html.shared import short_text as _short_text
from ...extraction.html.signals import SciencePnasHtmlFailure
from ...quality.html_availability import HTML_CONTAINER_DROP_BROWSER_WORKFLOW, clean_container, select_best_container
from ...utils import normalize_text
from .. import _wiley_html
from .._html_asset_engine import HtmlAssetExtractionPolicy, extract_scoped_assets_with_policy
from .normalization import (
    _drop_front_matter_teaser_figures,
    _normalize_abstract_blocks,
)
from .profile import (
    HEADING_TAG_PATTERN,
    _container_selection_policy,
    _content_fragment_html,
    _dedupe_top_level_nodes,
    _drop_abstract_sections_from_body_container,
)

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

SCIENCE_PNAS_SUPPLEMENTARY_SECTION_SELECTORS = (
    "section#supplementary-materials",
    "section.core-supplementary-materials",
    "section[id*='supplementary']",
    "section[class*='supplementary']",
    "section[aria-labelledby*='supplementary']",
)


SCIENCE_PNAS_SUPPLEMENTARY_HEADING_KEYS = {
    "supplementary material",
    "supplementary materials",
    "supplementary information",
    "supporting information",
}


def _extract_wiley_asset_html_scopes(
    body_container: Tag,
    supplementary_container: Tag,
) -> tuple[str, str]:
    for node in list(_wiley_html.find_supporting_information_sections(body_container)):
        node.decompose()

    supplementary_fragments = [
        _content_fragment_html(node, publisher="wiley")
        for node in _wiley_html.find_supporting_information_sections(supplementary_container)
    ]
    supplementary_html = "\n".join(
        fragment for fragment in supplementary_fragments if normalize_text(fragment)
    )
    return _content_fragment_html(body_container, publisher="wiley"), supplementary_html


def _science_pnas_supplementary_heading_key(node: Tag) -> str:
    heading = node.find(HEADING_TAG_PATTERN)
    if not isinstance(heading, Tag):
        return ""
    return normalize_heading(_short_text(heading))


def _is_science_pnas_supplementary_section(node: Any) -> bool:
    if Tag is None or not isinstance(node, Tag):
        return False
    if normalize_text(node.name or "").lower() != "section":
        return False

    heading_key = _science_pnas_supplementary_heading_key(node)
    if heading_key in SCIENCE_PNAS_SUPPLEMENTARY_HEADING_KEYS:
        return True

    identity = node_identity_text(node).lower()
    return any(
        token in identity
        for token in (
            "core-supplementary-materials",
            "supplementary-materials",
            "supplemental-materials",
        )
    )


def _science_pnas_supplementary_sections(container: Tag) -> list[Tag]:
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in SCIENCE_PNAS_SUPPLEMENTARY_SECTION_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag) or not _is_science_pnas_supplementary_section(match):
                continue
            match_id = id(match)
            if match_id in seen:
                continue
            seen.add(match_id)
            candidates.append(match)

    for section in container.find_all("section"):
        if not isinstance(section, Tag) or not _is_science_pnas_supplementary_section(section):
            continue
        section_id = id(section)
        if section_id in seen:
            continue
        seen.add(section_id)
        candidates.append(section)
    return _dedupe_top_level_nodes(candidates)


def _extract_science_pnas_asset_html_scopes(
    body_container: Tag,
    supplementary_container: Tag,
    *,
    publisher: str,
) -> tuple[str, str]:
    for node in list(_science_pnas_supplementary_sections(body_container)):
        node.decompose()

    supplementary_html = "\n".join(
        str(node)
        for node in _science_pnas_supplementary_sections(supplementary_container)
        if normalize_text(node.get_text(" ", strip=True))
    )
    return _content_fragment_html(body_container, publisher=publisher), supplementary_html


def _science_pnas_supplementary_asset_is_supported(asset: Mapping[str, Any]) -> bool:
    url = normalize_text(str(asset.get("url") or "")).lower()
    return "/doi/suppl/" in url and "/suppl_file/" in url


def extract_supplementary_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    return [
        asset
        for asset in _html_asset_impl.extract_supplementary_assets(html_text, source_url)
        if _science_pnas_supplementary_asset_is_supported(asset)
    ]


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile,
    supplementary_html_text: str | None = None,
) -> list[dict[str, str]]:
    return extract_scoped_assets_with_policy(
        body_html_text,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html_text,
        policy=HtmlAssetExtractionPolicy(supplementary_extractor=extract_supplementary_assets),
    )


def extract_browser_workflow_asset_html_scopes(
    html_text: str,
    source_url: str,
    publisher: str,
) -> tuple[str, str]:
    del source_url
    if BeautifulSoup is None:
        raise SciencePnasHtmlFailure("missing_bs4", "BeautifulSoup is required for browser-workflow HTML asset extraction.")

    soup = BeautifulSoup(html_text, choose_parser())
    container = select_best_container(soup, publisher, policy=_container_selection_policy(publisher))
    if container is None:
        raise SciencePnasHtmlFailure(
            "article_container_not_found",
            "Could not identify the main article container in publisher HTML.",
        )

    clean_container(container, publisher, drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW)

    supplementary_container = copy.deepcopy(container)
    body_container = copy.deepcopy(container)
    _normalize_abstract_blocks(body_container)
    _drop_front_matter_teaser_figures(body_container, publisher)
    _drop_abstract_sections_from_body_container(body_container, publisher)

    if publisher == "wiley":
        return _extract_wiley_asset_html_scopes(body_container, supplementary_container)
    if publisher in {"science", "pnas"}:
        return _extract_science_pnas_asset_html_scopes(
            body_container,
            supplementary_container,
            publisher=publisher,
        )

    return (
        _content_fragment_html(body_container, publisher=publisher),
        _content_fragment_html(supplementary_container, publisher=publisher),
    )


__all__ = [
    "SCIENCE_PNAS_SUPPLEMENTARY_SECTION_SELECTORS",
    "SCIENCE_PNAS_SUPPLEMENTARY_HEADING_KEYS",
    "extract_supplementary_assets",
    "extract_scoped_html_assets",
    "extract_browser_workflow_asset_html_scopes",
]
