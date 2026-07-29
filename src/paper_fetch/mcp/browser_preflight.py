"""MCP adapter for the shared live browser preflight core."""

from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any
from collections.abc import Callable, Mapping

from mcp.server.mcpserver import Context
from mcp.types import CallToolResult

from ..provider_catalog import browser_preflight_provider_names
from ..browser_preflight import BrowserPreflightResult
from ..utils import normalize_text
from ._deps import MCPDeps, default_mcp_deps
from .batch import report_progress, run_blocking_call
from .results import _tool_result, error_payload_from_exception, with_schema_version
from .schemas import BrowserPreflightRequest

_CHALLENGE_REASON_CODES = {
    "cloudflare_challenge",
    "iop_captcha_challenge",
    "iop_radware_challenge",
}
_AUTH_REQUIRED_REASON_CODES = {
    "abstract_only",
    "no_access",
    "publisher_access_denied",
    "publisher_paywall",
    "redirected_to_abstract",
}
_CANCELLED_REASON_CODES = {"cancelled", "request_cancelled"}
_PREFLIGHT_STATUSES = (
    "ready",
    "challenge",
    "auth_required",
    "runtime_error",
    "cancelled",
)


def _preflight_status(result: BrowserPreflightResult) -> str:
    if result.ok:
        return "ready"
    reason_code = normalize_text(result.reason).lower()
    if reason_code in _CANCELLED_REASON_CODES:
        return "cancelled"
    if reason_code in _CHALLENGE_REASON_CODES:
        return "challenge"
    if reason_code in _AUTH_REQUIRED_REASON_CODES:
        return "auth_required"
    return "runtime_error"


def _next_action(provider: str, status: str) -> str:
    if status == "ready":
        return "run the requested fetch"
    if status in {"challenge", "auth_required"}:
        return f"paper-fetch auth {provider}"
    if status == "cancelled":
        return f"rerun browser_preflight for {provider}"
    return f"inspect provider_status for {provider}, fix local runtime, then retry"


def _storage_state_payload(
    result: BrowserPreflightResult,
    *,
    save_requested: bool,
) -> dict[str, object]:
    diagnostics = result.diagnostics if isinstance(result.diagnostics, Mapping) else {}
    trace = diagnostics.get("browser_runtime_trace")
    trace_payload = trace if isinstance(trace, Mapping) else {}
    save = trace_payload.get("storage_state_save")
    save_payload = save if isinstance(save, Mapping) else {}
    return {
        "path": str(result.storage_state_path)
        if result.storage_state_path is not None
        else None,
        "save_requested": save_requested,
        "attempted": bool(save_payload.get("attempted")),
        "saved": bool(save_payload.get("saved")),
        "reason": normalize_text(str(save_payload.get("reason") or "")) or None,
    }


def _result_payload(
    result: BrowserPreflightResult,
    *,
    detail: str,
    save_storage_state: bool,
) -> dict[str, Any]:
    status = _preflight_status(result)
    reason_code = normalize_text(result.reason).lower() or (
        "browser_preflight_ready" if result.ok else "browser_preflight_failed"
    )
    reason = normalize_text(result.message) or (
        "Publisher browser HTML preflight completed successfully."
        if result.ok
        else "Publisher browser HTML preflight failed."
    )
    compact = {
        "provider": result.provider,
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "next_action": _next_action(result.provider, status),
    }
    if detail == "compact":
        return compact
    return {
        **compact,
        "provider_label": result.provider_label,
        "ready": result.ok,
        "target_url": result.target_url,
        "final_url": result.final_url,
        "title": result.title,
        "storage_state": _storage_state_payload(
            result,
            save_requested=save_storage_state,
        ),
        "diagnostics": dict(result.diagnostics or {}),
    }


