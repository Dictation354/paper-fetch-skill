"""Versioned v8 fetch-envelope sidecar cache with superset variant reuse."""

from __future__ import annotations

import glob
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..acquisition import PDF_RENDER_REVISION, is_pdf_article
from ..artifacts import ArtifactStore
from ..capability_scope import (
    PUBLIC_CAPABILITY_SCOPE,
    UNCACHEABLE_CAPABILITY_SCOPE,
)
from ..manifest import build_manifest_request_fingerprint
from ..models import (
    EXTRACTION_REVISION,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    ArticleModel,
    Asset,
    FetchEnvelope,
    Metadata,
)
from ..models.codec import (
    article_from_payload,
    dedupe_quality_flags,
    envelope_from_payload,
    metadata_from_payload,
    quality_from_payload,
    trace_from_payload,
)
from ..publisher_identity import extract_doi, nature_doi_from_article_url, normalize_doi
from ..runtime import RuntimeContext
from ..utils import normalize_text, sanitize_filename
from ..workflow.acceptance import (
    FetchAcceptanceStatus,
    IdentityAcceptanceStatus,
    OutputAcceptanceStatus,
    ProvenanceAcceptanceStatus,
    evaluate_fetch_acceptance,
)
from ..workflow.types import PaperFetchFailure, effective_asset_profile
from ._scoped_fs import (
    _scoped_file,
    cache_file_lock,
    fetch_envelope_lock_path,
    read_scoped_file,
)
from .requests import FetchPaperRequest

FETCH_ENVELOPE_SIDECAR_VERSION = 8
FETCH_ENVELOPE_EXTRACTION_REVISION = EXTRACTION_REVISION
PUBLIC_CREDENTIAL_SCOPE = PUBLIC_CAPABILITY_SCOPE
_HEX_DIGITS = frozenset("0123456789abcdef")
_SIDECAR_SUFFIX = ".fetch-envelope.json"


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX_DIGITS for char in value)


def fetch_envelope_variant_path(
    download_dir: Path,
    doi: str,
    request_fingerprint: str,
) -> Path:
    normalized_doi = normalize_doi(doi) or normalize_text(doi)
    fingerprint = normalize_text(request_fingerprint).lower()
    if not _is_sha256_hex(fingerprint):
        raise ValueError("request_fingerprint must be a lowercase SHA-256 digest")
    return download_dir / (
        f"{sanitize_filename(normalized_doi)}.{fingerprint}{_SIDECAR_SUFFIX}"
    )


def request_cache_payload(request: FetchPaperRequest) -> dict[str, Any]:
    return {
        "target": request.target,
        "modes": sorted(request.requested_modes()),
        "strategy": request.strategy.cache_request_payload(),
        "include_refs": request.include_refs,
        "max_tokens": request.max_tokens,
    }


def cache_request_fingerprint(
    doi: str,
    request_payload: Mapping[str, Any],
    *,
    credential_scope: str = PUBLIC_CREDENTIAL_SCOPE,
) -> str:
    """Return the shared manifest fingerprint for cache request semantics."""

    return build_manifest_request_fingerprint(
        {
            "query": doi or "<invalid-doi>",
            "parameters": {
                **dict(request_payload),
                "credential_scope": normalize_text(credential_scope)
                or PUBLIC_CREDENTIAL_SCOPE,
            },
        }
    )


def _request_needs_article_for_assets(
    request: FetchPaperRequest,
    *,
    source_name: str | None,
) -> bool:
    return (
        request.target == "paper"
        and not request.save_markdown
        and effective_asset_profile(
            request.strategy.asset_profile,
            source_name=source_name,
        )
        in {"body", "all"}
    )


def payload_from_envelope(
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    retain_article_for_assets: bool = False,
) -> dict[str, Any]:
    payload = envelope.to_dict()
    if "article" not in request.requested_modes() and not retain_article_for_assets:
        payload["article"] = None
    return payload


