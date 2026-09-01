"""arXiv HTML asset extraction and download retry helpers."""

from __future__ import annotations

import contextlib
import io
import math
import os
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence
import re
import urllib.parse
import uuid

from ..common_patterns import EXTENDED_DATA_FIGURE_LABEL
from ..asset_budget import AssetBudget, AssetBudgetExceeded, AssetReservation
from ..artifacts import ArtifactStore
from ..config import resolve_asset_download_concurrency
from ..extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_dimensions_from_path,
    image_mime_type_from_bytes,
    payload_mime_type_from_path,
)
from ..extraction.html import assets as html_assets
from ..http import (
    HttpRequestPolicy,
    HttpStreamOptions,
    HttpTransport,
    RequestFailure,
    provider_request_policy,
)
from ..runtime import RuntimeContext
from ..markdown.images import render_markdown_image
from ..utils import empty_asset_results, normalize_text, sanitize_filename
from ._arxiv_parsing import ARXIV_HTML_PARSER
from ._arxiv_source_archive import (
    _ARXIV_SOURCE_MAX_MEMBER_BYTES,
    _ArxivSourceMember,
    _cleanup_arxiv_source_members,
    _extract_arxiv_source_figure_references,
    _read_arxiv_source_files_from_path,
    _read_bounded_stream,
    _retain_arxiv_source_member as _retain_arxiv_source_member,
    _safe_arxiv_source_member_name as _safe_arxiv_source_member_name,
    _arxiv_source_url,
)
from ._asset_retry import AssetRetryPolicy, is_retryable_asset_failure
from ._arxiv_html import Tag, BeautifulSoup
from ._arxiv_references import _is_arxiv_inline_figure_container
from ._html_asset_engine import merge_assets_by_identity
from ._html_section_markdown import (
    INLINE_FIGURE_ALT_ATTR,
    INLINE_FIGURE_SRC_ATTR,
    render_clean_text_from_html,
)

ARXIV_ASSET_DOWNLOAD_CONCURRENCY_LIMIT = 2
ARXIV_IMAGE_ACCEPT = "image/avif,image/webp,image/*,*/*;q=0.8"
ARXIV_SOURCE_ACCEPT = (
    "application/gzip,application/x-gzip,application/x-tar,application/zip,*/*;q=0.8"
)
_ARXIV_FIGURE_CAPTION_LABEL_PATTERN = re.compile(
    rf"^(?P<label>(?:Figure|Fig\.?|{re.escape(EXTENDED_DATA_FIGURE_LABEL)}\.?)\s+\d+[A-Za-z]?)[.:]?\s*(?P<caption>.*)$",
    flags=re.IGNORECASE,
)
_ARXIV_FIGURE_ID_PATTERN = re.compile(
    r"(?:^|[.])F(?P<number>\d+[A-Za-z]?(?:\.\d+[A-Za-z]?)?)(?=$|[.])",
    flags=re.IGNORECASE,
)


def _arxiv_asset_download_concurrency(env: Mapping[str, str] | None) -> int:
    return min(
        resolve_asset_download_concurrency(env), ARXIV_ASSET_DOWNLOAD_CONCURRENCY_LIMIT
    )


def _asset_candidate_urls(asset: Mapping[str, Any]) -> set[str]:
    return {
        normalized
        for normalized in (
            normalize_text(str(asset.get(field) or ""))
            for field in (
                "url",
                "full_size_url",
                "preview_url",
                "download_url",
                "original_url",
                "link",
            )
        )
        if normalized
    }


def _arxiv_asset_retry_key(asset: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        tuple(sorted(_asset_candidate_urls(asset))),
        normalize_text(str(asset.get("heading") or "")),
        normalize_text(str(asset.get("caption") or "")),
    )


def _arxiv_asset_matches_failure(
    asset: Mapping[str, Any], failure: Mapping[str, Any]
) -> bool:
    failure_url = normalize_text(
        str(failure.get("source_url") or failure.get("url") or "")
    )
    if failure_url and failure_url in _asset_candidate_urls(asset):
        return True
    failure_heading = normalize_text(str(failure.get("heading") or ""))
    asset_heading = normalize_text(str(asset.get("heading") or ""))
    failure_caption = normalize_text(str(failure.get("caption") or ""))
    asset_caption = normalize_text(str(asset.get("caption") or ""))
    return bool(
        failure_heading
        and failure_heading == asset_heading
        and failure_caption == asset_caption
    )


