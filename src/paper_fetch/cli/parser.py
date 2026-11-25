"""Argument parser construction and conversion to typed CLI commands."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

import paper_fetch.cli as cli_pkg

from ..artifacts import ArtifactMode
from ..auth import browser_auth_provider_names
from ..catalog_payload import canonical_provider_hint
from ..diagnostics import provider_status_group_names, provider_status_provider_names
from ..models.schema import AssetProfile, MaxTokensMode
from ..provider_catalog import browser_preflight_provider_names
from ..publisher_identity import DOI_PATTERN, SICI_DOI_PATTERN, normalize_doi
from .commands import (
    AuthCommand,
    BatchFetchCommand,
    BrowserPreflightCommand,
    CliCommand,
    CliUsageError,
    DoctorCommand,
    FetchAssetsCommand,
    FetchExecutionOptions,
    FetchOutputPlan,
    FetchTarget,
    IncludeRefsMode,
    LookupCommand,
    OutputFormat,
    PresetName,
    ProgressMode,
    ResolutionCommand,
    ResolutionMode,
    SingleFetchCommand,
    UpdateCommand,
)


def parse_max_tokens(value: str) -> MaxTokensMode:
    normalized = value.strip().lower()
    if normalized == "full_text":
        return "full_text"
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "max_tokens must be a positive integer or 'full_text'."
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("max_tokens must be greater than 0.")
    return parsed


def parse_batch_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "batch-concurrency must be an integer from 1 to 8."
        ) from exc
    if not 1 <= parsed <= 8:
        raise argparse.ArgumentTypeError(
            "batch-concurrency must be an integer from 1 to 8."
        )
    return parsed


def parse_positive_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer.")
    return parsed


def _read_indexed_query_file(path: Path) -> list[tuple[int, str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read query file {path}: {exc}") from exc

    queries = []
    for index, line in enumerate(lines, 1):
        query = line.strip()
        if not query or query.startswith("#"):
            continue
        queries.append((index, query))
    if not queries:
        raise ValueError(
            "query file did not contain any queries after filtering blank lines and comments."
        )
    return queries


def read_query_file(path: Path) -> list[str]:
    return [query for _, query in _read_indexed_query_file(path)]


def load_query_file(path: str, *, command: str) -> tuple[str, ...]:
    try:
        return tuple(read_query_file(Path(path)))
    except ValueError as exc:
        raise CliUsageError(str(exc), command=command) from exc


def _doctor_provider(value: str) -> str:
    if value in provider_status_provider_names():
        return value
    hint = canonical_provider_hint(value)
    raise argparse.ArgumentTypeError(
        f"unknown provider {value!r}."
        + (f" Use {hint!r}." if hint else " Use doctor --catalog.")
    )


def _add_fetch_arguments(parser: argparse.ArgumentParser) -> None:
    """Register fetch flags directly on the fetch subparser."""

    parser.add_argument(
        "--progress",
        choices=("auto", "text", "jsonl", "none"),
        default="auto",
        help="Progress on stderr: auto shows text on a terminal; jsonl uses protocol 1.",
    )
    parser.add_argument(
        "--control-stdin",
        action="store_true",
        default=False,
        help="Read cooperative cancellation commands from stdin (requires --progress jsonl).",
    )
    parser.add_argument(
        "--preset",
        choices=("temporary_read", "cacheable_read", "archive"),
        default="temporary_read",
        help="Fill omitted options for temporary reading or text archiving.",
    )
    parser.add_argument(
        "--prefer-cache",
        action="store_true",
        default=None,
        help="Reuse compatible cached results in the selected output directory.",
    )
    query_group = parser.add_mutually_exclusive_group()
    query_group.add_argument(
        "--query",
        default=None,
        help="DOI, paper landing URL, or title query",
    )
    query_group.add_argument(
        "--query-file",
        default=None,
        help="Batch mode: read one DOI, paper landing URL, or title query per line.",
    )
    parser.add_argument(
        "--batch-concurrency",
        type=parse_batch_concurrency,
        default=1,
        help="Maximum concurrent fetches for --query-file batch mode (1-8; default: 1).",
    )
    parser.add_argument(
        "--batch-results",
        default=None,
        help="JSONL summary path for --query-file batch mode. Defaults to <output-dir>/batch-results.jsonl.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Additional single-paper schema-v2 manifest path. Every result also has an independent manifest; batch mode uses --batch-results."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Allow replacement of existing final outputs and batch results.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default=None,
        help=(
            "Serialization format for stdout, --output, or the default file under --output-dir "
            "when --output is omitted (default: markdown)."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Explicit body destination; use - for body stdout. Otherwise stdout contains JSON receipts."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory for the default formatted output when --output is omitted, plus Markdown, "
            "PDF fallback sources, and assets. Defaults to a retained system temporary directory."
        ),
    )
    parser.add_argument(
        "--artifact-mode",
        choices=("markdown-assets", "all", "none"),
        default=None,
        help=(
            "Controls local artifact retention. markdown-assets saves Markdown plus assets from "
            "--asset-profile and keeps PDF fallback sources; all preserves raw provider/cache "
            "artifacts; none disables provider artifacts and assets (preset default: none)."
        ),
    )
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        default=False,
        help=(
            "Also write the rendered AI Markdown full text to disk (defaults to PAPER_FETCH_DOWNLOAD_DIR "
            "or the user data downloads directory, "
            "overridable via --output-dir). Only writes when full text was actually retrieved. "
            "For Wiley the preferred Markdown route is provider-managed HTML; TDM or browser PDF/ePDF "
            "fallbacks may be lower fidelity than Elsevier XML or publisher-managed HTML."
        ),
    )
    parser.add_argument(
        "--include-refs",
        choices=("none", "top10", "all"),
        default=None,
        help=(
            "Reference rendering mode for Markdown output. Defaults to all for full_text "
            "and top10 for numeric --max-tokens."
        ),
    )
    parser.add_argument(
        "--target",
        choices=("paper", "supplementary"),
        default="paper",
        help=(
            "Fetch the paper (default) or independently retrieve supplementary materials. "
            "Only the supplementary target downloads attachments by default."
        ),
    )
    parser.add_argument(
        "--asset-profile",
        choices=("none", "body", "all"),
        default=None,
        help=(
            "Local content asset scope: none skips asset downloads, body saves body "
            "figures/tables/formula images. Use all to download supplementary materials "
            "alongside the paper (default for the paper target: none)."
        ),
    )
    parser.add_argument(
        "--require-local-body-assets",
        action="store_true",
        default=False,
        help=(
            "Degrade acceptance unless every discovered body asset is archived "
            "locally. Applies only to --asset-profile body or all."
        ),
    )
    parser.add_argument(
        "--require-full-size-body-assets",
        action="store_true",
        default=False,
        help=(
            "Degrade acceptance unless every discovered body asset is a local "
            "full-size file; this also implies --require-local-body-assets."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=parse_max_tokens,
        default=None,
        help=(
            "Markdown rendering budget: a positive integer token budget or full_text "
            "for the complete article (default: full_text)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-fetch {cli_pkg.package_version()}",
        help="Show the installed paper-fetch version and exit.",
    )


def _add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "provider",
        choices=browser_auth_provider_names(),
        help="Browser-backed provider to open for manual authentication.",
    )
    parser.add_argument(
        "--url",
        help="Publisher URL to open (default: the provider's built-in sample article).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="Browser navigation timeout in milliseconds (default: runtime configuration).",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this authentication run (default: runtime configuration).",
    )


def _add_browser_preflight_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        action="append",
        choices=browser_preflight_provider_names(),
        help=(
            "Browser-backed provider to preflight. May be repeated "
            "(default: all browser-backed providers)."
        ),
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="Browser navigation timeout in milliseconds (default: runtime configuration).",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this preflight run (default: runtime configuration).",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=None,
        help="Directory for privacy-sanitized failure diagnostics.",
    )
    parser.add_argument(
        "--artifact-mode",
        choices=("none", "all"),
        default="none",
        help="Use 'all' to persist sanitized page diagnostics (default: none).",
    )


def _add_doctor_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Show the shared runtime provider catalog without network access.",
    )
    parser.add_argument(
        "--provider",
        type=_doctor_provider,
        help="Inspect one canonical provider ID; use --catalog to discover IDs.",
    )
    parser.add_argument(
        "--group",
        choices=provider_status_group_names(),
        help="Inspect a catalog-derived provider group.",
    )
    parser.add_argument(
        "--detail",
        choices=("full", "compact"),
        default="full",
        help="Diagnostic detail level (default: full).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Explicit dotenv file used only for source-aware static diagnostics.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Write the machine-readable diagnostic report.",
    )


def _build_parser_bundle() -> tuple[
    argparse.ArgumentParser, dict[str, argparse.ArgumentParser]
]:
    parser = argparse.ArgumentParser(
        prog="paper-fetch",
        description=(
            "Fetch AI-friendly paper full text and manage browser-backed provider access."
        ),
        epilog="Doctor performs static, network-free checks.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-fetch {cli_pkg.package_version()}",
        help="Show the installed paper-fetch version and exit.",
    )
    subparsers_action = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Run `paper-fetch COMMAND --help` for command-specific options.",
    )
    subparsers_action.required = True
    subparsers: dict[str, argparse.ArgumentParser] = {}

    fetch_parser = subparsers_action.add_parser(
        "fetch",
        help="Fetch one paper or a query-file batch.",
        description=(
            "Fetch AI-friendly full text for a paper by DOI, URL, or title. "
            f"Managed Byparr uses the platform-selected engine ({cli_pkg.engine_name()} here)."
        ),
        epilog="See `paper-fetch doctor --catalog` for the browser catalog.",
    )
    _add_fetch_arguments(fetch_parser)
    subparsers["fetch"] = fetch_parser

    lookup_parser = subparsers_action.add_parser(
        "lookup",
        help="Find a retained, accepted full-text result by DOI in a project.",
    )
    lookup_queries = lookup_parser.add_mutually_exclusive_group(required=True)
    lookup_queries.add_argument("--doi", metavar="DOI", help="DOI of the paper.")
    lookup_queries.add_argument(
        "--query-file",
        metavar="PATH",
        help="UTF-8 text file with one DOI per line (blank lines and # comments ignored).",
    )
    lookup_parser.add_argument(
        "--output-dir",
        type=Path,
        action="append",
        required=True,
        help="Project directory to search. May be repeated.",
    )
    lookup_parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Allow historical full text if no verified result exists.",
    )
    subparsers["lookup"] = lookup_parser

    for name in ("resolve", "check"):
        resolution_parser = subparsers_action.add_parser(
            name,
            help="Resolve paper identity."
            if name == "resolve"
            else "Probe full-text availability without fetching the body.",
        )
        queries = resolution_parser.add_mutually_exclusive_group(required=True)
        queries.add_argument("--query")
        queries.add_argument("--query-file")
        resolution_parser.add_argument(
            "--batch-concurrency", type=parse_batch_concurrency, default=4
        )
        resolution_parser.add_argument(
            "--progress", choices=("auto", "text", "jsonl", "none"), default="none"
        )
        subparsers[name] = resolution_parser

    assets_parser = subparsers_action.add_parser(
        "fetch-assets",
        help="Fetch selected paper images without fetching the full text.",
    )
    asset_source = assets_parser.add_mutually_exclusive_group(required=True)
    asset_source.add_argument("--query", help="Known paper DOI, URL, or title.")
    asset_source.add_argument(
        "--manifest",
        help="Existing per-paper manifest; use its identity and image index.",
    )
    selectors = assets_parser.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--asset-id", action="append", dest="asset_ids")
    selectors.add_argument("--asset-url", action="append", dest="urls")
    selectors.add_argument("--kind", choices=("formula", "figure", "table"))
    assets_parser.add_argument(
        "--output-dir", help="Archive images; otherwise retain files in system temp."
    )
    assets_parser.add_argument(
        "--compact",
        action="store_true",
        help="Print a compact JSON receipt and save the full details separately.",
    )
    assets_parser.add_argument("--overwrite", action="store_true")
    subparsers["fetch-assets"] = assets_parser

    auth_parser = subparsers_action.add_parser(
        "auth",
        help="Open a headed browser and save provider authentication state.",
        description="Manage publisher browser authentication state.",
    )
    _add_auth_arguments(auth_parser)
    subparsers["auth"] = auth_parser

    preflight_parser = subparsers_action.add_parser(
        "browser-preflight",
        help="Live-check browser-backed providers and save usable storage state.",
        description=(
            "Serially open browser-backed provider sample pages, save provider "
            "storage-state JSON on success, and report providers that need manual auth."
        ),
    )
    _add_browser_preflight_arguments(preflight_parser)
    subparsers["browser-preflight"] = preflight_parser

    doctor_parser = subparsers_action.add_parser(
        "doctor",
        help="Inspect static provider configuration and local dependencies.",
        description=(
            "Inspect provider configuration sources and local browser/image dependencies "
            "without network access. Use browser-preflight for real page health."
        ),
    )
    _add_doctor_arguments(doctor_parser)
    subparsers["doctor"] = doctor_parser

    update_parser = subparsers_action.add_parser(
        "update",
        help="Update an official installation to the latest stable GitHub Release.",
        description=(
            "Download and verify the latest stable Release from "
            "Dictation354/paper-fetch-skill. Linux/macOS upgrade automatically; "
            "Windows opens the setup wizard at the current installation directory. "
            "Source and pip installations receive their existing update commands."
        ),
    )
    subparsers["update"] = update_parser

    return parser, subparsers


def build_parser() -> argparse.ArgumentParser:
    """Build the discoverable command-oriented CLI."""

    parser, _subparsers = _build_parser_bundle()
    return parser


def resolve_fetch_options(
    ns: argparse.Namespace, *, deliver_files: bool = True
) -> FetchExecutionOptions:
    """Resolve preset defaults and explicit flags from a parsed fetch Namespace."""

    if ns.control_stdin and ns.progress != "jsonl":
        raise CliUsageError(
            "--control-stdin requires --progress jsonl.", command="fetch"
        )

    preset = cast(PresetName, ns.preset or "temporary_read")
    target = cast(FetchTarget, ns.target)

    prefer_cache = (
        bool(ns.prefer_cache)
        if ns.prefer_cache is not None
        else preset in {"cacheable_read", "archive"}
    )

    default_asset_profile: AssetProfile = "none"
    default_artifact_mode: ArtifactMode = "none"
    if target == "supplementary":
        default_asset_profile = "all"
        default_artifact_mode = "markdown-assets"
    elif ns.asset_profile is not None and ns.asset_profile != "none":
        default_artifact_mode = "markdown-assets"

    explicit_format = ns.format is not None
    output_format = cast(OutputFormat, ns.format if explicit_format else "markdown")
    include_refs = cast(
        IncludeRefsMode, ns.include_refs if ns.include_refs is not None else "all"
    )
    max_tokens = cast(
        MaxTokensMode, ns.max_tokens if ns.max_tokens is not None else "full_text"
    )
    asset_profile = cast(
        AssetProfile,
        ns.asset_profile if ns.asset_profile is not None else default_asset_profile,
    )
    artifact_mode = cast(
        ArtifactMode,
        ns.artifact_mode if ns.artifact_mode is not None else default_artifact_mode,
    )

    output_is_explicit = ns.output is not None
    output = str(ns.output) if output_is_explicit else "-"
    output_dir = Path(ns.output_dir) if ns.output_dir else None
    batch_mode = ns.query_file is not None

    if batch_mode and output_is_explicit:
        raise CliUsageError(
            "--output cannot be used with --query-file; batch mode writes one primary output per query under --output-dir.",
            command="fetch",
        )
    if batch_mode and ns.manifest:
        raise CliUsageError(
            "--manifest is single-paper only; batch mode uses --batch-results.",
            command="fetch",
        )
    if not batch_mode and ns.batch_results:
        raise CliUsageError("--batch-results requires --query-file.", command="fetch")

    primary_output_to_output_dir = batch_mode or not output_is_explicit
    save_output_copy = (
        explicit_format
        and output_is_explicit
        and output == "-"
        and output_dir is not None
        and (
            artifact_mode == "all"
            or (artifact_mode == "markdown-assets" and output_format == "markdown")
        )
    )
    if ns.save_markdown:
        save_markdown_to_disk = True
    elif artifact_mode != "markdown-assets":
        save_markdown_to_disk = False
    elif output != "-" and not primary_output_to_output_dir:
        save_markdown_to_disk = False
    else:
        save_markdown_to_disk = not (
            output_format == "markdown"
            and (save_output_copy or primary_output_to_output_dir)
        )

    output_plan = FetchOutputPlan(
        output_format=output_format,
        output=output,
        output_is_explicit=output_is_explicit,
        output_dir=output_dir,
        primary_output_to_output_dir=primary_output_to_output_dir,
        save_output_copy=save_output_copy,
        save_markdown_to_disk=save_markdown_to_disk,
        deliver_files=deliver_files,
        overwrite=bool(ns.overwrite),
    )
    return FetchExecutionOptions(
        preset=preset,
        target=target,
        prefer_cache=prefer_cache,
        artifact_mode=artifact_mode,
        asset_profile=asset_profile,
        include_refs=include_refs,
        max_tokens=max_tokens,
        require_local_body_assets=bool(ns.require_local_body_assets),
        require_full_size_body_assets=bool(ns.require_full_size_body_assets),
        progress=cast(ProgressMode, ns.progress),
        control_stdin=bool(ns.control_stdin),
        output_plan=output_plan,
    )


def _command_from_namespace(ns: argparse.Namespace) -> CliCommand:
    command_name = str(ns.command)
    if command_name == "fetch":
        if ns.query is None and ns.query_file is None:
            raise CliUsageError(
                "one of the arguments --query --query-file is required",
                command="fetch",
            )
        options = resolve_fetch_options(ns, deliver_files=True)
        if ns.query_file is not None:
            queries = load_query_file(ns.query_file, command="fetch")
            return BatchFetchCommand(
                queries=queries,
                options=options,
                batch_concurrency=int(ns.batch_concurrency),
                batch_results=ns.batch_results,
            )
        assert ns.query is not None
        return SingleFetchCommand(
            query=str(ns.query),
            options=options,
            manifest=ns.manifest,
        )

    if command_name == "lookup":
        doi = normalize_doi(ns.doi) if ns.doi is not None else None
        if doi is not None and not (
            DOI_PATTERN.fullmatch(doi) or SICI_DOI_PATTERN.fullmatch(doi)
        ):
            raise CliUsageError("--doi requires a valid DOI.", command="lookup")
        output_dirs = tuple(path.expanduser() for path in ns.output_dir)
        if any(path.exists() and not path.is_dir() for path in output_dirs):
            raise CliUsageError("--output-dir must be a directory.", command="lookup")
        try:
            lookup_queries = (
                tuple(_read_indexed_query_file(Path(ns.query_file)))
                if ns.query_file is not None
                else ()
            )
        except ValueError as exc:
            raise CliUsageError(str(exc), command="lookup") from exc
        return LookupCommand(
            doi=doi,
            output_dirs=output_dirs,
            include_legacy=ns.include_legacy,
            queries=lookup_queries,
        )

    if command_name in {"resolve", "check"}:
        mode = cast(ResolutionMode, command_name)
        queries = (
            load_query_file(ns.query_file, command=mode)
            if ns.query_file is not None
            else (str(ns.query),)
        )
        return ResolutionCommand(
            mode=mode,
            queries=queries,
            batch_concurrency=int(ns.batch_concurrency),
            progress=cast(ProgressMode, ns.progress),
        )

    if command_name == "fetch-assets":
        return FetchAssetsCommand(
            query=ns.query,
            manifest=Path(ns.manifest) if ns.manifest else None,
            asset_ids=tuple(ns.asset_ids) if ns.asset_ids is not None else None,
            urls=tuple(ns.urls) if ns.urls is not None else None,
            kind=cast(Literal["formula", "figure", "table"] | None, ns.kind),
            output_dir=ns.output_dir or None,
            compact=bool(ns.compact),
            overwrite=bool(ns.overwrite),
        )

    if command_name == "auth":
        return AuthCommand(
            provider=str(ns.provider),
            url=ns.url,
            timeout_ms=ns.timeout_ms,
            browser_user_agent=ns.browser_user_agent,
        )

    if command_name == "browser-preflight":
        return BrowserPreflightCommand(
            providers=tuple(ns.provider) if ns.provider is not None else None,
            timeout_ms=ns.timeout_ms,
            browser_user_agent=ns.browser_user_agent,
            download_dir=ns.download_dir,
            artifact_mode=cast(Literal["none", "all"], ns.artifact_mode),
        )

    if command_name == "doctor":
        return DoctorCommand(
            catalog=bool(ns.catalog),
            provider=ns.provider,
            group=ns.group,
            detail=cast(Literal["full", "compact"], ns.detail),
            env_file=ns.env_file,
            output_json=bool(ns.output_json),
        )

    if command_name == "update":
        return UpdateCommand()

    raise CliUsageError(f"unknown command {command_name!r}")


def parse_cli_command(
    argv: Sequence[str],
    *,
    parser: argparse.ArgumentParser | None = None,
) -> CliCommand:
    """Parse CLI arguments into a strongly typed command object."""

    active_parser = parser if parser is not None else build_parser()
    ns = active_parser.parse_args(list(argv))
    return _command_from_namespace(ns)
