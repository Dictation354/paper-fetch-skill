"""CLI package facade and command dispatcher for paper-fetch."""

from __future__ import annotations

import json
import signal
import sys
import threading
import time
from typing import Any

from paper_fetch.service import fetch_paper, resolve_paper

from ..artifacts import ArtifactStore
from ..auth import authenticate_provider_profile
from ..browser_preflight import BrowserPreflightResult, run_browser_provider_preflight
from ..browser_runtime_policy import engine_name
from ..config import build_runtime_env, resolve_cli_download_dir
from ..diagnostics import doctor_payload as build_doctor_payload
from ..manifest import DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
from ..manifest_writer import write_manifest_record
from ..providers.base import ProviderFailure
from ..runtime import RuntimeContext
from ..version import package_version
from ..workflow.rendering import rewrite_markdown_asset_links
from .commands import (
    AssetProfile,
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
    ManifestTargetConflict,
    ManifestWriteError,
    OutputDirectoryError,
    OutputFormat,
    OutputOverwriteRequired,
    PresetName,
    ProgressMode,
    ResolutionCommand,
    ResolutionMode,
    SingleFetchCommand,
    SupportsControlStdin,
    UpdateCommand,
    compute_output_modes,
)
from .fetch_runner import (
    CliBatchItem,
    CliFetchOutcome,
    _ensure_cli_ams_auth,
    _resolve_cli_batch_item_lane,
    _run_batch_item,
    _run_single_fetch_with_context,
    run_batch_fetch,
    run_batch_fetch_command,
    run_single_fetch,
    run_single_fetch_command,
)
from .manifest_io import (
    CliManifestAttempt,
    CliManifestBuildContext,
    SingleFetchResult,
    _build_cli_manifest_record,
    _error_payload,
    _formatted_output_filename,
    exit_code_for_batch_results,
    prepare_output_dir,
    save_formatted_output_copy,
    save_markdown_to_disk,
    serialize_envelope,
    write_output,
)
from .parser import (
    _build_parser_bundle,
    build_parser,
    parse_batch_concurrency,
    parse_cli_command,
    parse_max_tokens,
    parse_positive_int_arg,
    read_query_file,
    resolve_fetch_options,
)
from .progress import FetchProgress
from .subcommands import (
    run_auth_command,
    run_browser_preflight_command,
    run_doctor_command,
    run_fetch_assets_command,
    run_lookup_command,
    run_resolution_command,
    run_update_command,
)


def dispatch_command(command: CliCommand) -> int:
    """Dispatch a strongly typed CLI command to its execution handler."""

    if isinstance(command, SingleFetchCommand):
        return run_single_fetch_command(command)
    if isinstance(command, BatchFetchCommand):
        return run_batch_fetch_command(command)
    if isinstance(command, LookupCommand):
        return run_lookup_command(command)
    if isinstance(command, ResolutionCommand):
        return run_resolution_command(command)
    if isinstance(command, FetchAssetsCommand):
        return run_fetch_assets_command(command)
    if isinstance(command, AuthCommand):
        return run_auth_command(command)
    if isinstance(command, BrowserPreflightCommand):
        return run_browser_preflight_command(command)
    if isinstance(command, DoctorCommand):
        return run_doctor_command(command)
    if isinstance(command, UpdateCommand):
        return run_update_command(command)
    raise AssertionError(f"Unhandled CLI command: {command!r}")


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else list(argv)
    parser, subparsers = _build_parser_bundle()
    try:
        command = parse_cli_command(raw_args, parser=parser)
    except CliUsageError as exc:
        target_parser = subparsers.get(exc.command, parser) if exc.command else parser
        target_parser.error(str(exc))

    previous_termination_handler = None
    install_termination_handler = (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGTERM")
    )
    if install_termination_handler:
        previous_termination_handler = signal.getsignal(signal.SIGTERM)

        def terminate(_signum: int, _frame: Any) -> None:
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, terminate)
    try:
        return dispatch_command(command)
    except CliUsageError as exc:
        target_parser = subparsers.get(exc.command, parser) if exc.command else parser
        target_parser.error(str(exc))
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return 1
    except KeyboardInterrupt:
        return 1
    finally:
        if install_termination_handler:
            signal.signal(signal.SIGTERM, previous_termination_handler)


__all__ = [
    "DEFAULT_MANIFEST_BUILDER_DEPENDENCIES",
    "ArtifactStore",
    "AssetProfile",
    "AuthCommand",
    "BatchFetchCommand",
    "BrowserPreflightCommand",
    "BrowserPreflightResult",
    "CliBatchItem",
    "CliCommand",
    "CliFetchOutcome",
    "CliManifestAttempt",
    "CliManifestBuildContext",
    "CliUsageError",
    "DoctorCommand",
    "FetchAssetsCommand",
    "FetchExecutionOptions",
    "FetchOutputPlan",
    "FetchProgress",
    "FetchTarget",
    "IncludeRefsMode",
    "LookupCommand",
    "ManifestTargetConflict",
    "ManifestWriteError",
    "OutputDirectoryError",
    "OutputFormat",
    "OutputOverwriteRequired",
    "PresetName",
    "ProgressMode",
    "ResolutionCommand",
    "ResolutionMode",
    "RuntimeContext",
    "SingleFetchCommand",
    "SingleFetchResult",
    "SupportsControlStdin",
    "UpdateCommand",
    "_build_cli_manifest_record",
    "_ensure_cli_ams_auth",
    "_formatted_output_filename",
    "_resolve_cli_batch_item_lane",
    "_run_batch_item",
    "_run_single_fetch_with_context",
    "authenticate_provider_profile",
    "build_doctor_payload",
    "build_parser",
    "build_runtime_env",
    "compute_output_modes",
    "dispatch_command",
    "engine_name",
    "exit_code_for_batch_results",
    "fetch_paper",
    "main",
    "package_version",
    "parse_batch_concurrency",
    "parse_cli_command",
    "parse_max_tokens",
    "parse_positive_int_arg",
    "prepare_output_dir",
    "read_query_file",
    "resolve_cli_download_dir",
    "resolve_fetch_options",
    "resolve_paper",
    "rewrite_markdown_asset_links",
    "run_auth_command",
    "run_batch_fetch",
    "run_batch_fetch_command",
    "run_browser_preflight_command",
    "run_browser_provider_preflight",
    "run_doctor_command",
    "run_fetch_assets_command",
    "run_lookup_command",
    "run_resolution_command",
    "run_single_fetch",
    "run_single_fetch_command",
    "run_update_command",
    "save_formatted_output_copy",
    "save_markdown_to_disk",
    "serialize_envelope",
    "sys",
    "time",
    "write_manifest_record",
    "write_output",
]
