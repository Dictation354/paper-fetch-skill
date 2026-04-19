"""HTML figure and supplementary asset helpers."""

from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping

from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ..models import AssetProfile, normalize_text
from ..utils import build_asset_output_path, empty_asset_results, sanitize_filename, save_payload
from ._pdf_fallback import _build_cookie_seeded_opener, _cookie_header_for_url, _request_with_opener
from .html_noise import decode_html

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    Tag = None

SPRINGER_MEDIA_SIZE_SEGMENT_PATTERN = re.compile(r"^(?:lw|w|m|h)\d+(?:h\d+)?$")
FULL_SIZE_IMAGE_ATTRS = (
    "data-original",
    "data-full-size",
    "data-fullsize",
    "data-zoom-src",
    "data-zoom-image",
    "data-lg-src",
    "data-hi-res-src",
    "data-hires",
    "data-large-src",
    "data-image-full",
    "data-download-url",
)
PREVIEW_IMAGE_ATTRS = (
    "data-src",
    "src",
    "data-lazy-src",
)
FULL_SIZE_URL_TOKENS = (
    "/full/",
    "/large/",
    "/original/",
    "/fullsize/",
    "download=true",
    "download=1",
    "hi-res",
    "hires",
    "high-res",
    "highres",
)
PREVIEW_URL_TOKENS = (
    "/thumb/",
    "/thumbnail/",
    "thumbnail",
    "/small/",
    "/preview/",
)
FIGURE_PAGE_HINTS = (
    "full size image",
    "view figure",
    "open in viewer",
    "view larger",
    "download figure",
    "download image",
    "figure viewer",
)

FigurePageFetcher = Callable[[str], tuple[str, str] | None]
AssetUrlRewriter = Callable[[str], str | None]
SupplementaryUrlDetector = Callable[[str], bool]


def _host_matches(hostname: str, expected_host: str) -> bool:
    normalized_hostname = normalize_text(hostname).lower()
    normalized_expected = normalize_text(expected_host).lower()
    if not normalized_hostname or not normalized_expected:
        return False
    return normalized_hostname == normalized_expected or normalized_hostname.endswith(f".{normalized_expected}")


class _FigureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.assets: list[dict[str, str]] = []
        self._in_figure = False
        self._in_figcaption = False
        self._current_src = ""
        self._caption_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "figure":
            self._in_figure = True
            self._current_src = ""
            self._caption_parts = []
        elif self._in_figure and lowered_tag == "img" and not self._current_src:
            self._current_src = attributes.get("src", "").strip()
        elif self._in_figure and lowered_tag == "figcaption":
            self._in_figcaption = True

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if lowered_tag == "figcaption":
            self._in_figcaption = False
        elif lowered_tag == "figure":
            caption = normalize_text(" ".join(self._caption_parts))
            if self._current_src or caption:
                self.assets.append(
                    {
                        "kind": "figure",
                        "heading": caption[:80] or "Figure",
                        "caption": caption,
                        "url": self._current_src,
                    }
                )
            self._in_figure = False
            self._in_figcaption = False
            self._current_src = ""
            self._caption_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_figcaption and data.strip():
            self._caption_parts.append(data)


def _first_url_from_srcset(value: str | None) -> str:
    srcset = normalize_text(value)
    if not srcset:
        return ""
    first = srcset.split(",", 1)[0].strip()
    if not first:
        return ""
    return first.split()[0].strip()


def _soup_attr_url(tag: Any, *attrs: str) -> str:
    if Tag is None or not isinstance(tag, Tag):
        return ""
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        if attr.endswith("srcset"):
            candidate = _first_url_from_srcset(raw)
        else:
            candidate = normalize_text(str(raw))
        if candidate:
            return candidate
    return ""


def looks_like_full_size_asset_url(url: str | None) -> bool:
    candidate = normalize_text(url).lower()
    if not candidate:
        return False
    if any(token in candidate for token in PREVIEW_URL_TOKENS):
        return False
    return any(token in candidate for token in FULL_SIZE_URL_TOKENS)


