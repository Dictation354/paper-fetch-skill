"""Handlers for non-fetch CLI subcommands."""

from __future__ import annotations

import contextlib
import json
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import paper_fetch.cli as cli_pkg

from .. import service, targeted_assets, update
from ..auth import ams_auth_coordination
from ..browser_preflight import (
    BrowserPreflightResult,
    BrowserPreflightRuntimeOptions,
    browser_preflight_next_action,
)
from ..catalog_payload import provider_catalog_payload
from ..delivery.lookup import lookup_receipt
from ..delivery.receipts import public_diagnostics
from ..reason_codes import ERROR
from ..utils import provider_display_name
from ..workflow.batch_routing import expected_doi_from_query
from ..workflow.batch_runner import run_batch
from .commands import (
    AuthCommand,
    BrowserPreflightCommand,
    CliUsageError,
    DoctorCommand,
    FetchAssetsCommand,
    LookupCommand,
    ResolutionCommand,
    UpdateCommand,
)
from .fetch_runner import _confirm_auth_on_stderr, _ensure_cli_ams_auth
from .manifest_io import _error_payload

if TYPE_CHECKING:
    from ..targeted_assets import AssetContext


def run_lookup_command(command: LookupCommand) -> int:
    receipt = lookup_receipt(command.doi, command.output_dir)
    result = (
        receipt if receipt is not None else {"status": "not_found", "doi": command.doi}
    )
    cli_pkg.sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0 if receipt is not None else 1


def run_resolution_command(command: ResolutionCommand) -> int:
    def lookup(item: tuple[int, str]) -> dict[str, Any]:
        index, query = item
        with cli_pkg.RuntimeContext(artifact_mode="none") as context:
            try:
                if command.mode == "resolve":
                    resolved = cli_pkg.resolve_paper(query, context=context)
                    payload = resolved.to_dict()
                    payload["status"] = (
                        "ambiguous"
                        if resolved.candidates and not resolved.doi
                        else "ok"
                    )
                    if (
                        not resolved.doi
                        and not resolved.landing_url
                        and not resolved.candidates
                    ):
                        payload["status"] = "unresolved"
                else:
                    payload = service.probe_has_fulltext(
                        query, context=context
                    ).to_dict()
                    payload["status"] = "ok"
                return {
                    "schema_version": 1,
                    "contract": f"paper-fetch/{command.mode}",
                    **public_diagnostics(payload),
                    "index": index,
                    "query": query,
                }
            except Exception as error:  # noqa: BLE001
                return {
                    "schema_version": 1,
                    "contract": f"paper-fetch/{command.mode}",
                    "index": index,
                    "query": query,
                    "status": "failed",
                    "error": public_diagnostics(_error_payload(error)),
                }

    result = run_batch(
        list(enumerate(command.queries, 1)),
        lookup,
        max_workers=command.batch_concurrency,
    )
    payloads = [item.value for item in result.results]
    for payload in payloads:
        cli_pkg.sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return int(
        any(payload is None or payload.get("status") != "ok" for payload in payloads)
    )


def _compact_asset_receipt(
    payload: dict[str, Any], *, output_dir: str | None, state: AssetContext | None
) -> dict[str, Any]:
    details = public_diagnostics(payload)
    results = []
    for original, item in zip(payload["results"], details["results"], strict=True):
        if "path" in original:
            # Local paths can contain URL punctuation and must still open on disk.
            item["path"] = original["path"]
        if item["status"] == "ok":
            results.append({key: item[key] for key in ("status", "asset_id", "path")})
        else:
            identity = "asset_id" if "asset_id" in item else "selector"
            results.append({key: item[key] for key in ("status", identity, "reason")})

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "contract": "paper-fetch/asset-receipt",
        "doi": details["doi"],
        "status": details["status"],
        "results": results,
        "details_path": None,
    }
    if "reason" in details:
        reason = " ".join(details["reason"].split())
        receipt["reason"] = reason if len(reason) <= 300 else reason[:297] + "..."

    try:
        if output_dir:
            directory = Path(output_dir).expanduser().resolve()
        elif state is not None:
            directory = state.temporary_dir()
        else:
            directory = Path(tempfile.mkdtemp(prefix="paper-fetch-images-"))
        path = cli_pkg.ArtifactStore.from_download_dir(directory).write_json_file(
            directory / f"fetch-assets-{uuid4().hex}.json", details, overwrite=False
        )
        receipt["details_path"] = str(path.resolve())
    except Exception:  # noqa: BLE001
        cli_pkg.sys.stderr.write("Warning: could not save fetch-assets details.\n")
    return receipt


