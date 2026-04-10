"""MCP-facing request validation and service conversion helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import RenderOptions, normalize_text
from ..service import FetchStrategy

ALLOWED_INCLUDE_REFS = {"none", "top10", "all"}
ALLOWED_OUTPUT_MODES = {"article", "markdown", "metadata"}
DEFAULT_MCP_MODES = ["article", "markdown"]


class ResolvePaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized


class FetchStrategyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_html_fallback: bool = True
    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None

    @field_validator("preferred_providers", mode="before")
    @classmethod
    def coerce_preferred_providers(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("preferred_providers")
    @classmethod
    def normalize_preferred_providers(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        for item in value:
            provider = normalize_text(str(item)).lower()
            if provider and provider not in normalized:
                normalized.append(provider)
        return normalized or None

    def to_service_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            allow_html_fallback=self.allow_html_fallback,
            allow_metadata_only_fallback=self.allow_metadata_only_fallback,
            preferred_providers=list(self.preferred_providers) if self.preferred_providers is not None else None,
        )


class FetchPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    modes: list[str] = Field(default_factory=lambda: list(DEFAULT_MCP_MODES))
    strategy: FetchStrategyInput = Field(default_factory=FetchStrategyInput)
    include_refs: str = "top10"
    max_tokens: int = 8000

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized

    @field_validator("modes", mode="before")
    @classmethod
    def default_modes_when_null(cls, value: Any) -> Any:
        return list(DEFAULT_MCP_MODES) if value is None else value

    @field_validator("modes")
    @classmethod
    def normalize_modes(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        invalid: list[str] = []
        for item in value:
            mode = normalize_text(str(item)).lower()
            if mode not in ALLOWED_OUTPUT_MODES:
                invalid.append(str(item))
                continue
            if mode not in normalized:
                normalized.append(mode)
        if invalid:
            raise ValueError(
                "unsupported output modes: "
                + ", ".join(sorted(set(invalid)))
                + f". Expected one or more of: {', '.join(sorted(ALLOWED_OUTPUT_MODES))}."
            )
        return normalized

    @field_validator("strategy", mode="before")
    @classmethod
    def default_strategy_when_null(cls, value: Any) -> Any:
        return {} if value is None else value

    @field_validator("include_refs")
    @classmethod
    def normalize_include_refs(cls, value: str) -> str:
        normalized = normalize_text(value).lower()
        if normalized not in ALLOWED_INCLUDE_REFS:
            raise ValueError(
                f"unsupported include_refs value: {value!r}. Expected one of: {', '.join(sorted(ALLOWED_INCLUDE_REFS))}."
            )
        return normalized

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_tokens must be greater than 0.")
        return value

    def requested_modes(self) -> set[str]:
        return set(self.modes)

    def to_render_options(self) -> RenderOptions:
        return RenderOptions(include_refs=self.include_refs, max_tokens=self.max_tokens)