def _collect_tag_attr_urls(tag: Any, source_url: str, *attrs: str) -> list[str]:
    if Tag is None or not isinstance(tag, Tag):
        return []
    urls: list[str] = []
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        values = [raw] if not isinstance(raw, list) else raw
        for value in values:
            candidate = _first_url_from_srcset(value) if attr.endswith("srcset") else normalize_text(str(value))
            absolute_candidate = urllib.parse.urljoin(source_url, candidate) if candidate else ""
            if absolute_candidate and absolute_candidate not in urls:
                urls.append(absolute_candidate)
    return urls


def _figure_caption_from_soup(node: Any, soup: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""

    figcaption = node.find("figcaption")
    if isinstance(figcaption, Tag):
        caption = normalize_text(figcaption.get_text(" ", strip=True))
        if caption:
            return caption

    image = node.find("img")
    if isinstance(image, Tag):
        described_by = normalize_text(str(image.get("aria-describedby") or ""))
        if described_by:
            described_node = soup.find(id=described_by)
            if isinstance(described_node, Tag):
                caption = normalize_text(described_node.get_text(" ", strip=True))
                if caption:
                    return caption

    for context in (node, node.parent if isinstance(node.parent, Tag) else None):
        if not isinstance(context, Tag):
            continue
        description = context.select_one(".c-article-section__figure-description")
        if isinstance(description, Tag):
            caption = normalize_text(description.get_text(" ", strip=True))
            if caption:
                return caption
    return ""


def _figure_page_url_from_soup(node: Any, source_url: str) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""

    contexts: list[Any] = [node]
    if isinstance(node.parent, Tag):
        contexts.append(node.parent)

    for context in contexts:
        for anchor in context.find_all("a", href=True):
            href = normalize_text(str(anchor.get("href") or ""))
            text = normalize_text(anchor.get_text(" ", strip=True)).lower()
            hint_blob = " ".join(
                [
                    text,
                    normalize_text(str(anchor.get("aria-label") or "")).lower(),
                    normalize_text(str(anchor.get("title") or "")).lower(),
                ]
            )
            if any(token in hint_blob for token in FIGURE_PAGE_HINTS) and href and not href.startswith("#"):
                return urllib.parse.urljoin(source_url, href)

    for context in contexts:
        for anchor in context.find_all("a", href=True):
            href = normalize_text(str(anchor.get("href") or ""))
            if "/figures/" in href:
                return urllib.parse.urljoin(source_url, href)
    return ""


def _figure_full_size_url_from_soup(node: Any, source_url: str) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""

    contexts: list[Any] = [node]
    if isinstance(node.parent, Tag):
        contexts.append(node.parent)

    for context in contexts:
        for tag in [context, *context.find_all(True)]:
            for candidate in _collect_tag_attr_urls(tag, source_url, *FULL_SIZE_IMAGE_ATTRS):
                if looks_like_full_size_asset_url(candidate):
                    return candidate

    for context in contexts:
        for anchor in context.find_all("a", href=True):
            href = normalize_text(str(anchor.get("href") or ""))
            if href.startswith("#"):
                continue
            absolute_href = urllib.parse.urljoin(source_url, href)
            hint_blob = " ".join(
                [
                    normalize_text(anchor.get_text(" ", strip=True)).lower(),
                    normalize_text(str(anchor.get("aria-label") or "")).lower(),
                    normalize_text(str(anchor.get("title") or "")).lower(),
                ]
            )
            if looks_like_full_size_asset_url(absolute_href) or (
                any(token in hint_blob for token in FIGURE_PAGE_HINTS) and "/figures/" not in href
            ):
                return absolute_href
    return ""


def _figure_asset_from_soup_node(node: Any, soup: Any, source_url: str) -> dict[str, str] | None:
    if Tag is None or not isinstance(node, Tag):
        return None

    image = node.find("img")
    source = node.find("source")
    preview_url = _soup_attr_url(image, *PREVIEW_IMAGE_ATTRS) if image else ""
    if not preview_url:
        preview_url = _soup_attr_url(source, "srcset", "data-srcset") if source else ""
    full_size_url = _figure_full_size_url_from_soup(node, source_url)
    if not full_size_url and image is not None:
        full_size_url = _soup_attr_url(image, *FULL_SIZE_IMAGE_ATTRS)
    if not full_size_url and source is not None:
        full_size_url = _soup_attr_url(source, *FULL_SIZE_IMAGE_ATTRS)
    if not full_size_url and looks_like_full_size_asset_url(preview_url):
        full_size_url = preview_url
    absolute_preview_url = urllib.parse.urljoin(source_url, preview_url) if preview_url else ""
    absolute_full_size_url = urllib.parse.urljoin(source_url, full_size_url) if full_size_url else ""

    caption = _figure_caption_from_soup(node, soup)
    alt_text = normalize_text(str(image.get("alt") or "")) if isinstance(image, Tag) else ""
    heading = caption[:80] or alt_text or "Figure"
    if not caption and alt_text:
        caption = alt_text

    if not preview_url and not full_size_url and not caption:
        return None

    asset: dict[str, str] = {
        "kind": "figure",
        "heading": heading,
        "caption": caption,
        "url": absolute_full_size_url or absolute_preview_url,
        "section": "body",
    }
    if absolute_preview_url:
        asset["preview_url"] = absolute_preview_url
    if absolute_full_size_url:
        asset["full_size_url"] = absolute_full_size_url
    figure_page_url = _figure_page_url_from_soup(node, source_url)
    if figure_page_url:
        asset["figure_page_url"] = figure_page_url
    return asset


def _tag_classes(node: Any) -> list[str]:
    if Tag is None or not isinstance(node, Tag):
        return []
    raw_classes = node.get("class") or []
    return [normalize_text(str(item)).lower() for item in raw_classes if normalize_text(str(item))]


def _is_supplementary_context(node: Any) -> bool:
    if Tag is None or not isinstance(node, Tag):
        return False
    class_tokens = _tag_classes(node)
    joined = " ".join(class_tokens)
    if "supplement" in joined or "supp-info" in joined:
        return True
    data_test = normalize_text(str(node.get("data-test") or "")).lower()
    return data_test == "supp-info-link"


def _find_supplementary_context(node: Any) -> Any:
    if Tag is None or not isinstance(node, Tag):
        return None
    current: Any = node
    while isinstance(current, Tag):
        if _is_supplementary_context(current):
            return current
        current = current.parent
    return None


def _springer_supplementary_url_supported(url: str) -> bool:
    lowered = normalize_text(url).lower()
    return "static-content.springer.com/esm/" in lowered or "/mediaobjects/" in lowered


SUPPLEMENTARY_URL_DETECTORS: dict[str, SupplementaryUrlDetector] = {
    "static-content.springer.com": _springer_supplementary_url_supported,
    "media.springernature.com": _springer_supplementary_url_supported,
}


def _matches_supplementary_detector(url: str) -> bool:
    parsed = urllib.parse.urlsplit(normalize_text(url))
    hostname = normalize_text(parsed.netloc).lower()
    if not hostname:
        return False
    for registered_host, detector in SUPPLEMENTARY_URL_DETECTORS.items():
        if _host_matches(hostname, registered_host):
            return detector(url)
    return False


def _supplementary_anchor_is_supported(anchor: Any) -> bool:
    if Tag is None or not isinstance(anchor, Tag):
        return False

    href = normalize_text(str(anchor.get("href") or ""))
    if not href:
        return False
    if href.startswith("#"):
        return False

    text = normalize_text(anchor.get_text(" ", strip=True)).lower()
    data_test = normalize_text(str(anchor.get("data-test") or "")).lower()
    data_track_action = normalize_text(str(anchor.get("data-track-action") or "")).lower()
    data_supp_info_image = normalize_text(str(anchor.get("data-supp-info-image") or ""))
    supported_tokens = (
        "supplementary",
        "extended data",
        "peer review",
        "source data",
        "reporting summary",
        "supplementary information",
    )

    if data_test == "supp-info-link":
        return True
    if data_track_action == "view supplementary info":
        return True
    if data_supp_info_image:
        return True
    if any(token in text for token in supported_tokens):
        if "/figures/" in href:
            return True
        if _matches_supplementary_detector(href) or any(
            token in href.lower() for token in (".pdf", ".csv", ".xlsx", ".zip")
        ):
            return True
        return False
    if "/figures/" in href and "extended data" in text:
        return True
    if _matches_supplementary_detector(href) and _find_supplementary_context(anchor) is not None:
        return True
    return False


def _supplementary_caption_from_anchor(anchor: Any) -> str:
    contexts: list[Any] = []
    current: Any = anchor
    while isinstance(current, Tag):
        contexts.append(current)
        current = current.parent

    for context in contexts:
        for selector in (
            ".c-article-supplementary__description",
            ".c-article-section__figure-description",
            "[class*='supplementary__description']",
        ):
            description = context.select_one(selector)
            if isinstance(description, Tag):
                caption = normalize_text(description.get_text(" ", strip=True))
                if caption:
                    return caption
    return ""


def _supplementary_asset_from_anchor(anchor: Any, source_url: str) -> dict[str, str] | None:
    if Tag is None or not isinstance(anchor, Tag):
        return None

    if not _supplementary_anchor_is_supported(anchor):
        return None

    href = normalize_text(str(anchor.get("href") or ""))
    if not href:
        return None

    heading = normalize_text(anchor.get_text(" ", strip=True)) or "Supplementary Material"
    heading = re.sub(r"\s*\(\s*download\s+pdf\s*\)\s*$", "", heading, flags=re.IGNORECASE)
    caption = _supplementary_caption_from_anchor(anchor)
    preview_url = normalize_text(str(anchor.get("data-supp-info-image") or ""))
    absolute_href = urllib.parse.urljoin(source_url, href)

    asset: dict[str, str] = {
        "kind": "supplementary",
        "heading": heading,
        "caption": caption,
        "section": "supplementary",
    }
    if preview_url:
        asset["url"] = urllib.parse.urljoin(source_url, preview_url)
    elif absolute_href:
        asset["url"] = absolute_href
    if "/figures/" in href:
        asset["figure_page_url"] = absolute_href
    return asset


def _extract_figure_assets_with_soup(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    candidates: list[Any] = []
    seen_nodes: set[int] = set()

    for node in soup.find_all("figure"):
        node_id = id(node)
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            candidates.append(node)
    for node in soup.select(".c-article-section__figure-item"):
        node_id = id(node)
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            candidates.append(node)

    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for node in candidates:
        asset = _figure_asset_from_soup_node(node, soup, source_url)
        if asset is None:
            continue
        figure_page_url = normalize_text(asset.get("figure_page_url") or "")
        preview_url = normalize_text(asset.get("url") or "")
        caption = normalize_text(asset.get("caption") or "")
        heading = normalize_text(asset.get("heading") or "")
        key = (
            figure_page_url or preview_url,
            preview_url,
            "figure",
        )
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
            continue

        existing_caption = normalize_text(existing.get("caption") or "")
        existing_heading = normalize_text(existing.get("heading") or "")
        if len(caption) > len(existing_caption):
            existing["caption"] = caption
        if len(heading) > len(existing_heading):
            existing["heading"] = heading
        if figure_page_url and not normalize_text(existing.get("figure_page_url") or ""):
            existing["figure_page_url"] = figure_page_url
        if preview_url and not normalize_text(existing.get("url") or ""):
            existing["url"] = preview_url

    return list(assets_by_key.values())


def extract_supplementary_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        asset = _supplementary_asset_from_anchor(anchor, source_url)
        if asset is None:
            continue

        figure_page_url = normalize_text(asset.get("figure_page_url") or "")
        url = normalize_text(asset.get("url") or "")
        key = (
            figure_page_url or url or normalize_text(asset.get("heading") or ""),
            "supplementary",
            normalize_text(asset.get("heading") or ""),
        )
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
            continue

        existing_caption = normalize_text(existing.get("caption") or "")
        caption = normalize_text(asset.get("caption") or "")
        if len(caption) > len(existing_caption):
            existing["caption"] = caption
        if figure_page_url and not normalize_text(existing.get("figure_page_url") or ""):
            existing["figure_page_url"] = figure_page_url
        if url and not normalize_text(existing.get("url") or ""):
            existing["url"] = url

    return list(assets_by_key.values())


def extract_html_assets(
    html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, str]]:
    assets = extract_figure_assets(html_text, source_url)
    if asset_profile == "all":
        assets.extend(extract_supplementary_assets(html_text, source_url))
    return assets


def extract_full_size_figure_image_url(html_text: str, source_url: str) -> str | None:
    from .html_generic import parse_html_metadata

    metadata = parse_html_metadata(html_text, source_url)
    raw_meta = metadata.get("raw_meta") if isinstance(metadata, Mapping) else {}
    if isinstance(raw_meta, Mapping):
        for key in ("twitter:image", "twitter:image:src", "og:image"):
            for value in raw_meta.get(key, []):
                candidate = urllib.parse.urljoin(source_url, normalize_text(str(value or "")))
                if candidate:
                    return candidate

    if BeautifulSoup is None:
        return None

    soup = BeautifulSoup(html_text, "html.parser")
    fallback_candidate = None
    springer_candidate = None
    seen: set[str] = set()
    for tag in soup.find_all(["img", "source"]):
        candidate = _soup_attr_url(
            tag,
            *FULL_SIZE_IMAGE_ATTRS,
            "data-src",
            "src",
            "data-lazy-src",
            "srcset",
            "data-srcset",
        )
        if not candidate:
            continue
        absolute_candidate = urllib.parse.urljoin(source_url, candidate)
        if not absolute_candidate or absolute_candidate in seen:
            continue
        seen.add(absolute_candidate)
        lowered = absolute_candidate.lower()
        if looks_like_full_size_asset_url(lowered):
            return absolute_candidate
        if springer_candidate is None and _rewrite_registered_asset_url(absolute_candidate):
            springer_candidate = absolute_candidate
        if fallback_candidate is None:
            fallback_candidate = absolute_candidate
    return springer_candidate or fallback_candidate


def _rewrite_springer_media_url_to_full_size(url: str) -> str | None:
    candidate = normalize_text(url)
    if not candidate:
        return None

    parsed = urllib.parse.urlsplit(candidate)
    hostname = parsed.netloc.lower()
    if "media.springernature.com" not in hostname:
        return None

    path = parsed.path or ""
    if not path.startswith("/"):
        return None
    segments = path.lstrip("/").split("/", 1)
    if len(segments) < 2:
        return None
    size_segment, remainder = segments
    if size_segment == "full":
        return urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, path, parsed.query, parsed.fragment))
    if not SPRINGER_MEDIA_SIZE_SEGMENT_PATTERN.match(size_segment):
        return None
    if "/springer-static/" not in f"/{remainder}":
        return None

    return urllib.parse.urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc,
            f"/full/{remainder}",
            parsed.query,
            parsed.fragment,
        )
    )


