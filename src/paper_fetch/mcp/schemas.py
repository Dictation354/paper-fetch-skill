"""MCP-facing request validation and service conversion helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..models import RenderOptions, normalize_text
from ..service import FetchStrategy
from ..utils import dedupe_authors

ALLOWED_INCLUDE_REFS = {"none", "top10", "all"}
ALLOWED_ASSET_PROFILES = {"none", "body", "all"}
ALLOWED_OUTPUT_MODES = {"article", "markdown", "metadata"}
ALLOWED_BATCH_CHECK_MODES = {"article", "metadata"}
DEFAULT_MCP_MODES = ["article", "markdown"]


class ResolvePaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None

    @field_validator("query", "title", mode="before")
    @classmethod
    def normalize_optional_text_field(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = normalize_text(value)
        if not normalized:
            return None
        return normalized

    @field_validator("authors", mode="before")
    @classmethod
    def coerce_authors(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("authors")
    @classmethod
    def normalize_authors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized_authors = dedupe_authors([normalize_text(str(item)) for item in value if normalize_text(str(item))])
        return normalized_authors or None

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 1000 or value > 9999:
            raise ValueError("year must be a four-digit integer.")
        return value

    @model_validator(mode="after")
    def validate_input_mode(self) -> "ResolvePaperRequest":
        has_query = self.query is not None
        has_structured = self.title is not None or self.authors is not None or self.year is not None

        if has_query and has_structured:
            raise ValueError("provide either query or structured title/authors/year fields, but not both.")
        if has_query:
            return self
        if self.title is None:
            raise ValueError("title is required when query is omitted.")
        return self

    def composed_query(self) -> str:
        if self.query is not None:
            return self.query

        parts: list[str] = [self.title or ""]
        parts.extend((self.authors or [])[:3])
        if self.year is not None:
            parts.append(str(self.year))
        return normalize_text(" ".join(parts))


class HasFulltextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized


def _normalize_query_list(value: Any) -> list[str]:
    if value is None:
        raise ValueError("queries must contain at least one entry.")
    if not isinstance(value, list):
        raise ValueError("queries must be provided as a list of strings.")
    if not value:
        raise ValueError("queries must contain at least one entry.")

    normalized_queries: list[str] = []
    for index, item in enumerate(value):
        normalized = normalize_text(str(item))
        if not normalized:
            raise ValueError(f"queries[{index}] must not be empty.")
        normalized_queries.append(normalized)
    return normalized_queries


class FetchStrategyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_html_fallback: bool = True
    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None
    asset_profile: str = "none"

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

    @field_validator("asset_profile")
    @classmethod
    def normalize_asset_profile(cls, value: str) -> str:
        normalized = normalize_text(value).lower()
        if normalized not in ALLOWED_ASSET_PROFILES:
            raise ValueError(
                f"unsupported asset_profile value: {value!r}. Expected one of: {', '.join(sorted(ALLOWED_ASSET_PROFILES))}."
            )
        return normalized

    def to_service_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            allow_html_fallback=self.allow_html_fallback,
            allow_metadata_only_fallback=self.allow_metadata_only_fallback,
            preferred_providers=list(self.preferred_providers) if self.preferred_providers is not None else None,
            asset_profile=self.asset_profile,
        )


class FetchPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    modes: list[str] = Field(default_factory=lambda: list(DEFAULT_MCP_MODES))
    strategy: FetchStrategyInput = Field(default_factory=FetchStrategyInput)
    include_refs: str | None = None
    max_tokens: int | str = "full_text"

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
    def normalize_include_refs(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_text(value).lower()
        if normalized not in ALLOWED_INCLUDE_REFS:
            raise ValueError(
                f"unsupported include_refs value: {value!r}. Expected one of: {', '.join(sorted(ALLOWED_INCLUDE_REFS))}."
            )
        return normalized

    @field_validator("max_tokens", mode="before")
    @classmethod
    def validate_max_tokens(cls, value: int | str) -> int | str:
        if isinstance(value, str):
            normalized = normalize_text(value).lower()
            if normalized == "full_text":
                return "full_text"
            try:
                value = int(normalized)
            except ValueError as exc:
                raise ValueError("max_tokens must be a positive integer or 'full_text'.") from exc
        if value <= 0:
            raise ValueError("max_tokens must be greater than 0.")
        return value

    def requested_modes(self) -> set[str]:
        return set(self.modes)

    def to_render_options(self) -> RenderOptions:
        return RenderOptions(
            include_refs=self.include_refs,
            asset_profile=self.strategy.asset_profile,
            max_tokens=self.max_tokens,
        )


class BatchResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[str]

    @field_validator("queries", mode="before")
    @classmethod
    def normalize_queries(cls, value: Any) -> list[str]:
        return _normalize_query_list(value)


class BatchCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[str]
    mode: str = "metadata"

    @field_validator("queries", mode="before")
    @classmethod
    def normalize_queries(cls, value: Any) -> list[str]:
        return _normalize_query_list(value)

    @field_validator("mode")
    @classmethod
    def normalize_mode(cls, value: str) -> str:
        normalized = normalize_text(value).lower()
        if normalized not in ALLOWED_BATCH_CHECK_MODES:
            raise ValueError(
                f"unsupported batch_check mode: {value!r}. Expected one of: "
                + ", ".join(sorted(ALLOWED_BATCH_CHECK_MODES))
                + "."
            )
        return normalized
