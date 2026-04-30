"""Provider interfaces, diagnostics, and shared error types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
import time
from typing import Any, Mapping

from ..artifacts import ArtifactStore
from ..http import RequestFailure
from ..models import ArticleModel, AssetProfile
from ..runtime import RuntimeContext
from ..tracing import TraceEvent, source_trail_from_trace, trace_from_markers
from ..utils import empty_asset_results


class ProviderFailure(Exception):
    """Provider-specific failure with a stable category."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        missing_env: list[str] | None = None,
        warnings: list[str] | None = None,
        source_trail: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.missing_env = list(missing_env or [])
        self.warnings = [str(item) for item in (warnings or []) if str(item).strip()]
        self.source_trail = [str(item) for item in (source_trail or []) if str(item).strip()]


@dataclass(frozen=True)
class ProviderContent:
    route_kind: str
    source_url: str
    content_type: str
    body: bytes
    markdown_text: str | None = None
    merged_metadata: dict[str, Any] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    fetcher: str | None = None
    browser_context_seed: dict[str, Any] = field(default_factory=dict)
    suggested_filename: str | None = None
    html_failure_reason: str | None = None
    html_failure_message: str | None = None
    extracted_assets: list[dict[str, Any]] = field(default_factory=list)
    needs_local_copy: bool = False