ASSET_URL_REWRITERS: dict[str, AssetUrlRewriter] = {
    "media.springernature.com": _rewrite_springer_media_url_to_full_size,
}


def _rewrite_registered_asset_url(url: str | None) -> str | None:
    candidate = normalize_text(url)
    if not candidate:
        return None
    parsed = urllib.parse.urlsplit(candidate)
    hostname = normalize_text(parsed.netloc).lower()
    if not hostname:
        return None
    for registered_host, rewriter in ASSET_URL_REWRITERS.items():
        if _host_matches(hostname, registered_host):
            return rewriter(candidate)
    return None


def promote_springer_media_url_to_full_size(url: str | None) -> str | None:
    candidate = normalize_text(url)
    rewritten = _rewrite_registered_asset_url(candidate)
    if not candidate or not rewritten:
        return None
    parsed = urllib.parse.urlsplit(candidate)
    if not _host_matches(parsed.netloc, "media.springernature.com"):
        return None
    return rewritten


def figure_download_candidates(
    transport: HttpTransport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: FigurePageFetcher | None = None,
) -> list[str]:
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []

    if direct_full_size_url:
        candidates.append(direct_full_size_url)

    promoted_preview_url = _rewrite_registered_asset_url(primary_url)
    if promoted_preview_url:
        candidates.append(promoted_preview_url)
    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url:
        try:
            if figure_page_fetcher is not None:
                page_result = figure_page_fetcher(figure_page_url)
                if page_result is None:
                    raise RequestFailure(None, f"Missing figure-page HTML for {figure_page_url}", url=figure_page_url)
                page_html, page_url = page_result
            else:
                response = transport.request(
                    "GET",
                    figure_page_url,
                    headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
                page_html = decode_html(response["body"])
                page_url = str(response["url"] or figure_page_url)
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)
        except RequestFailure:
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


