"""Provider-neutral HTML asset helpers."""

from __future__ import annotations

import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping

from ...http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ...models import AssetProfile, normalize_text
from ...utils import build_asset_output_path, empty_asset_results, sanitize_filename, save_payload
from ..image_payloads import image_dimensions_from_bytes, image_mime_type_from_bytes
from ._metadata import parse_html_metadata
from .formula_rules import (
    FORMULA_IMAGE_ATTRS,
    FORMULA_IMAGE_SRCSET_ATTRS,
    formula_heading_for_image,
    formula_image_url_from_node,
    looks_like_formula_image,
)
from ._runtime import decode_html

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    Tag = None

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
PREVIEW_IMAGE_ATTRS = ("data-src", "src", "data-lazy-src")
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
PREVIEW_URL_TOKENS = ("/thumb/", "/thumbnail/", "thumbnail", "/small/", "/preview/")
ACCEPTABLE_PREVIEW_MIN_WIDTH = 300
ACCEPTABLE_PREVIEW_MIN_HEIGHT = 200
FIGURE_PAGE_HINTS = (
    "full size image",
    "view figure",
    "open in viewer",
    "view larger",
    "download figure",
    "download image",
    "figure viewer",
)
SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary",
    "extended data",
    "source data",
    "peer review",
    "supporting information",
)
SUPPLEMENTARY_FILE_TOKENS = (".pdf", ".csv", ".xlsx", ".xls", ".zip")
FigurePageFetcher = Callable[[str], tuple[str, str] | None]
ImageDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]


def _response_header(response: Mapping[str, Any], name: str) -> str:
    headers = response.get("headers") or {}
    if not isinstance(headers, Mapping):
        return ""
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return normalize_text(str(value or ""))
    return ""


def _image_magic_type(body: bytes | bytearray | None) -> str:
    return image_mime_type_from_bytes(body)


def _image_dimensions(body: bytes | bytearray | None) -> tuple[int, int] | None:
    return image_dimensions_from_bytes(body)


def _response_dimensions(response: Mapping[str, Any]) -> tuple[int, int] | None:
    dimensions = response.get("dimensions")
    if isinstance(dimensions, Mapping):
        try:
            width = int(dimensions.get("width") or 0)
            height = int(dimensions.get("height") or 0)
        except (TypeError, ValueError):
            width = height = 0
        if width > 0 and height > 0:
            return width, height
    return _image_dimensions(response.get("body", b""))


def preview_dimensions_are_acceptable(width: int | None, height: int | None) -> bool:
    return int(width or 0) >= ACCEPTABLE_PREVIEW_MIN_WIDTH and int(height or 0) >= ACCEPTABLE_PREVIEW_MIN_HEIGHT


def _looks_like_image_payload(content_type: str | None, body: bytes | bytearray | None, source_url: str | None) -> bool:
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    if normalized_content_type.startswith("image/"):
        return True
    if normalized_content_type:
        return False
    if _image_magic_type(body):
        return True
    return bool(re.search(r"\.(?:avif|gif|jpe?g|png|tiff?|webp)(?:[?#]|$)", normalize_text(source_url), re.IGNORECASE))


def _requires_image_payload(asset: Mapping[str, Any]) -> bool:
    kind = normalize_text(str(asset.get("kind") or "")).lower()
    section = normalize_text(str(asset.get("section") or "")).lower()
    return kind in {"figure", "table", "formula"} and section != "supplementary"


def _fetch_image_document_fallback(
    fetcher: ImageDocumentFetcher | None,
    candidate_url: str,
    asset: Mapping[str, Any],
) -> dict[str, Any] | None:
    if fetcher is None or not _requires_image_payload(asset):
        return None
    try:
        response = fetcher(candidate_url, asset)
    except Exception:
        return None
    if not response:
        return None
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)):
        return None
    content_type = _response_header(response, "content-type")
    final_url = normalize_text(str(response.get("url") or candidate_url))
    if not _looks_like_image_payload(content_type, body, final_url):
        return None
    return dict(response)


