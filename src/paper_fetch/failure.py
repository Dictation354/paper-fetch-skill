"""Typed diagnostics shared by provider and workflow failures."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any
from collections.abc import Mapping

from .utils import normalize_text


@dataclass(frozen=True)
class FailureDiagnostics:
    """Machine-readable context for a failed provider attempt."""

    provider: str | None = None
    route: str | None = None
    stage: str | None = None
    http_status: int | None = None
    error_category: str | None = None
    retryable: bool | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider", normalize_text(self.provider).lower() or None
        )
        object.__setattr__(self, "route", normalize_text(self.route).lower() or None)
        object.__setattr__(self, "stage", normalize_text(self.stage).lower() or None)
        object.__setattr__(
            self,
            "error_category",
            normalize_text(self.error_category).lower() or None,
        )
        object.__setattr__(self, "details", dict(self.details))

    def with_updates(self, **updates: Any) -> FailureDiagnostics:
        if "details" in updates:
            updates["details"] = dict(updates["details"] or {})
        return replace(self, **updates)

    @classmethod
    def from_failure(cls, failure: object) -> FailureDiagnostics:
        existing = getattr(failure, "diagnostics", None)
        if isinstance(existing, cls):
            return existing
        return cls(
            provider=getattr(failure, "provider", None),
            route=getattr(failure, "route", None),
            stage=getattr(failure, "stage", None),
            http_status=getattr(failure, "http_status", None),
            error_category=getattr(failure, "error_category", None),
            retryable=getattr(failure, "retryable", None),
            details=getattr(failure, "details", None) or {},
        )