def run_fetch_assets_command(command: FetchAssetsCommand) -> int:
    state: AssetContext | None = None
    output_dir = command.output_dir
    asset_ids = list(command.asset_ids) if command.asset_ids is not None else None
    urls = list(command.urls) if command.urls is not None else None
    try:
        with cli_pkg.RuntimeContext(artifact_mode="none") as runtime:
            if command.manifest is not None:
                state = targeted_assets.context_from_manifest(command.manifest)
            else:
                assert command.query is not None
                state = targeted_assets.context_from_query(command.query, runtime)
            # CLI files outlive this process so a host reader can open the paths.
            state.cleanup_temporary = output_dir is not None
            if state.provider == "ams" and targeted_assets.selected_assets_need_network(
                state, asset_ids=asset_ids, urls=urls, kind=command.kind
            ):
                _ensure_cli_ams_auth(command, runtime)
            payload = targeted_assets.fetch_selected_assets(
                state,
                asset_ids=asset_ids,
                urls=urls,
                kind=command.kind,
                output_dir=output_dir,
                overwrite=command.overwrite,
                runtime=runtime,
            )
            payload["query"] = command.query
            if not command.compact:
                cli_pkg.sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
                return 0 if payload["status"] == "ok" else 1
        exit_code = 0 if payload["status"] == "ok" else 1
    except Exception as error:  # noqa: BLE001
        payload = _error_payload(error)
        exit_code = 1
        if not command.compact:
            cli_pkg.sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            cli_pkg.sys.stderr.write(str(error) + "\n")
            return exit_code
        doi = state.doi if state is not None else None
        if state is None and command.query:
            with contextlib.suppress(ValueError):
                doi = expected_doi_from_query(command.query)
        payload.update(doi=doi, results=[], query=command.query)
    receipt = _compact_asset_receipt(payload, output_dir=output_dir, state=state)
    cli_pkg.sys.stdout.write(json.dumps(receipt, separators=(",", ":")) + "\n")
    return exit_code


def _write_doctor_human(report: Mapping[str, Any]) -> None:
    provider_report = report.get("provider_status")
    providers = (
        provider_report.get("providers", [])
        if isinstance(provider_report, Mapping)
        else []
    )
    cli_pkg.sys.stdout.write(
        "Paper Fetch doctor: static configuration and local dependencies\n"
    )
    cli_pkg.sys.stdout.write(f"Status: {report.get('status', ERROR)}\n")
    cli_pkg.sys.stdout.write("Live publisher or browser-page checks: not run\n")
    for item in providers:
        if not isinstance(item, Mapping):
            continue
        provider_name = item.get("provider", "unknown")
        status = item.get("status", ERROR)
        reason = item.get("reason")
        action = item.get("suggested_action")
        cli_pkg.sys.stdout.write(f"- {provider_name}: {status}")
        if reason:
            cli_pkg.sys.stdout.write(f" — {reason}")
        cli_pkg.sys.stdout.write("\n")
        if action:
            cli_pkg.sys.stdout.write(f"  Next: {action}\n")
    cli_pkg.sys.stdout.write(
        "For real browser-path health, run browser-preflight; if authentication is "
        "required, run auth explicitly.\n"
    )


