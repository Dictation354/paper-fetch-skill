"""Shared PDF validation and Markdown conversion helpers."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import contextlib
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from collections.abc import Mapping
import hashlib
import urllib.parse

from ..common_patterns import WORD_TOKEN_PATTERN
from ..http import PDF_ACCEPT_HEADER, is_pdf_content_type
from ..models.markdown import replace_markdown_images
from ..utils import normalize_text, sanitize_filename
from .browser_runtime.seed import CLOUDFLARE_COOKIE_NAMES, _CLOUDFLARE_COOKIE_PREFIXES

PdfAssetProfile = Literal["none", "body", "all"]


@dataclass(frozen=True)
class PdfFetchResult:
    source_url: str
    final_url: str
    pdf_bytes: bytes
    markdown_text: str
    suggested_filename: str | None = None
    assets: list[dict[str, Any]] = field(default_factory=list)


def pdf_fetch_result_assets(pdf_result: Any) -> list[dict[str, Any]]:
    assets = getattr(pdf_result, "assets", None)
    if assets is None or isinstance(assets, Mapping | str | bytes | bytearray):
        return []
    try:
        return [dict(item) for item in assets if isinstance(item, Mapping)]
    except TypeError:
        return []


class PdfFetchFailure(Exception):
    def __init__(self, kind: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.details = dict(details or {})


_CONTENT_DISPOSITION_FILENAME_PATTERN = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', flags=re.IGNORECASE)
_PDF_MARKDOWN_WORD_PATTERN = WORD_TOKEN_PATTERN
# IEEE PDF cover/license pages are the common failure mode this guard was
# calibrated against; keep the marker name provider-specific so callers do not
# treat it as a generic publisher-license classifier.
_IEEE_PDF_LICENSE_MARKERS = (
    "authorized licensed use limited to",
    "restrictions apply",
    "downloaded on",
    "from ieee xplore",
    "personal use is permitted",
)
_MIN_USABLE_PDF_MARKDOWN_WORDS = 250
_MIN_TRANSPARENT_TEXT_WORDS = 500
_TRANSPARENT_FALLBACK_WORD_FACTOR = 3
_PYMUPDF_SUBPROCESS_PATCH_LOCK = threading.RLock()


@dataclass(frozen=True)
class _PdfMarkdownQuality:
    word_count: int
    license_word_count: int
    license_only: bool
    has_text: bool

    @property
    def is_usable(self) -> bool:
        return self.word_count >= _MIN_USABLE_PDF_MARKDOWN_WORDS and not self.license_only


@dataclass(frozen=True)
class _PdfTextLayerStats:
    raw_words: int
    visible_words: int
    transparent_words: int


@dataclass(frozen=True)
class PdfMarkdownRenderResult:
    markdown_text: str
    assets: list[dict[str, Any]] = field(default_factory=list)


def sanitize_storage_state(path: Path) -> Path:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies", []) or []
    filtered_cookies = [
        cookie
        for cookie in cookies
        if cookie.get("name") not in CLOUDFLARE_COOKIE_NAMES
        and not str(cookie.get("name", "")).startswith(_CLOUDFLARE_COOKIE_PREFIXES)
    ]
    payload["cookies"] = filtered_cookies

    fd, temp_path = tempfile.mkstemp(prefix="playwright_state_", suffix=".json")
    temp_file = Path(temp_path)
    os.close(fd)
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return temp_file


def filename_from_headers(headers: Mapping[str, str] | None) -> str | None:
    content_disposition = str((headers or {}).get("content-disposition") or "")
    if not content_disposition:
        return None
    match = _CONTENT_DISPOSITION_FILENAME_PATTERN.search(content_disposition)
    if not match:
        return None
    return normalize_text(match.group(1)) or None


def default_pdf_headers(user_agent: str, *, referer: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": PDF_ACCEPT_HEADER,
        "User-Agent": user_agent,
    }
    if referer:
        headers["Referer"] = referer
    return headers


def pdf_asset_profile_from_context(
    context: Any | None,
    default: PdfAssetProfile = "none",
) -> PdfAssetProfile:
    value = normalize_text(getattr(context, "asset_profile", default)).lower()
    if value in {"body", "all"}:
        return value  # type: ignore[return-value]
    return "none"


def pdf_asset_output_dir(
    context: Any | None,
    *,
    asset_profile: PdfAssetProfile | None = None,
    doi: str | None = None,
) -> Path | None:
    effective_profile = asset_profile or pdf_asset_profile_from_context(context)
    if effective_profile == "none":
        return None
    normalized_doi = normalize_text(doi)
    artifact_store = getattr(context, "artifact_store", None)
    if artifact_store is not None:
        output_dir = getattr(artifact_store, "asset_download_dir", None)
        if output_dir is None:
            return None
        output_path = Path(output_dir)
        if normalized_doi:
            return output_path / f"{sanitize_filename(normalized_doi)}_assets"
        return output_path
    output_dir = getattr(context, "download_dir", None)
    if output_dir is None:
        return None
    output_path = Path(output_dir)
    if normalized_doi:
        return output_path / f"{sanitize_filename(normalized_doi)}_assets"
    return output_path


def _pdf_word_count(text: str) -> int:
    return len(_PDF_MARKDOWN_WORD_PATTERN.findall(normalize_text(text)))


def _pdf_markdown_quality(markdown_text: str) -> _PdfMarkdownQuality:
    normalized = normalize_text(markdown_text)
    word_count = _pdf_word_count(normalized)
    lines = [line for line in normalized.splitlines() if normalize_text(line)]
    license_word_count = 0
    for line in lines:
        normalized_line = normalize_text(line).lower()
        if any(marker in normalized_line for marker in _IEEE_PDF_LICENSE_MARKERS):
            license_word_count += _pdf_word_count(line)
    license_only = license_word_count > 0 and (
        word_count < _MIN_USABLE_PDF_MARKDOWN_WORDS
        or license_word_count >= max(20, int(word_count * 0.6))
    )
    return _PdfMarkdownQuality(
        word_count=word_count,
        license_word_count=license_word_count,
        license_only=license_only,
        has_text=bool(normalized),
    )


class _SubprocessTextDecodeReplace:
    def __enter__(self) -> None:
        _PYMUPDF_SUBPROCESS_PATCH_LOCK.acquire()
        self._original_run = subprocess.run

        def run_with_replace(*args, **kwargs):
            if (
                "errors" not in kwargs
                and (
                    kwargs.get("text")
                    or kwargs.get("universal_newlines")
                    or kwargs.get("encoding") is not None
                )
            ):
                kwargs = dict(kwargs)
                kwargs["errors"] = "replace"
            return self._original_run(*args, **kwargs)

        subprocess.run = run_with_replace

    def __exit__(self, exc_type, exc, tb) -> None:
        subprocess.run = self._original_run
        _PYMUPDF_SUBPROCESS_PATCH_LOCK.release()


def _render_default_pdf_markdown(pdf_path: Path, *, image_dir: Path | None = None) -> str:
    try:
        import pymupdf4llm
    except Exception as exc:  # pragma: no cover - exercised by missing dependency integration tests
        raise PdfFetchFailure("missing_pymupdf4llm", "pymupdf4llm is not installed; cannot use PDF fallback.") from exc
    kwargs: dict[str, Any] = {}
    if image_dir is not None:
        image_dir.mkdir(parents=True, exist_ok=True)
        kwargs.update(
            {
                "write_images": True,
                "image_path": str(image_dir),
            }
        )
    with _SubprocessTextDecodeReplace():
        return str(pymupdf4llm.to_markdown(str(pdf_path), **kwargs) or "")


def _render_transparent_pdf_markdown(pdf_path: Path) -> str:
    try:
        from pymupdf4llm.helpers import pymupdf_rag
    except Exception as exc:  # pragma: no cover - exercised by missing dependency integration tests
        raise PdfFetchFailure("missing_pymupdf4llm", "pymupdf4llm is not installed; cannot use PDF fallback.") from exc
    with _SubprocessTextDecodeReplace():
        return str(pymupdf_rag.to_markdown(str(pdf_path), ignore_alpha=True, hdr_info=False) or "")


def _pdf_text_layer_stats(pdf_path: Path) -> _PdfTextLayerStats:
    try:
        import pymupdf
    except Exception:  # pragma: no cover - PyMuPDF is a pymupdf4llm dependency in supported installs
        try:
            import fitz as pymupdf
        except Exception:
            return _PdfTextLayerStats(raw_words=0, visible_words=0, transparent_words=0)

    raw_words = 0
    transparent_words = 0
    try:
        with pymupdf.open(str(pdf_path)) as document:
            for page in document:
                text_dict = page.get_text("dict")
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_words = _pdf_word_count(str(span.get("text") or ""))
                            raw_words += span_words
                            alpha_value = span.get("alpha", 255)
                            if alpha_value is None:
                                alpha_value = 255
                            if int(alpha_value) == 0:
                                transparent_words += span_words
    except Exception:
        return _PdfTextLayerStats(raw_words=0, visible_words=0, transparent_words=0)
    return _PdfTextLayerStats(
        raw_words=raw_words,
        visible_words=max(0, raw_words - transparent_words),
        transparent_words=transparent_words,
    )


def _should_try_transparent_pdf_fallback(
    *,
    default_quality: _PdfMarkdownQuality,
    text_layer_stats: _PdfTextLayerStats,
) -> bool:
    if default_quality.is_usable:
        return False
    return (
        text_layer_stats.transparent_words >= _MIN_TRANSPARENT_TEXT_WORDS
        and text_layer_stats.raw_words >= default_quality.word_count * _TRANSPARENT_FALLBACK_WORD_FACTOR
    )


def _insufficient_pdf_markdown_failure(
    *,
    default_quality: _PdfMarkdownQuality,
    text_layer_stats: _PdfTextLayerStats,
    legacy_quality: _PdfMarkdownQuality | None = None,
) -> PdfFetchFailure:
    details: dict[str, Any] = {
        "default_words": default_quality.word_count,
        "default_license_words": default_quality.license_word_count,
        "default_license_only": default_quality.license_only,
        "raw_words": text_layer_stats.raw_words,
        "visible_words": text_layer_stats.visible_words,
        "transparent_words": text_layer_stats.transparent_words,
    }
    if legacy_quality is not None:
        details.update(
            {
                "legacy_words": legacy_quality.word_count,
                "legacy_license_words": legacy_quality.license_word_count,
                "legacy_license_only": legacy_quality.license_only,
            }
        )
    return PdfFetchFailure(
        "insufficient_pdf_markdown",
        "PDF fallback produced insufficient Markdown.",
        details=details,
    )


def _pdf_image_dir(asset_output_dir: Path | None, asset_profile: PdfAssetProfile) -> Path | None:
    if asset_profile == "none" or asset_output_dir is None:
        return None
    if asset_output_dir.name == "body_assets" or asset_output_dir.name.endswith("_assets"):
        return asset_output_dir
    return asset_output_dir / "body_assets"


def _pdf_image_relative_url(path: Path, image_dir: Path) -> str:
    prefix = normalize_text(image_dir.name) or "assets"
    return f"{prefix}/{path.name}"


def _resolve_pdf_image_reference(image_url: str, image_dir: Path) -> Path | None:
    normalized = normalize_text(image_url)
    if not normalized:
        return None
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme in {"http", "https", "data"}:
        return None
    raw_path = urllib.parse.unquote(parsed.path or normalized)
    candidate = Path(raw_path)
    candidates: list[Path] = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.extend(
            [
                Path.cwd() / candidate,
                image_dir / candidate.name,
            ]
        )
    image_dir_resolved = image_dir.resolve()
    for item in candidates:
        try:
            resolved = item.resolve()
        except OSError:
            continue
        if not resolved.is_file():
            continue
        try:
            resolved.relative_to(image_dir_resolved)
        except ValueError:
            continue
        return resolved
    return None


def _pdf_image_asset(
    *,
    path: Path,
    image_dir: Path,
    heading: str,
    source_url: str | None,
) -> dict[str, Any]:
    relative_url = _pdf_image_relative_url(path, image_dir)
    asset: dict[str, Any] = {
        "kind": "figure",
        "heading": heading,
        "url": relative_url,
        "path": str(path),
        "section": "body",
        "render_state": "inline",
        "download_tier": "full_size",
        "download_url": relative_url,
        "content_type": _content_type_from_image_path(path),
    }
    if source_url:
        asset["source_url"] = source_url
    with contextlib.suppress(OSError):
        asset["downloaded_bytes"] = path.stat().st_size
    return asset


def _content_type_from_image_path(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    return None


def _normalize_pdf_markdown_image_assets(
    markdown_text: str,
    *,
    image_dir: Path | None,
    source_url: str | None,
) -> PdfMarkdownRenderResult:
    if image_dir is None or not markdown_text:
        return PdfMarkdownRenderResult(markdown_text=markdown_text, assets=[])

    assets: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    def replace_image(image) -> str:
        path = _resolve_pdf_image_reference(image.url, image_dir)
        if path is None:
            return image.text
        heading = normalize_text(image.alt) or f"Figure {len(assets) + 1}"
        if path not in seen_paths:
            seen_paths.add(path)
            assets.append(
                _pdf_image_asset(
                    path=path,
                    image_dir=image_dir,
                    heading=heading,
                    source_url=source_url,
                )
            )
        return f"![{heading}]({_pdf_image_relative_url(path, image_dir)})"

    rewritten = replace_markdown_images(markdown_text, replace_image)
    return PdfMarkdownRenderResult(markdown_text=rewritten, assets=assets)


def render_pdf_markdown_result(
    pdf_path: Path,
    *,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    source_url: str | None = None,
) -> PdfMarkdownRenderResult:
    image_dir = _pdf_image_dir(asset_output_dir, asset_profile)
    default_markdown = _render_default_pdf_markdown(pdf_path, image_dir=image_dir)
    default_render = _normalize_pdf_markdown_image_assets(
        default_markdown,
        image_dir=image_dir,
        source_url=source_url,
    )
    default_quality = _pdf_markdown_quality(default_markdown)
    if default_quality.is_usable:
        return default_render

    text_layer_stats = _pdf_text_layer_stats(pdf_path)
    if _should_try_transparent_pdf_fallback(
        default_quality=default_quality,
        text_layer_stats=text_layer_stats,
    ):
        legacy_markdown = _render_transparent_pdf_markdown(pdf_path)
        legacy_quality = _pdf_markdown_quality(legacy_markdown)
        min_legacy_words = max(
            _MIN_USABLE_PDF_MARKDOWN_WORDS,
            default_quality.word_count * _TRANSPARENT_FALLBACK_WORD_FACTOR,
        )
        if legacy_quality.word_count >= min_legacy_words and not legacy_quality.license_only:
            return PdfMarkdownRenderResult(markdown_text=legacy_markdown, assets=[])
        raise _insufficient_pdf_markdown_failure(
            default_quality=default_quality,
            text_layer_stats=text_layer_stats,
            legacy_quality=legacy_quality,
        )

    if not default_quality.has_text:
        return default_render
    raise _insufficient_pdf_markdown_failure(
        default_quality=default_quality,
        text_layer_stats=text_layer_stats,
    )


def render_pdf_markdown(pdf_path: Path) -> str:
    return render_pdf_markdown_result(pdf_path).markdown_text


def looks_like_pdf_payload(content_type: str | None, payload: bytes, final_url: str | None = None) -> bool:
    normalized_content_type = normalize_text(content_type).lower()
    normalized_final_url = normalize_text(final_url).lower()
    return (
        payload.startswith(b"%PDF-")
        or is_pdf_content_type(normalized_content_type)
        or normalized_final_url.endswith(".pdf")
    )


def _normalized_response_headers(response: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(key).lower(): str(value)
        for key, value in (response.get("headers") or {}).items()
    }


def pdf_fetch_result_from_response(
    response: Mapping[str, Any],
    *,
    artifact_dir: Path | None,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    source_url: str,
    not_pdf_message: str,
    final_url: str | None = None,
) -> PdfFetchResult:
    response_headers = _normalized_response_headers(response)
    resolved_final_url = normalize_text(str(final_url or response.get("url") or source_url)) or source_url
    try:
        status = int(response.get("status_code") or 0) or None
    except (TypeError, ValueError):
        status = None
    raw_body = response.get("body", b"")
    pdf_bytes = bytes(raw_body) if isinstance(raw_body, (bytes, bytearray)) else b""
    content_type = str(response_headers.get("content-type") or "")
    if not isinstance(raw_body, (bytes, bytearray)) or not looks_like_pdf_payload(
        content_type,
        pdf_bytes,
        resolved_final_url,
    ):
        raise PdfFetchFailure(
            "downloaded_file_not_pdf",
            not_pdf_message,
            details={
                "source_url": source_url,
                "final_url": resolved_final_url,
                "status": status,
                "content_type": content_type or None,
            },
        )

    return pdf_fetch_result_from_bytes(
        artifact_dir=artifact_dir,
        asset_profile=asset_profile,
        asset_output_dir=asset_output_dir,
        source_url=source_url,
        final_url=resolved_final_url,
        pdf_bytes=pdf_bytes,
        suggested_filename=filename_from_headers(response_headers),
    )


def _stable_pdf_filename(
    *,
    source_url: str,
    final_url: str,
    suggested_filename: str | None,
) -> str:
    candidates = [suggested_filename, final_url, source_url]
    stem = ""
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if not normalized:
            continue
        parsed = urllib.parse.urlparse(normalized)
        raw_name = urllib.parse.unquote(Path(parsed.path or normalized).name)
        raw_stem = Path(raw_name).stem if raw_name else ""
        raw_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_stem).strip("._-")
        if raw_stem:
            stem = raw_stem[:80]
            break
    digest_source = normalize_text(final_url) or normalize_text(source_url) or stem or "pdf"
    digest = hashlib.sha1(digest_source.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"{stem or 'downloaded'}-{digest}.pdf"


def pdf_fetch_result_from_bytes(
    *,
    artifact_dir: Path | None,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    source_url: str,
    final_url: str,
    pdf_bytes: bytes,
    suggested_filename: str | None = None,
) -> PdfFetchResult:
    temp_dir_cm = tempfile.TemporaryDirectory(prefix="paper_fetch_pdf_") if artifact_dir is None else nullcontext(None)
    with temp_dir_cm as temp_dir:
        active_dir = Path(temp_dir) if temp_dir is not None else artifact_dir
        assert active_dir is not None
        active_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = active_dir / _stable_pdf_filename(
            source_url=source_url,
            final_url=final_url,
            suggested_filename=suggested_filename,
        )
        pdf_path.write_bytes(pdf_bytes)
        if not pdf_bytes.startswith(b"%PDF-"):
            pdf_path.unlink(missing_ok=True)
            raise PdfFetchFailure(
                "downloaded_file_not_pdf",
                "PDF fallback did not produce a PDF file.",
                details={"source_url": source_url, "suggested_filename": suggested_filename},
            )

        render_result = render_pdf_markdown_result(
            pdf_path,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            source_url=final_url or source_url,
        )
        markdown_text = render_result.markdown_text
        if not normalize_text(markdown_text):
            raise PdfFetchFailure(
                "empty_pdf_markdown",
                "PDF fallback produced empty Markdown.",
                details={"source_url": source_url, "final_url": final_url},
            )

        return PdfFetchResult(
            source_url=source_url,
            final_url=final_url,
            pdf_bytes=pdf_bytes,
            markdown_text=markdown_text,
            suggested_filename=suggested_filename,
            assets=[dict(item) for item in render_result.assets],
        )
