"""Provider interfaces and shared error types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..http import RequestFailure


class ProviderFailure(Exception):
    """Provider-specific failure with a stable category."""

    def __init__(self, code: str, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


@dataclass
class RawFulltextPayload:
    provider: str
    source_url: str
    content_type: str
    body: bytes
    metadata: dict[str, Any] = field(default_factory=dict)
    needs_local_copy: bool = False


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
    return ProviderFailure(
        selected_failure.code,
        message,
        retry_after_seconds=selected_failure.retry_after_seconds,
    )


class ProviderClient:
    """Provider interface used by the fetch workflow."""

    name = "provider"

    def fetch_metadata(self, query: Mapping[str, str | None]) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} metadata retrieval is not available.")

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, Any]) -> RawFulltextPayload:
        raise ProviderFailure("not_supported", f"{self.name} raw full-text retrieval is not available.")

    def fetch_fulltext(self, doi: str, metadata: Mapping[str, Any], output_dir: Path | None) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} full-text retrieval is not available.")
