"""Strongly typed CLI command models, output planning, and CLI exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from ..artifacts import ArtifactMode
from ..models.schema import AssetProfile, MaxTokensMode, OutputMode, RenderOptions

FetchTarget = Literal["paper", "supplementary"]
IncludeRefsMode = Literal["none", "top10", "all"]
OutputFormat = Literal["markdown", "json", "both"]
PresetName = Literal["temporary_read", "cacheable_read", "archive"]
ProgressMode = Literal["auto", "text", "jsonl", "none"]
ResolutionMode = Literal["resolve", "check"]


class CliUsageError(ValueError):
    """Raised when CLI options violate command-specific usage rules."""

    def __init__(self, message: str, *, command: str | None = None) -> None:
        super().__init__(message)
        self.command = command


class OutputDirectoryError(Exception):
    """Raised when the CLI output directory cannot be prepared."""


class ManifestWriteError(OutputDirectoryError):
    """Raised when an explicitly requested CLI manifest cannot be written."""


class ManifestTargetConflict(OutputDirectoryError):
    """Raised when a manifest would overwrite a recorded output artifact."""


class OutputOverwriteRequired(OutputDirectoryError):
    """Raised when replacing an existing final artifact needs permission."""


class SupportsControlStdin(Protocol):
    """Protocol for execution options carrying cooperative stdin control mode."""

    @property
    def control_stdin(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class FetchOutputPlan:
    """Resolved output destination and artifact writing flags for fetch."""

    output_format: OutputFormat = "markdown"
    output: str = "-"
    output_is_explicit: bool = False
    output_dir: Path | None = None
    primary_output_to_output_dir: bool = False
    save_output_copy: bool = False
    save_markdown_to_disk: bool = False
    deliver_files: bool = False
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class FetchExecutionOptions:
    """Resolved shared execution options for single and batch fetch commands."""

    preset: PresetName = "temporary_read"
    target: FetchTarget = "paper"
    prefer_cache: bool = False
    artifact_mode: ArtifactMode = "none"
    asset_profile: AssetProfile = "none"
    include_refs: IncludeRefsMode = "all"
    max_tokens: MaxTokensMode = "full_text"
    require_local_body_assets: bool = False
    require_full_size_body_assets: bool = False
    progress: ProgressMode = "auto"
    control_stdin: bool = False
    output_plan: FetchOutputPlan = FetchOutputPlan()

    def render_options(self) -> RenderOptions:
        return RenderOptions(
            include_refs=self.include_refs,
            asset_profile=self.asset_profile,
            max_tokens=self.max_tokens,
        )


@dataclass(frozen=True, slots=True)
class SingleFetchCommand:
    """CLI request to fetch a single paper or supplementary bundle."""

    query: str
    options: FetchExecutionOptions = FetchExecutionOptions()
    manifest: str | None = None


@dataclass(frozen=True, slots=True)
class BatchFetchCommand:
    """CLI request to fetch a batch of queries from a query file."""

    queries: tuple[str, ...]
    options: FetchExecutionOptions = FetchExecutionOptions()
    batch_concurrency: int = 1
    batch_results: str | None = None


@dataclass(frozen=True, slots=True)
class LookupCommand:
    """CLI request to look up a retained accepted receipt by DOI."""

    doi: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class ResolutionCommand:
    """CLI request to resolve paper identity or probe full-text availability."""

    mode: ResolutionMode
    queries: tuple[str, ...]
    batch_concurrency: int = 4


@dataclass(frozen=True, slots=True)
class FetchAssetsCommand:
    """CLI request to download selected paper assets without full-text fetch."""

    query: str | None = None
    manifest: Path | None = None
    asset_ids: tuple[str, ...] | None = None
    urls: tuple[str, ...] | None = None
    kind: Literal["formula"] | None = None
    output_dir: str | None = None
    compact: bool = False
    overwrite: bool = False
    control_stdin: bool = False


@dataclass(frozen=True, slots=True)
class AuthCommand:
    """CLI request to run headed manual browser authentication."""

    provider: str
    url: str | None = None
    timeout_ms: int | None = None
    browser_user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class BrowserPreflightCommand:
    """CLI request to run serial browser-backed provider preflight checks."""

    providers: tuple[str, ...] | None = None
    timeout_ms: int | None = None
    browser_user_agent: str | None = None
    download_dir: Path | None = None
    artifact_mode: Literal["none", "all"] = "none"


@dataclass(frozen=True, slots=True)
class DoctorCommand:
    """CLI request to inspect static configuration or provider catalog."""

    catalog: bool = False
    provider: str | None = None
    group: str | None = None
    detail: Literal["full", "compact"] = "full"
    env_file: Path | None = None
    output_json: bool = False


@dataclass(frozen=True, slots=True)
class UpdateCommand:
    """CLI request to upgrade an official installation."""


CliCommand = (
    SingleFetchCommand
    | BatchFetchCommand
    | LookupCommand
    | ResolutionCommand
    | FetchAssetsCommand
    | AuthCommand
    | BrowserPreflightCommand
    | DoctorCommand
    | UpdateCommand
)


def compute_output_modes(plan: FetchOutputPlan) -> set[OutputMode]:
    """Compute required pipeline output modes from the resolved output plan."""

    modes: set[OutputMode] = (
        {"markdown"} if plan.output_format == "markdown" else {"article"}
    )
    # Writing Markdown to a file or saving an extra Markdown copy needs the
    # structured article payload so we can rewrite local asset links relative
    # to the target path and decide whether full text was actually usable.
    if plan.output_format == "markdown" and (
        plan.output != "-" or plan.save_output_copy or plan.primary_output_to_output_dir
    ):
        modes.add("article")
    if plan.output_format == "both" or plan.save_markdown_to_disk:
        modes.add("markdown")
    if plan.save_markdown_to_disk:
        modes.add("article")
    return modes