def cached_request_matches(
    cached_request: Mapping[str, Any],
    request: FetchPaperRequest,
) -> bool:
    if cached_request.get("target") != request.target:
        return False
    raw_modes = cached_request.get("modes")
    if not isinstance(raw_modes, list) or any(
        not isinstance(item, str) for item in raw_modes
    ):
        return False
    if not request.requested_modes().issubset(set(raw_modes)):
        return False
    if cached_request.get("strategy") != request.strategy.cache_request_payload():
        return False
    if cached_request.get("include_refs") != request.include_refs:
        return False
    max_tokens = cached_request.get("max_tokens")
    if isinstance(max_tokens, bool):
        return False
    return max_tokens == request.max_tokens


def cached_payload_satisfies_request(
    payload: Mapping[str, Any], request: FetchPaperRequest
) -> bool:
    if payload.get("target") != request.target:
        return False
    quality = payload.get("quality")
    if not isinstance(quality, Mapping):
        return False
    has_fulltext = quality.get("has_fulltext")
    content_kind = quality.get("content_kind")
    has_abstract = quality.get("has_abstract")
    if (
        not isinstance(has_fulltext, bool)
        or not isinstance(has_abstract, bool)
        or not isinstance(content_kind, str)
        or content_kind not in {"fulltext", "abstract_only", "metadata_only"}
        or has_fulltext != (content_kind == "fulltext")
        or (content_kind == "abstract_only" and not has_abstract)
    ):
        return False
    source = payload.get("source")
    if not isinstance(source, str):
        return False
    if request.target == "supplementary":
        materials = payload.get("supplementary")
        return bool(
            isinstance(materials, Mapping)
            and materials.get("discovery_complete")
            and materials.get("identity_verified")
            and not materials.get("asset_failures")
            and (
                "markdown" not in request.requested_modes()
                or payload.get("markdown") is not None
            )
            and (
                "metadata" not in request.requested_modes()
                or payload.get("metadata") is not None
            )
        )
    requested_modes = request.requested_modes()
    if "article" in requested_modes and payload.get("article") is None:
        return False
    if (
        _request_needs_article_for_assets(
            request,
            source_name=normalize_text(source) or None,
        )
        and payload.get("article") is None
    ):
        return False
    if "markdown" in requested_modes and payload.get("markdown") is None:
        return False
    if "metadata" in requested_modes and payload.get("metadata") is None:
        return False
    return True


def _metadata_has_useful_content(metadata: Metadata | None) -> bool:
    if metadata is None:
        return False
    return bool(
        normalize_text(metadata.title)
        or normalize_text(metadata.abstract)
        or metadata.authors
        or normalize_text(metadata.journal)
        or bool(metadata.publication_dates)
    )


def cached_envelope_satisfies_request(
    envelope: FetchEnvelope,
    payload: Mapping[str, Any],
    request: FetchPaperRequest,
    *,
    expected_doi: str,
) -> bool:
    """Apply structural, identity, semantic, and acceptance gates before reuse."""

    if not cached_payload_satisfies_request(payload, request):
        return False
    normalized_expected_doi = normalize_doi(expected_doi)
    if not normalized_expected_doi:
        return False
    if normalize_doi(envelope.doi or "") != normalized_expected_doi:
        return False
    if not normalize_text(envelope.source) or envelope.acquisition is None:
        return False
    if envelope.quality.has_fulltext != (envelope.quality.content_kind == "fulltext"):
        return False

    if request.target == "supplementary":
        result = envelope.supplementary
        try:
            acceptance = evaluate_fetch_acceptance(
                envelope,
                asset_profile="all",
                requested_outputs=request.requested_modes(),
                expected_doi=normalized_expected_doi,
            )
        except (ValueError, AssertionError):
            return False
        return bool(
            acceptance.provenance.status == ProvenanceAcceptanceStatus.COMPLETE
            and acceptance.output.status == OutputAcceptanceStatus.COMPLETE
            and result
            and result.discovery_complete
            and result.identity_verified
            and not result.asset_failures
            and all(asset.get("path") for asset in result.assets)
        )
    requested_modes = request.requested_modes()
    if "markdown" in requested_modes and not normalize_text(envelope.markdown):
        return False
    if "metadata" in requested_modes:
        raw_metadata = payload.get("metadata")
        if (
            not isinstance(raw_metadata, Mapping)
            or not raw_metadata
            or not _metadata_has_useful_content(envelope.metadata)
        ):
            return False
    if "article" in requested_modes:
        raw_article = payload.get("article")
        article = envelope.article
        if not isinstance(raw_article, Mapping) or not raw_article or article is None:
            return False
        if article.doi and normalize_doi(article.doi) != normalized_expected_doi:
            return False
        if not (
            _metadata_has_useful_content(article.metadata)
            or article.sections
            or article.references
        ):
            return False

    try:
        acceptance = evaluate_fetch_acceptance(
            envelope,
            asset_profile=effective_asset_profile(
                request.strategy.asset_profile,
                source_name=envelope.source,
            ),
            require_local_body_assets=request.strategy.require_local_body_assets,
            require_full_size_body_assets=request.strategy.require_full_size_body_assets,
            requested_outputs=requested_modes,
            expected_doi=normalized_expected_doi,
        )
    except Exception:
        return False
    return (
        acceptance.identity.status == IdentityAcceptanceStatus.RESOLVED
        and acceptance.fetch.status == FetchAcceptanceStatus.OK
        and acceptance.output.status == OutputAcceptanceStatus.COMPLETE
        and acceptance.provenance.status == ProvenanceAcceptanceStatus.COMPLETE
    )


