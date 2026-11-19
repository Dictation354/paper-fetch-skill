"""Springer asset extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..config import resolve_asset_download_concurrency
from ..extraction.html.assets import (
    FIGURE_KIND,
    FULL_SIZE_IMAGE_ATTRS,
    PREVIEW_IMAGE_ATTRS,
    SUPPLEMENTARY_KIND,
    AssetDownloadOptions,
    FigurePageFetcher,
    _soup_attr_url,
    download_assets,
    looks_like_full_size_asset_url,
    split_body_and_supplementary_assets,
)
from ..extraction.html.assets import (
    extract_figure_assets as extract_generic_figure_assets,
)
from ..extraction.html.assets import (
    extract_formula_assets as extract_generic_formula_assets,
)
from ..extraction.html.assets import (
    extract_supplementary_assets as extract_generic_supplementary_assets,
)
from ..extraction.html.parsing import choose_parser
from ..extraction.html.semantics import normalize_section_title
from ..http.headers import header_value
from ..utils import normalize_text
from ._html_asset_engine import (
    HtmlAssetExtractionPolicy,
    extract_scoped_assets_with_policy,
)
from ._springer_dom import (
    SPRINGER_EXTENDED_DATA_SECTION_TITLES,
    SPRINGER_PEER_REVIEW_TOKENS,
    SPRINGER_SOURCE_DATA_TITLE_PREFIX,
    SPRINGER_TABLE_LABEL_PATTERN,
    _extract_asset_html_scope_fragments,
    _normalized_root_html,
    _springer_collect_asset_sections,
    _springer_expected_table_number,
    _springer_figure_asset_key,
    _springer_figure_asset_score,
    _springer_figure_caption,
    _springer_figure_heading,
    _springer_figure_page_url,
    _springer_section_title_key,
    _springer_table_image_candidate_score,
    _springer_table_image_candidate_urls,
    _springer_table_image_roots,
    _springer_table_meta_image_urls,
    decode_html,
    extract_full_size_figure_image_url,
    extract_html_extraction_sidecars,
    promote_springer_media_url_to_full_size,
)
from ._springer_dom import (
    SPRINGER_SUPPLEMENTARY_SECTION_TITLES as SPRINGER_SUPPLEMENTARY_SECTION_TITLES,
)


def extract_asset_html_scopes(
    html_text: str,
    source_url: str,
    *,
    title: str | None = None,
) -> tuple[str, str]:
    cleaned_html, active_root = _normalized_root_html(html_text)
    if active_root is None:
        extraction_sidecars = extract_html_extraction_sidecars(
            html_text, source_url, title=title
        )
        cleaned_html = str(extraction_sidecars["cleaned_html"] or "")
        return cleaned_html, ""

    body_html, supplementary_html, _ = _extract_asset_html_scope_fragments(
        cleaned_html, active_root
    )
    return body_html, supplementary_html


def extract_source_data_html_scope(
    html_text: str,
    source_url: str,
    *,
    title: str | None = None,
) -> str:
    cleaned_html, active_root = _normalized_root_html(html_text)
    if active_root is None:
        extraction_sidecars = extract_html_extraction_sidecars(
            html_text, source_url, title=title
        )
        return str(extraction_sidecars["cleaned_html"] or "")

    _, _, source_data_html = _extract_asset_html_scope_fragments(
        cleaned_html, active_root
    )
    return source_data_html


def extract_springer_table_image_url(
    html_text: str,
    source_url: str,
    *,
    label: str = "",
    table_url: str = "",
) -> str | None:
    """Return a trusted image fallback for a Springer/Nature table page."""
    soup = BeautifulSoup(html_text, choose_parser())
    table_number = _springer_expected_table_number(label, table_url or source_url)
    requested = urllib.parse.urlparse(table_url or source_url)
    final = urllib.parse.urlparse(source_url)
    if table_url and (
        requested.hostname != final.hostname or requested.path != final.path
    ):
        return None
    expected_label = SPRINGER_TABLE_LABEL_PATTERN.search(label)
    expected_label_text = (
        expected_label.group(0).lower().replace(".", "") if expected_label else ""
    )
    page_labels = [
        match.group(0).lower().replace(".", "")
        for node in soup.select("h1, title")
        if (
            match := SPRINGER_TABLE_LABEL_PATTERN.search(node.get_text(" ", strip=True))
        )
    ]
    label_matches = bool(expected_label and page_labels) and all(
        value == expected_label_text for value in page_labels
    )
    if expected_label and page_labels and not label_matches:
        return None
    article_path = requested.path.rsplit("/tables/", 1)[0]
    nature_article = requested.hostname in {
        "www.nature.com",
        "nature.com",
    } and article_path.startswith("/articles/")
    article_doi = (
        "10.1038/" + article_path.removeprefix("/articles/") if nature_article else ""
    )
    article_link_matches = any(
        urllib.parse.urlparse(
            urllib.parse.urljoin(source_url, str(a.get("href") or ""))
        ).path
        == article_path
        for a in soup.select(".c-article-satellite-subtitle a[href]")
    )
    scored_candidates: list[tuple[int, int, str]] = []
    order = 0

    for meta_url in _springer_table_meta_image_urls(soup, source_url):
        meta_path = urllib.parse.unquote(urllib.parse.urlparse(meta_url).path)
        media_doi = re.search(
            r"/art:(10\.[^/]+/.+?)/MediaObjects/", meta_path, re.IGNORECASE
        )
        if (
            article_doi
            and media_doi
            and media_doi.group(1).lower() != article_doi.lower()
        ):
            continue
        score = _springer_table_image_candidate_score(
            meta_url,
            node=None,
            table_number=table_number,
            from_meta=True,
        )
        if score >= 0:
            scored_candidates.append((score, order, meta_url))
            order += 1

    seen_roots: set[int] = set()
    for root in _springer_table_image_roots(soup):
        if id(root) in seen_roots:
            continue
        seen_roots.add(id(root))
        for candidate_url, tag in _springer_table_image_candidate_urls(
            root,
            source_url,
        ):
            candidate_path = urllib.parse.unquote(
                urllib.parse.urlparse(candidate_url).path
            )
            media_doi = re.search(
                r"/art:(10\.[^/]+/.+?)/MediaObjects/", candidate_path, re.IGNORECASE
            )
            if (
                article_doi
                and media_doi
                and media_doi.group(1).lower() != article_doi.lower()
            ):
                continue
            score = _springer_table_image_candidate_score(
                candidate_url,
                node=tag,
                table_number=table_number,
                from_meta=False,
                verified_legacy_table_image=bool(
                    label_matches
                    and article_link_matches
                    and article_doi
                    and media_doi
                    and media_doi.group(1).lower() == article_doi.lower()
                    and urllib.parse.urlparse(candidate_url).hostname
                    == "media.springernature.com"
                    and re.search(
                        r"_Fig[a-z]+_ESM\.(?:jpe?g|png)$", candidate_path, re.IGNORECASE
                    )
                ),
            )
            if score >= 0:
                scored_candidates.append((score, order, candidate_url))
                order += 1

    if not scored_candidates:
        return None
    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    return scored_candidates[0][2]


def extract_formula_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    return extract_generic_formula_assets(
        html_text,
        source_url,
        noise_profile="springer_nature",
    )


def extract_figure_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, choose_parser())
    candidates: list[Any] = []
    seen_nodes: set[int] = set()
    for node in soup.find_all("figure"):
        if id(node) not in seen_nodes:
            seen_nodes.add(id(node))
            candidates.append(node)
    for selector in (".c-article-section__figure-item",):
        for node in soup.select(selector):
            if id(node) not in seen_nodes:
                seen_nodes.add(id(node))
                candidates.append(node)

    assets_by_key: dict[str, dict[str, str]] = {}
    fallback_assets: list[dict[str, str]] = []
    for node in candidates:
        if not isinstance(node, Tag):
            continue
        image = node.find("img")
        source = node.find("source")
        preview_url = _soup_attr_url(image, *PREVIEW_IMAGE_ATTRS) if image else ""
        if not preview_url:
            preview_url = (
                _soup_attr_url(source, "srcset", "data-srcset") if source else ""
            )
        full_size_url = _soup_attr_url(image, *FULL_SIZE_IMAGE_ATTRS) if image else ""
        if not full_size_url:
            full_size_url = (
                _soup_attr_url(source, *FULL_SIZE_IMAGE_ATTRS) if source else ""
            )
        absolute_preview = (
            urllib.parse.urljoin(source_url, preview_url) if preview_url else ""
        )
        absolute_full = (
            urllib.parse.urljoin(source_url, full_size_url) if full_size_url else ""
        )
        promoted_preview = promote_springer_media_url_to_full_size(absolute_preview)
        figure_page_url = _springer_figure_page_url(node, source_url)
        caption = _springer_figure_caption(node, soup)
        alt_text = (
            normalize_text(str(image.get("alt") or ""))
            if isinstance(image, Tag)
            else ""
        )
        heading = _springer_figure_heading(
            figure_page_url,
            caption=caption,
            alt_text=alt_text,
        )
        if (
            not absolute_preview
            and not absolute_full
            and not figure_page_url
            and not caption
        ):
            continue
        asset = {
            "kind": "figure",
            "heading": heading,
            "caption": caption or alt_text,
            "url": absolute_full or promoted_preview or absolute_preview,
            "section": "body",
        }
        if absolute_preview:
            asset["preview_url"] = absolute_preview
        if absolute_full:
            asset["full_size_url"] = absolute_full
        elif promoted_preview:
            asset["full_size_url"] = promoted_preview
        if figure_page_url:
            asset["figure_page_url"] = figure_page_url
        key = _springer_figure_asset_key(asset)
        if not key:
            fallback_assets.append(asset)
            continue
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
        else:
            if _springer_figure_asset_score(asset) > _springer_figure_asset_score(
                existing
            ):
                preserved_path = existing.get("path")
                existing.clear()
                existing.update(asset)
                if preserved_path and not existing.get("path"):
                    existing["path"] = preserved_path
            if len(normalize_text(asset.get("caption") or "")) > len(
                normalize_text(existing.get("caption") or "")
            ):
                existing["caption"] = asset["caption"]
            if len(normalize_text(asset.get("heading") or "")) > len(
                normalize_text(existing.get("heading") or "")
            ):
                existing["heading"] = asset["heading"]
            if asset.get("full_size_url") and not existing.get("full_size_url"):
                existing["full_size_url"] = asset["full_size_url"]
            if asset.get("preview_url") and not existing.get("preview_url"):
                existing["preview_url"] = asset["preview_url"]
    deduped_assets = list(assets_by_key.values()) + fallback_assets
    return deduped_assets or extract_generic_figure_assets(html_text, source_url)


def extract_supplementary_assets(
    html_text: str, source_url: str
) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    soup = BeautifulSoup(html_text, choose_parser())
    extended_figures: dict[str, Tag] = {}
    for link in soup.select(".c-article-supplementary__title a[href]"):
        if re.match(
            r"Extended Data Fig(?:ure)?\.?\s+\d",
            link.get_text(" ", strip=True),
            re.IGNORECASE,
        ):
            page_url = urllib.parse.urljoin(source_url, str(link.get("href") or ""))
            if re.search(r"/figures/\d+$", urllib.parse.urlparse(page_url).path):
                extended_figures[page_url] = link
    for asset in extract_generic_supplementary_assets(
        html_text, source_url, noise_profile="springer_nature"
    ):
        heading = normalize_text(str(asset.get("heading") or ""))
        if _springer_asset_is_source_data(heading) or _springer_asset_is_peer_review(
            heading
        ):
            continue
        item = dict(asset)
        url = item.get("url", "")
        parsed_url = urllib.parse.urlparse(url)
        if (
            parsed_url.fragment
            and url.split("#", 1)[0] == source_url.split("#", 1)[0]
            and re.match(r"Extended Data Fig", heading, re.IGNORECASE)
        ):
            continue
        link = extended_figures.get(url)
        if link is not None:
            preview = str(link.get("data-supp-info-image") or "").strip()
            preview_url = urllib.parse.urljoin(source_url, preview) if preview else ""
            item.update(kind="figure", figure_page_url=url, url=preview_url)
            if preview_url:
                item["preview_url"] = preview_url
                promoted_url = promote_springer_media_url_to_full_size(preview_url)
                if promoted_url:
                    item["full_size_url"] = promoted_url
                    item["url"] = promoted_url
        assets.append(item)
    return _dedupe_springer_supplementary_assets(assets)


def _springer_asset_is_source_data(text: str) -> bool:
    normalized = normalize_section_title(text)
    return bool(normalized) and normalized.startswith(SPRINGER_SOURCE_DATA_TITLE_PREFIX)


def _springer_asset_is_peer_review(text: str) -> bool:
    normalized = normalize_section_title(text)
    return any(token in normalized for token in SPRINGER_PEER_REVIEW_TOKENS)


def _mark_source_data_assets(
    assets: list[dict[str, str]],
) -> list[dict[str, str]]:
    marked_assets: list[dict[str, str]] = []
    for asset in assets:
        heading = normalize_text(str(asset.get("heading") or ""))
        if _springer_asset_is_peer_review(heading):
            continue
        marked_asset = dict(asset)
        marked_asset["kind"] = "supplementary"
        marked_asset["section"] = "supplementary"
        marked_asset["asset_kind"] = "source_data"
        marked_assets.append(marked_asset)
    return marked_assets


def _anchor_text_candidates(anchor: Any) -> list[str]:
    if not isinstance(anchor, Tag):
        return []
    candidates = [
        normalize_text(anchor.get_text(" ", strip=True)),
        normalize_text(str(anchor.get("aria-label") or "")),
        normalize_text(str(anchor.get("title") or "")),
        normalize_text(str(anchor.get("data-track-label") or "")),
    ]
    return [candidate for candidate in candidates if candidate]


def _anchor_mentions_source_data(anchor: Any) -> bool:
    return any(
        _springer_asset_is_source_data(candidate)
        for candidate in _anchor_text_candidates(anchor)
    )


def _anchor_target_id(anchor: Any) -> str:
    if not isinstance(anchor, Tag):
        return ""
    href = normalize_text(str(anchor.get("href") or ""))
    if not href:
        return ""
    parsed = urllib.parse.urlparse(href)
    return normalize_text(urllib.parse.unquote(parsed.fragment or ""))


def extract_source_data_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, choose_parser())
    root = soup.body or soup
    supplementary_sections, source_data_sections = _springer_collect_asset_sections(
        root
    )
    assets: list[dict[str, str]] = []

    for section in source_data_sections:
        assets.extend(
            _mark_source_data_assets(
                extract_generic_supplementary_assets(
                    str(section), source_url, noise_profile="springer_nature"
                )
            )
        )

    for section in supplementary_sections:
        title_key = _springer_section_title_key(section)
        if (
            normalize_section_title(title_key)
            not in SPRINGER_EXTENDED_DATA_SECTION_TITLES
        ):
            continue
        for anchor in section.find_all("a", href=True):
            if not isinstance(anchor, Tag) or not _anchor_mentions_source_data(anchor):
                continue
            target_id = _anchor_target_id(anchor)
            if target_id:
                target = soup.find(id=target_id)
                if isinstance(target, Tag):
                    assets.extend(
                        _mark_source_data_assets(
                            extract_generic_supplementary_assets(
                                str(target),
                                source_url,
                                noise_profile="springer_nature",
                            )
                        )
                    )
                continue
            assets.extend(
                _mark_source_data_assets(
                    extract_generic_supplementary_assets(
                        str(anchor), source_url, noise_profile="springer_nature"
                    )
                )
            )

    return _dedupe_springer_supplementary_assets(assets)


def _springer_asset_identity(asset: Mapping[str, Any]) -> str:
    for field in (
        "figure_page_url",
        "full_size_url",
        "preview_url",
        "download_url",
        "url",
        "source_url",
    ):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return normalize_text(str(asset.get("heading") or ""))


def _springer_asset_priority(asset: Mapping[str, Any]) -> int:
    if normalize_text(str(asset.get("asset_kind") or "")).lower() == "source_data":
        return 20
    if normalize_text(str(asset.get("kind") or "")).lower() == "supplementary":
        return 10
    return 0


def _dedupe_springer_supplementary_assets(
    assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    by_identity: dict[str, int] = {}

    for item in assets:
        asset = dict(item)
        identity = _springer_asset_identity(asset)
        if not identity:
            deduped.append(asset)
            continue
        existing_index = by_identity.get(identity)
        if existing_index is None:
            by_identity[identity] = len(deduped)
            deduped.append(asset)
            continue
        existing = deduped[existing_index]
        if _springer_asset_priority(asset) > _springer_asset_priority(existing):
            merged = dict(existing)
            merged.update(asset)
            deduped[existing_index] = merged
        else:
            for key, value in asset.items():
                if key not in existing or existing[key] in ("", None, [], {}):
                    existing[key] = value

    return deduped


def extract_html_assets(
    html_text: str,
    source_url: str,
    *,
    asset_profile,
) -> list[dict[str, str]]:
    body_html, supplementary_html = extract_asset_html_scopes(html_text, source_url)
    source_data_html = extract_source_data_html_scope(html_text, source_url)
    return extract_scoped_html_assets(
        body_html,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html,
        source_data_html_text=source_data_html,
    )


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile,
    supplementary_html_text: str | None = None,
    source_data_html_text: str | None = None,
) -> list[dict[str, str]]:
    return extract_scoped_assets_with_policy(
        body_html_text,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html_text,
        source_data_html_text=source_data_html_text,
        policy=HtmlAssetExtractionPolicy(
            figure_extractor=extract_figure_assets,
            formula_extractor=extract_formula_assets,
            supplementary_extractor=extract_supplementary_assets,
            source_data_extractor=extract_source_data_assets,
            finalizer=_dedupe_springer_supplementary_assets,
        ),
    )


def _known_figure_candidates(asset: Mapping[str, Any]) -> list[str]:
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    candidates: list[str] = []
    if direct_full_size_url:
        candidates.append(direct_full_size_url)
    promoted_preview = promote_springer_media_url_to_full_size(primary_url)
    if promoted_preview:
        candidates.append(promoted_preview)
    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)
    return list(dict.fromkeys(candidates))


def figure_download_candidates(
    transport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: FigurePageFetcher | None = None,
) -> list[str]:
    candidates = _known_figure_candidates(asset)
    preview_url = normalize_text(
        str(asset.get("preview_url") or asset.get("url") or "")
    )

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url:
        try:
            if figure_page_fetcher is not None:
                page_result = figure_page_fetcher(figure_page_url)
                if page_result is None:
                    raise ValueError("missing figure-page HTML")
                page_html, page_url = page_result
            else:
                response = transport.request(
                    "GET",
                    figure_page_url,
                    headers={
                        "User-Agent": user_agent,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                    timeout=20,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
                page_html = decode_html(
                    response["body"],
                    content_type=header_value(response.get("headers"), "content-type"),
                )
                page_url = str(response["url"] or figure_page_url)
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)
        except Exception:
            pass
    if preview_url:
        candidates.append(preview_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def download_assets_for_springer(
    transport,
    *,
    article_id: str,
    assets: list[dict[str, str]],
    output_dir,
    user_agent: str,
    asset_profile="all",
    figure_page_fetcher: FigurePageFetcher | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    seed_urls: list[str] | None = None,
    runtime_context: Any | None = None,
):
    asset_download_concurrency = resolve_asset_download_concurrency(
        getattr(runtime_context, "env", None)
    )
    body_assets, supplementary_assets = split_body_and_supplementary_assets(assets)
    missing_tables = [
        asset
        for asset in supplementary_assets
        if asset_profile == "all"
        and asset.get("kind") == "table"
        and not asset.get("url")
    ]
    supplementary_assets = [
        asset for asset in supplementary_assets if asset not in missing_tables
    ]
    if asset_profile == "all":
        supplementary_images = [
            asset
            for asset in supplementary_assets
            if asset.get("kind") in {"figure", "table"}
            and (asset.get("url") or asset.get("kind") == "figure")
        ]
        body_assets.extend(supplementary_images)
        supplementary_assets = [
            asset for asset in supplementary_assets if asset not in supplementary_images
        ]
    body_result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=article_id,
        assets=body_assets,
        output_dir=output_dir,
        user_agent=user_agent,
        asset_profile=asset_profile,
        options=AssetDownloadOptions(
            figure_page_fetcher=figure_page_fetcher,
            browser_context_seed=browser_context_seed,
            candidate_builder=lambda _transport, *, asset, **_kwargs: (
                _known_figure_candidates(asset)
            ),
            _fallback_candidate_builder=figure_download_candidates,
            asset_download_concurrency=asset_download_concurrency,
            provider_name="springer",
            runtime_context=runtime_context,
        ),
    )
    supplementary_result = download_assets(
        SUPPLEMENTARY_KIND,
        transport,
        article_id=article_id,
        assets=supplementary_assets,
        output_dir=output_dir,
        user_agent=user_agent,
        asset_profile=asset_profile,
        options=AssetDownloadOptions(
            browser_context_seed=browser_context_seed,
            asset_download_concurrency=asset_download_concurrency,
            provider_name="springer",
            runtime_context=runtime_context,
        ),
    )
    return {
        "assets": [
            *list(body_result.get("assets") or []),
            *list(supplementary_result.get("assets") or []),
        ],
        "asset_failures": [
            *[
                SUPPLEMENTARY_KIND.failure_template(
                    asset,
                    asset.get("source_url", ""),
                    reason="Springer extended table page did not provide a verified table image or table body.",
                )
                for asset in missing_tables
            ],
            *list(body_result.get("asset_failures") or []),
            *list(supplementary_result.get("asset_failures") or []),
        ],
    }


__all__ = [
    "SPRINGER_SUPPLEMENTARY_SECTION_TITLES",
    "download_assets_for_springer",
    "extract_asset_html_scopes",
    "extract_html_assets",
    "extract_scoped_html_assets",
    "extract_source_data_html_scope",
    "extract_springer_table_image_url",
    "figure_download_candidates",
]