def _image_document_fetch_failure(
    fetcher: ImageDocumentFetcher | None,
    candidate_url: str,
) -> dict[str, Any]:
    reporter = getattr(fetcher, "failure_for", None)
    if not callable(reporter):
        return {}
    try:
        failure = reporter(candidate_url)
    except Exception:
        return {}
    return dict(failure) if isinstance(failure, Mapping) else {}


def _is_preview_candidate(candidate_url: str, *, preview_url: str, full_size_url: str) -> bool:
    normalized_candidate = normalize_text(candidate_url)
    if not normalized_candidate or not preview_url:
        return False
    return (
        normalized_candidate == preview_url
        and normalized_candidate != full_size_url
        and not looks_like_full_size_asset_url(normalized_candidate.lower())
    )


def _preview_upgrade_targets(candidate_url: str, asset: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    for value in (
        asset.get("figure_page_url"),
        asset.get("full_size_url"),
        asset.get("download_url"),
        candidate_url,
    ):
        normalized = normalize_text(str(value or ""))
        if normalized and normalized not in targets:
            targets.append(normalized)
    return targets


def _build_cookie_seeded_opener(
    seed_urls: list[str] | None,
    *,
    headers: Mapping[str, str],
    timeout: int,
    browser_cookies: list[dict[str, Any]] | None = None,
) -> urllib.request.OpenerDirector | None:
    normalized_seed_urls = [normalize_text(url) for url in seed_urls or [] if normalize_text(url)]
    if not normalized_seed_urls and not any(isinstance(cookie, dict) for cookie in browser_cookies or []):
        return None

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    seed_headers = {
        key: value
        for key, value in dict(headers).items()
        if str(key).lower() != "accept"
    }
    seed_headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

    for seed_url in normalized_seed_urls:
        request_headers = dict(seed_headers)
        cookie_header = _cookie_header_for_url(browser_cookies, seed_url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        request = urllib.request.Request(seed_url, headers=request_headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                response.read(1024)
        except Exception:
            continue

    return opener


def _request_with_opener(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            return {
                "status_code": int(getattr(response, "status", response.getcode())),
                "headers": {str(key).lower(): str(value) for key, value in response.headers.items()},
                "body": response.read(),
                "url": str(response.geturl() or url),
            }
    except urllib.error.HTTPError as exc:
        raise RequestFailure(
            exc.code,
            f"HTTP {exc.code} for {url}",
            body=exc.read(),
            headers={str(key).lower(): str(value) for key, value in exc.headers.items()},
            url=str(exc.geturl() or url),
        ) from exc
    except urllib.error.URLError as exc:
        raise RequestFailure(
            None,
            f"Failed to download asset candidate: {exc.reason or exc}",
            url=url,
        ) from exc


def _cookie_header_for_url(browser_cookies: list[dict[str, Any]] | None, url: str) -> str | None:
    parsed_url = urllib.parse.urlparse(normalize_text(url))
    host = normalize_text(parsed_url.hostname).lower()
    path = normalize_text(parsed_url.path) or "/"
    scheme = normalize_text(parsed_url.scheme).lower()
    if not host:
        return None

    matched_pairs: list[str] = []
    for cookie in browser_cookies or []:
        if not isinstance(cookie, dict):
            continue
        name = normalize_text(str(cookie.get("name") or ""))
        value = str(cookie.get("value") or "")
        if not name:
            continue

        cookie_domain = normalize_text(str(cookie.get("domain") or "")).lower().lstrip(".")
        if not cookie_domain:
            cookie_url = normalize_text(str(cookie.get("url") or ""))
            cookie_domain = normalize_text(urllib.parse.urlparse(cookie_url).hostname).lower()
        if cookie_domain and host != cookie_domain and not host.endswith(f".{cookie_domain}"):
            continue

        cookie_path = normalize_text(str(cookie.get("path") or "")) or "/"
        if not path.startswith(cookie_path):
            continue

        if bool(cookie.get("secure")) and scheme != "https":
            continue

        matched_pairs.append(f"{name}={value}")

    return "; ".join(matched_pairs) if matched_pairs else None


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
    best_url = ""
    best_score = -1.0
    for raw_part in srcset.split(","):
        part = raw_part.strip()
        if not part:
            continue
        pieces = part.split()
        url = pieces[0].strip()
        score = 0.0
        for descriptor in pieces[1:]:
            match = re.match(r"^([0-9]+(?:\.[0-9]+)?)(w|x)$", descriptor.strip().lower())
            if not match:
                continue
            multiplier = 1000.0 if match.group(2) == "x" else 1.0
            score = max(score, float(match.group(1)) * multiplier)
        if score >= best_score:
            best_url = url
            best_score = score
    return best_url


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


def _looks_like_formula_image(tag: Any, url: str) -> bool:
    return looks_like_formula_image(tag, url)


def _formula_heading_for_image(tag: Any, index: int) -> str:
    return formula_heading_for_image(tag, index)


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
            if looks_like_full_size_asset_url(absolute_href) or any(token in hint_blob for token in FIGURE_PAGE_HINTS):
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
    figure_page_url = _figure_page_url_from_soup(node, source_url)
    if (
        absolute_full_size_url
        and figure_page_url
        and absolute_full_size_url == figure_page_url
        and not looks_like_full_size_asset_url(absolute_full_size_url)
    ):
        absolute_full_size_url = ""

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
    if figure_page_url:
        asset["figure_page_url"] = figure_page_url
    return asset


def _supplementary_anchor_is_supported(anchor: Any) -> bool:
    if Tag is None or not isinstance(anchor, Tag):
        return False

    href = normalize_text(str(anchor.get("href") or ""))
    if not href or href.startswith("#"):
        return False
    text = normalize_text(anchor.get_text(" ", strip=True)).lower()
    data_test = normalize_text(str(anchor.get("data-test") or "")).lower()
    data_track_action = normalize_text(str(anchor.get("data-track-action") or "")).lower()
    if data_test == "supp-info-link" or data_track_action == "view supplementary info":
        return True
    if any(token in text for token in SUPPLEMENTARY_TEXT_TOKENS):
        return True
    lowered_href = href.lower()
    return any(token in lowered_href for token in SUPPLEMENTARY_FILE_TOKENS)


def _supplementary_asset_from_anchor(anchor: Any, source_url: str) -> dict[str, str] | None:
    if Tag is None or not isinstance(anchor, Tag):
        return None
    if not _supplementary_anchor_is_supported(anchor):
        return None

    href = normalize_text(str(anchor.get("href") or ""))
    heading = normalize_text(anchor.get_text(" ", strip=True)) or "Supplementary Material"
    heading = re.sub(r"\s*\(\s*download\s+pdf\s*\)\s*$", "", heading, flags=re.IGNORECASE)
    absolute_href = urllib.parse.urljoin(source_url, href)
    return {
        "kind": "supplementary",
        "heading": heading,
        "caption": "",
        "section": "supplementary",
        "url": absolute_href,
    }


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

    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for node in candidates:
        asset = _figure_asset_from_soup_node(node, soup, source_url)
        if asset is None:
            continue
        figure_page_url = normalize_text(asset.get("figure_page_url") or "")
        preview_url = normalize_text(asset.get("url") or "")
        caption = normalize_text(asset.get("caption") or "")
        heading = normalize_text(asset.get("heading") or "")
        key = (figure_page_url or preview_url, preview_url, "figure")
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


def extract_formula_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    for image in soup.find_all("img"):
        if not isinstance(image, Tag):
            continue
        url = formula_image_url_from_node(image) or _soup_attr_url(
            image,
            *FORMULA_IMAGE_ATTRS,
            *FORMULA_IMAGE_SRCSET_ATTRS,
        )
        if not url or not _looks_like_formula_image(image, url):
            continue
        absolute_url = urllib.parse.urljoin(source_url, url)
        if not absolute_url or absolute_url in seen:
            continue
        seen.add(absolute_url)
        heading = _formula_heading_for_image(image, len(assets) + 1)
        assets.append(
            {
                "kind": "formula",
                "heading": heading,
                "caption": "",
                "url": absolute_url,
                "preview_url": absolute_url,
                "section": "body",
            }
        )
    return assets


def extract_supplementary_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        asset = _supplementary_asset_from_anchor(anchor, source_url)
        if asset is None:
            continue
        url = normalize_text(asset.get("url") or "")
        key = (url or normalize_text(asset.get("heading") or ""), "supplementary", normalize_text(asset.get("heading") or ""))
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
            continue
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
    assets.extend(extract_formula_assets(html_text, source_url))
    if asset_profile == "all":
        assets.extend(extract_supplementary_assets(html_text, source_url))
    return assets


def extract_full_size_figure_image_url(html_text: str, source_url: str) -> str | None:
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
        if looks_like_full_size_asset_url(absolute_candidate.lower()):
            return absolute_candidate
        if fallback_candidate is None:
            fallback_candidate = absolute_candidate
    return fallback_candidate


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
    candidates = figure_download_candidates(transport, asset=asset, user_agent=user_agent)
    return candidates[0] if candidates else normalize_text(str(asset.get("url") or ""))


def html_asset_identity_key(asset: Mapping[str, Any]) -> str:
    for field in ("figure_page_url", "original_url", "download_url", "full_size_url", "preview_url", "url", "source_url", "path"):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return ""


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
    candidate_builder: Callable[..., list[str]] | None = None,
    image_document_fetcher: ImageDocumentFetcher | None = None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None] | None = None,
    opener_requester: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or asset_profile == "none" or not assets:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    active_candidate_builder = candidate_builder or figure_download_candidates
    active_cookie_opener_builder = cookie_opener_builder or _build_cookie_seeded_opener
    active_opener_requester = opener_requester or _request_with_opener

    for asset in assets:
        preview_url = normalize_text(str(asset.get("preview_url") or asset.get("url") or ""))
        full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
        candidate_urls = active_candidate_builder(
            transport,
            asset=asset,
            user_agent=user_agent,
            figure_page_fetcher=figure_page_fetcher,
        )
        if not candidate_urls:
            continue

        response = None
        source_url = ""
        download_tier_override = ""
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
                    active_cookie_opener_builder(
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
                    active_opener_requester(
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
                body = response.get("body", b"")
                content_type = _response_header(response, "content-type")
                final_url = normalize_text(str(response.get("url") or candidate_url))
                if _requires_image_payload(asset) and not _looks_like_image_payload(content_type, body, final_url):
                    last_failure = {
                        "kind": asset.get("kind", "figure"),
                        "heading": asset.get("heading", "Figure"),
                        "caption": asset.get("caption", ""),
                        "source_url": candidate_url,
                        "status": response.get("status_code"),
                        "reason": f"Asset candidate did not return image content (content-type: {content_type or 'unknown'}).",
                        "section": asset.get("section") or "body",
                    }
                    fallback_response = _fetch_image_document_fallback(image_document_fetcher, candidate_url, asset)
                    if fallback_response is not None:
                        response = fallback_response
                        source_url = candidate_url
                        download_tier_override = "playwright_canvas_fallback"
                        break
                    response = None
                    continue
                if _requires_image_payload(asset) and _is_preview_candidate(candidate_url, preview_url=preview_url, full_size_url=full_size_url):
                    for upgrade_target in _preview_upgrade_targets(candidate_url, asset):
                        if upgrade_target == candidate_url:
                            continue
                        fallback_response = _fetch_image_document_fallback(image_document_fetcher, upgrade_target, asset)
                        if fallback_response is not None:
                            response = fallback_response
                            source_url = upgrade_target
                            download_tier_override = "playwright_canvas_fallback"
                            break
                    if download_tier_override:
                        break
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
                fallback_response = _fetch_image_document_fallback(image_document_fetcher, candidate_url, asset)
                if fallback_response is not None:
                    response = fallback_response
                    source_url = candidate_url
                    download_tier_override = "playwright_canvas_fallback"
                    break
                continue

        if response is None:
            if last_failure is not None:
                failures.append(last_failure)
            continue

        content_type = _response_header(response, "content-type")
        dimensions = _response_dimensions(response) or (0, 0)
        width, height = dimensions
        download_tier = (
            download_tier_override
            or (
                "preview"
                if preview_url
                and source_url == preview_url
                and source_url != full_size_url
                and not looks_like_full_size_asset_url(source_url.lower())
                else "full_size"
            )
        )
        output_path = build_asset_output_path(asset_dir, source_url, content_type, response["url"], used_names)
        download = {
            "kind": asset.get("kind", "figure"),
            "heading": asset.get("heading", "Figure"),
            "caption": asset.get("caption", ""),
            "original_url": preview_url,
            "figure_page_url": asset.get("figure_page_url", ""),
            "download_url": source_url,
            "download_tier": download_tier,
            "source_url": response["url"],
            "content_type": content_type,
            "path": save_payload(output_path, response["body"]),
            "downloaded_bytes": len(response["body"]),
            "section": asset.get("section") or "body",
        }
        if width > 0 and height > 0:
            download["width"] = width
            download["height"] = height
        if download_tier == "preview" and preview_dimensions_are_acceptable(width, height):
            download["preview_accepted"] = True
        downloads.append(download)

    return {
        "assets": downloads,
        "asset_failures": failures,
    }


def download_figure_assets_with_image_document_fetcher(
    transport: HttpTransport,
    *,
    article_id: str,
    assets: list[dict[str, str]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile = "all",
    figure_page_fetcher: FigurePageFetcher | None = None,
    candidate_builder: Callable[..., list[str]] | None = None,
    image_document_fetcher: ImageDocumentFetcher | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or asset_profile == "none" or not assets:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    active_candidate_builder = candidate_builder or figure_download_candidates

    for asset in assets:
        if not _requires_image_payload(asset):
            continue
        preview_url = normalize_text(str(asset.get("preview_url") or asset.get("url") or ""))
        full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
        candidate_urls = active_candidate_builder(
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

            response = _fetch_image_document_fallback(image_document_fetcher, candidate_url, asset)
            if response is not None:
                source_url = candidate_url
                break
            fetch_failure = _image_document_fetch_failure(image_document_fetcher, candidate_url)
            last_failure = {
                "kind": asset.get("kind", "figure"),
                "heading": asset.get("heading", "Figure"),
                "caption": asset.get("caption", ""),
                "source_url": candidate_url,
                "reason": f"Asset candidate did not return image content for {candidate_url}.",
                "section": asset.get("section") or "body",
                **fetch_failure,
            }

        if response is None:
            if last_failure is not None:
                failures.append(last_failure)
            continue

        content_type = _response_header(response, "content-type")
        dimensions = _response_dimensions(response) or (0, 0)
        width, height = dimensions
        download_tier = (
            "preview"
            if preview_url
            and source_url == preview_url
            and source_url != full_size_url
            and not looks_like_full_size_asset_url(source_url.lower())
            else "full_size"
        )
        output_path = build_asset_output_path(asset_dir, source_url, content_type, response["url"], used_names)
        download = {
            "kind": asset.get("kind", "figure"),
            "heading": asset.get("heading", "Figure"),
            "caption": asset.get("caption", ""),
            "original_url": preview_url,
            "figure_page_url": asset.get("figure_page_url", ""),
            "download_url": source_url,
            "download_tier": download_tier,
            "source_url": response["url"],
            "content_type": content_type,
            "path": save_payload(output_path, response["body"]),
            "downloaded_bytes": len(response["body"]),
            "section": asset.get("section") or "body",
        }
        if width > 0 and height > 0:
            download["width"] = width
            download["height"] = height
        if download_tier == "preview" and preview_dimensions_are_acceptable(width, height):
            download["preview_accepted"] = True
        downloads.append(download)

    return {
        "assets": downloads,
        "asset_failures": failures,
    }