def _asset_integrity(
    article: ArticleModel, asset: Asset
) -> tuple[int | None, str | None]:
    expected_size = asset.downloaded_bytes
    expected_hash: str | None = None
    asset_path = normalize_text(asset.path)
    for diagnostic in article.quality.asset_summary.diagnostics:
        if normalize_text(diagnostic.path) != asset_path:
            continue
        if diagnostic.byte_count is not None:
            expected_size = diagnostic.byte_count
        expected_hash = normalize_text(diagnostic.sha256) or None
        break
    return expected_size, expected_hash


def cached_envelope_assets_are_scoped(
    envelope: FetchEnvelope, download_dir: Path
) -> bool:
    if envelope.target == "supplementary":
        if envelope.supplementary is None:
            return False
        for material in envelope.supplementary.assets:
            if not material.get("path"):
                continue
            opened = read_scoped_file(
                download_dir,
                material["path"],
                expected_size=material.get("downloaded_bytes"),
                expected_sha256=material.get("sha256"),
            )
            if opened is None:
                return False
            material["path"] = str(opened[0])
        return True
    article = envelope.article
    if article is None:
        return True
    for asset in article.assets:
        path_text = normalize_text(asset.path)
        if path_text:
            expected_size, expected_hash = _asset_integrity(article, asset)
            opened = read_scoped_file(
                download_dir,
                path_text,
                expected_size=expected_size,
                expected_sha256=expected_hash,
            )
            if opened is None:
                return False
            asset.path = str(opened[0])
        source_path = normalize_text(asset.source_path)
        if source_path and _scoped_file(download_dir, source_path) is None:
            return False
    return True


def mark_envelope_cached_with_current_revision(envelope: FetchEnvelope) -> None:
    envelope.quality.flags = dedupe_quality_flags(
        [*envelope.quality.flags, QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION]
    )
    envelope.quality.extraction_revision = FETCH_ENVELOPE_EXTRACTION_REVISION


