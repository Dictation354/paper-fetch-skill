"""Provider interfaces, diagnostics, and shared error types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..http import RequestFailure
from ..models import AssetProfile
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
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.missing_env = list(missing_env or [])


@dataclass
class RawFulltextPayload:
    provider: str
    source_url: str
    content_type: str
    body: bytes
    metadata: dict[str, Any] = field(default_factory=dict)
    needs_local_copy: bool = False


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
    )


class ProviderClient:
    """Provider interface used by the fetch workflow."""

    name = "provider"
    official_provider = True

    def fetch_metadata(self, query: Mapping[str, str | None]) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} metadata retrieval is not available.")

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, Any]) -> RawFulltextPayload:
        raise ProviderFailure("not_supported", f"{self.name} raw full-text retrieval is not available.")

    def fetch_fulltext(self, doi: str, metadata: Mapping[str, Any], output_dir: Path | None) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} full-text retrieval is not available.")

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        raise ProviderFailure("not_supported", f"{self.name} article conversion is not available.")

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
    ) -> dict[str, list[dict[str, Any]]]:
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
