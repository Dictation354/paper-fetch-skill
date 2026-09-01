"""MCP-facing request validation and service conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, TypeAlias, cast, get_args
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from ..artifacts import ArtifactMode
from ..provider_catalog import browser_preflight_provider_names
from ..diagnostics import (
    PROVIDER_STATUS_DETAILS,
    PROVIDER_STATUS_GROUPS,
    ProviderStatusDetail,
    ProviderStatusGroup,
    normalize_provider_status_detail,
    normalize_provider_status_group,
    normalize_provider_status_provider,
    provider_status_provider_names,
    selected_provider_status_names,
)
from ..models import (
    AssetProfile,
    MaxTokensMode,
    OutputMode,
    RenderOptions,
    normalize_text,
)
from ..resolve.query import StructuredResolveRequest
from ..service import FetchStrategy
from ..workflow.types import allowed_preferred_providers
from ..utils import dedupe_authors

IncludeRefsMode = Literal["none", "top10", "all"]
BatchCheckMode = Literal["article", "metadata"]
CacheDetail = Literal["full", "compact"]
BrowserPreflightDetail = Literal["full", "compact"]
BatchFetchDetail = Literal["compact", "bounded"]

ALLOWED_INCLUDE_REFS = set(get_args(IncludeRefsMode))


def _allowed_values_from_literal(literal_type: Any) -> frozenset[str]:
    return frozenset(str(value) for value in get_args(literal_type))


ALLOWED_ASSET_PROFILES = _allowed_values_from_literal(AssetProfile)
ALLOWED_ARTIFACT_MODES = _allowed_values_from_literal(ArtifactMode)
ALLOWED_OUTPUT_MODES = _allowed_values_from_literal(OutputMode)
ALLOWED_BATCH_CHECK_MODES = set(get_args(BatchCheckMode))
DEFAULT_MCP_MODES = ["article", "markdown"]
DEFAULT_MCP_ARTIFACT_MODE: ArtifactMode = "markdown-assets"
DEFAULT_INLINE_IMAGE_MAX_IMAGES = 3
DEFAULT_INLINE_IMAGE_MAX_BYTES_PER_IMAGE = 2 * 1024 * 1024
DEFAULT_INLINE_IMAGE_MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_BATCH_QUERIES = 50

ConcurrencyInput: TypeAlias = Annotated[int, Field(ge=1, le=8)]
BatchContentMaxCharsInput: TypeAlias = Annotated[int, Field(ge=1, le=100_000)]


def _coerce_optional_string_list(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return value


def _normalize_output_modes(value: Any) -> list[str]:
    if value is None:
        return list(DEFAULT_MCP_MODES)
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


def _normalize_include_refs(value: Any) -> Any:
    if value is None:
        return None
    normalized = normalize_text(value).lower()
    if normalized not in ALLOWED_INCLUDE_REFS:
        raise ValueError(
            f"unsupported include_refs value: {value!r}. Expected one of: "
            + ", ".join(sorted(ALLOWED_INCLUDE_REFS))
            + "."
        )
    return normalized


def _normalize_asset_profile(value: Any) -> Any:
    if value is None:
        return None
    normalized = normalize_text(value).lower()
    if normalized not in ALLOWED_ASSET_PROFILES:
        raise ValueError(
            f"unsupported asset_profile value: {value!r}. Expected one of: "
            + ", ".join(sorted(ALLOWED_ASSET_PROFILES))
            + "."
        )
    return normalized


def _normalize_artifact_mode(value: Any) -> str:
    normalized = normalize_text(value).lower()
    if normalized not in ALLOWED_ARTIFACT_MODES:
        raise ValueError(
            f"unsupported artifact_mode value: {value!r}. Expected one of: "
            + ", ".join(sorted(ALLOWED_ARTIFACT_MODES))
            + "."
        )
    return normalized


def _normalize_batch_check_mode(value: Any) -> str:
    normalized = normalize_text(value).lower()
    if normalized not in ALLOWED_BATCH_CHECK_MODES:
        raise ValueError(
            f"unsupported batch_check mode: {value!r}. Expected one of: "
            + ", ".join(sorted(ALLOWED_BATCH_CHECK_MODES))
            + "."
        )
    return normalized


def _normalize_cache_detail(value: Any) -> str:
    normalized = normalize_text(value).lower()
    allowed = set(get_args(CacheDetail))
    if normalized not in allowed:
        raise ValueError(
            f"unsupported cache detail value: {value!r}. Expected one of: "
            + ", ".join(sorted(allowed))
            + "."
        )
    return normalized


def _normalize_browser_preflight_provider(value: Any) -> str:
    normalized = normalize_text(str(value or "")).lower()
    allowed = browser_preflight_provider_names()
    if normalized not in allowed:
        raise ValueError(
            f"unsupported browser preflight provider {value!r}. Expected one of: "
            + ", ".join(allowed)
            + "."
        )
    return normalized


def _normalize_browser_preflight_detail(value: Any) -> str:
    normalized = normalize_text(str(value or "")).lower()
    allowed = set(get_args(BrowserPreflightDetail))
    if normalized not in allowed:
        raise ValueError(
            f"unsupported browser preflight detail {value!r}. Expected one of: "
            + ", ".join(sorted(allowed))
            + "."
        )
    return normalized


def _normalize_batch_fetch_detail(value: Any) -> str:
    normalized = normalize_text(str(value or "")).lower()
    allowed = set(get_args(BatchFetchDetail))
    if normalized not in allowed:
        raise ValueError(
            f"unsupported batch_fetch detail {value!r}. Expected one of: "
            + ", ".join(sorted(allowed))
            + "."
        )
    return normalized


def _normalize_max_tokens(value: Any) -> int | str:
    if isinstance(value, str):
        normalized = normalize_text(value).lower()
        if normalized == "full_text":
            return "full_text"
        try:
            value = int(normalized)
        except ValueError as exc:
            raise ValueError(
                "max_tokens must be a positive integer or 'full_text'."
            ) from exc
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("max_tokens must be greater than 0.")
    return value


OutputModesInput: TypeAlias = Annotated[
    list[OutputMode], BeforeValidator(_normalize_output_modes)
]
IncludeRefsInput: TypeAlias = Annotated[
    IncludeRefsMode, BeforeValidator(_normalize_include_refs)
]
AssetProfileInput: TypeAlias = Annotated[
    AssetProfile, BeforeValidator(_normalize_asset_profile)
]
ArtifactModeInput: TypeAlias = Annotated[
    ArtifactMode, BeforeValidator(_normalize_artifact_mode)
]
BatchCheckModeInput: TypeAlias = Annotated[
    BatchCheckMode, BeforeValidator(_normalize_batch_check_mode)
]
CacheDetailInput: TypeAlias = Annotated[
    CacheDetail, BeforeValidator(_normalize_cache_detail)
]
ProviderNameInput: TypeAlias = Annotated[
    str,
    BeforeValidator(normalize_provider_status_provider),
    WithJsonSchema({"type": "string", "enum": list(provider_status_provider_names())}),
]
ProviderStatusGroupInput: TypeAlias = Annotated[
    ProviderStatusGroup,
    BeforeValidator(normalize_provider_status_group),
    WithJsonSchema({"type": "string", "enum": list(PROVIDER_STATUS_GROUPS)}),
]
ProviderStatusDetailInput: TypeAlias = Annotated[
    ProviderStatusDetail,
    BeforeValidator(normalize_provider_status_detail),
    WithJsonSchema({"type": "string", "enum": list(PROVIDER_STATUS_DETAILS)}),
]
BrowserPreflightProviderInput: TypeAlias = Annotated[
    str,
    BeforeValidator(_normalize_browser_preflight_provider),
    WithJsonSchema(
        {"type": "string", "enum": list(browser_preflight_provider_names())}
    ),
]
BrowserPreflightDetailInput: TypeAlias = Annotated[
    BrowserPreflightDetail,
    BeforeValidator(_normalize_browser_preflight_detail),
]
BatchFetchDetailInput: TypeAlias = Annotated[
    BatchFetchDetail,
    BeforeValidator(_normalize_batch_fetch_detail),
]
BrowserPreflightTimeoutInput: TypeAlias = Annotated[int, Field(ge=1, le=600_000)]
MaxTokensInput: TypeAlias = Annotated[
    Annotated[int, Field(gt=0)] | Literal["full_text"],
    BeforeValidator(_normalize_max_tokens),
]


@dataclass(frozen=True)
class InlineImageBudget:
    max_images: int = DEFAULT_INLINE_IMAGE_MAX_IMAGES
    max_bytes_per_image: int = DEFAULT_INLINE_IMAGE_MAX_BYTES_PER_IMAGE
    max_total_bytes: int = DEFAULT_INLINE_IMAGE_MAX_TOTAL_BYTES

    @property
    def disabled(self) -> bool:
        return (
            self.max_images == 0
            or self.max_bytes_per_image == 0
            or self.max_total_bytes == 0
        )


class InlineImageBudgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_images: int | None = Field(default=None, ge=0)
    max_bytes_per_image: int | None = Field(default=None, ge=0)
    max_total_bytes: int | None = Field(default=None, ge=0)

    def resolved(self) -> InlineImageBudget:
        return InlineImageBudget(
            max_images=self.max_images
            if self.max_images is not None
            else DEFAULT_INLINE_IMAGE_MAX_IMAGES,
            max_bytes_per_image=(
                self.max_bytes_per_image
                if self.max_bytes_per_image is not None
                else DEFAULT_INLINE_IMAGE_MAX_BYTES_PER_IMAGE
            ),
            max_total_bytes=(
                self.max_total_bytes
                if self.max_total_bytes is not None
                else DEFAULT_INLINE_IMAGE_MAX_TOTAL_BYTES
            ),
        )


InlineImageBudgetToolInput: TypeAlias = Annotated[
    InlineImageBudgetInput,
    WithJsonSchema(InlineImageBudgetInput.model_json_schema()),
]


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
        return _coerce_optional_string_list(value)

    @field_validator("authors")
    @classmethod
    def normalize_authors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized_authors = dedupe_authors(
            [normalize_text(str(item)) for item in value if normalize_text(str(item))]
        )
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
    def validate_input_mode(self) -> ResolvePaperRequest:
        has_query = self.query is not None
        has_structured = (
            self.title is not None or self.authors is not None or self.year is not None
        )

        if has_query and has_structured:
            raise ValueError(
                "provide either query or structured title/authors/year fields, but not both."
            )
        if has_query:
            return self
        if self.title is None:
            raise ValueError("title is required when query is omitted.")
        return self

    def composed_query(self) -> str:
        if self.query is not None:
            return self.query
        return self.title or ""

    def to_resolution_request(self) -> StructuredResolveRequest:
        if self.query is not None:
            return StructuredResolveRequest(query=self.query)
        return StructuredResolveRequest(
            title=self.title,
            authors=tuple(self.authors or ()),
            year=self.year,
        )


class _RequiredQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("query must not be empty.")
        return normalized


class HasFulltextRequest(_RequiredQueryRequest):
    pass


def _normalize_query_list(value: Any) -> list[str]:
    if value is None:
        raise ValueError("queries must contain at least one entry.")
    if not isinstance(value, list):
        raise ValueError("queries must be provided as a list of strings.")
    if not value:
        raise ValueError("queries must contain at least one entry.")
    if len(value) > MAX_BATCH_QUERIES:
        raise ValueError(f"queries must contain at most {MAX_BATCH_QUERIES} entries.")

    normalized_queries: list[str] = []
    for index, item in enumerate(value):
        normalized = normalize_text(str(item))
        if not normalized:
            raise ValueError(f"queries[{index}] must not be empty.")
        normalized_queries.append(normalized)
    return normalized_queries


BatchQueriesInput: TypeAlias = Annotated[
    list[str],
    BeforeValidator(_normalize_query_list),
    Field(min_length=1, max_length=MAX_BATCH_QUERIES),
]


class FetchStrategyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None
    asset_profile: AssetProfileInput | None = None
    require_local_body_assets: bool = False
    require_full_size_body_assets: bool = False
    inline_image_budget: InlineImageBudgetToolInput | None = None

    @field_validator("preferred_providers", mode="before")
    @classmethod
    def coerce_preferred_providers(cls, value: Any) -> Any:
        return _coerce_optional_string_list(value)

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
        allowed_providers = allowed_preferred_providers()
        invalid = [
            provider for provider in normalized if provider not in allowed_providers
        ]
        if invalid:
            raise ValueError(
                "unsupported preferred_providers values: "
                + ", ".join(invalid)
                + ". Expected one or more of: "
                + ", ".join(sorted(allowed_providers))
                + "."
            )
        return normalized or None

    @field_validator("asset_profile", mode="before")
    @classmethod
    def normalize_asset_profile(cls, value: Any) -> Any:
        return _normalize_asset_profile(value)

    @model_validator(mode="after")
    def imply_local_assets_for_full_size(self) -> FetchStrategyInput:
        if self.require_full_size_body_assets:
            self.require_local_body_assets = True
        return self

    def to_service_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            allow_metadata_only_fallback=self.allow_metadata_only_fallback,
            preferred_providers=list(self.preferred_providers)
            if self.preferred_providers is not None
            else None,
            asset_profile=cast(AssetProfile | None, self.asset_profile),
            require_local_body_assets=self.require_local_body_assets,
            require_full_size_body_assets=self.require_full_size_body_assets,
        )

    def resolved_inline_image_budget(self) -> InlineImageBudget:
        budget = self.inline_image_budget or InlineImageBudgetInput()
        return budget.resolved()

    def cache_request_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"inline_image_budget"})


FetchStrategyToolInput: TypeAlias = Annotated[
    FetchStrategyInput,
    WithJsonSchema(FetchStrategyInput.model_json_schema()),
]


class FetchPaperRequest(_RequiredQueryRequest):
    modes: OutputModesInput = Field(default_factory=lambda: list(DEFAULT_MCP_MODES))
    strategy: FetchStrategyToolInput = Field(default_factory=FetchStrategyInput)
    include_refs: IncludeRefsInput | None = None
    max_tokens: MaxTokensInput = "full_text"
    prefer_cache: bool = False
    no_download: bool = False
    artifact_mode: ArtifactModeInput = DEFAULT_MCP_ARTIFACT_MODE
    save_markdown: bool = False
    markdown_output_dir: str | None = None
    markdown_filename: str | None = None

    @field_validator("modes", mode="before")
    @classmethod
    def default_modes_when_null(cls, value: Any) -> Any:
        return list(DEFAULT_MCP_MODES) if value is None else value

    @field_validator("modes")
    @classmethod
    def normalize_modes(cls, value: Any) -> list[str]:
        return _normalize_output_modes(value)

    @field_validator("strategy", mode="before")
    @classmethod
    def default_strategy_when_null(cls, value: Any) -> Any:
        return {} if value is None else value

    @field_validator("artifact_mode")
    @classmethod
    def normalize_artifact_mode(cls, value: Any) -> str:
        return _normalize_artifact_mode(value)

    @field_validator("markdown_output_dir", "markdown_filename", mode="before")
    @classmethod
    def normalize_optional_string(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("markdown_filename")
    @classmethod
    def validate_markdown_filename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if Path(value).name != value:
            raise ValueError("markdown_filename must be a file name, not a path.")
        return value

    @field_validator("include_refs")
    @classmethod
    def normalize_include_refs(cls, value: Any) -> Any:
        return _normalize_include_refs(value)

    @field_validator("max_tokens", mode="before")
    @classmethod
    def validate_max_tokens(cls, value: Any) -> int | str:
        return _normalize_max_tokens(value)

    def requested_modes(self) -> set[str]:
        requested: set[str] = set(self.modes)
        if self.save_markdown:
            requested.update({"article", "markdown"})
        return requested

    def to_render_options(self) -> RenderOptions:
        return RenderOptions(
            include_refs=self.include_refs,
            asset_profile=cast(AssetProfile | None, self.strategy.asset_profile),
            max_tokens=cast(MaxTokensMode, self.max_tokens),
        )


class FetchPaperToolRequest(FetchPaperRequest):
    download_dir: str | None = None

    @field_validator("download_dir", mode="before")
    @classmethod
    def normalize_download_dir(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class BatchResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: BatchQueriesInput
    concurrency: ConcurrencyInput = 1

    @field_validator("queries", mode="before")
    @classmethod
    def normalize_queries(cls, value: Any) -> list[str]:
        return _normalize_query_list(value)


class BatchCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: BatchQueriesInput
    mode: BatchCheckModeInput = "metadata"
    concurrency: ConcurrencyInput = 1

    @field_validator("queries", mode="before")
    @classmethod
    def normalize_queries(cls, value: Any) -> list[str]:
        return _normalize_query_list(value)

    @field_validator("mode")
    @classmethod
    def normalize_mode(cls, value: Any) -> str:
        return _normalize_batch_check_mode(value)


class BatchFetchRequest(BaseModel):
    """Typed batch adapter input sharing the single-fetch request semantics."""

    model_config = ConfigDict(extra="forbid")

    queries: BatchQueriesInput
    concurrency: ConcurrencyInput = 1
    modes: OutputModesInput = Field(default_factory=lambda: list(DEFAULT_MCP_MODES))
    strategy: FetchStrategyToolInput = Field(default_factory=FetchStrategyInput)
    include_refs: IncludeRefsInput | None = None
    max_tokens: MaxTokensInput = "full_text"
    prefer_cache: bool = False
    no_download: bool = False
    artifact_mode: ArtifactModeInput = DEFAULT_MCP_ARTIFACT_MODE
    save_markdown: bool = False
    markdown_output_dir: str | None = None
    markdown_filename: str | None = None
    download_dir: str | None = None
    detail: BatchFetchDetailInput = "compact"
    content_max_chars: BatchContentMaxCharsInput = 20_000
    continue_on_error: bool = True
    batch_results: str | None = None
    overwrite: bool = False

    @field_validator("queries", mode="before")
    @classmethod
    def normalize_queries(cls, value: Any) -> list[str]:
        return _normalize_query_list(value)

    @field_validator("modes", mode="before")
    @classmethod
    def default_modes_when_null(cls, value: Any) -> Any:
        return list(DEFAULT_MCP_MODES) if value is None else value

    @field_validator("modes")
    @classmethod
    def normalize_modes(cls, value: Any) -> list[str]:
        return _normalize_output_modes(value)

    @field_validator("strategy", mode="before")
    @classmethod
    def default_strategy_when_null(cls, value: Any) -> Any:
        return {} if value is None else value

    @field_validator("artifact_mode")
    @classmethod
    def normalize_artifact_mode(cls, value: Any) -> str:
        return _normalize_artifact_mode(value)

    @field_validator("include_refs")
    @classmethod
    def normalize_include_refs(cls, value: Any) -> Any:
        return _normalize_include_refs(value)

    @field_validator("max_tokens", mode="before")
    @classmethod
    def validate_max_tokens(cls, value: Any) -> int | str:
        return _normalize_max_tokens(value)

    @field_validator("detail")
    @classmethod
    def normalize_detail(cls, value: Any) -> str:
        return _normalize_batch_fetch_detail(value)

    @field_validator(
        "markdown_output_dir",
        "markdown_filename",
        "download_dir",
        "batch_results",
        mode="before",
    )
    @classmethod
    def normalize_optional_string(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("markdown_filename")
    @classmethod
    def validate_markdown_filename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if Path(value).name != value:
            raise ValueError("markdown_filename must be a file name, not a path.")
        return value

    @model_validator(mode="after")
    def validate_batch_contract(self) -> BatchFetchRequest:
        if self.markdown_filename is not None and len(self.queries) != 1:
            raise ValueError(
                "markdown_filename is only valid when batch_fetch has one query."
            )
        return self

    def to_fetch_request(self, query: str) -> FetchPaperRequest:
        return FetchPaperRequest.model_validate(
            {
                "query": query,
                "modes": self.modes,
                "strategy": self.strategy,
                "include_refs": self.include_refs,
                "max_tokens": self.max_tokens,
                "prefer_cache": self.prefer_cache,
                "no_download": self.no_download,
                "artifact_mode": self.artifact_mode,
                "save_markdown": self.save_markdown,
                "markdown_output_dir": self.markdown_output_dir,
                "markdown_filename": self.markdown_filename,
            }
        )


class ListCachedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    download_dir: str | None = None

    @field_validator("download_dir", mode="before")
    @classmethod
    def normalize_download_dir(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class GetCachedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doi: str
    download_dir: str | None = None
    detail: CacheDetailInput = "full"
    preferred_only: bool = False
    modes: OutputModesInput = Field(default_factory=lambda: list(DEFAULT_MCP_MODES))
    strategy: FetchStrategyToolInput = Field(default_factory=FetchStrategyInput)
    include_refs: IncludeRefsInput | None = None
    max_tokens: MaxTokensInput = "full_text"

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, value: str) -> str:
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("doi must not be empty.")
        return normalized

    @field_validator("download_dir", mode="before")
    @classmethod
    def normalize_download_dir(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("detail")
    @classmethod
    def normalize_detail(cls, value: Any) -> str:
        return _normalize_cache_detail(value)

    @field_validator("modes", mode="before")
    @classmethod
    def default_modes_when_null(cls, value: Any) -> Any:
        return list(DEFAULT_MCP_MODES) if value is None else value

    @field_validator("modes")
    @classmethod
    def normalize_modes(cls, value: Any) -> list[str]:
        return _normalize_output_modes(value)

    @field_validator("strategy", mode="before")
    @classmethod
    def default_strategy_when_null(cls, value: Any) -> Any:
        return {} if value is None else value

    def to_fetch_request(self) -> FetchPaperRequest:
        return FetchPaperRequest(
            query=self.doi,
            modes=self.modes,
            strategy=self.strategy,
            include_refs=self.include_refs,
            max_tokens=self.max_tokens,
        )


class ProviderStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderNameInput | None = None
    group: ProviderStatusGroupInput | None = None
    detail: ProviderStatusDetailInput = "full"

    @model_validator(mode="after")
    def validate_filters(self) -> ProviderStatusRequest:
        selected_provider_status_names(provider=self.provider, group=self.group)
        return self


class BrowserPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: BrowserPreflightProviderInput | None = None
    test_url: str | None = None
    timeout_ms: BrowserPreflightTimeoutInput | None = None
    browser_user_agent: str | None = None
    storage_state_path: str | None = None
    save_storage_state: bool = True
    detail: BrowserPreflightDetailInput = "full"

    @field_validator("test_url", "browser_user_agent", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = normalize_text(str(value))
        return normalized or None

    @field_validator("storage_state_path", mode="before")
    @classmethod
    def normalize_storage_state_path(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("test_url")
    @classmethod
    def validate_test_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError(
                "test_url must be an http(s) publisher URL without embedded credentials."
            )
        return value

    @model_validator(mode="after")
    def validate_scoped_options(self) -> BrowserPreflightRequest:
        if (self.test_url is not None or self.storage_state_path is not None) and (
            self.provider is None
        ):
            raise ValueError(
                "test_url and storage_state_path require one explicit provider."
            )
        return self


MCP_TOOL_REQUEST_MODELS: dict[str, type[BaseModel]] = {
    "resolve_paper": ResolvePaperRequest,
    "has_fulltext": HasFulltextRequest,
    "fetch_paper": FetchPaperToolRequest,
    "list_cached": ListCachedRequest,
    "get_cached": GetCachedRequest,
    "batch_resolve": BatchResolveRequest,
    "batch_check": BatchCheckRequest,
    "batch_fetch": BatchFetchRequest,
    "provider_status": ProviderStatusRequest,
    "browser_preflight": BrowserPreflightRequest,
}


def host_safe_tool_input_schema(tool_name: str) -> dict[str, Any]:
    """Return the Pydantic-owned, reference-free schema exposed to MCP hosts."""

    try:
        request_model = MCP_TOOL_REQUEST_MODELS[tool_name]
    except KeyError as exc:
        raise ValueError(
            f"No MCP request model registered for tool {tool_name!r}."
        ) from exc
    schema = request_model.model_json_schema(by_alias=True)

    def reject_reference(value: Any) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                raise ValueError(
                    f"Host-safe MCP schema for {tool_name!r} contains a JSON reference."
                )
            for child in value.values():
                reject_reference(child)
        elif isinstance(value, list):
            for child in value:
                reject_reference(child)

    reject_reference(schema)
    return schema
