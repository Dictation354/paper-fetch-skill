"""Typed asset download kinds for HTML assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from collections.abc import Callable, Mapping, Sequence

from ....utils import normalize_text
from ...image_payloads import image_mime_type_from_bytes
from ....image_tools import source_image_format_from_payload
from ..shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)
from .dom import looks_like_full_size_asset_url, supplementary_response_block_reason


@dataclass(frozen=True)
class AssetDownloadKind:
    name: Literal["figure", "supplementary"]
    candidate_url_resolver: Callable[[Mapping[str, Any]], list[str]]
    upgrade_targets: Callable[[str, Mapping[str, Any]], list[str]] | None
    accepts_response: Callable[[str | None, bytes], bool]
    response_block_reason: Callable[[str | None, bytes], str | None]
    failure_template: Callable[..., dict[str, Any]]
    output_subdir: Callable[[Mapping[str, Any]], Path | None]
    file_document_fetcher_kind: Literal["image", "file"]
    request_headers: Callable[[Mapping[str, str] | None, str, Mapping[str, Any] | None], dict[str, str]]


def _dedupe_asset_urls(asset: Mapping[str, Any], fields: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for field in fields:
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def requires_image_payload(asset: Mapping[str, Any]) -> bool:
    kind = normalize_text(str(asset.get("kind") or "")).lower()
    section = normalize_text(str(asset.get("section") or "")).lower()
    return kind in {"figure", "table", "formula"} and section != "supplementary"


def is_preview_candidate(candidate_url: str, *, preview_url: str, full_size_url: str) -> bool:
    normalized_candidate = normalize_text(candidate_url)
    if not normalized_candidate or not preview_url:
        return False
    return (
        normalized_candidate == preview_url
        and normalized_candidate != full_size_url
        and not looks_like_full_size_asset_url(normalized_candidate.lower())
    )


def resolved_full_size_url(
    asset: Mapping[str, Any],
    *,
    preview_url: str,
    candidate_urls: list[str],
) -> str:
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    if direct_full_size_url:
        return direct_full_size_url
    primary_url = normalize_text(str(asset.get("url") or asset.get("original_url") or asset.get("link") or ""))
    if primary_url and primary_url != preview_url and looks_like_full_size_asset_url(primary_url.lower()):
        return primary_url
    for candidate_url in candidate_urls:
        candidate = normalize_text(candidate_url)
        if candidate and candidate != preview_url:
            return candidate
    return ""


def active_seed_urls(
    seed_urls: Sequence[str] | None,
    browser_context_seed: Mapping[str, Any] | None,
) -> list[str]:
    return [
        normalized
        for normalized in [
            *[normalize_text(item) for item in seed_urls or []],
            normalize_text(str((browser_context_seed or {}).get("browser_final_url") or "")),
        ]
        if normalized
    ]


def failure_from_document_fetch(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate_url: str,
    fetch_failure: Mapping[str, Any],
) -> dict[str, Any]:
    if kind.name == "supplementary":
        return kind.failure_template(
            asset,
            candidate_url,
            reason=normalize_text(str(fetch_failure.get("reason") or "")) or "file_fetch_error",
            status=fetch_failure.get("status") if isinstance(fetch_failure.get("status"), int) else None,
            content_type=normalize_text(str(fetch_failure.get("content_type") or "")),
            final_url=normalize_text(str(fetch_failure.get("final_url") or "")),
            extra=fetch_failure,
        )
    return kind.failure_template(
        asset,
        candidate_url,
        reason=normalize_text(str(fetch_failure.get("reason") or "")) or "image_fetch_error",
        status=fetch_failure.get("status") if isinstance(fetch_failure.get("status"), int) else None,
        content_type=normalize_text(str(fetch_failure.get("content_type") or "")),
        final_url=normalize_text(str(fetch_failure.get("final_url") or "")),
        title_snippet=normalize_text(str(fetch_failure.get("title_snippet") or "")),
        body_snippet=normalize_text(str(fetch_failure.get("body_snippet") or "")),
        recovery_attempts=(
            list(fetch_failure.get("recovery_attempts"))
            if isinstance(fetch_failure.get("recovery_attempts"), list)
            else None
        ),
        canvas_error=normalize_text(str(fetch_failure.get("canvas_error") or "")),
        error_type=normalize_text(str(fetch_failure.get("error_type") or fetch_failure.get("exception_type") or "")),
        error_message=normalize_text(str(fetch_failure.get("error_message") or fetch_failure.get("message") or "")),
    )


def _figure_candidate_urls(asset: Mapping[str, Any]) -> list[str]:
    return _dedupe_asset_urls(
        asset,
        (
            "download_url",
            "full_size_url",
            "url",
            "original_url",
            "link",
            "preview_url",
            "figure_page_url",
        ),
    )


def _supplementary_candidate_urls(asset: Mapping[str, Any]) -> list[str]:
    return _dedupe_asset_urls(
        asset,
        (
            "download_url",
            "original_url",
            "link",
            "url",
            "source_url",
            "full_size_url",
            "preview_url",
        ),
    )


def _figure_upgrade_targets(candidate_url: str, asset: Mapping[str, Any]) -> list[str]:
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


def _figure_accepts_response(content_type: str | None, body: bytes) -> bool:
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    if image_mime_type_from_bytes(body):
        return True
    if source_image_format_from_payload(body, content_type=content_type):
        return True
    if normalized_content_type and not normalized_content_type.startswith("image/"):
        return False
    return False


def _figure_response_block_reason(content_type: str | None, body: bytes) -> str | None:
    if _figure_accepts_response(content_type, body):
        return None
    normalized_content_type = normalize_text(content_type)
    return f"Asset candidate did not return image content (content-type: {normalized_content_type or 'unknown'})."


def _supplementary_accepts_response(content_type: str | None, body: bytes) -> bool:
    return bool(body) and not supplementary_response_block_reason(content_type, body)


def _figure_failure_template(
    asset: Mapping[str, Any],
    source_url: str,
    *,
    reason: str,
    status: int | None = None,
    content_type: str | None = None,
    final_url: str | None = None,
    title_snippet: str | None = None,
    body_snippet: str | None = None,
    recovery_attempts: list[dict[str, Any]] | None = None,
    canvas_error: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    error_category: str | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "kind": asset.get("kind", "figure"),
        "heading": asset.get("heading", "Figure"),
        "caption": asset.get("caption", ""),
        "source_url": source_url,
        "reason": reason,
        "section": asset.get("section") or "body",
    }
    if status is not None:
        failure["status"] = status
    if content_type:
        failure["content_type"] = content_type
    if final_url:
        failure["final_url"] = final_url
    if title_snippet:
        failure["title_snippet"] = title_snippet
    if body_snippet:
        failure["body_snippet"] = body_snippet
    if recovery_attempts:
        failure["recovery_attempts"] = list(recovery_attempts)
    if canvas_error:
        failure["canvas_error"] = canvas_error
    if error_type:
        failure["error_type"] = error_type
    if error_message:
        failure["error_message"] = error_message
    if error_category:
        failure["error_category"] = error_category
    return failure


def _supplementary_template(
    asset: Mapping[str, Any],
    source_url: str,
    *,
    reason: str,
    status: int | None = None,
    content_type: str | None = None,
    final_url: str | None = None,
    body: bytes | bytearray | None = None,
    extra: Mapping[str, Any] | None = None,
    **_unused: Any,
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "kind": "supplementary",
        "heading": asset.get("heading") or asset.get("filename_hint") or "Supplementary Material",
        "caption": asset.get("caption", ""),
        "source_url": source_url,
        "reason": reason,
        "section": "supplementary",
    }
    if status is not None:
        failure["status"] = status
    normalized_content_type = normalize_text(content_type)
    if normalized_content_type:
        failure["content_type"] = normalized_content_type
    normalized_final_url = normalize_text(final_url)
    if normalized_final_url:
        failure["final_url"] = normalized_final_url
    title_snippet = _html_title_snippet(body)
    if title_snippet:
        failure["title_snippet"] = title_snippet
    body_snippet = _html_text_snippet(body)
    if body_snippet:
        failure["body_snippet"] = body_snippet
    for key in (
        "asset_type",
        "source_kind",
        "source_ref",
        "filename_hint",
        "attachment_type",
        "object_type",
        "category",
    ):
        value = asset.get(key)
        if value:
            failure[key] = value
    if extra:
        for key, value in extra.items():
            if value not in (None, "", [], {}):
                failure[key] = value
    return failure


def _supplementary_response_block_reason(content_type: str | None, body: bytes) -> str | None:
    if not body:
        return "empty_response_body"
    return supplementary_response_block_reason(content_type, body)


def _source_data_output_subdir(asset: Mapping[str, Any]) -> Path | None:
    if normalize_text(str(asset.get("asset_kind") or "")).lower() == "source_data":
        return Path("source_data")
    return None


def _base_request_headers(
    headers: Mapping[str, str] | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
) -> dict[str, str]:
    request_headers = {"User-Agent": user_agent, "Accept": "*/*"}
    request_headers.update({str(key): str(value) for key, value in (headers or {}).items() if value is not None})
    active_user_agent = normalize_text(str((browser_context_seed or {}).get("browser_user_agent") or ""))
    if active_user_agent:
        request_headers["User-Agent"] = active_user_agent
    elif not normalize_text(request_headers.get("User-Agent")):
        request_headers.pop("User-Agent", None)
    request_headers.setdefault("Accept", "*/*")
    return request_headers


FIGURE_KIND = AssetDownloadKind(
    name="figure",
    candidate_url_resolver=_figure_candidate_urls,
    upgrade_targets=_figure_upgrade_targets,
    accepts_response=_figure_accepts_response,
    response_block_reason=_figure_response_block_reason,
    failure_template=_figure_failure_template,
    output_subdir=lambda _asset: None,
    file_document_fetcher_kind="image",
    request_headers=_base_request_headers,
)

SUPPLEMENTARY_KIND = AssetDownloadKind(
    name="supplementary",
    candidate_url_resolver=_supplementary_candidate_urls,
    upgrade_targets=None,
    accepts_response=_supplementary_accepts_response,
    response_block_reason=_supplementary_response_block_reason,
    failure_template=_supplementary_template,
    output_subdir=_source_data_output_subdir,
    file_document_fetcher_kind="file",
    request_headers=_base_request_headers,
)


__all__ = [
    "FIGURE_KIND",
    "SUPPLEMENTARY_KIND",
    "AssetDownloadKind",
]
