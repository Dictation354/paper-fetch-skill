"""Atypon asset scope selection for provider browser workflows."""

from __future__ import annotations

import copy
from typing import Any
from collections.abc import Mapping

from ...extraction.html import assets as _html_asset_impl
from ...extraction.html.parsing import choose_parser
from ...extraction.html.semantics import (
    SUPPLEMENTARY_BACK_MATTER_HEADINGS,
    node_identity_text,
    normalize_heading,
)
from ...extraction.html.shared import short_text as _short_text
from ...extraction.html.signals import HtmlExtractionFailure
from ...quality.html_availability import (
    HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
    clean_container,
    select_best_container,
)
from ...utils import normalize_text
from .._html_asset_engine import (
    HtmlAssetExtractionPolicy,
    extract_scoped_assets_with_policy,
)
from .normalization import _normalize_abstract_blocks
from .profile import (
    HEADING_TAG_PATTERN,
    _container_selection_policy,
    _content_fragment_html,
    _dedupe_top_level_nodes,
    _publisher_profile,
)

from bs4 import BeautifulSoup, Tag

ATYPON_BROWSER_WORKFLOW_SUPPLEMENTARY_SECTION_SELECTORS = (
    "section#supplementary-materials",
    "section.core-supplementary-materials",
    "section[id*='supplementary']",
    "section[class*='supplementary']",
    "section[aria-labelledby*='supplementary']",
    ".widget-ArticleDataSupplements",
)


ATYPON_BROWSER_WORKFLOW_SUPPLEMENTARY_HEADING_KEYS = (
    SUPPLEMENTARY_BACK_MATTER_HEADINGS - {"electronic supplementary material"}
)


def _atypon_browser_workflow_supplementary_heading_key(node: Tag) -> str:
    heading = node.find(HEADING_TAG_PATTERN)
    if not isinstance(heading, Tag):
        return ""
    return normalize_heading(_short_text(heading))


def _is_atypon_browser_workflow_supplementary_section(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    classes = {
        normalize_text(str(value))
        for value in (node.get("class") or [])
        if normalize_text(str(value))
    }
    if "widget-ArticleDataSupplements" in classes:
        return True
    if normalize_text(node.name or "").lower() != "section":
        return False

    heading_key = _atypon_browser_workflow_supplementary_heading_key(node)
    if heading_key in ATYPON_BROWSER_WORKFLOW_SUPPLEMENTARY_HEADING_KEYS:
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


def _atypon_browser_workflow_supplementary_sections(container: Tag) -> list[Tag]:
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in ATYPON_BROWSER_WORKFLOW_SUPPLEMENTARY_SECTION_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(
                match, Tag
            ) or not _is_atypon_browser_workflow_supplementary_section(match):
                continue
            match_id = id(match)
            if match_id in seen:
                continue
            seen.add(match_id)
            candidates.append(match)

    for section in container.find_all("section"):
        if not isinstance(
            section, Tag
        ) or not _is_atypon_browser_workflow_supplementary_section(section):
            continue
        section_id = id(section)
        if section_id in seen:
            continue
        seen.add(section_id)
        candidates.append(section)
    return _dedupe_top_level_nodes(candidates)


def _extract_atypon_browser_workflow_asset_html_scopes(
    body_container: Tag,
    supplementary_container: Tag,
    *,
    publisher: str,
) -> tuple[str, str]:
    for node in list(_atypon_browser_workflow_supplementary_sections(body_container)):
        node.decompose()

    supplementary_html = "\n".join(
        str(node)
        for node in _atypon_browser_workflow_supplementary_sections(
            supplementary_container
        )
        if normalize_text(node.get_text(" ", strip=True))
    )
    return _content_fragment_html(
        body_container, publisher=publisher
    ), supplementary_html


def _atypon_browser_workflow_supplementary_asset_is_supported(
    asset: Mapping[str, Any],
) -> bool:
    url = normalize_text(str(asset.get("url") or "")).lower()
    return (
        "/doi/suppl/" in url and "/suppl_file/" in url or "/article-supplement/" in url
    )


def extract_supplementary_assets(
    html_text: str, source_url: str
) -> list[dict[str, str]]:
    return [
        asset
        for asset in _html_asset_impl.extract_supplementary_assets(
            html_text, source_url
        )
        if _atypon_browser_workflow_supplementary_asset_is_supported(asset)
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
        policy=HtmlAssetExtractionPolicy(
            supplementary_extractor=extract_supplementary_assets
        ),
    )


def extract_browser_workflow_asset_html_scopes(
    html_text: str,
    source_url: str,
    publisher: str,
) -> tuple[str, str]:
    soup = BeautifulSoup(html_text, choose_parser())
    container = select_best_container(
        soup, publisher, policy=_container_selection_policy(publisher)
    )
    if container is None:
        raise HtmlExtractionFailure(
            "article_container_not_found",
            "Could not identify the main article container in publisher HTML.",
        )

    raw_body_container = copy.deepcopy(container)
    clean_container(
        container, publisher, drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW
    )

    supplementary_container = copy.deepcopy(container)
    body_container = copy.deepcopy(container)
    _normalize_abstract_blocks(body_container)

    profile = _publisher_profile(publisher)
    hook = profile.dom_hooks.asset_body_container
    if hook is not None:
        hook(body_container)
    if profile.extract_asset_html_scopes is not None:
        return profile.extract_asset_html_scopes(
            body_container,
            supplementary_container,
            publisher=publisher,
            source_url=source_url,
            raw_body_container=raw_body_container,
            content_fragment_html=_content_fragment_html,
            atypon_browser_workflow_supplementary_sections=_atypon_browser_workflow_supplementary_sections,
        )

    return (
        _content_fragment_html(body_container, publisher=publisher),
        _content_fragment_html(supplementary_container, publisher=publisher),
    )


def extract_atypon_browser_workflow_supplementary_section_asset_html_scopes(
    body_container: Tag,
    supplementary_container: Tag,
    *,
    publisher: str,
) -> tuple[str, str]:
    return _extract_atypon_browser_workflow_asset_html_scopes(
        body_container,
        supplementary_container,
        publisher=publisher,
    )


__all__ = [
    "ATYPON_BROWSER_WORKFLOW_SUPPLEMENTARY_HEADING_KEYS",
    "ATYPON_BROWSER_WORKFLOW_SUPPLEMENTARY_SECTION_SELECTORS",
    "extract_atypon_browser_workflow_supplementary_section_asset_html_scopes",
    "extract_browser_workflow_asset_html_scopes",
    "extract_scoped_html_assets",
    "extract_supplementary_assets",
]
