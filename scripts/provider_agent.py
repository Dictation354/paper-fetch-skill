#!/usr/bin/env python3
"""Agent-facing provider onboarding wrapper.

This module translates add/continue/status/doctor intents into the existing
manifest-driven coordinator. It does not own a separate DAG or state file.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from typing import Any
from collections.abc import Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import backfill_access_reviews  # noqa: E402
import onboard_from_manifests as coordinator  # noqa: E402


DEFAULT_OUTPUT_DIR_TEMPLATE = ".paper-fetch-runs/{provider}-onboarding"


def _provider_slug(provider: str) -> str:
    return coordinator._provider_slug(provider)


def _state_path(value: str) -> Path:
    return coordinator._state_path(value)


def _load_state(path: Path) -> dict[str, Any]:
    return coordinator._load_state(path)


def _manifest_exists(provider: str) -> bool:
    return (_repo_root() / coordinator.default_manifest_path(provider)).exists()


def _repo_root() -> Path:
    return coordinator._repo_root()


def _output_dir(provider: str, value: str | None) -> str:
    return value or DEFAULT_OUTPUT_DIR_TEMPLATE.format(provider=provider)


def _capture_call(
    func: Callable[[argparse.Namespace], int], args: argparse.Namespace
) -> coordinator.ToolError | None:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            func(args)
    except coordinator.ToolError as exc:
        return exc
    return None


def _capture_backfill(argv: list[str]) -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        backfill_access_reviews.main(argv)


def _access_review_summary(provider: str) -> dict[str, Any]:
    return coordinator._access_review_summary(provider)


def _ensure_access_review_draft(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> None:
    access = _access_review_summary(provider)
    if access.get("status") != "missing":
        return
    if not domain:
        return
    argv = ["--provider", provider, "--domain", domain, "--write"]
    if doi_prefix:
        argv.extend(["--doi-prefix", doi_prefix])
    _capture_backfill(argv)


def _build_summary(
    *,
    provider: str,
    target: str,
    state_path: Path,
    command: str,
    error: coordinator.ToolError | None = None,
    resume_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _load_state(state_path)
    payload = coordinator.build_agent_user_summary(
        provider=provider,
        state=state,
        target=target,
        state_path=state_path,
    )
    payload["command"] = command
    if error is not None:
        payload["error"] = {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
            "details": error.details,
        }
    if resume_plan is not None:
        payload["resume_plan"] = resume_plan
    return payload


def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(coordinator.render_agent_user_summary_markdown(payload), end="")
        resume_plan = payload.get("resume_plan")
        if isinstance(resume_plan, dict):
            print()
            print("诊断:")
            print(f"- resumable: {resume_plan.get('resumable')}")
            if resume_plan.get("next_task"):
                print(f"- next_task: {resume_plan.get('next_task')}")
            blockers = resume_plan.get("blockers")
            if isinstance(blockers, list) and blockers:
                for blocker in blockers:
                    print(f"- blocker: {blocker}")


def _run_until(
    *,
    provider: str,
    target: str,
    state_path: Path,
    output_dir: str,
    domain: str | None = None,
    doi_prefix: str | None = None,
) -> coordinator.ToolError | None:
    target_step = coordinator.agent_target_step(target)
    manifest_path = coordinator.default_manifest_path(provider)
    if (_repo_root() / manifest_path).exists():
        args = argparse.Namespace(
            provider=None,
            manifest=manifest_path,
            domain=None,
            doi_prefix=None,
            until=target_step,
            output_dir=output_dir,
            state=str(state_path),
        )
    else:
        args = argparse.Namespace(
            provider=provider,
            manifest=None,
            domain=domain,
            doi_prefix=doi_prefix,
            until=target_step,
            output_dir=output_dir,
            state=str(state_path),
        )
    return _capture_call(coordinator.run_run, args)


def _provider_state(provider: str, state: dict[str, Any]) -> dict[str, Any] | None:
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    value = providers.get(provider) if isinstance(providers, dict) else None
    return value if isinstance(value, dict) else None


def _target_complete(provider_state: dict[str, Any] | None, target: str) -> bool:
    if not isinstance(provider_state, dict):
        return False
    return coordinator._agent_target_complete(provider_state, target)


def cmd_add(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    target = coordinator.normalize_agent_target(args.target)
    state_path = _state_path(args.state)
    output_dir = _output_dir(provider, args.output_dir)

    if not args.domain and not _manifest_exists(provider):
        payload = _build_summary(
            provider=provider,
            target=target,
            state_path=state_path,
            command="add",
        )
        payload["phase"] = "intake"
        payload["why_stopped"] = "缺少 domain，且没有现成 manifest 可以继续。"
        payload["next_user_action"] = (
            f"请提供 domain，例如：添加 {provider} provider，domain 是 example.org"
        )
        _emit(payload, args.format)
        return 2

    _ensure_access_review_draft(
        provider=provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
    )
    access = _access_review_summary(provider)
    error = None
    if access.get("approved"):
        error = _run_until(
            provider=provider,
            target=target,
            state_path=state_path,
            output_dir=output_dir,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
        )
    payload = _build_summary(
        provider=provider,
        target=target,
        state_path=state_path,
        command="add",
        error=error,
    )
    _emit(payload, args.format)
    return 1 if error is not None else 0


def cmd_continue(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    target = coordinator.normalize_agent_target(args.target)
    state_path = _state_path(args.state)
    output_dir = _output_dir(provider, args.output_dir)
    state = _load_state(state_path)
    provider_state = _provider_state(provider, state)
    resume_plan = None
    error = None

    if _target_complete(provider_state, target):
        payload = _build_summary(
            provider=provider,
            target=target,
            state_path=state_path,
            command="continue",
        )
        _emit(payload, args.format)
        return 0

    access = _access_review_summary(provider)
    if access.get("approved"):
        if (
            isinstance(provider_state, dict)
            and provider_state.get("status") == "blocked"
        ):
            resume_plan = coordinator.plan_resume_blocked(provider_state)
            if resume_plan.get("resumable"):
                error = _capture_call(
                    coordinator.run_resume_blocked,
                    argparse.Namespace(
                        provider=provider,
                        dry_run=False,
                        until=coordinator.agent_target_step(target),
                        output_dir=output_dir,
                        state=str(state_path),
                    ),
                )
        elif _manifest_exists(provider):
            error = _run_until(
                provider=provider,
                target=target,
                state_path=state_path,
                output_dir=output_dir,
            )
    payload = _build_summary(
        provider=provider,
        target=target,
        state_path=state_path,
        command="continue",
        error=error,
        resume_plan=resume_plan,
    )
    _emit(payload, args.format)
    return 1 if error is not None else 0


def cmd_status(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    target = coordinator.normalize_agent_target(args.target)
    state_path = _state_path(args.state)
    payload = _build_summary(
        provider=provider,
        target=target,
        state_path=state_path,
        command="status",
    )
    _emit(payload, args.format)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    target = coordinator.normalize_agent_target(args.target)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _provider_state(provider, state)
    resume_plan = (
        coordinator.plan_resume_blocked(provider_state)
        if isinstance(provider_state, dict)
        and provider_state.get("status") == "blocked"
        else None
    )
    payload = _build_summary(
        provider=provider,
        target=target,
        state_path=state_path,
        command="doctor",
        resume_plan=resume_plan,
    )
    _emit(payload, args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agent-facing wrapper for provider onboarding."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--provider", required=True, help="provider name")
        subparser.add_argument(
            "--target",
            choices=tuple(coordinator.AGENT_TARGET_STEPS),
            default="local-ready",
            help="target tier; defaults to local-ready",
        )
        subparser.add_argument(
            "--format",
            choices=("markdown", "json"),
            default="markdown",
            help="output format",
        )
        subparser.add_argument(
            "--output-dir",
            help="directory for DAG, briefs, and worker logs",
        )
        subparser.add_argument(
            "--state",
            default=coordinator.DEFAULT_STATE_PATH,
            help="coordinator state JSON path",
        )

    add = subparsers.add_parser(
        "add", help="add a provider from natural-language seeds"
    )
    add_common(add)
    add.add_argument("--domain", help="provider domain seed")
    add.add_argument("--doi-prefix", help="optional DOI prefix seed")
    add.set_defaults(func=cmd_add)

    cont = subparsers.add_parser(
        "continue", help="continue an existing provider onboarding"
    )
    add_common(cont)
    cont.set_defaults(func=cmd_continue)

    status = subparsers.add_parser("status", help="show user-facing onboarding status")
    add_common(status)
    status.set_defaults(func=cmd_status)

    doctor = subparsers.add_parser(
        "doctor", help="diagnose why provider onboarding is stuck"
    )
    add_common(doctor)
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except coordinator.ToolError as exc:
        provider = _provider_slug(
            getattr(args, "provider", "") or exc.provider or "unknown"
        )
        target = coordinator.normalize_agent_target(
            getattr(args, "target", "local-ready")
        )
        state_path = _state_path(getattr(args, "state", coordinator.DEFAULT_STATE_PATH))
        payload = _build_summary(
            provider=provider,
            target=target,
            state_path=state_path,
            command=getattr(args, "command", "unknown"),
            error=exc,
        )
        _emit(payload, getattr(args, "format", "markdown"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