def run_doctor_command(command: DoctorCommand) -> int:
    if command.catalog:
        report = provider_catalog_payload()
        if command.output_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"paper-fetch {report['tool_version']} catalog")
            print(json.dumps(report["runtime"], ensure_ascii=False))
            for provider in report["providers"]:
                print(
                    f"{provider['provider']}: {provider['display_name']} targets={','.join(provider['capabilities']['targets'])}"
                )
        return 0
    try:
        report = cli_pkg.build_doctor_payload(
            provider=command.provider,
            group=command.group,
            detail=command.detail,
            env_file=command.env_file,
        )
    except ValueError as error:
        raise CliUsageError(str(error), command="doctor") from error
    if command.output_json:
        cli_pkg.sys.stdout.write(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    else:
        _write_doctor_human(report)
    status = report.get("status")
    if status == "ready":
        return 0
    if status == ERROR:
        return 2
    return 1


def _write_auth_result(provider_key: str, provider_label: str, result: Any) -> None:
    if result.profile_dir is not None:
        cli_pkg.sys.stdout.write(
            f"{provider_label} profile dir: {result.profile_dir}\n"
        )
    if result.verified:
        cli_pkg.sys.stdout.write(f"{provider_label} verification detected: yes\n")
    else:
        cli_pkg.sys.stdout.write(f"{provider_label} verification detected: no\n")
        cli_pkg.sys.stderr.write(
            f"Warning: {provider_label} article body was not detected before timeout; rerun `paper-fetch auth {provider_key}` if fetches still hit verification.\n"
        )
    if result.final_url:
        cli_pkg.sys.stdout.write(f"Final URL: {result.final_url}\n")
    cli_pkg.sys.stdout.write(
        f"{provider_label} native profile verified: {bool(result.verified)}\n"
    )


def run_auth_command(command: AuthCommand) -> int:
    runtime_env = cli_pkg.build_runtime_env()
    with cli_pkg.RuntimeContext(env=runtime_env) as context:
        coordination = (
            ams_auth_coordination(runtime_env, cancel=context.raise_if_cancelled)
            if command.provider == "ams"
            else contextlib.nullcontext()
        )
        with coordination:
            result = cli_pkg.authenticate_provider_profile(
                provider=command.provider,
                target_url=command.url,
                timeout_ms=command.timeout_ms,
                browser_user_agent=command.browser_user_agent,
                env=runtime_env,
                confirm=lambda prompt: _confirm_auth_on_stderr(prompt, context),
            )
    _write_auth_result(
        command.provider, provider_display_name(command.provider), result
    )
    return 0


def _browser_preflight_failure_details(
    result: BrowserPreflightResult,
) -> Mapping[str, Any]:
    diagnostics = result.diagnostics or {}
    browser_failure = diagnostics.get("browser_failure")
    if isinstance(browser_failure, Mapping):
        return browser_failure
    trace = diagnostics.get("trace")
    if isinstance(trace, Mapping):
        browser_failure = trace.get("browser_failure")
        if isinstance(browser_failure, Mapping):
            return browser_failure
    return {}


def _write_browser_preflight_results(results: list[BrowserPreflightResult]) -> None:
    cli_pkg.sys.stdout.write("Browser preflight results:\n")
    for result in results:
        status = "ok" if result.ready else result.status
        cli_pkg.sys.stdout.write(
            f"- {status}: {result.provider_label} ({result.provider})\n"
        )
        if result.final_url:
            cli_pkg.sys.stdout.write(f"  Final URL: {result.final_url}\n")
        if result.profile_dir is not None:
            cli_pkg.sys.stdout.write(f"  Profile directory: {result.profile_dir}\n")
        if not result.ready:
            detail = result.message or "Browser preflight failed."
            cli_pkg.sys.stdout.write(f"  Code: {result.reason_code}\n")
            browser_failure = _browser_preflight_failure_details(result)
            stage = result.stage or str(browser_failure.get("stage") or "").strip()
            if stage:
                cli_pkg.sys.stdout.write(f"  Stage: {stage}\n")
            exit_code = browser_failure.get("exit_code")
            if exit_code is not None:
                cli_pkg.sys.stdout.write(f"  Exit code: {exit_code}\n")
            stderr_summary = str(browser_failure.get("stderr_summary") or "").strip()
            if stderr_summary:
                cli_pkg.sys.stdout.write(
                    f"  Browser runtime stderr: {stderr_summary}\n"
                )
            diagnostic_path = str(browser_failure.get("diagnostic_path") or "").strip()
            if diagnostic_path:
                cli_pkg.sys.stdout.write(f"  Diagnostic artifact: {diagnostic_path}\n")
            cli_pkg.sys.stdout.write(f"  Reason: {detail}\n")


def _write_browser_preflight_failure_hints(
    results: list[BrowserPreflightResult],
) -> None:
    failures = [result for result in results if not result.ready]
    if not failures:
        return
    cli_pkg.sys.stderr.write("Browser preflight needs attention for these providers:\n")
    for result in failures:
        detail = result.message or "Browser preflight failed."
        browser_failure = _browser_preflight_failure_details(result)
        artifact = str(browser_failure.get("diagnostic_path") or "").strip()
        if not artifact:
            artifact = str(
                (result.diagnostics or {}).get("diagnostic_path") or ""
            ).strip()
        artifact_hint = f" Diagnostic artifact: {artifact}." if artifact else ""
        action = browser_preflight_next_action(result.provider, result.status)
        cli_pkg.sys.stderr.write(
            f"- {result.provider_label} ({result.provider}) "
            f"[{result.status}/{result.reason_code}]: {detail}.{artifact_hint} "
            f"Next action: {action}.\n"
        )


def run_browser_preflight_command(command: BrowserPreflightCommand) -> int:
    runtime_env = cli_pkg.build_runtime_env()
    results = cli_pkg.run_browser_provider_preflight(
        providers=list(command.providers) if command.providers is not None else None,
        timeout_ms=command.timeout_ms,
        browser_user_agent=command.browser_user_agent,
        runtime_options=BrowserPreflightRuntimeOptions(
            env=runtime_env,
            download_dir=command.download_dir,
            artifact_mode=command.artifact_mode,
        ),
    )
    _write_browser_preflight_results(results)
    _write_browser_preflight_failure_hints(results)
    return 1 if any(not result.ready for result in results) else 0


def run_update_command(_command: UpdateCommand) -> int:
    return update.run_update()
