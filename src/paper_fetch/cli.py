"""CLI entrypoint for paper-fetch."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import importlib.metadata
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from .auth import (
    authenticate_provider_profile,
    browser_auth_provider_names,
)
from .artifacts import ArtifactMode, ArtifactStore
from .browser_preflight import BrowserPreflightResult, run_browser_provider_preflight
from .config import build_runtime_env, resolve_cli_download_dir
from .models import FetchEnvelope, RenderOptions
from .providers.base import ProviderFailure
from .reason_codes import ERROR, NO_ACCESS, RATE_LIMITED
from .runtime import build_http_transport_for_context
from .service import FetchStrategy, PaperFetchFailure, fetch_paper
from .utils import _extract_year, format_paper_stem, provider_display_name
from .workflow.pipeline import FetchPipeline, MarkdownSaveSpec
from .workflow.request_builder import build_fetch_pipeline_request
from .workflow.rendering import rewrite_markdown_asset_links
from .workflow.rendering import save_markdown_to_disk as save_markdown_to_disk_for_target


@dataclass(frozen=True)
class SingleFetchResult:
    envelope: FetchEnvelope
    output_path: Path | None = None
    saved_markdown_path: Path | None = None


class OutputDirectoryError(Exception):
    """Raised when the CLI output directory cannot be prepared."""


def package_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        version = payload.get("project", {}).get("version")
        if version:
            return str(version)
    except OSError:
        pass
    try:
        return importlib.metadata.version("paper-fetch-skill")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def save_markdown_to_disk(envelope: FetchEnvelope, *, output_dir: Path, render: RenderOptions) -> Path | None:
    return save_markdown_to_disk_for_target(
        envelope,
        output_dir=output_dir,
        render=render,
        request_label="--save-markdown",
    )


def serialize_envelope(envelope: FetchEnvelope, *, output_format: str, markdown_override: str | None = None) -> str:
    if output_format == "markdown":
        return markdown_override if markdown_override is not None else envelope.markdown or ""
    if output_format == "json":
        if envelope.article is None:
            raise ValueError("CLI json output requires the article payload.")
        return envelope.article.to_json()
    if envelope.article is None:
        raise ValueError("CLI both output requires the article payload.")
    markdown = markdown_override if markdown_override is not None else envelope.markdown
    return json.dumps({"article": envelope.article.to_dict(), "markdown": markdown}, ensure_ascii=False, indent=2)


def write_output(serialized: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(serialized)
        if not serialized.endswith("\n"):
            sys.stdout.write("\n")
        return
    Path(output).write_text(serialized, encoding="utf-8")


def prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise OutputDirectoryError(f"output directory path exists but is not a directory: {output_dir}")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputDirectoryError(f"could not create output directory {output_dir}: {exc}") from exc
    if not output_dir.is_dir():
        raise OutputDirectoryError(f"output directory path exists but is not a directory: {output_dir}")
    if not os.access(output_dir, os.W_OK | os.X_OK):
        raise OutputDirectoryError(f"output directory is not writable: {output_dir}")


def _has_explicit_option(argv: list[str], option: str) -> bool:
    return any(value == option or value.startswith(f"{option}=") for value in argv)


def _should_save_formatted_output_copy(
    args: argparse.Namespace,
    *,
    explicit_format: bool,
    output_is_explicit: bool,
    artifact_mode: ArtifactMode,
) -> bool:
    if not (explicit_format and output_is_explicit and args.output == "-" and args.output_dir):
        return False
    if artifact_mode == "all":
        return True
    return artifact_mode == "markdown-assets" and args.format == "markdown"


def _should_write_primary_output_to_output_dir(args: argparse.Namespace) -> bool:
    return bool(args.output_dir and not getattr(args, "output_is_explicit", False))


def _should_save_markdown_via_pipeline(
    args: argparse.Namespace,
    *,
    artifact_mode: ArtifactMode,
) -> bool:
    if args.save_markdown:
        return True
    if artifact_mode != "markdown-assets":
        return False
    primary_output_to_output_dir = getattr(args, "primary_output_to_output_dir", False)
    if args.output != "-" and not primary_output_to_output_dir:
        return False
    return not (
        args.format == "markdown"
        and (getattr(args, "save_output_copy", False) or primary_output_to_output_dir)
    )


def _formatted_output_filename(envelope: FetchEnvelope, *, output_format: str) -> str:
    meta = envelope.article.metadata if envelope.article is not None else envelope.metadata
    authors = list(meta.authors) if meta and meta.authors else None
    year = _extract_year(meta.published if meta else None)
    title = meta.title if meta else None
    stem = format_paper_stem(authors, year, title, doi=envelope.doi)
    suffix = {
        "markdown": ".md",
        "json": ".json",
        "both": ".both.json",
    }[output_format]
    return f"{stem}{suffix}"


def save_formatted_output_copy(
    envelope: FetchEnvelope,
    *,
    output_dir: Path,
    output_format: str,
    render: RenderOptions,
) -> Path:
    target = output_dir / _formatted_output_filename(envelope, output_format=output_format)
    markdown_override = (
        rewrite_markdown_asset_links(
            envelope.markdown or "",
            envelope,
            target_path=target,
            render=render,
        )
        if output_format in {"markdown", "both"}
        else None
    )
    serialized = serialize_envelope(envelope, output_format=output_format, markdown_override=markdown_override)
    return ArtifactStore.from_download_dir(output_dir).write_text_file(target, serialized, encoding="utf-8")


def parse_max_tokens(value: str) -> int | str:
    normalized = value.strip().lower()
    if normalized == "full_text":
        return "full_text"
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max_tokens must be a positive integer or 'full_text'.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("max_tokens must be greater than 0.")
    return parsed


def parse_batch_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("batch-concurrency must be an integer from 1 to 8.") from exc
    if not 1 <= parsed <= 8:
        raise argparse.ArgumentTypeError("batch-concurrency must be an integer from 1 to 8.")
    return parsed


def parse_positive_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer.")
    return parsed


def read_query_file(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read query file {path}: {exc}") from exc

    queries = []
    for line in lines:
        query = line.strip()
        if not query or query.startswith("#"):
            continue
        queries.append(query)
    if not queries:
        raise ValueError("query file did not contain any queries after filtering blank lines and comments.")
    return queries


def _compute_modes(args: argparse.Namespace) -> set[str]:
    modes = {"markdown"} if args.format == "markdown" else {"article"}
    save_markdown_to_disk = getattr(
        args,
        "save_markdown_to_disk",
        getattr(args, "save_markdown", False),
    )

    # Writing Markdown to a file or saving an extra Markdown copy needs the
    # structured article payload so we can rewrite local asset links relative
    # to the target path and decide whether full text was actually usable.
    if args.format == "markdown" and (
        args.output != "-"
        or getattr(args, "save_output_copy", False)
        or getattr(args, "primary_output_to_output_dir", False)
    ):
        modes.add("article")
    if args.format == "both" or save_markdown_to_disk:
        modes.add("markdown")
    if save_markdown_to_disk:
        modes.add("article")
    return modes


def _effective_artifact_mode(args: argparse.Namespace) -> ArtifactMode:
    if args.no_download:
        return "none"
    return args.artifact_mode


def exit_code_for_error(error: Exception) -> int:
    if isinstance(error, PaperFetchFailure):
        status = error.status
    elif isinstance(error, ProviderFailure):
        status = error.code
    else:
        status = ERROR

    if status == "ambiguous":
        return 2
    if status == NO_ACCESS:
        return 3
    if status == RATE_LIMITED:
        return 4
    return 1


def _error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
        }
    if isinstance(error, ProviderFailure):
        return {"status": error.code, "reason": error.message}
    return {"status": ERROR, "reason": str(error)}


def _render_options_from_args(args: argparse.Namespace) -> RenderOptions:
    return RenderOptions(
        include_refs=args.include_refs,
        asset_profile=args.asset_profile,
        max_tokens=args.max_tokens,
    )


def _markdown_save_spec(
    args: argparse.Namespace,
    *,
    output_dir: Path,
    render_options: RenderOptions,
) -> MarkdownSaveSpec | None:
    if not args.save_markdown_to_disk:
        return None
    return MarkdownSaveSpec(
        output_dir=output_dir,
        render=render_options,
        request_label="--save-markdown",
    )


def run_single_fetch(
    args: argparse.Namespace,
    *,
    query: str,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    transport=None,
) -> SingleFetchResult:
    modes = _compute_modes(args)
    render_options = _render_options_from_args(args)
    result = FetchPipeline(fetch_paper).run(
        build_fetch_pipeline_request(
            query=query,
            modes=modes,
            strategy=FetchStrategy(
                allow_metadata_only_fallback=True,
                asset_profile=args.asset_profile,
            ),
            render=render_options,
            env=dict(runtime_env),
            download_dir=output_dir,
            no_download=args.no_download,
            artifact_mode=artifact_mode,
            transport=transport,
            markdown_save=_markdown_save_spec(
                args,
                output_dir=output_dir,
                render_options=render_options,
            ),
        )
    )
    envelope = result.envelope
    if args.primary_output_to_output_dir:
        output_path = save_formatted_output_copy(
            envelope,
            output_dir=output_dir,
            output_format=args.format,
            render=render_options,
        )
        return SingleFetchResult(
            envelope=envelope,
            output_path=output_path,
            saved_markdown_path=result.saved_markdown_path,
        )

    markdown_override = (
        rewrite_markdown_asset_links(
            envelope.markdown or "",
            envelope,
            target_path=Path(args.output),
            render=render_options,
        )
        if args.output != "-" and args.format in {"markdown", "both"}
        else None
    )
    serialized = serialize_envelope(envelope, output_format=args.format, markdown_override=markdown_override)
    output_path = None
    if args.save_output_copy:
        output_path = save_formatted_output_copy(
            envelope,
            output_dir=output_dir,
            output_format=args.format,
            render=render_options,
        )
    write_output(serialized, args.output)
    if args.output != "-":
        output_path = Path(args.output)
    return SingleFetchResult(
        envelope=envelope,
        output_path=output_path,
        saved_markdown_path=result.saved_markdown_path,
    )


def _batch_success_payload(
    *,
    index: int,
    query: str,
    result: SingleFetchResult,
) -> dict[str, Any]:
    envelope = result.envelope
    return {
        "index": index,
        "query": query,
        "status": "ok",
        "doi": envelope.doi,
        "source": envelope.source,
        "output_path": str(result.output_path) if result.output_path is not None else None,
        "saved_markdown_path": str(result.saved_markdown_path) if result.saved_markdown_path is not None else None,
        "warnings": list(envelope.warnings),
        "error": None,
    }


def _batch_error_payload(*, index: int, query: str, error: Exception) -> dict[str, Any]:
    payload = _error_payload(error)
    warnings = list(getattr(error, "warnings", []) or [])
    return {
        "index": index,
        "query": query,
        "status": payload["status"],
        "doi": None,
        "source": None,
        "output_path": None,
        "saved_markdown_path": None,
        "warnings": warnings,
        "error": payload,
    }


def _run_batch_item(
    args: argparse.Namespace,
    *,
    index: int,
    query: str,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    transport,
) -> dict[str, Any]:
    try:
        result = run_single_fetch(
            args,
            query=query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            artifact_mode=artifact_mode,
            transport=transport,
        )
    except Exception as exc:  # noqa: BLE001 - batch mode records per-item failures and continues.
        return _batch_error_payload(index=index, query=query, error=exc)
    return _batch_success_payload(index=index, query=query, result=result)


def exit_code_for_batch_results(results: list[dict[str, Any]]) -> int:
    failure_statuses = {
        str(item.get("status"))
        for item in results
        if item.get("status") != "ok"
    }
    if not failure_statuses:
        return 0
    for status, exit_code in (
        (NO_ACCESS, 3),
        (RATE_LIMITED, 4),
        ("ambiguous", 2),
    ):
        if status in failure_statuses:
            return exit_code
    return 1


def run_batch_fetch(
    args: argparse.Namespace,
    *,
    queries: list[str],
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
) -> int:
    results_path = Path(args.batch_results) if args.batch_results else output_dir / "batch-results.jsonl"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    shared_transport = build_http_transport_for_context(
        runtime_env,
        download_dir=output_dir,
        cancel_check=None,
        artifact_mode=artifact_mode,
    )
    with results_path.open("w", encoding="utf-8") as results_file:
        with ThreadPoolExecutor(max_workers=args.batch_concurrency) as executor:
            futures = [
                executor.submit(
                    _run_batch_item,
                    args,
                    index=index,
                    query=query,
                    output_dir=output_dir,
                    runtime_env=runtime_env,
                    artifact_mode=artifact_mode,
                    transport=shared_transport,
                )
                for index, query in enumerate(queries, start=1)
            ]
            for future in as_completed(futures):
                item = future.result()
                results.append(item)
                results_file.write(json.dumps(item, ensure_ascii=False) + "\n")
                results_file.flush()
    return exit_code_for_batch_results(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch AI-friendly full text for a paper by DOI, URL, or title. "
            "Use CLOAKBROWSER_CDP_ENDPOINT for browser-backed providers."
        )
    )
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="DOI, paper landing URL, or title query")
    query_group.add_argument(
        "--query-file",
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
        help="JSONL summary path for --query-file batch mode. Defaults to <output-dir>/batch-results.jsonl.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default="markdown",
        help=(
            "Serialization format for stdout, --output, or the default file under --output-dir "
            "when --output is omitted."
        ),
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output destination. Use - for stdout; omit with --output-dir to write a default file there.",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory for the default formatted output when --output is omitted, plus Markdown, "
            "PDF fallback sources, and assets. Defaults to PAPER_FETCH_DOWNLOAD_DIR or the user "
            "data downloads directory."
        ),
    )
    parser.add_argument(
        "--artifact-mode",
        choices=("markdown-assets", "all", "none"),
        default="markdown-assets",
        help=(
            "Controls local artifact retention. markdown-assets saves Markdown plus assets from "
            "--asset-profile and keeps PDF fallback sources; all preserves raw provider/cache "
            "artifacts; none disables provider artifacts and assets."
        ),
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help=(
            "Alias for --artifact-mode none; disables provider artifacts and assets. "
            "Explicit --output, --output-dir primary output, or --save-markdown can still write files."
        ),
    )
    parser.add_argument(
        "--save-markdown",
        action="store_true",
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
        "--asset-profile",
        choices=("none", "body", "all"),
        default="body",
        help=(
            "Local content asset scope: none skips asset downloads, body saves body "
            "figures/tables/formula images, all also saves supplementary assets."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=parse_max_tokens,
        default="full_text",
        help=(
            "Markdown rendering budget: a positive integer token budget or full_text "
            "for the complete article (default: full_text)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-fetch {package_version()}",
        help="Show the installed paper-fetch version and exit.",
    )
    return parser


def build_auth_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-fetch auth",
        description="Manage publisher browser authentication state.",
    )
    parser.add_argument(
        "provider",
        choices=browser_auth_provider_names(),
        help="Browser-backed provider to open for manual authentication.",
    )
    parser.add_argument(
        "--url",
        help="Publisher URL to open. Defaults to a built-in sample article for the provider.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="CloakBrowser navigation timeout in milliseconds.",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this authentication run.",
    )
    parser.add_argument(
        "--state-json",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--env-file",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-env-write",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--wait-seconds",
        type=parse_positive_int_arg,
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser


def build_browser_preflight_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-fetch browser-preflight",
        description=(
            "Serially open browser-backed provider sample pages, save provider "
            "storage-state JSON on success, and report providers that need manual auth."
        ),
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=browser_auth_provider_names(),
        help=(
            "Browser-backed provider to preflight. May be repeated. "
            "Defaults to all browser-backed providers."
        ),
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="CloakBrowser navigation timeout in milliseconds.",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this preflight run.",
    )
    return parser


def _write_auth_result(provider_key: str, provider_label: str, result) -> None:
    sys.stdout.write(f"{provider_label} storage state: {result.storage_state_path}\n")
    profile_dir = getattr(result, "profile_dir", None)
    if profile_dir is not None:
        sys.stdout.write(f"{provider_label} profile dir: {profile_dir}\n")
    if result.env_written and result.env_file_path is not None:
        sys.stdout.write(f"Environment updated: {result.env_file_path}\n")
    else:
        sys.stdout.write("Environment update skipped.\n")
    if result.verified:
        sys.stdout.write(f"{provider_label} verification detected: yes\n")
    else:
        sys.stdout.write(f"{provider_label} verification detected: no\n")
        sys.stderr.write(
            f"Warning: {provider_label} article body was not detected before timeout; rerun `paper-fetch auth {provider_key}` if fetches still hit verification.\n"
        )
    if result.final_url:
        sys.stdout.write(f"Final URL: {result.final_url}\n")
    sys.stdout.write("Persistent browser state is optional; fetches still run without it.\n")


def _write_browser_preflight_results(results: list[BrowserPreflightResult]) -> None:
    sys.stdout.write("Browser preflight results:\n")
    for result in results:
        status = "ok" if result.ok else "failed"
        sys.stdout.write(f"- {status}: {result.provider_label} ({result.provider})\n")
        if result.final_url:
            sys.stdout.write(f"  Final URL: {result.final_url}\n")
        if result.storage_state_path is not None:
            sys.stdout.write(f"  Storage state: {result.storage_state_path}\n")
        if not result.ok:
            detail = result.message or result.reason or "Browser preflight failed."
            sys.stdout.write(f"  Reason: {detail}\n")


def _write_browser_preflight_failure_hints(results: list[BrowserPreflightResult]) -> None:
    failures = [result for result in results if not result.ok]
    if not failures:
        return
    sys.stderr.write("Browser preflight failed for these providers; run manual auth before retrying:\n")
    for result in failures:
        detail = result.message or result.reason or "Browser preflight failed."
        sys.stderr.write(
            f"- {result.provider_label} ({result.provider}): {detail} "
            f"Run: paper-fetch auth {result.provider}\n"
        )


def run_auth_command(raw_args: list[str]) -> int:
    parser = build_auth_parser()
    args = parser.parse_args(raw_args)
    uses_direct_storage_args = bool(
        args.state_json
        or args.env_file
        or args.no_env_write
        or args.wait_seconds is not None
    )
    if uses_direct_storage_args:
        parser.error(
            "--state-json, --env-file, --no-env-write, and --wait-seconds are unsupported for provider auth; "
            "auth saves provider-scoped storage-state. Use CLOAKBROWSER_PROFILE_DIR "
            "or CLOAKBROWSER_USER_DATA_DIR to override that location."
        )
    result = authenticate_provider_profile(
        provider=args.provider,
        target_url=args.url,
        timeout_ms=args.timeout_ms,
        browser_user_agent=args.browser_user_agent,
    )
    _write_auth_result(args.provider, provider_display_name(args.provider), result)
    return 0


def run_browser_preflight_command(raw_args: list[str]) -> int:
    parser = build_browser_preflight_parser()
    args = parser.parse_args(raw_args)
    results = run_browser_provider_preflight(
        providers=args.provider,
        timeout_ms=args.timeout_ms,
        browser_user_agent=args.browser_user_agent,
    )
    _write_browser_preflight_results(results)
    _write_browser_preflight_failure_hints(results)
    return 1 if any(not result.ok for result in results) else 0


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else list(argv)
    if raw_args[:1] == ["auth"]:
        try:
            return run_auth_command(raw_args[1:])
        except ProviderFailure as exc:
            sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
            return exit_code_for_error(exc)
    if raw_args[:1] == ["browser-preflight"]:
        try:
            return run_browser_preflight_command(raw_args[1:])
        except ProviderFailure as exc:
            sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
            return exit_code_for_error(exc)
    parser = build_parser()
    args = parser.parse_args(raw_args)
    artifact_mode = _effective_artifact_mode(args)
    args.output_is_explicit = _has_explicit_option(raw_args, "--output")
    batch_mode = bool(args.query_file)
    if batch_mode and args.output_is_explicit:
        parser.error("--output cannot be used with --query-file; batch mode writes one primary output per query under --output-dir.")
    if not batch_mode and args.batch_results:
        parser.error("--batch-results requires --query-file.")
    args.primary_output_to_output_dir = batch_mode or _should_write_primary_output_to_output_dir(args)
    args.save_output_copy = _should_save_formatted_output_copy(
        args,
        explicit_format=_has_explicit_option(raw_args, "--format"),
        output_is_explicit=args.output_is_explicit,
        artifact_mode=artifact_mode,
    )
    args.save_markdown_to_disk = _should_save_markdown_via_pipeline(
        args,
        artifact_mode=artifact_mode,
    )
    queries = None
    if batch_mode:
        try:
            queries = read_query_file(Path(args.query_file))
        except ValueError as exc:
            parser.error(str(exc))

    try:
        runtime_env = build_runtime_env()
        output_dir = Path(args.output_dir) if args.output_dir else resolve_cli_download_dir(runtime_env)
        prepare_output_dir(output_dir)
        if batch_mode:
            assert queries is not None
            return run_batch_fetch(
                args,
                queries=queries,
                output_dir=output_dir,
                runtime_env=runtime_env,
                artifact_mode=artifact_mode,
            )

        run_single_fetch(
            args,
            query=args.query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            artifact_mode=artifact_mode,
        )
        return 0
    except OutputDirectoryError as exc:
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)
    except PaperFetchFailure as exc:
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