def _response_payload(
    results: list[BrowserPreflightResult],
    *,
    request: BrowserPreflightRequest,
) -> dict[str, Any]:
    result_payloads = [
        _result_payload(
            result,
            detail=request.detail,
            save_storage_state=request.save_storage_state,
        )
        for result in results
    ]
    counts = {
        status: sum(item["status"] == status for item in result_payloads)
        for status in _PREFLIGHT_STATUSES
    }
    if counts["cancelled"]:
        overall_status = "cancelled"
    elif counts["runtime_error"] or counts["auth_required"] or counts["challenge"]:
        overall_status = "partial" if counts["ready"] else "action_required"
    else:
        overall_status = "ready"
    return with_schema_version(
        {
            "status": overall_status,
            "diagnostic_scope": "live_browser_preflight",
            "provider_filter": request.provider,
            "detail": request.detail,
            "network_access": (
                "attempted"
                if any(item["status"] != "cancelled" for item in result_payloads)
                else "not_started"
            ),
            "storage_state_write_enabled": request.save_storage_state,
            "pdf_fallback_attempted": False,
            "auth_attempted": False,
            "results": result_payloads,
            "summary": {
                "requested": (
                    1
                    if request.provider is not None
                    else len(browser_preflight_provider_names())
                ),
                "completed": len(result_payloads),
                **counts,
            },
        }
    )


def browser_preflight_payload(
    *,
    provider: str | None = None,
    test_url: str | None = None,
    timeout_ms: int | None = None,
    browser_user_agent: str | None = None,
    storage_state_path: str | None = None,
    save_storage_state: bool = True,
    detail: str = "full",
    env: Mapping[str, str] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    on_result: Callable[[BrowserPreflightResult, int, int], None] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    """Run the existing preflight core and shape its MCP response."""

    request = BrowserPreflightRequest.model_validate(
        {
            "provider": provider,
            "test_url": test_url,
            "timeout_ms": timeout_ms,
            "browser_user_agent": browser_user_agent,
            "storage_state_path": storage_state_path,
            "save_storage_state": save_storage_state,
            "detail": detail,
        }
    )
    results = deps.run_browser_provider_preflight(
        providers=[request.provider] if request.provider is not None else None,
        timeout_ms=request.timeout_ms,
        browser_user_agent=request.browser_user_agent,
        env=env,
        cancel_check=cancel_check,
        target_url=request.test_url,
        storage_state_path=(
            Path(request.storage_state_path).expanduser()
            if request.storage_state_path is not None
            else None
        ),
        save_storage_state=request.save_storage_state,
        cancel_as_result=True,
        on_result=on_result,
    )
    return _response_payload(results, request=request)


async def browser_preflight_tool_async(
    *,
    provider: str | None = None,
    test_url: str | None = None,
    timeout_ms: int | None = None,
    browser_user_agent: str | None = None,
    storage_state_path: str | None = None,
    save_storage_state: bool = True,
    detail: str = "full",
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        request = BrowserPreflightRequest.model_validate(
            {
                "provider": provider,
                "test_url": test_url,
                "timeout_ms": timeout_ms,
                "browser_user_agent": browser_user_agent,
                "storage_state_path": storage_state_path,
                "save_storage_state": save_storage_state,
                "detail": detail,
            }
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total = (
        1 if request.provider is not None else len(browser_preflight_provider_names())
    )
    await report_progress(ctx, 0, total, "Starting live browser_preflight")
    cancelled = threading.Event()
    loop = asyncio.get_running_loop()

    def on_result(result: BrowserPreflightResult, completed: int, count: int) -> None:
        status = _preflight_status(result)
        future = asyncio.run_coroutine_threadsafe(
            report_progress(
                ctx,
                completed,
                count,
                f"Preflight {result.provider}: {status}",
            ),
            loop,
        )
        try:
            future.result(timeout=5)
        except Exception:
            return

    try:
        payload = await run_blocking_call(
            browser_preflight_payload,
            provider=request.provider,
            test_url=request.test_url,
            timeout_ms=request.timeout_ms,
            browser_user_agent=request.browser_user_agent,
            storage_state_path=request.storage_state_path,
            save_storage_state=request.save_storage_state,
            detail=request.detail,
            env=env,
            cancel_check=cancelled.is_set,
            on_result=on_result,
            deps=deps,
            cancel_event=cancelled,
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    await report_progress(
        ctx,
        payload["summary"]["completed"],
        total,
        "browser_preflight complete",
    )
    return _tool_result(payload, is_error=False)


__all__ = [
    "browser_preflight_payload",
    "browser_preflight_tool_async",
]