ARXIV_ASSET_RETRY_POLICY = AssetRetryPolicy(
    name="arxiv",
    key_fn=_arxiv_asset_retry_key,
    retryable_failure=is_retryable_asset_failure,
    failure_match=_arxiv_asset_matches_failure,
)


def _asset_has_download_candidate(asset: Mapping[str, Any]) -> bool:
    return bool(
        normalize_text(
            str(
                asset.get("url")
                or asset.get("full_size_url")
                or asset.get("preview_url")
                or asset.get("download_url")
                or asset.get("original_url")
                or asset.get("link")
                or ""
            )
        )
    )


def _extract_arxiv_html_assets(
    article_html: str, source_url: str
) -> list[dict[str, Any]]:
    assets = [
        _postprocess_arxiv_html_asset(item)
        for item in html_assets.extract_figure_assets(article_html, source_url)
        if normalize_text(str(item.get("kind") or "")).lower() == "figure"
        and _asset_has_download_candidate(item)
    ]
    return [dict(item) for item in merge_assets_by_identity(assets)]


def _arxiv_figure_label_from_text(text: str) -> str:
    normalized = normalize_text(str(text or "").replace("\n", " "))
    match = _ARXIV_FIGURE_CAPTION_LABEL_PATTERN.match(normalized)
    if match is None:
        return ""
    raw_label = normalize_text(match.group("label"))
    number_match = re.search(r"(\d+[A-Za-z]?)$", raw_label)
    if number_match is None:
        return raw_label.rstrip(".:")
    if raw_label.lower().startswith(EXTENDED_DATA_FIGURE_LABEL.lower()):
        return f"{EXTENDED_DATA_FIGURE_LABEL}. {number_match.group(1)}"
    return f"Figure {number_match.group(1)}"


def _arxiv_figure_label_from_dom_id(dom_id: Any) -> str:
    normalized = normalize_text(str(dom_id or ""))
    match = _ARXIV_FIGURE_ID_PATTERN.search(normalized)
    if match is None:
        return ""
    return f"Figure {match.group('number')}"


def _clean_arxiv_asset_caption(text: Any) -> str:
    return html_assets.clean_noisy_image_alt_text(str(text or "").replace("\n", " "))