class FetchCache:
    """Single-sidecar v8 cache with lightweight header filtering and superset reuse."""

    def __init__(
        self,
        download_dir: Path | None,
        *,
        artifact_store: ArtifactStore | None = None,
        credential_scope: str = PUBLIC_CREDENTIAL_SCOPE,
        read_credential_scopes: Sequence[str] | None = None,
    ) -> None:
        self._artifact_store = artifact_store or ArtifactStore.from_download_dir(
            download_dir
        )
        self.download_dir = self._artifact_store.download_dir
        self.credential_scope = (
            normalize_text(credential_scope) or PUBLIC_CREDENTIAL_SCOPE
        )
        self.read_credential_scopes: tuple[str, ...]
        if self.credential_scope in {
            PUBLIC_CREDENTIAL_SCOPE,
            UNCACHEABLE_CAPABILITY_SCOPE,
        }:
            self.read_credential_scopes = (PUBLIC_CREDENTIAL_SCOPE,)
        else:
            requested_scopes = read_credential_scopes or (self.credential_scope,)
            normalized_scopes = [
                normalize_text(scope) or PUBLIC_CREDENTIAL_SCOPE
                for scope in requested_scopes
            ]
            # A private reader may read only its exact scope and then public. It
            # cannot move laterally into a different private capability scope.
            self.read_credential_scopes = (
                (self.credential_scope, PUBLIC_CREDENTIAL_SCOPE)
                if self.credential_scope in normalized_scopes
                else (PUBLIC_CREDENTIAL_SCOPE,)
            )

    def _candidate_sidecar_paths(
        self,
        doi: str,
        request: FetchPaperRequest,
    ) -> list[Path]:
        if (
            self.download_dir is None
            or self.credential_scope == UNCACHEABLE_CAPABILITY_SCOPE
        ):
            return []
        req_payload = request_cache_payload(request)
        exact_paths = [
            fetch_envelope_variant_path(
                self.download_dir,
                doi,
                cache_request_fingerprint(doi, req_payload, credential_scope=scope),
            )
            for scope in self.read_credential_scopes
        ]
        prefix = f"{sanitize_filename(normalize_doi(doi) or normalize_text(doi))}."
        discovered: list[tuple[int, str, Path]] = []
        for candidate in self.download_dir.glob(
            f"{glob.escape(prefix[:-1])}.*{_SIDECAR_SUFFIX}"
        ):
            middle = candidate.name.removeprefix(prefix).removesuffix(_SIDECAR_SUFFIX)
            if not _is_sha256_hex(middle):
                continue
            try:
                mtime_ns = candidate.stat().st_mtime_ns
            except OSError:
                continue
            discovered.append((-mtime_ns, candidate.name, candidate))
        discovered.sort()
        return list(dict.fromkeys([*exact_paths, *(item[2] for item in discovered)]))

    def _load_matching_sidecar(
        self,
        doi: str,
        request: FetchPaperRequest,
        path: Path,
    ) -> FetchEnvelope | None:
        assert self.download_dir is not None
        opened = read_scoped_file(self.download_dir, str(path))
        if opened is None:
            return None
        try:
            raw_sidecar = json.loads(opened[1].decode("utf-8"))
        except (RecursionError, ValueError):
            return None
        if not isinstance(raw_sidecar, Mapping):
            return None

        # Lightweight header gate: reject incompatible versions, revisions,
        # scopes, or non-superset requests before deserializing the body.
        version = raw_sidecar.get("version")
        extraction_revision = raw_sidecar.get("extraction_revision")
        if (
            type(version) is not int
            or version != FETCH_ENVELOPE_SIDECAR_VERSION
            or type(extraction_revision) is not int
            or extraction_revision != FETCH_ENVELOPE_EXTRACTION_REVISION
        ):
            return None
        raw_scope = raw_sidecar.get("credential_scope")
        if raw_scope is not None and not isinstance(raw_scope, str):
            return None
        cached_scope = normalize_text(raw_scope) or PUBLIC_CREDENTIAL_SCOPE
        if cached_scope not in self.read_credential_scopes:
            return None
        cached_request = raw_sidecar.get("request")
        payload = raw_sidecar.get("payload")
        if not isinstance(cached_request, Mapping) or not isinstance(payload, Mapping):
            return None
        if not cached_request_matches(cached_request, request):
            return None
        try:
            expected_fp = cache_request_fingerprint(
                doi, cached_request, credential_scope=cached_scope
            )
        except (TypeError, ValueError):
            return None
        if raw_sidecar.get("request_fingerprint") != expected_fp:
            return None
        if normalize_doi(str(payload.get("doi") or "")) != doi:
            return None
        if not cached_payload_satisfies_request(payload, request):
            return None

        try:
            envelope = envelope_from_payload(payload)
        except Exception:
            return None
        if (
            is_pdf_article(envelope)
            and raw_sidecar.get("pdf_render_revision") != PDF_RENDER_REVISION
        ):
            return None
        if not cached_envelope_assets_are_scoped(envelope, self.download_dir):
            return None
        if not cached_envelope_satisfies_request(
            envelope,
            payload,
            request,
            expected_doi=doi,
        ):
            return None

        requested_modes = request.requested_modes()
        if "article" not in requested_modes:
            envelope.article = None
        if "markdown" not in requested_modes:
            envelope.markdown = None
        if "metadata" not in requested_modes:
            envelope.metadata = None
        mark_envelope_cached_with_current_revision(envelope)
        return envelope

    def load_fetch_envelope(
        self,
        request: FetchPaperRequest,
        *,
        resolve_paper_fn: Callable[..., Any],
        context: RuntimeContext,
    ) -> FetchEnvelope | None:
        if (
            not request.prefer_cache
            or self.download_dir is None
            or self.credential_scope == UNCACHEABLE_CAPABILITY_SCOPE
        ):
            return None
        doi = normalize_doi(
            nature_doi_from_article_url(request.query) or extract_doi(request.query)
        )
        if not doi:
            resolved = resolve_paper_fn(request.query, context=context)
            if resolved.candidates and not resolved.doi:
                raise PaperFetchFailure(
                    "ambiguous",
                    "Query resolution is ambiguous; choose one of the DOI candidates.",
                    candidates=resolved.candidates,
                )
            doi = normalize_doi(normalize_text(resolved.doi))
        if not doi or not self.download_dir.exists():
            return None

        with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
            for candidate_path in self._candidate_sidecar_paths(doi, request):
                if not candidate_path.exists():
                    continue
                envelope = self._load_matching_sidecar(doi, request, candidate_path)
                if envelope is not None:
                    return envelope
        return None

    def write_fetch_envelope(
        self,
        envelope: FetchEnvelope,
        request: FetchPaperRequest,
        *,
        commit_guard: Callable[[], None] | None = None,
    ) -> None:
        if (
            self.download_dir is None
            or self.credential_scope == UNCACHEABLE_CAPABILITY_SCOPE
        ):
            return
        doi = normalize_doi(normalize_text(envelope.doi))
        if not doi:
            return
        request_payload = request_cache_payload(request)
        request_fingerprint = cache_request_fingerprint(
            doi,
            request_payload,
            credential_scope=self.credential_scope,
        )
        variant_path = fetch_envelope_variant_path(
            self.download_dir,
            doi,
            request_fingerprint,
        )
        payload: dict[str, Any] = {
            "version": FETCH_ENVELOPE_SIDECAR_VERSION,
            "extraction_revision": FETCH_ENVELOPE_EXTRACTION_REVISION,
            "request_fingerprint": request_fingerprint,
            "credential_scope": self.credential_scope,
            "request": request_payload,
            "payload": payload_from_envelope(
                envelope,
                request,
                retain_article_for_assets=_request_needs_article_for_assets(
                    request,
                    source_name=envelope.source,
                ),
            ),
        }
        if is_pdf_article(envelope):
            payload["pdf_render_revision"] = PDF_RENDER_REVISION
        with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
            self._artifact_store.write_json_file(
                variant_path,
                payload,
                commit_guard=commit_guard,
            )
        if commit_guard is not None:
            commit_guard()


__all__ = [
    "FETCH_ENVELOPE_EXTRACTION_REVISION",
    "FETCH_ENVELOPE_SIDECAR_VERSION",
    "PUBLIC_CREDENTIAL_SCOPE",
    "FetchCache",
    "article_from_payload",
    "cache_request_fingerprint",
    "cached_envelope_assets_are_scoped",
    "cached_envelope_satisfies_request",
    "cached_payload_satisfies_request",
    "cached_request_matches",
    "dedupe_quality_flags",
    "envelope_from_payload",
    "fetch_envelope_variant_path",
    "mark_envelope_cached_with_current_revision",
    "metadata_from_payload",
    "payload_from_envelope",
    "quality_from_payload",
    "request_cache_payload",
    "trace_from_payload",
]