@dataclass(frozen=True)
class ProviderArtifacts:
    assets: list[dict[str, Any]] = field(default_factory=list)
    asset_failures: list[dict[str, Any]] = field(default_factory=list)
    allow_related_assets: bool = True
    text_only: bool = False
    skip_warning: str | None = None
    skip_trace: list[TraceEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderFetchResult:
    provider: str
    article: ArticleModel
    content: ProviderContent | None = None
    warnings: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    artifacts: ProviderArtifacts = field(default_factory=ProviderArtifacts)


@dataclass
class PreparedFetchResultPayload:
    raw_payload: RawFulltextPayload
    provisional_article: ArticleModel | None = None
    finalize_warnings: list[str] = field(default_factory=list)
    result_warnings: list[str] | None = None
    result_trace: list[TraceEvent] | None = None
    context: dict[str, Any] = field(default_factory=dict)


STRUCTURED_METADATA_KEYS = {
    "route",
    "reason",
    "markdown_text",
    "merged_metadata",
    "availability_diagnostics",
    "extraction",
    "html_fetcher",
    "browser_context_seed",
    "suggested_filename",
    "html_failure_reason",
    "html_failure_message",
    "extracted_assets",
    "warnings",
    "source_trail",
}


def _passthrough_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    legacy = dict(metadata or {})
    return {key: value for key, value in legacy.items() if key not in STRUCTURED_METADATA_KEYS}


@dataclass(init=False)
class RawFulltextPayload:
    provider: str
    source_url: str
    content_type: str
    body: bytes
    content: ProviderContent | None = None
    warnings: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    merged_metadata: dict[str, Any] | None = None
    needs_local_copy: bool = False
    _legacy_metadata: dict[str, Any] = field(default_factory=dict, repr=False)

    def __init__(
        self,
        provider: str,
        source_url: str,
        content_type: str,
        body: bytes,
        *,
        content: ProviderContent | None = None,
        warnings: list[str] | None = None,
        trace: list[TraceEvent] | None = None,
        merged_metadata: Mapping[str, Any] | None = None,
        needs_local_copy: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.provider = provider
        self.source_url = source_url
        self.content_type = content_type
        self.body = body
        self.content = content
        self.warnings = [str(item) for item in (warnings or []) if str(item).strip()]
        self.trace = list(trace or [])
        self.merged_metadata = dict(merged_metadata) if isinstance(merged_metadata, Mapping) else None
        self.needs_local_copy = needs_local_copy
        self._legacy_metadata = _passthrough_metadata(metadata)

    @property
    def metadata(self) -> dict[str, Any]:
        """Legacy read-only compatibility view synthesized from typed payload fields."""

        content = self.content
        payload: dict[str, Any] = dict(self._legacy_metadata)
        if content is not None:
            if content.route_kind:
                payload["route"] = content.route_kind
            if content.reason:
                payload["reason"] = content.reason
            if content.markdown_text is not None:
                payload["markdown_text"] = content.markdown_text
            if content.merged_metadata is not None:
                payload["merged_metadata"] = dict(content.merged_metadata)
            if content.diagnostics:
                payload["availability_diagnostics"] = dict(content.diagnostics.get("availability_diagnostics") or content.diagnostics)
                for key, value in content.diagnostics.items():
                    if key not in {"availability_diagnostics"} and key not in payload:
                        payload[key] = value
            if content.fetcher:
                payload["html_fetcher"] = content.fetcher
            if content.browser_context_seed:
                payload["browser_context_seed"] = dict(content.browser_context_seed)
            if content.suggested_filename:
                payload["suggested_filename"] = content.suggested_filename
            if content.html_failure_reason:
                payload["html_failure_reason"] = content.html_failure_reason
            if content.html_failure_message:
                payload["html_failure_message"] = content.html_failure_message
            if content.extracted_assets:
                payload["extracted_assets"] = list(content.extracted_assets)
        if self.merged_metadata is not None and "merged_metadata" not in payload:
            payload["merged_metadata"] = dict(self.merged_metadata)
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.trace:
            payload["source_trail"] = source_trail_from_trace(self.trace)
        return payload


@dataclass(frozen=True)
class ProviderStatusCheck:
    name: str
    status: str
    message: str
    missing_env: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderStatusResult:
    provider: str
    status: str
    available: bool
    official_provider: bool
    missing_env: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    checks: list[ProviderStatusCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "available": self.available,
            "official_provider": self.official_provider,
            "missing_env": list(self.missing_env),
            "notes": list(self.notes),
            "checks": [check.to_dict() for check in self.checks],
        }


def _dedupe_strings(values: list[str] | tuple[str, ...] | None) -> list[str]:
    deduped: list[str] = []
    for raw_value in values or []:
        value = str(raw_value or "").strip()
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def build_provider_status_check(
    name: str,
    status: str,
    message: str,
    *,
    missing_env: list[str] | tuple[str, ...] | None = None,
    details: Mapping[str, Any] | None = None,
) -> ProviderStatusCheck:
    return ProviderStatusCheck(
        name=name,
        status=status,
        message=message,
        missing_env=_dedupe_strings(list(missing_env or [])),
        details=dict(details or {}),
    )


def provider_status_check_from_failure(
    name: str,
    failure: "ProviderFailure",
    *,
    details: Mapping[str, Any] | None = None,
) -> ProviderStatusCheck:
    status = failure.code if failure.code in {"not_configured", "rate_limited"} else "error"
    merged_details = dict(details or {})
    if failure.retry_after_seconds is not None:
        merged_details["retry_after_seconds"] = failure.retry_after_seconds
    return build_provider_status_check(
        name,
        status,
        failure.message,
        missing_env=failure.missing_env,
        details=merged_details,
    )


def summarize_capability_status(
    provider: str,
    *,
    official_provider: bool,
    checks: list[ProviderStatusCheck],
    notes: list[str] | None = None,
) -> ProviderStatusResult:
    deduped_notes = _dedupe_strings(list(notes or []))
    missing_env: list[str] = []
    ok_checks = 0
    has_error = False
    has_rate_limit = False
    for check in checks:
        if check.status == "ok":
            ok_checks += 1
        elif check.status == "error":
            has_error = True
        elif check.status == "rate_limited":
            has_rate_limit = True
        for name in check.missing_env:
            if name not in missing_env:
                missing_env.append(name)

    available = ok_checks > 0
    if has_error:
        status = "error"
    elif has_rate_limit and ok_checks == 0:
        status = "rate_limited"
    elif checks and all(check.status == "ok" for check in checks):
        status = "ready"
    elif available:
        status = "partial"
    else:
        status = "not_configured"

    return ProviderStatusResult(
        provider=provider,
        status=status,
        available=available,
        official_provider=official_provider,
        missing_env=missing_env,
        notes=deduped_notes,
        checks=list(checks),
    )


def map_request_failure(exc: RequestFailure) -> ProviderFailure:
    if exc.status_code in {401, 403}:
        return ProviderFailure("no_access", str(exc))
    if exc.status_code == 404:
        return ProviderFailure("no_result", str(exc))
    if exc.status_code == 429:
        return ProviderFailure("rate_limited", str(exc), retry_after_seconds=exc.retry_after_seconds)
    if exc.status_code in {400, 406, 422}:
        return ProviderFailure("error", str(exc))
    if exc.status_code is None:
        return ProviderFailure("error", str(exc))
    if exc.status_code >= 500:
        return ProviderFailure("error", str(exc))
    return ProviderFailure("error", str(exc))


def combine_provider_failures(failures: list[tuple[str, ProviderFailure]]) -> ProviderFailure:
    priority = {
        "no_access": 0,
        "no_result": 1,
        "rate_limited": 2,
        "error": 3,
        "not_configured": 4,
        "not_supported": 5,
    }
    selected_label, selected_failure = min(
        failures,
        key=lambda item: priority.get(item[1].code, 99),
    )
    message = "; ".join(f"{label}: {failure.message}" for label, failure in failures)
    if len(failures) == 1:
        message = f"{selected_label}: {selected_failure.message}"
    missing_env: list[str] = []
    for _label, failure in failures:
        for name in failure.missing_env:
            if name not in missing_env:
                missing_env.append(name)
    return ProviderFailure(
        selected_failure.code,
        message,
        retry_after_seconds=selected_failure.retry_after_seconds,
        missing_env=missing_env,
        warnings=[
            warning
            for _label, failure in failures
            for warning in failure.warnings
            if str(warning).strip()
        ],
        source_trail=[
            marker
            for _label, failure in failures
            for marker in failure.source_trail
            if str(marker).strip()
        ],
    )


class ProviderClient:
    """Provider interface used by the fetch workflow."""

    name = "provider"
    official_provider = True

    def fetch_metadata(self, query: Mapping[str, str | None]) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} metadata retrieval is not available.")

    def fetch_result(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "none",
        artifact_store: ArtifactStore | None = None,
        context: RuntimeContext | None = None,
    ) -> ProviderFetchResult:
        context = self._runtime_context(context, output_dir=output_dir)
        active_artifact_store = artifact_store or ArtifactStore.from_download_dir(output_dir)
        asset_output_dir = active_artifact_store.download_dir
        prepared = self.prepare_fetch_result_payload(doi, metadata, asset_profile=asset_profile, context=context)
        prepared.raw_payload = self._sync_fetch_result_content_local_copy(prepared.raw_payload)
        prepared = self.maybe_recover_fetch_result_payload(
            doi,
            metadata,
            prepared,
            asset_profile=asset_profile,
            context=context,
        )
        prepared.raw_payload = self._sync_fetch_result_content_local_copy(prepared.raw_payload)
        raw_payload = prepared.raw_payload
        content = raw_payload.content
        artifact_policy = self.describe_artifacts(raw_payload)
        downloaded_assets: list[Mapping[str, Any]] = []
        asset_failures: list[Mapping[str, Any]] = []
        warnings = list(prepared.result_warnings if prepared.result_warnings is not None else raw_payload.warnings)
        trace = list(prepared.result_trace if prepared.result_trace is not None else raw_payload.trace)
        if (
            asset_output_dir is not None
            and asset_profile != "none"
            and artifact_policy.allow_related_assets
            and self.should_download_related_assets_for_result(
                raw_payload,
                provisional_article=prepared.provisional_article,
            )
        ):
            try:
                asset_started_at = time.monotonic()
                try:
                    asset_results = self.download_related_assets(
                        doi,
                        metadata,
                        raw_payload,
                        asset_output_dir,
                        asset_profile=asset_profile,
                        context=context,
                    )
                finally:
                    context.accumulate_stage_timing("asset_seconds", started_at=asset_started_at)
                downloaded_assets = list(asset_results.get("assets") or [])
                asset_failures = list(asset_results.get("asset_failures") or [])
            except ProviderFailure as exc:
                warnings.append(self.asset_download_failure_warning(exc))
                trace.extend(trace_from_markers([f"download:{self.name}_assets_failed"]))
            except (RequestFailure, OSError) as exc:
                warnings.append(self.asset_download_failure_warning(exc))
                trace.extend(trace_from_markers([f"download:{self.name}_assets_failed"]))
        if prepared.provisional_article is not None and not downloaded_assets and not asset_failures:
            article = prepared.provisional_article
        else:
            article = self.to_article_model(
                metadata,
                raw_payload,
                downloaded_assets=downloaded_assets,
                asset_failures=asset_failures,
                context=context,
            )
        article = self.finalize_fetch_result_article(
            article,
            raw_payload=raw_payload,
            provisional_article=prepared.provisional_article,
            finalize_warnings=prepared.finalize_warnings,
        )
        artifacts = self.describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        return ProviderFetchResult(
            provider=raw_payload.provider or self.name,
            article=article,
            content=content,
            warnings=warnings,
            trace=list(trace or trace_from_markers(article.quality.source_trail)),
            artifacts=artifacts,
        )

    def _runtime_context(self, context: RuntimeContext | None, *, output_dir: Path | None = None) -> RuntimeContext:
        if context is not None:
            return context
        return RuntimeContext(
            env=getattr(self, "env", {}) or {},
            transport=getattr(self, "transport", None),
            download_dir=output_dir,
        )

    def _sync_fetch_result_content_local_copy(self, raw_payload: RawFulltextPayload) -> RawFulltextPayload:
        content = raw_payload.content
        if content is not None and content.needs_local_copy != raw_payload.needs_local_copy:
            raw_payload.content = replace(content, needs_local_copy=raw_payload.needs_local_copy)
        return raw_payload

    def prepare_fetch_result_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        asset_profile: AssetProfile = "none",
        context: RuntimeContext | None = None,
    ) -> PreparedFetchResultPayload:
        context = self._runtime_context(context)
        return PreparedFetchResultPayload(raw_payload=self.fetch_raw_fulltext(doi, metadata, context=context))

    def maybe_recover_fetch_result_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        prepared: PreparedFetchResultPayload,
        *,
        asset_profile: AssetProfile = "none",
        context: RuntimeContext | None = None,
    ) -> PreparedFetchResultPayload:
        del context
        return prepared

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article: ArticleModel | None = None,
    ) -> bool:
        return True

    def finalize_fetch_result_article(
        self,
        article: ArticleModel,
        *,
        raw_payload: RawFulltextPayload,
        provisional_article: ArticleModel | None = None,
        finalize_warnings: list[str] | None = None,
    ) -> ArticleModel:
        return article

    def asset_download_failure_warning(self, exc: ProviderFailure | RequestFailure | OSError) -> str:
        message = exc.message if isinstance(exc, ProviderFailure) else str(exc)
        return f"{self.name.replace('_', ' ').title()} related assets could not be downloaded: {message}"

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        return ProviderArtifacts(
            assets=[dict(item) for item in (downloaded_assets or [])],
            asset_failures=[dict(item) for item in (asset_failures or [])],
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        del context
        raise ProviderFailure("not_supported", f"{self.name} raw full-text retrieval is not available.")

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        del context
        raise ProviderFailure("not_supported", f"{self.name} article conversion is not available.")

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        del context
        return empty_asset_results()

    def probe_status(self) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider=self.name,
            status="error",
            available=False,
            official_provider=self.official_provider,
            notes=["Provider diagnostics are not implemented for this client."],
            checks=[
                build_provider_status_check(
                    "diagnostics",
                    "error",
                    f"{self.name} provider diagnostics are not implemented.",
                )
            ],
        )