def _postprocess_arxiv_html_asset(asset: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(asset)
    caption = _clean_arxiv_asset_caption(result.get("caption"))
    heading = _clean_arxiv_asset_caption(result.get("heading")) or "Figure"
    short_heading = _arxiv_figure_label_from_text(
        caption
    ) or _arxiv_figure_label_from_text(heading)
    if not short_heading:
        short_heading = _arxiv_figure_label_from_dom_id(
            result.get("dom_id")
        ) or _arxiv_figure_label_from_dom_id(result.get("image_id"))
    result["heading"] = short_heading or heading
    result["caption"] = caption
    return result


def _caption_match_text(value: Any) -> str:
    normalized = normalize_text(str(value or "")).lower()
    match = _ARXIV_FIGURE_CAPTION_LABEL_PATTERN.match(normalized)
    if match is not None:
        normalized = normalize_text(match.group("caption")).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalize_text(normalized)


def _caption_similarity(left: Any, right: Any) -> int:
    left_text = _caption_match_text(left)
    right_text = _caption_match_text(right)
    if not left_text or not right_text:
        return 0
    try:
        from rapidfuzz import fuzz
    except Exception:
        return 100 if left_text == right_text else 0
    return int(fuzz.token_set_ratio(left_text, right_text))


def _match_source_figures_to_html_placeholders(
    placeholders: Sequence[Mapping[str, Any]],
    source_figures: Sequence[Mapping[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    unused = set(range(len(source_figures)))
    matches: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for index, placeholder in enumerate(placeholders):
        best_index: int | None = None
        best_score = -1
        for source_index in sorted(unused):
            score = _caption_similarity(
                placeholder.get("caption"), source_figures[source_index].get("caption")
            )
            if score > best_score:
                best_index = source_index
                best_score = score
        if best_index is not None and best_score >= 55:
            unused.remove(best_index)
            matches.append((dict(placeholder), dict(source_figures[best_index])))
            continue
        fallback_index = index if index in unused else None
        if fallback_index is None and unused:
            fallback_index = min(unused)
        if fallback_index is None:
            matches.append((dict(placeholder), None))
            continue
        unused.remove(fallback_index)
        matches.append((dict(placeholder), dict(source_figures[fallback_index])))
    return matches


def _render_pdf_source_figure_to_png(body: bytes) -> tuple[bytes, int, int] | None:
    try:
        import pymupdf
    except Exception:
        try:
            import fitz as pymupdf
        except Exception:
            return None
    try:
        with pymupdf.open(stream=body, filetype="pdf") as document:
            if len(document) <= 0:
                return None
            page = document.load_page(0)
            rect = page.rect
            projected_width = max(1, math.ceil(float(rect.width) * 2))
            projected_height = max(1, math.ceil(float(rect.height) * 2))
            if projected_width * projected_height > 64_000_000:
                return None
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            payload = bytes(pixmap.tobytes("png"))
            if len(payload) > _ARXIV_SOURCE_MAX_MEMBER_BYTES:
                return None
            return payload, int(pixmap.width), int(pixmap.height)
    except Exception:
        return None


def _render_pdf_source_figure_path_to_png(
    source_path: Path,
    destination: Path,
    *,
    reservation: AssetReservation,
) -> tuple[int, int, int]:
    """Render the first PDF page path-to-path after a pre-raster pixel check."""

    try:
        import pymupdf
    except Exception:
        try:
            import fitz as pymupdf
        except Exception as exc:
            raise RuntimeError("PyMuPDF is unavailable") from exc
    reservation.register_staging(destination)
    try:
        with pymupdf.open(str(source_path)) as document:
            if len(document) <= 0:
                raise RuntimeError("PDF source figure has no pages")
            page = document.load_page(0)
            rect = page.rect
            projected_width = max(1, math.ceil(float(rect.width) * 2))
            projected_height = max(1, math.ceil(float(rect.height) * 2))
            reservation.validate_pixels(projected_width, projected_height)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            width = int(pixmap.width)
            height = int(pixmap.height)
            reservation.validate_pixels(width, height)
            # The unique staging suffix is deliberately ``.part``; state the
            # encoder explicitly instead of relying on filename inference.
            pixmap.save(str(destination), output="png")
        with destination.open("rb+") as output:
            output.flush()
            os.fsync(output.fileno())
        output_bytes = destination.stat().st_size
        reservation.consume(output_bytes)
        if output_bytes <= 0:
            raise RuntimeError("PDF source figure rendered an empty PNG")
        return width, height, output_bytes
    except BaseException:
        reservation.rollback()
        with contextlib.suppress(OSError):
            destination.unlink(missing_ok=True)
        raise


def _source_figure_image_payload(
    source_path: str, body: bytes
) -> tuple[bytes, str, int | None, int | None] | None:
    suffix = Path(source_path).suffix.lower()
    if suffix == ".pdf":
        rendered = _render_pdf_source_figure_to_png(body)
        if rendered is None:
            return None
        png_body, png_width, png_height = rendered
        return png_body, "image/png", png_width, png_height
    mime_type = image_mime_type_from_bytes(body)
    if not mime_type:
        return None
    dimensions = image_dimensions_from_bytes(body)
    width: int | None
    height: int | None
    width, height = dimensions if dimensions is not None else (None, None)
    return bytes(body), mime_type, width, height


def _unique_source_asset_path(
    asset_dir: Path,
    *,
    source_path: str,
    content_type: str,
    used_names: set[str],
) -> Path:
    source = Path(source_path.replace("\\", "/"))
    stem = sanitize_filename(source.stem or "figure")
    suffix = (
        ".png"
        if content_type == "image/png" and source.suffix.lower() == ".pdf"
        else source.suffix
    )
    if not suffix:
        suffix = ".png" if content_type == "image/png" else ".bin"
    filename = f"{stem}{suffix}"
    counter = 2
    while filename in used_names or (asset_dir / filename).exists():
        filename = f"{stem}_{counter}{suffix}"
        counter += 1
    used_names.add(filename)
    return asset_dir / filename


def _arxiv_source_asset_failure(
    asset: Mapping[str, Any],
    source_url: str,
    *,
    reason: str,
    message: str | None = None,
) -> dict[str, Any]:
    failure = html_assets.FIGURE_KIND.failure_template(asset, source_url, reason=reason)
    if message:
        failure["error_message"] = message
    return failure


def _arxiv_source_downloaded_asset(
    placeholder: Mapping[str, Any],
    *,
    arxiv_id: str,
    source_archive_url: str,
    source_path: str,
    content_type: str,
    saved_path: str,
    output_bytes: int,
    width: int | None,
    height: int | None,
) -> dict[str, Any]:
    source_ref_url = (
        f"{source_archive_url}#{urllib.parse.quote(source_path, safe='/._-')}"
    )
    asset = {
        **dict(placeholder),
        "url": f"arxiv-source://{arxiv_id}/{source_path}",
        "original_url": source_ref_url,
        "download_url": source_ref_url,
        "source_url": source_archive_url,
        "source_path": source_path,
        "content_type": content_type,
        "path": saved_path,
        "downloaded_bytes": output_bytes,
        "download_tier": "arxiv_source",
        "section": "body",
    }
    if width is not None and height is not None:
        asset["width"] = width
        asset["height"] = height
    return asset


def _extract_arxiv_missing_html_figure_placeholders(
    article_html: str, source_url: str
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(article_html, ARXIV_HTML_PARSER)
    article = soup.find("article") or soup
    placeholders: list[dict[str, Any]] = []
    for figure in article.find_all("figure"):
        if not isinstance(figure, Tag) or not _is_arxiv_inline_figure_container(figure):
            continue
        images = [image for image in figure.find_all("img") if isinstance(image, Tag)]
        missing_images = [
            image
            for image in images
            if not _arxiv_image_url_candidates(image, source_url)
        ]
        if not missing_images or len(missing_images) != len(images):
            continue
        caption_node = figure.find("figcaption")
        caption = (
            render_clean_text_from_html(caption_node)
            if isinstance(caption_node, Tag)
            else ""
        )
        for order, image in enumerate(missing_images):
            placeholders.append(
                _postprocess_arxiv_html_asset(
                    {
                        "kind": "figure",
                        "heading": _arxiv_figure_label_from_dom_id(figure.get("id")),
                        "caption": caption,
                        "dom_id": figure.get("id"),
                        "image_id": image.get("id"),
                        "asset_order": str(order),
                        "section": "body",
                        "source_kind": "arxiv_source",
                    }
                )
            )
    return placeholders


def _admit_arxiv_source_placeholders(
    placeholders: Sequence[Mapping[str, Any]],
    *,
    source_url: str,
    asset_budget: AssetBudget,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    admission = asset_budget.admit_work(
        [
            "|".join(
                (
                    "arxiv_source",
                    normalize_text(str(item.get("dom_id") or "")),
                    normalize_text(str(item.get("image_id") or "")),
                    normalize_text(str(item.get("asset_order") or "")),
                )
            )
            for item in placeholders
        ]
    )
    admitted = [
        dict(item)
        for item, accepted in zip(placeholders, admission, strict=True)
        if accepted
    ]
    rejected = [
        _arxiv_source_asset_failure(
            item,
            source_url,
            reason="asset_file_limit_exceeded",
        )
        for item, accepted in zip(placeholders, admission, strict=True)
        if not accepted
    ]
    return admitted, rejected


def _stage_arxiv_source_archive(
    transport: HttpTransport,
    source_archive_url: str,
    source_staging: Path,
    *,
    user_agent: str,
    asset_budget: AssetBudget,
    reservation: AssetReservation,
) -> None:
    request_policy = provider_request_policy(
        "arxiv",
        "source_assets",
        base=HttpRequestPolicy(
            max_response_bytes=asset_budget.max_bytes_per_asset,
            max_compressed_response_bytes=asset_budget.max_bytes_per_asset,
        ),
    )
    if bool(
        getattr(transport, "_streaming_ready", False) is True
        and callable(getattr(transport, "stream_to_file", None))
    ):
        transport.stream_to_file(
            "GET",
            source_archive_url,
            source_staging,
            headers={"Accept": ARXIV_SOURCE_ACCEPT, "User-Agent": user_agent},
            options=HttpStreamOptions(
                request_policy=request_policy,
                on_content_length=reservation.declare_content_length,
                on_chunk=reservation.consume,
            ),
        )
        reservation.reconcile_actual()
        return

    # Compatibility path for explicitly injected test transports only.  It
    # still consumes the exact compiled route policy; production capability is
    # gated by the strict instance-scoped pinned-streaming marker above.
    source_response = transport.request(
        "GET",
        source_archive_url,
        headers={"Accept": ARXIV_SOURCE_ACCEPT, "User-Agent": user_agent},
        request_policy=request_policy,
    )
    source_body = source_response.get("body")
    if not isinstance(source_body, (bytes, bytearray)):
        source_body = b""
    reservation.declare_content_length(len(source_body))
    _read_bounded_stream(
        io.BytesIO(bytes(source_body)),
        reservation=reservation,
        destination=source_staging,
    )


def download_arxiv_source_figure_assets(
    transport: HttpTransport,
    *,
    arxiv_id: str,
    article_id: str,
    article_html: str,
    source_url: str,
    output_dir: Path | None,
    user_agent: str,
    runtime_context: RuntimeContext | None = None,
    placeholders: Sequence[Mapping[str, Any]] | None = None,
    admit_placeholders: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None:
        return empty_asset_results()
    active_placeholders = (
        [dict(item) for item in placeholders]
        if placeholders is not None
        else _extract_arxiv_missing_html_figure_placeholders(article_html, source_url)
    )
    if not active_placeholders:
        return empty_asset_results()

    active_budget = (
        runtime_context.asset_budget
        if runtime_context is not None and runtime_context.asset_budget is not None
        else AssetBudget()
    )
    if admit_placeholders:
        active_placeholders, rejected = _admit_arxiv_source_placeholders(
            active_placeholders,
            source_url=source_url,
            asset_budget=active_budget,
        )
    else:
        rejected = []
    if not active_placeholders:
        return {"assets": [], "asset_failures": rejected}

    source_archive_url = _arxiv_source_url(arxiv_id)
    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    source_staging = asset_dir / f".paper-fetch-arxiv-{uuid.uuid4().hex}.part"
    files: dict[str, _ArxivSourceMember] = {}
    archive_reservation: AssetReservation | None = None
    try:
        archive_reservation = active_budget.reserve_transient()
        archive_reservation.register_staging(source_staging)
        _stage_arxiv_source_archive(
            transport,
            source_archive_url,
            source_staging,
            user_agent=user_agent,
            asset_budget=active_budget,
            reservation=archive_reservation,
        )
        files = _read_arxiv_source_files_from_path(
            source_staging,
            staging_dir=asset_dir,
            asset_budget=active_budget,
        )
    except (AssetBudgetExceeded, RequestFailure) as exc:
        _cleanup_arxiv_source_members(files)
        return {
            "assets": [],
            "asset_failures": [
                _arxiv_source_asset_failure(
                    asset,
                    source_archive_url,
                    reason=(
                        exc.reason_code
                        if isinstance(exc, AssetBudgetExceeded)
                        else normalize_text(str(getattr(exc, "reason_code", "") or ""))
                        or "arxiv_source_fetch_failed"
                    ),
                    message=str(exc),
                )
                for asset in active_placeholders
            ]
            + rejected,
        }
    finally:
        if archive_reservation is not None:
            archive_reservation.rollback()
        source_staging.unlink(missing_ok=True)
    source_figures = _extract_arxiv_source_figure_references(files)
    if not source_figures:
        _cleanup_arxiv_source_members(files)
        return {
            "assets": [],
            "asset_failures": [
                _arxiv_source_asset_failure(
                    asset,
                    source_archive_url,
                    reason="arxiv_source_figures_not_found",
                )
                for asset in active_placeholders
            ]
            + rejected,
        }
    referenced_member_ids = {
        id(member)
        for figure in source_figures
        for member in [figure.get("source_member")]
        if isinstance(member, _ArxivSourceMember)
    }
    _cleanup_arxiv_source_members(files, keep_ids=referenced_member_ids)
    used_names = {path.name for path in asset_dir.iterdir() if path.is_file()}
    downloaded_assets: list[dict[str, Any]] = []
    asset_failures: list[dict[str, Any]] = []
    published_members: dict[int, tuple[str, str, int, int | None, int | None]] = {}
    try:
        for placeholder, source_figure in _match_source_figures_to_html_placeholders(
            active_placeholders, source_figures
        ):
            if source_figure is None:
                asset_failures.append(
                    _arxiv_source_asset_failure(
                        placeholder,
                        source_archive_url,
                        reason="arxiv_source_figure_not_matched",
                    )
                )
                continue
            source_path = normalize_text(str(source_figure.get("source_path") or ""))
            source_member = source_figure.get("source_member")
            source_body = source_figure.get("body")
            if not source_path or not (
                isinstance(source_member, _ArxivSourceMember)
                or isinstance(source_body, (bytes, bytearray))
            ):
                asset_failures.append(
                    _arxiv_source_asset_failure(
                        placeholder,
                        source_archive_url,
                        reason="arxiv_source_figure_not_found",
                    )
                )
                continue

            if isinstance(source_member, _ArxivSourceMember):
                cached_publication = published_members.get(id(source_member))
                if cached_publication is not None:
                    (
                        saved_path,
                        content_type,
                        output_bytes,
                        cached_width,
                        cached_height,
                    ) = cached_publication
                    downloaded_assets.append(
                        _arxiv_source_downloaded_asset(
                            placeholder,
                            arxiv_id=arxiv_id,
                            source_archive_url=source_archive_url,
                            source_path=source_path,
                            content_type=content_type,
                            saved_path=saved_path,
                            output_bytes=output_bytes,
                            width=cached_width,
                            height=cached_height,
                        )
                    )
                    continue

            width: int | None = None
            height: int | None = None
            output_bytes = 0
            reservation: AssetReservation
            output_staging: Path | None = None
            suffix = Path(source_path).suffix.lower()
            try:
                if isinstance(source_member, _ArxivSourceMember):
                    if suffix == ".pdf":
                        content_type = "image/png"
                        reservation = active_budget.reserve()
                        output_staging = (
                            asset_dir
                            / f".paper-fetch-arxiv-render-{uuid.uuid4().hex}.part"
                        )
                        width, height, output_bytes = (
                            _render_pdf_source_figure_path_to_png(
                                source_member.path,
                                output_staging,
                                reservation=reservation,
                            )
                        )
                    else:
                        content_type = payload_mime_type_from_path(source_member.path)
                        if not content_type.startswith("image/"):
                            raise ValueError("arXiv source figure is not an image")
                        dimensions = image_dimensions_from_path(source_member.path)
                        width, height = (
                            dimensions if dimensions is not None else (None, None)
                        )
                        if width is not None and height is not None:
                            source_member.reservation.validate_pixels(width, height)
                        source_member.reservation.promote_file()
                        reservation = source_member.reservation
                        output_staging = source_member.path
                        output_bytes = source_member.size
                else:
                    if not isinstance(source_body, (bytes, bytearray)):
                        raise ValueError("arXiv source figure body is unavailable")
                    image_payload = _source_figure_image_payload(
                        source_path, bytes(source_body)
                    )
                    if image_payload is None:
                        raise ValueError("arXiv source figure is not an image")
                    image_body, content_type, width, height = image_payload
                    reservation = active_budget.reserve(declared_bytes=len(image_body))
                    if width is not None and height is not None:
                        reservation.validate_pixels(width, height)
                    output_staging = (
                        asset_dir / f".paper-fetch-arxiv-compat-{uuid.uuid4().hex}.part"
                    )
                    _read_bounded_stream(
                        io.BytesIO(image_body),
                        reservation=reservation,
                        destination=output_staging,
                    )
                    output_bytes = len(image_body)
            except AssetBudgetExceeded as exc:
                failure = _arxiv_source_asset_failure(
                    placeholder,
                    source_archive_url,
                    reason=exc.reason_code,
                )
                failure.update(exc.diagnostic)
                asset_failures.append(failure)
                break
            except (OSError, RuntimeError, ValueError) as exc:
                asset_failures.append(
                    _arxiv_source_asset_failure(
                        placeholder,
                        f"{source_archive_url}#{urllib.parse.quote(source_path, safe='/._-')}",
                        reason="arxiv_source_figure_not_image",
                        message=str(exc),
                    )
                )
                continue

            output_path = _unique_source_asset_path(
                asset_dir,
                source_path=source_path,
                content_type=content_type,
                used_names=used_names,
            )
            store = (
                runtime_context.artifact_store
                if runtime_context is not None
                and isinstance(runtime_context.artifact_store, ArtifactStore)
                else ArtifactStore.from_download_dir(output_dir)
            )
            try:
                assert output_staging is not None
                with reservation.commit_critical_section():
                    saved_path = str(
                        store.publish_staged_file(output_staging, output_path)
                    )
                    reservation.unregister_staging(output_staging)
                    reservation.commit()
            except BaseException:
                reservation.rollback()
                raise
            finally:
                if suffix == ".pdf" and isinstance(source_member, _ArxivSourceMember):
                    source_member.cleanup()
            if isinstance(source_member, _ArxivSourceMember):
                published_members[id(source_member)] = (
                    saved_path,
                    content_type,
                    output_bytes,
                    width,
                    height,
                )
            downloaded_assets.append(
                _arxiv_source_downloaded_asset(
                    placeholder,
                    arxiv_id=arxiv_id,
                    source_archive_url=source_archive_url,
                    source_path=source_path,
                    content_type=content_type,
                    saved_path=saved_path,
                    output_bytes=output_bytes,
                    width=width,
                    height=height,
                )
            )
    finally:
        _cleanup_arxiv_source_members(files)
    return {
        "assets": downloaded_assets,
        "asset_failures": [*asset_failures, *rejected],
    }


def inline_arxiv_source_assets_in_markdown(
    markdown_text: str,
    assets: Sequence[Mapping[str, Any]] | None,
) -> str:
    if not markdown_text or not assets:
        return markdown_text

    source_assets_by_heading: dict[str, list[Mapping[str, Any]]] = {}
    heading_order: list[str] = []
    for asset in assets:
        if normalize_text(str(asset.get("download_tier") or "")) != "arxiv_source":
            continue
        heading = normalize_text(str(asset.get("heading") or ""))
        inline_url = normalize_text(str(asset.get("url") or ""))
        if not heading or not inline_url or inline_url in markdown_text:
            continue
        if heading not in source_assets_by_heading:
            source_assets_by_heading[heading] = []
            heading_order.append(heading)
        source_assets_by_heading[heading].append(asset)

    rendered = markdown_text
    for heading in heading_order:
        image_lines: list[str] = []
        for asset in source_assets_by_heading[heading]:
            inline_url = normalize_text(str(asset.get("url") or ""))
            alt = normalize_text(str(asset.get("heading") or heading)) or "Figure"
            if inline_url:
                image_lines.append(render_markdown_image("figure", alt, inline_url))
        if not image_lines:
            continue
        caption_pattern = re.compile(
            rf"(?m)^(?P<caption>\*\*{re.escape(heading)}[.:]?\*\*.*)$"
        )
        rendered, count = caption_pattern.subn(
            "\n".join(image_lines) + "\n\n" + r"\g<caption>",
            rendered,
            count=1,
        )
        if count:
            continue
    return rendered


def _arxiv_parent_figures(node: Any, article: Any) -> list[Any]:
    figures: list[Any] = []
    current = getattr(node, "parent", None)
    while isinstance(current, Tag) and current is not article:
        if current.name == "figure":
            figures.append(current)
        current = getattr(current, "parent", None)
    return figures


def _arxiv_inline_figure_for_image(image: Any, article: Any) -> Any:
    if not isinstance(image, Tag):
        return None
    figures = _arxiv_parent_figures(image, article)
    if not figures:
        return None
    if any(not _is_arxiv_inline_figure_container(figure) for figure in figures):
        return None
    return figures[0]


def _arxiv_srcset_url_candidates(raw_value: Any) -> list[str]:
    raw = normalize_text(str(raw_value or ""))
    if not raw:
        return []
    candidates: list[str] = []
    for item in raw.split(","):
        candidate = normalize_text(item).split(" ", 1)[0]
        if candidate:
            candidates.append(candidate)
    return candidates


def _arxiv_url_reference_candidates(raw_value: Any, source_url: str = "") -> set[str]:
    raw = normalize_text(str(raw_value or "")).strip("<>").replace("\\", "/")
    if not raw:
        return set()
    values = [raw]
    if source_url:
        values.append(urllib.parse.urljoin(source_url, raw))
    candidates: set[str] = set()
    for value in values:
        normalized = normalize_text(value).strip("<>").replace("\\", "/")
        if not normalized:
            continue
        parsed = urllib.parse.urlsplit(normalized)
        path = parsed.path or normalized
        for candidate in (
            normalized,
            urllib.parse.unquote(normalized),
            path,
            urllib.parse.unquote(path),
        ):
            cleaned = normalize_text(candidate).replace("\\", "/").strip()
            if not cleaned:
                continue
            candidates.add(cleaned)
            candidates.add(cleaned.lstrip("/"))
            basename = cleaned.rstrip("/").rsplit("/", 1)[-1]
            if basename:
                candidates.add(basename)
    return candidates


def _arxiv_url_candidate_sets_match(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    for left_item in left:
        for right_item in right:
            if left_item.endswith(f"/{right_item}") or right_item.endswith(
                f"/{left_item}"
            ):
                return True
    return False


def _arxiv_image_url_candidates(image: Any, source_url: str) -> set[str]:
    if not isinstance(image, Tag):
        return set()
    candidates: set[str] = set()
    for attr in ("src", "data-src", "data-lazy-src"):
        candidates |= _arxiv_url_reference_candidates(image.get(attr), source_url)
    for attr in ("srcset", "data-srcset"):
        for srcset_url in _arxiv_srcset_url_candidates(image.get(attr)):
            candidates |= _arxiv_url_reference_candidates(srcset_url, source_url)

    picture = image.find_parent("picture")
    if isinstance(picture, Tag):
        for source in picture.find_all("source"):
            if not isinstance(source, Tag):
                continue
            for attr in ("src", "data-src"):
                candidates |= _arxiv_url_reference_candidates(
                    source.get(attr), source_url
                )
            for attr in ("srcset", "data-srcset"):
                for srcset_url in _arxiv_srcset_url_candidates(source.get(attr)):
                    candidates |= _arxiv_url_reference_candidates(
                        srcset_url, source_url
                    )

    anchor = image.find_parent("a", href=True)
    if isinstance(anchor, Tag):
        candidates |= _arxiv_url_reference_candidates(anchor.get("href"), source_url)
    return candidates


def _arxiv_inline_asset_url(asset: Mapping[str, Any]) -> str:
    for field in (
        "url",
        "full_size_url",
        "preview_url",
        "download_url",
        "original_url",
        "link",
    ):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return ""


def _arxiv_inline_asset_alt(asset: Mapping[str, Any]) -> str:
    return (
        normalize_text(str(asset.get("heading") or ""))
        or _arxiv_figure_label_from_dom_id(asset.get("image_id"))
        or _arxiv_figure_label_from_dom_id(asset.get("dom_id"))
        or "Figure"
    )


def _arxiv_asset_order(asset: Mapping[str, Any]) -> int | None:
    raw_value = normalize_text(str(asset.get("asset_order") or ""))
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        return None
    return value if value >= 0 else None


def _arxiv_inline_images_for_figure(figure: Any, article: Any) -> list[Any]:
    if not isinstance(figure, Tag):
        return []
    images: list[Any] = []
    for image in figure.find_all("img"):
        if not isinstance(image, Tag):
            continue
        if _arxiv_inline_figure_for_image(image, article) is None:
            continue
        if figure not in _arxiv_parent_figures(image, article):
            continue
        images.append(image)
    return images


def _annotate_arxiv_inline_figure_images(
    article: Any,
    extracted_assets: Sequence[Mapping[str, Any]],
    source_url: str,
) -> dict[str, int]:
    if not isinstance(article, Tag):
        return {
            "inline_figure_image_count": 0,
            "inline_figure_asset_match_count": 0,
            "inline_figure_asset_miss_count": len(extracted_assets),
        }

    figure_by_id: dict[str, Any] = {}
    for figure in article.find_all("figure"):
        if not _is_arxiv_inline_figure_container(figure):
            continue
        figure_id = normalize_text(str(figure.get("id") or ""))
        if figure_id and figure_id not in figure_by_id:
            figure_by_id[figure_id] = figure

    eligible_images: list[Any] = []
    image_by_id: dict[str, Any] = {}
    image_url_candidates: dict[int, set[str]] = {}
    for image in article.find_all("img"):
        if (
            not isinstance(image, Tag)
            or _arxiv_inline_figure_for_image(image, article) is None
        ):
            continue
        eligible_images.append(image)
        image_id = normalize_text(str(image.get("id") or ""))
        if image_id and image_id not in image_by_id:
            image_by_id[image_id] = image
        image_url_candidates[id(image)] = _arxiv_image_url_candidates(image, source_url)

    consumed_image_ids: set[int] = set()
    match_count = 0
    miss_count = 0

    for asset in extracted_assets:
        inline_url = _arxiv_inline_asset_url(asset)
        if not inline_url:
            miss_count += 1
            continue

        matched_image = None
        image_id = normalize_text(str(asset.get("image_id") or ""))
        if image_id:
            candidate = image_by_id.get(image_id)
            if candidate is not None and id(candidate) not in consumed_image_ids:
                matched_image = candidate

        if matched_image is None:
            dom_id = normalize_text(str(asset.get("dom_id") or ""))
            order = _arxiv_asset_order(asset)
            figure = figure_by_id.get(dom_id) if dom_id else None
            figure_images = (
                _arxiv_inline_images_for_figure(figure, article)
                if figure is not None
                else []
            )
            if order is not None and order < len(figure_images):
                candidate = figure_images[order]
                if id(candidate) not in consumed_image_ids:
                    matched_image = candidate

        if matched_image is None:
            asset_candidates = set()
            for candidate_url in _asset_candidate_urls(asset):
                asset_candidates |= _arxiv_url_reference_candidates(
                    candidate_url, source_url
                )
            for image in eligible_images:
                if id(image) in consumed_image_ids:
                    continue
                if _arxiv_url_candidate_sets_match(
                    asset_candidates,
                    image_url_candidates.get(id(image), set()),
                ):
                    matched_image = image
                    break

        if matched_image is None:
            miss_count += 1
            continue

        matched_image[INLINE_FIGURE_SRC_ATTR] = inline_url
        matched_image[INLINE_FIGURE_ALT_ATTR] = _arxiv_inline_asset_alt(asset)
        consumed_image_ids.add(id(matched_image))
        match_count += 1

    return {
        "inline_figure_image_count": match_count,
        "inline_figure_asset_match_count": match_count,
        "inline_figure_asset_miss_count": miss_count,
    }
