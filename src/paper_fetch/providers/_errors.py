"""Lightweight provider error, status, and payload data structures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from ..failure import FailureDiagnostics
from ..http import RequestFailure
from ..reason_codes import (
    ERROR,
    IDENTITY_MISMATCH,
    NO_ACCESS,
    NO_RESULT,
    NOT_CONFIGURED,
    NOT_SUPPORTED,
    OK,
    PARTIAL,
    RATE_LIMITED,
    READY,
)
from ..tracing import TraceEvent, merge_trace
from ..utils import extend_unique, normalize_text

if TYPE_CHECKING:
    from ..models.schema import ArticleModel


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
        trace: list[TraceEvent] | None = None,
        diagnostics: FailureDiagnostics | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.missing_env = list(missing_env or [])
        self.warnings = [str(item) for item in (warnings or []) if str(item).strip()]
        self.trace = list(trace or [])
        self.diagnostics = diagnostics or FailureDiagnostics()

    def with_updates(self, **updates: Any) -> ProviderFailure:
        values: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
            "missing_env": self.missing_env,
            "warnings": self.warnings,
            "trace": self.trace,
            "diagnostics": self.diagnostics,
        }
        diagnostic_updates = {
            key: updates.pop(key)
            for key in (
                "provider",
                "route",
                "stage",
                "http_status",
                "error_category",
                "retryable",
                "details",
            )
            if key in updates
        }
        if diagnostic_updates:
            values["diagnostics"] = self.diagnostics.with_updates(**diagnostic_updates)
        values.update(updates)
        return ProviderFailure(**values)


@dataclass(frozen=True, kw_only=True)
class ProviderContent:
    route_kind: str
    source_url: str
    content_type: str
    body: bytes
    markdown_text: str | None = None
    merged_metadata: Mapping[str, Any] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    fetcher: str | None = None
    browser_context_seed: dict[str, Any] = field(default_factory=dict)
    suggested_filename: str | None = None
    html_failure_reason: str | None = None
    html_failure_message: str | None = None
    extracted_assets: list[dict[str, Any]] = field(default_factory=list)
    needs_local_copy: bool = False
    route_name: str | None = None


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
class RawFulltextPayload:
    """Provider content and its acquisition diagnostics."""

    provider: str
    content: ProviderContent
    warnings: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.content, ProviderContent):
            raise TypeError("content must be ProviderContent")


@dataclass
class PreparedFetchResultPayload:
    raw_payload: RawFulltextPayload
    provisional_article: ArticleModel | None = None
    finalize_warnings: list[str] = field(default_factory=list)
    result_warnings: list[str] | None = None
    result_trace: list[TraceEvent] | None = None
    context: dict[str, Any] = field(default_factory=dict)


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
    failure: ProviderFailure,
    *,
    details: Mapping[str, Any] | None = None,
) -> ProviderStatusCheck:
    status = failure.code if failure.code in {NOT_CONFIGURED, RATE_LIMITED} else ERROR
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
        if check.status == OK:
            ok_checks += 1
        elif check.status == ERROR:
            has_error = True
        elif check.status == RATE_LIMITED:
            has_rate_limit = True
        for name in check.missing_env:
            if name not in missing_env:
                missing_env.append(name)

    available = ok_checks > 0
    if has_error:
        status = ERROR
    elif has_rate_limit and ok_checks == 0:
        status = RATE_LIMITED
    elif checks and all(check.status == OK for check in checks):
        status = READY
    elif available:
        status = PARTIAL
    else:
        status = NOT_CONFIGURED

    return ProviderStatusResult(
        provider=provider,
        status=status,
        available=available,
        official_provider=official_provider,
        missing_env=missing_env,
        notes=deduped_notes,
        checks=list(checks),
    )


def map_request_failure(
    exc: RequestFailure,
    *,
    no_result_status_codes: set[int] | frozenset[int] | None = None,
    no_result_messages: Mapping[int, str] | None = None,
) -> ProviderFailure:
    status_code = exc.status_code
    if status_code is not None and status_code in (no_result_status_codes or set()):
        message = normalize_text(
            str((no_result_messages or {}).get(status_code) or "")
        ) or str(exc)
        return ProviderFailure(
            NO_RESULT,
            message,
            diagnostics=FailureDiagnostics(
                http_status=status_code,
                error_category=str(exc.error_category or "") or None,
                retryable=False,
            ),
        )
    if status_code in {401, 403}:
        return ProviderFailure(
            NO_ACCESS,
            str(exc),
            diagnostics=FailureDiagnostics(
                http_status=status_code,
                error_category=str(exc.error_category or "") or None,
                retryable=False,
            ),
        )
    if status_code == 404:
        return ProviderFailure(
            NO_RESULT,
            str(exc),
            diagnostics=FailureDiagnostics(
                http_status=status_code,
                error_category=str(exc.error_category or "") or None,
                retryable=False,
            ),
        )
    if status_code == 429:
        return ProviderFailure(
            RATE_LIMITED,
            str(exc),
            retry_after_seconds=exc.retry_after_seconds,
            diagnostics=FailureDiagnostics(
                http_status=status_code,
                error_category=RATE_LIMITED,
                retryable=True,
            ),
        )
    if status_code in {400, 406, 422}:
        return ProviderFailure(
            ERROR,
            str(exc),
            diagnostics=FailureDiagnostics(
                http_status=status_code,
                error_category=str(exc.error_category or "") or None,
                retryable=False,
            ),
        )
    if status_code is None:
        category = str(exc.error_category or "") or None
        return ProviderFailure(
            ERROR,
            str(exc),
            diagnostics=FailureDiagnostics(
                error_category=category,
                retryable=category
                in {
                    "timeout",
                    "dns_error",
                    "connection_reset",
                    "connection_closed",
                    "network_error",
                },
            ),
        )
    if status_code >= 500:
        return ProviderFailure(
            ERROR,
            str(exc),
            diagnostics=FailureDiagnostics(
                http_status=status_code,
                error_category=str(exc.error_category or "") or None,
                retryable=True,
            ),
        )
    return ProviderFailure(
        ERROR,
        str(exc),
        diagnostics=FailureDiagnostics(
            http_status=status_code,
            error_category=str(exc.error_category or "") or None,
            retryable=False,
        ),
    )


def combine_provider_failures(
    failures: list[tuple[str, ProviderFailure]],
) -> ProviderFailure:
    if not failures:
        return ProviderFailure(
            NO_RESULT,
            "Provider waterfall did not record any retrieval failures.",
        )

    priority = {
        NO_ACCESS: 0,
        NO_RESULT: 1,
        IDENTITY_MISMATCH: 1,
        RATE_LIMITED: 2,
        ERROR: 3,
        NOT_CONFIGURED: 4,
        NOT_SUPPORTED: 5,
    }
    selected_label, selected_failure = min(
        failures,
        key=lambda item: priority.get(item[1].code, 99),
    )
    message = "; ".join(f"{label}: {failure.message}" for label, failure in failures)
    if len(failures) == 1:
        message = f"{selected_label}: {selected_failure.message}"
    missing_env: list[str] = []
    warnings: list[str] = []
    retry_after_values: list[int] = []
    trace: list[TraceEvent] = []
    for _label, failure in failures:
        extend_unique(missing_env, failure.missing_env)
        extend_unique(warnings, failure.warnings)
        trace = merge_trace(trace, failure.trace)
        if failure.retry_after_seconds is not None:
            retry_after_values.append(failure.retry_after_seconds)
    return selected_failure.with_updates(
        message=message,
        retry_after_seconds=max(retry_after_values) if retry_after_values else None,
        missing_env=missing_env,
        warnings=warnings,
        trace=trace,
    )


__all__ = [
    "PreparedFetchResultPayload",
    "ProviderArtifacts",
    "ProviderContent",
    "ProviderFailure",
    "ProviderFetchResult",
    "ProviderStatusCheck",
    "ProviderStatusResult",
    "RawFulltextPayload",
    "build_provider_status_check",
    "combine_provider_failures",
    "map_request_failure",
    "provider_status_check_from_failure",
    "summarize_capability_status",
]
