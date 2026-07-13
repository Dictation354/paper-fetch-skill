"""Conservative, filesystem-backed asset authenticity diagnostics."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, cast
from collections.abc import Mapping, Sequence

from ..extraction.image_payloads import (
    image_dimensions_from_path,
    is_placeholder_image_url,
    payload_mime_type_from_path,
)
from ..models.schema import (
    Asset,
    AssetDiagnostic,
    AssetDiagnosticStatus,
    AssetKindSummary,
    AssetLogicalKind,
    AssetProfile,
    AssetQualitySummary,
)
from ..utils import normalize_text

ASSET_SHA256_CHUNK_BYTES = 1024 * 1024
PLACEHOLDER_SUSPECT_MAX_BYTES = 32
PLACEHOLDER_SUSPECT_MAX_DIMENSION = 16
PLACEHOLDER_SUSPECT_MAX_AREA = 16 * 16

_ASSET_KINDS: tuple[AssetLogicalKind, ...] = (
    "figure",
    "formula",
    "table",
    "supplement",
    "decoration",
)
_BODY_ASSET_KINDS = frozenset({"figure", "formula", "table"})
_REMOTE_PREFIXES = ("http://", "https://", "//")
_REMOTE_FIELDS = (
    "url",
    "download_url",
    "original_url",
    "source_url",
    "source_href",
    "full_size_url",
    "preview_url",
)
_PLACEHOLDER_FIELDS = (*_REMOTE_FIELDS, "path", "source_path")
_IDENTITY_FIELDS = (
    "anchor_key",
    "heading",
    "caption",
    "url",
    "download_url",
    "original_url",
    "source_url",
    "path",
)
_FAILURE_MATCH_FIELDS = (
    "anchor_key",
    "url",
    "download_url",
    "original_url",
    "source_url",
    "path",
)

AssetLike = Asset | Mapping[str, Any]


def _field(asset: AssetLike, name: str) -> Any:
    if isinstance(asset, Mapping):
        return asset.get(name)
    return getattr(asset, name, None)


def _text_field(asset: AssetLike, name: str) -> str:
    return normalize_text(str(_field(asset, name) or ""))


def logical_asset_kind(asset: AssetLike) -> AssetLogicalKind:
    """Collapse provider labels into the five manifest-level kinds."""

    kind = _text_field(asset, "kind").lower()
    section = _text_field(asset, "section").lower()
    if kind in {"formula", "equation", "math", "inline_formula"}:
        return "formula"
    if kind in {"table", "table_image"}:
        return "table"
    if kind in {"supplement", "supplementary", "source_data", "attachment"} or (
        section in {"supplement", "supplementary", "source_data"}
    ):
        return "supplement"
    if kind in {"figure", "fig", "image", "graphical_abstract"}:
        return "figure"
    return "decoration"


def _asset_requested(kind: AssetLogicalKind, profile: AssetProfile) -> bool:
    if profile == "none":
        return False
    if profile == "body":
        return kind in _BODY_ASSET_KINDS
    return True


def _local_path(
    asset: AssetLike, base_dir: Path | None
) -> tuple[str | None, Path | None]:
    raw_path = _text_field(asset, "path")
    if not raw_path:
        return None, None
    path = Path(raw_path).expanduser()
    if not path.is_absolute() and base_dir is not None and not path.is_file():
        # Download helpers may return either a process-relative path or a path
        # relative to the archive root. Do not apply a relative archive root
        # twice when the recorded path already exists.
        path = base_dir / path
    return raw_path, path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(ASSET_SHA256_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _is_remote(value: Any) -> bool:
    return normalize_text(str(value or "")).lower().startswith(_REMOTE_PREFIXES)


def _has_remote_link(asset: AssetLike) -> bool:
    return any(_is_remote(_field(asset, field)) for field in _REMOTE_FIELDS)


def _placeholder_url_suspected(asset: AssetLike) -> bool:
    return any(
        is_placeholder_image_url(_text_field(asset, field))
        for field in _PLACEHOLDER_FIELDS
    )


def _dedupe_strings(values: Sequence[Any] | None) -> list[str]:
    return list(
        dict.fromkeys(
            normalized
            for value in values or []
            if (normalized := normalize_text(str(value or "")))
        )
    )


def _asset_provenance(asset: AssetLike) -> list[str]:
    raw = _field(asset, "provenance")
    values = (
        list(raw)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray))
        else []
    )
    if _text_field(asset, "conversion_source_format"):
        values.append("source_converted")
    return _dedupe_strings(values)


def _failure_code(failure: Mapping[str, Any]) -> str | None:
    for field in ("code", "error_category", "reason"):
        code = normalize_text(str(failure.get(field) or "")).lower()
        if code:
            return code
    return None


def _failure_provenance(failure: Mapping[str, Any]) -> list[str]:
    raw = failure.get("provenance")
    values = (
        list(raw)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray))
        else []
    )
    values.append("failure_diagnostic")
    return _dedupe_strings(values)


def _mime_extension_mismatch(path: Path, real_mime: str | None) -> bool:
    if not real_mime or not real_mime.startswith("image/"):
        return False
    suffix_mime = normalize_text(mimetypes.guess_type(path.name)[0]).lower()
    if not suffix_mime or not suffix_mime.startswith("image/"):
        return False
    normalized_real = "image/jpeg" if real_mime == "image/jpg" else real_mime
    normalized_suffix = "image/jpeg" if suffix_mime == "image/jpg" else suffix_mime
    return normalized_real != normalized_suffix


def _identity_key(asset: AssetLike, kind: AssetLogicalKind) -> str:
    for field in _IDENTITY_FIELDS:
        value = _text_field(asset, field).lower()
        if value:
            return f"{kind}:{field}:{value}"
    return f"{kind}:anonymous:{id(asset)}"


def _failure_matches_asset(failure: Mapping[str, Any], asset: AssetLike) -> bool:
    failure_values = {
        normalize_text(str(failure.get(field) or "")).lower()
        for field in _FAILURE_MATCH_FIELDS
        if normalize_text(str(failure.get(field) or ""))
    }
    asset_values = {
        _text_field(asset, field).lower()
        for field in _FAILURE_MATCH_FIELDS
        if _text_field(asset, field)
    }
    if failure_values & asset_values:
        return True
    failure_heading = normalize_text(str(failure.get("heading") or "")).lower()
    return bool(
        failure_heading
        and failure_heading == _text_field(asset, "heading").lower()
        and logical_asset_kind(failure) == logical_asset_kind(asset)
    )


def _diagnose_asset(
    asset: AssetLike,
    *,
    profile: AssetProfile,
    archive_enabled: bool,
    base_dir: Path | None,
) -> tuple[AssetDiagnostic, bool, bool, str]:
    kind = logical_asset_kind(asset)
    requested = _asset_requested(kind, profile)
    raw_path, resolved_path = _local_path(asset, base_dir)
    has_remote = _has_remote_link(asset)
    suspected_reasons: list[str] = []
    if _placeholder_url_suspected(asset):
        suspected_reasons.append("blank_url")

    real_mime: str | None = None
    byte_count: int | None = None
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    path_exists = bool(resolved_path is not None and resolved_path.is_file())
    path_failure_code: str | None = None
    if path_exists and resolved_path is not None:
        try:
            byte_count = resolved_path.stat().st_size
            sha256 = _sha256(resolved_path)
            real_mime = payload_mime_type_from_path(resolved_path) or None
            dimensions = image_dimensions_from_path(resolved_path)
            if dimensions is not None:
                width, height = dimensions
        except OSError:
            path_failure_code = "unreadable_path"
        if byte_count == 0:
            suspected_reasons.append("zero_byte")
        elif byte_count is not None and byte_count < PLACEHOLDER_SUSPECT_MAX_BYTES:
            suspected_reasons.append("tiny_file")
        if kind in _BODY_ASSET_KINDS | {"decoration"} and not (
            real_mime or ""
        ).startswith("image/"):
            suspected_reasons.append("invalid_mime")
        if (
            width is not None
            and height is not None
            and (
                min(width, height) <= PLACEHOLDER_SUSPECT_MAX_DIMENSION
                or width * height <= PLACEHOLDER_SUSPECT_MAX_AREA
            )
        ):
            suspected_reasons.append("tiny_dimensions")
        if real_mime and _mime_extension_mismatch(resolved_path, real_mime):
            suspected_reasons.append("mime_extension_mismatch")
    elif raw_path:
        path_failure_code = "missing_path"

    if not requested:
        # Request policy is authoritative for this run: stale path metadata
        # must not turn profile=none/body exclusions into download failures.
        status: AssetDiagnosticStatus = "not_requested"
    elif path_failure_code == "unreadable_path":
        status = "failed"
    elif path_exists:
        status = "placeholder_suspected" if suspected_reasons else "available"
    elif not archive_enabled and has_remote:
        status = "not_archived"
    elif path_failure_code is not None:
        status = "failed"
    elif suspected_reasons:
        status = "placeholder_suspected"
    elif has_remote:
        status = "failed"
        path_failure_code = "missing_path"
    else:
        # Some logical table/decoration records have no downloadable payload.
        status = "available"

    diagnostic = AssetDiagnostic(
        request_profile=profile,
        kind=kind,
        status=status,
        download_tier=_text_field(asset, "download_tier") or None,
        path=raw_path,
        real_mime=real_mime,
        byte_count=byte_count,
        width=width,
        height=height,
        sha256=sha256,
        failure_code=path_failure_code,
        provenance=_asset_provenance(asset),
        suspected_reasons=_dedupe_strings(suspected_reasons),
    )
    return diagnostic, has_remote, path_exists, _identity_key(asset, kind)


def _apply_duplicate_sha_suspicions(
    rows: list[tuple[AssetLike, AssetDiagnostic, bool, bool, str]],
) -> None:
    by_sha: dict[str, list[tuple[AssetDiagnostic, str]]] = {}
    for _asset, diagnostic, _has_remote, path_exists, identity in rows:
        if (
            path_exists
            and diagnostic.sha256
            and diagnostic.kind in _BODY_ASSET_KINDS
            and diagnostic.status != "failed"
        ):
            by_sha.setdefault(diagnostic.sha256, []).append((diagnostic, identity))
    for duplicates in by_sha.values():
        if len({identity for _diagnostic, identity in duplicates}) <= 1:
            continue
        for diagnostic, _identity in duplicates:
            diagnostic.suspected_reasons = _dedupe_strings(
                [*diagnostic.suspected_reasons, "duplicate_sha256"]
            )
            diagnostic.status = "placeholder_suspected"


def _blank_kind_summaries() -> dict[AssetLogicalKind, AssetKindSummary]:
    return {kind: AssetKindSummary() for kind in _ASSET_KINDS}


def build_asset_quality_summary(
    assets: Sequence[AssetLike] | None,
    *,
    asset_failures: Sequence[Mapping[str, Any]] | None = None,
    asset_profile: AssetProfile,
    archive_enabled: bool,
    base_dir: Path | None = None,
) -> AssetQualitySummary:
    """Audit assets without deleting, rewriting, decoding, or fetching content."""

    rows = [
        (
            asset,
            *(
                _diagnose_asset(
                    asset,
                    profile=asset_profile,
                    archive_enabled=archive_enabled,
                    base_dir=base_dir,
                )
            ),
        )
        for asset in assets or []
    ]

    # The tuple comprehension above expands to asset, diagnostic, remote, local,
    # identity. Keep the precise type visible to static readers.
    typed_rows = cast(list[tuple[AssetLike, AssetDiagnostic, bool, bool, str]], rows)
    if asset_profile != "none" and archive_enabled:
        for failure in asset_failures or []:
            failure_kind = logical_asset_kind(failure)
            if not _asset_requested(failure_kind, asset_profile):
                continue
            matched = next(
                (row for row in typed_rows if _failure_matches_asset(failure, row[0])),
                None,
            )
            code = _failure_code(failure) or "asset_failure"
            if matched is not None:
                matched[1].status = "failed"
                matched[1].failure_code = code
                matched[1].provenance = _dedupe_strings(
                    [*matched[1].provenance, *_failure_provenance(failure)]
                )
                continue
            diagnostic = AssetDiagnostic(
                request_profile=asset_profile,
                kind=failure_kind,
                status="failed",
                download_tier=normalize_text(str(failure.get("download_tier") or ""))
                or None,
                path=normalize_text(str(failure.get("path") or "")) or None,
                failure_code=code,
                provenance=_failure_provenance(failure),
            )
            typed_rows.append(
                (
                    failure,
                    diagnostic,
                    _has_remote_link(failure),
                    False,
                    _identity_key(failure, failure_kind),
                )
            )

    _apply_duplicate_sha_suspicions(typed_rows)
    by_kind = _blank_kind_summaries()
    remote_link_count = 0
    remote_only_count = 0
    local = 0
    for _asset, diagnostic, has_remote, path_exists, _identity in typed_rows:
        counts = by_kind[diagnostic.kind]
        counts.total += 1
        if _asset_requested(diagnostic.kind, diagnostic.request_profile):
            counts.requested += 1
        if has_remote:
            remote_link_count += 1
            if diagnostic.path is None:
                remote_only_count += 1
        if path_exists:
            local += 1
        if diagnostic.status == "failed":
            counts.failed += 1
        elif diagnostic.status == "not_requested":
            counts.not_requested += 1
        elif diagnostic.status == "not_archived":
            counts.not_archived += 1
        if diagnostic.suspected_reasons:
            counts.placeholder_suspected += 1
        if (
            path_exists
            and diagnostic.download_tier == "preview"
            and diagnostic.status != "failed"
        ):
            counts.preview += 1
        elif path_exists and diagnostic.status != "failed":
            counts.full_size += 1

    diagnostics = [row[1] for row in typed_rows]
    return AssetQualitySummary(
        audited=True,
        requested=asset_profile != "none",
        profile=asset_profile,
        total=len(diagnostics),
        local=local,
        full_size=sum(item.full_size for item in by_kind.values()),
        preview=sum(item.preview for item in by_kind.values()),
        failed=sum(item.failed for item in by_kind.values()),
        placeholder_suspected=sum(
            item.placeholder_suspected for item in by_kind.values()
        ),
        not_requested=sum(item.not_requested for item in by_kind.values()),
        not_archived=sum(item.not_archived for item in by_kind.values()),
        remote_link_count=remote_link_count,
        remote_only_count=remote_only_count,
        failure_codes=sorted(
            {
                diagnostic.failure_code
                for diagnostic in diagnostics
                if diagnostic.failure_code
            }
        ),
        by_kind=by_kind,
        diagnostics=diagnostics,
    )


__all__ = [
    "ASSET_SHA256_CHUNK_BYTES",
    "PLACEHOLDER_SUSPECT_MAX_AREA",
    "PLACEHOLDER_SUSPECT_MAX_BYTES",
    "PLACEHOLDER_SUSPECT_MAX_DIMENSION",
    "build_asset_quality_summary",
    "logical_asset_kind",
]