def resolve_figure_download_url(
    transport: HttpTransport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
) -> str:
    candidates = figure_download_candidates(
        transport,
        asset=asset,
        user_agent=user_agent,
    )
    return candidates[0] if candidates else normalize_text(str(asset.get("url") or ""))


def html_asset_identity_key(asset: Mapping[str, Any]) -> str:
    for field in ("figure_page_url", "original_url", "url", "source_url", "path"):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return ""


def extract_figure_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is not None:
        assets = _extract_figure_assets_with_soup(html_text, source_url)
        if assets:
            return assets

    parser = _FigureParser()
    parser.feed(html_text)
    parser.close()
    assets: list[dict[str, str]] = []
    for item in parser.assets:
        url = item.get("url", "").strip()
        assets.append(
            {
                "kind": "figure",
                "heading": item.get("heading", "Figure"),
                "caption": item.get("caption", ""),
                "url": urllib.parse.urljoin(source_url, url) if url else "",
                "section": "body",
            }
        )
    return assets


def download_figure_assets(
    transport: HttpTransport,
    *,
    article_id: str,
    assets: list[dict[str, str]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile = "all",
    figure_page_fetcher: FigurePageFetcher | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    seed_urls: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or asset_profile == "none" or not assets:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for asset in assets:
        preview_url = normalize_text(str(asset.get("preview_url") or asset.get("url") or ""))
        candidate_urls = figure_download_candidates(
            transport,
            asset=asset,
            user_agent=user_agent,
            figure_page_fetcher=figure_page_fetcher,
        )
        if not candidate_urls:
            continue

        response = None
        source_url = ""
        last_failure: dict[str, Any] | None = None
        active_user_agent = normalize_text(str((browser_context_seed or {}).get("browser_user_agent") or "")) or user_agent
        browser_cookies = list((browser_context_seed or {}).get("browser_cookies") or [])
        active_seed_urls = [
            normalized
            for normalized in [
                *[normalize_text(item) for item in seed_urls or []],
                normalize_text(str((browser_context_seed or {}).get("browser_final_url") or "")),
            ]
            if normalized
        ]
        for candidate_url in candidate_urls:
            parsed = urllib.parse.urlparse(candidate_url)
            if parsed.scheme not in {"http", "https"}:
                last_failure = {
                    "kind": asset.get("kind", "figure"),
                    "heading": asset.get("heading", "Figure"),
                    "caption": asset.get("caption", ""),
                    "source_url": candidate_url,
                    "reason": f"Unsupported asset URL scheme for {candidate_url}",
                    "section": asset.get("section") or "body",
                }
                continue

            try:
                request_headers = {"User-Agent": active_user_agent, "Accept": "*/*"}
                opener = (
                    _build_cookie_seeded_opener(
                        active_seed_urls,
                        headers=request_headers,
                        timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                        browser_cookies=browser_cookies,
                    )
                    if browser_cookies
                    else None
                )
                cookie_header = _cookie_header_for_url(browser_cookies, candidate_url)
                if cookie_header:
                    request_headers["Cookie"] = cookie_header
                response = (
                    _request_with_opener(
                        opener,
                        candidate_url,
                        headers=request_headers,
                        timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    )
                    if opener is not None
                    else transport.request(
                        "GET",
                        candidate_url,
                        headers=request_headers,
                        timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                        retry_on_rate_limit=True,
                        retry_on_transient=True,
                    )
                )
                source_url = candidate_url
                break
            except RequestFailure as exc:
                last_failure = {
                    "kind": asset.get("kind", "figure"),
                    "heading": asset.get("heading", "Figure"),
                    "caption": asset.get("caption", ""),
                    "source_url": candidate_url,
                    "status": exc.status_code,
                    "reason": str(exc),
                    "section": asset.get("section") or "body",
                }
                continue

        if response is None:
            if last_failure is not None:
                failures.append(last_failure)
            continue

        content_type = response["headers"].get("content-type")
        output_path = build_asset_output_path(
            asset_dir,
            source_url,
            content_type,
            response["url"],
            used_names,
        )
        downloads.append(
            {
                "kind": asset.get("kind", "figure"),
                "heading": asset.get("heading", "Figure"),
                "caption": asset.get("caption", ""),
                "original_url": preview_url,
                "figure_page_url": asset.get("figure_page_url", ""),
                "source_url": response["url"],
                "content_type": content_type,
                "path": save_payload(output_path, response["body"]),
                "downloaded_bytes": len(response["body"]),
                "section": asset.get("section") or "body",
            }
        )

    return {
        "assets": downloads,
        "asset_failures": failures,
    }
