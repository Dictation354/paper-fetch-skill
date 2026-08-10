"""Silverchair-specific image URL helpers shared by provider extractors."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ....utils import normalize_text
from ..parsing import choose_parser
from .dom import _first_url_from_srcset


def promote_silverchair_srcset_originals(html_text: str) -> str:
    """Expose the largest Silverchair srcset rendition to neutral extraction."""

    if "srcset" not in html_text.lower():
        return html_text
    soup = BeautifulSoup(html_text, choose_parser())
    changed = False
    for tag in soup.find_all(["img", "source"]):
        if not isinstance(tag, Tag) or tag.get("data-hi-res-src"):
            continue
        for attr in ("data-srcset", "srcset"):
            candidate = _first_url_from_srcset(normalize_text(str(tag.get(attr) or "")))
            if candidate:
                tag["data-hi-res-src"] = candidate
                changed = True
                break
    return str(soup) if changed else html_text


def silverchair_image_basename(value: str | None) -> str:
    """Return a stable basename for matching preview and original images."""

    basename = PurePosixPath(urlparse(normalize_text(value)).path).name.lower()
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return stem.removeprefix("m_")


def silverchair_download_image_url(
    node: Any,
    source_url: str,
    *,
    expected_image_basename: str = "",
) -> str:
    """Unwrap a signed Silverchair ``DownloadImage.aspx`` figure URL safely."""

    if not isinstance(node, Tag):
        return ""
    expected = silverchair_image_basename(expected_image_basename)
    for anchor in node.find_all("a", href=True):
        href = normalize_text(str(anchor.get("href") or ""))
        if not href:
            continue
        wrapper_url = urljoin(source_url, href)
        parsed_wrapper = urlparse(wrapper_url)
        if not parsed_wrapper.path.lower().endswith("/downloadfile/downloadimage.aspx"):
            continue

        # The nested image URL is not percent-encoded as a whole, so preserve
        # its query string while separating Silverchair's outer parameters.
        image_value = ""
        outer_signature_segments: dict[str, str] = {}
        for segment in parsed_wrapper.query.split("&"):
            key, separator, value = segment.partition("=")
            if not separator:
                continue
            normalized_key = unquote(key).strip().lower()
            if normalized_key == "image" and not image_value:
                image_value = value
            elif normalized_key in {"expires", "signature", "key-pair-id"}:
                outer_signature_segments.setdefault(normalized_key, segment)
        if not image_value:
            continue

        image_url = urljoin(source_url, unquote(image_value))
        parsed_image = urlparse(image_url)
        image_host = normalize_text(parsed_image.hostname or "").lower()
        if (
            parsed_image.scheme not in {"http", "https"}
            or not image_host
            or (
                image_host != "silverchair-cdn.com"
                and not image_host.endswith(".silverchair-cdn.com")
            )
        ):
            continue
        if expected and silverchair_image_basename(image_url) != expected:
            continue

        nested_keys = {
            unquote(segment.partition("=")[0]).strip().lower()
            for segment in parsed_image.query.split("&")
            if segment
        }
        missing_signature_segments = [
            segment
            for key, segment in outer_signature_segments.items()
            if key not in nested_keys
        ]
        if missing_signature_segments:
            separator = "&" if parsed_image.query else "?"
            image_url = f"{image_url}{separator}{'&'.join(missing_signature_segments)}"
        return image_url
    return ""


__all__ = [
    "promote_silverchair_srcset_originals",
    "silverchair_download_image_url",
    "silverchair_image_basename",
]
