# ruff: noqa
from __future__ import annotations


def _command_failed(
    command: list[str], completed: subprocess.CompletedProcess[str]
) -> bool:
    argv = _command_argv(command)
    if len(argv) >= 2 and argv[0] == "git" and argv[1] == "grep":
        return completed.returncode != 1
    return completed.returncode != 0


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _command_argv(command: list[str]) -> list[str]:
    return [
        part for part in command if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", part)
    ]


def _is_cleaning_contract_command(command: list[str]) -> bool:
    argv = _command_argv(command)
    return (
        len(argv) >= 3
        and argv[0] == "python3"
        and argv[1] == "scripts/propose_cleaning_chain.py"
        and "--check-contract" in argv
    )


def _failure_code_for_task(task: str, command: list[str] | None = None) -> str:
    if command is not None and _is_cleaning_contract_command(command):
        return "MARKDOWN_CONTRACT_DRIFT"
    if task == SNAPSHOT_EXPECTED_STEP:
        return "EXPECTED_SNAPSHOT_FAILED"
    if task == "global-lint":
        return "GLOBAL_LINT_FAILED"
    if task == SHARED_INTEGRATION_STEP:
        return "SHARED_INTEGRATION_FAILED"
    if task == "provider-local-acceptance":
        return "PROVIDER_LOCAL_ACCEPTANCE_FAILED"
    if task == "validate-manifest":
        return "MANIFEST_SCHEMA_INVALID"
    if task == ACCESS_PREFLIGHT_STEP:
        return "ACCESS_REVIEW_NOT_FOUND"
    return "LOCAL_CHECK_FAILED"


def _load_failure_recovery_entries() -> dict[str, dict[str, Any]]:
    path = _repo_root() / FAILURE_RECOVERY_PATH
    entries: dict[str, dict[str, Any]] = {}
    current_code: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## Signal: "):
            current_code = line.removeprefix("## Signal: ").strip()
            entries[current_code] = {}
            continue
        if current_code is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {"diagnosis", "action", "retryable"}:
            entries[current_code][key] = value
    for entry in entries.values():
        retryable = entry.get("retryable")
        if isinstance(retryable, str):
            entry["retryable"] = retryable.lower() == "true"
    return entries


def _latest_failure(provider_state: dict[str, Any]) -> dict[str, Any] | None:
    runs = provider_state.get("runs")
    if not isinstance(runs, dict):
        return None
    ordered_tasks: list[str] = []
    task_statuses = provider_state.get("task_statuses")
    task_statuses = task_statuses if isinstance(task_statuses, dict) else {}
    current_step = provider_state.get("current_step")
    if isinstance(current_step, str) and task_statuses.get(current_step) != "completed":
        ordered_tasks.append(current_step)
    steps = provider_state.get("steps")
    if isinstance(steps, list):
        ordered_tasks.extend(
            str(step)
            for step in reversed(steps)
            if task_statuses.get(step) in {"failed", "blocked"}
        )
    ordered_tasks.extend(
        str(task)
        for task, status in task_statuses.items()
        if status in {"failed", "blocked"}
        and (not isinstance(steps, list) or task not in steps)
    )
    seen: set[str] = set()
    for task in ordered_tasks:
        if task in seen:
            continue
        seen.add(task)
        run = runs.get(task)
        if not isinstance(run, dict):
            continue
        failure = run.get("failure")
        if isinstance(failure, dict):
            return {"task": task, **failure}
    return None


def _access_review_summary(provider: str) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    path = _repo_root() / default_access_review_path(provider_name)
    if not path.exists():
        return {
            "status": "missing",
            "path": default_access_review_path(provider_name),
            "may_continue": False,
            "approved": False,
        }
    try:
        review = _load_access_review(provider_name)
    except ToolError as exc:
        return {
            "status": "schema_invalid",
            "path": default_access_review_path(provider_name),
            "may_continue": False,
            "approved": False,
            "error_code": exc.code,
        }
    status = str(review.get("status") or "unknown")
    may_continue = review.get("may_continue") is True
    approved = status == "approved" and may_continue
    if not approved and review.get("reviewed_by") == "operator-required":
        status_label = "draft"
    else:
        status_label = "approved" if approved else status
    return {
        "status": status_label,
        "path": default_access_review_path(provider_name),
        "may_continue": may_continue,
        "approved": approved,
        "reviewed_by": review.get("reviewed_by"),
        "legal_access_mode": (
            review.get("legal_access", {}).get("mode")
            if isinstance(review.get("legal_access"), dict)
            else None
        ),
        "allowed_runtimes": review.get("allowed_runtimes"),
    }


OPERATOR_REQUIRED_FAILURE_CODES = {
    "ACCESS_REVIEW_NOT_FOUND",
    "ACCESS_REVIEW_SCHEMA_INVALID",
    "ACCESS_REVIEW_NOT_APPROVED",
    "BROWSER_RUNTIME_REQUIRED",
    "CHALLENGE_DETECTED",
    "WORKER_MODIFIED_FORBIDDEN_FILE",
    "MANIFEST_PROVIDER_CONFLICT",
    "DISCOVERY_RETRY_EXHAUSTED",
    "TASK_RETRY_EXHAUSTED",
}

AGENT_TARGET_STEPS = {
    "local-ready": "provider-local-acceptance",
    "merge-ready": "merge-ready",
}

AGENT_FAILURE_USER_ACTIONS = {
    "ACCESS_REVIEW_NOT_FOUND": (
        "我需要生成或定位 access review 草稿；你稍后只需确认访问策略。"
    ),
    "ACCESS_REVIEW_NOT_APPROVED": (
        "我停在访问批准点；请人工确认 access review 后告诉我继续。"
    ),
    "ACCESS_REVIEW_SCHEMA_INVALID": (
        "access review 文件结构不合法；我会指出字段，用户只需确认真实访问策略。"
    ),
    "BROWSER_RUNTIME_REQUIRED": (
        "当前路线需要 browser runtime；请决定是否允许，不能默认绕过。"
    ),
    "HTTP_FORBIDDEN": (
        "当前样本被拒绝；若 access review 允许 browser 我会重试，否则我会换 DOI 或停下说明。"
    ),
    "HTTP_RATE_LIMITED": (
        "这是暂态或限流；我会按 retry budget 重试，耗尽后给出等待或换样本建议。"
    ),
    "NETWORK_TRANSIENT": (
        "这是暂态网络失败；我会按 retry budget 重试，耗尽后给出等待或换样本建议。"
    ),
    "CHALLENGE_DETECTED": (
        "遇到 challenge/CAPTCHA；我不会绕过，只能按 access review 重试或换样本。"
    ),
    "UNSUITABLE_DOI_SAMPLE": (
        "这个 DOI 不适合当前 purpose；我会只替换这个 purpose 的样本。"
    ),
    "NON_PDF_FALLBACK_CONTENT": (
        "PDF fallback 样本不是 PDF；我会重新找 pdf_fallback 样本。"
    ),
    "ACCESS_GATE_CAPTURED": ("样本捕获到 access gate；我会替换失败 purpose 的 DOI。"),
    "EMPTY_ARTICLE_SHELL": ("样本捕获到空文章壳；我会替换失败 purpose 的 DOI。"),
    "MARKDOWN_CONTRACT_DRIFT": (
        "Markdown contract 与当前 fixture 不一致；我会先刷新 cleaning proposal 或回到实现修复。"
    ),
    "MARKDOWN_QUALITY_FAILED": (
        "当前 Markdown 还有 blocking issue；我会运行 repair loop，失败后给出具体 artifact。"
    ),
    "MARKDOWN_QUALITY_REPAIR_FAILED": (
        "自动修复预算耗尽；需要人工看最后一轮 quality report 和 repair logs。"
    ),
    "PROVIDER_LOCAL_ACCEPTANCE_FAILED": (
        "provider-local 验证失败；我会修 provider-owned 实现或测试，并汇报失败命令。"
    ),
    "SHARED_INTEGRATION_FAILED": (
        "shared integration 验证失败；我会只修有 manifest/fixture/test 证据支持的 shared surface。"
    ),
    "GLOBAL_LINT_FAILED": ("全局本地检查失败；我只修当前 provider 引入的问题。"),
    "WORKER_MODIFIED_FORBIDDEN_FILE": (
        "worker 修改了不该改的文件；我会停下保护工作区并说明越界路径。"
    ),
    "DISCOVERY_RETRY_EXHAUSTED": (
        "自动 discovery 重试耗尽；我会列出失败 task、最近命令、artifact 路径和需要的新事实。"
    ),
    "TASK_RETRY_EXHAUSTED": (
        "自动重试耗尽；我会列出失败 task、最近命令、artifact 路径和需要的新事实。"
    ),
}


def _latest_markdown_quality_repair(
    provider_state: dict[str, Any],
) -> dict[str, Any] | None:
    repairs = provider_state.get("repairs")
    if not isinstance(repairs, dict):
        return None
    markdown_repairs = repairs.get("markdown_quality")
    if not isinstance(markdown_repairs, list) or not markdown_repairs:
        return None
    latest = markdown_repairs[-1]
    return latest if isinstance(latest, dict) else None


def diagnose_provider_state(provider_state: dict[str, Any]) -> dict[str, Any]:
    provider = _provider_slug(str(provider_state.get("provider") or "unknown"))
    recovery_entries = _load_failure_recovery_entries()
    failure = _latest_failure(provider_state)
    failure_code = str(failure.get("code")) if failure and failure.get("code") else None
    recovery = recovery_entries.get(failure_code or "", {})
    retryable = (
        bool(recovery.get("retryable")) if failure_code in recovery_entries else None
    )
    operator_required = (
        failure_code in OPERATOR_REQUIRED_FAILURE_CODES
        if failure_code is not None
        else False
    )
    access = _access_review_summary(provider)
    if not access["approved"] and provider_state.get("status") == "blocked":
        operator_required = True
    return {
        "provider": provider,
        "status": provider_state.get("status"),
        "current_step": provider_state.get("current_step"),
        "failure": {
            "task": failure.get("task") if failure else None,
            "code": failure_code,
            "retryable": retryable,
            "diagnosis": recovery.get("diagnosis"),
            "action": recovery.get("action"),
        },
        "access_review": access,
        "recent_markdown_quality_repair": _latest_markdown_quality_repair(
            provider_state
        ),
        "operator_required": operator_required,
    }


def plan_resume_blocked(provider_state: dict[str, Any]) -> dict[str, Any]:
    diagnosis = diagnose_provider_state(provider_state)
    provider = diagnosis["provider"]
    failure = diagnosis["failure"]
    code = failure.get("code")
    task = failure.get("task") or provider_state.get("current_step")
    blockers: list[str] = []
    if provider_state.get("status") != "blocked":
        blockers.append("provider status is not blocked")
    if not isinstance(task, str) or not task:
        blockers.append("no failed or current task is recorded")
    if failure.get("retryable") is not True:
        blockers.append(f"failure code is not retryable: {code}")
    access = diagnosis["access_review"]
    if not access.get("approved"):
        blockers.append(f"access review is not approved: {access.get('status')}")
    if code in OPERATOR_REQUIRED_FAILURE_CODES:
        blockers.append(f"operator action required for failure code: {code}")
    if code == "UNSUITABLE_DOI_SAMPLE":
        blockers.append(
            "failed DOI purpose must be replaced or explicitly approved before retry"
        )
    if code == "NON_PDF_FALLBACK_CONTENT":
        blockers.append("failed pdf_fallback DOI sample must be replaced before retry")
    if code == "BROWSER_RUNTIME_REQUIRED":
        blockers.append("browser runtime must be configured and approved before retry")
    resumable = not blockers
    next_task = IMPLEMENT_STEP if code == "MARKDOWN_CONTRACT_DRIFT" else task
    return {
        "provider": provider,
        "resumable": resumable,
        "next_task": next_task if isinstance(next_task, str) else None,
        "operator_required": bool(blockers),
        "blockers": blockers,
        "diagnosis": diagnosis,
    }


def _source_from_provider_state(provider_state: dict[str, Any]) -> OnboardingSource:
    provider = _provider_slug(str(provider_state["provider"]))
    manifest = str(provider_state.get("manifest") or default_manifest_path(provider))
    include_discovery = DISCOVER_STEP in set(provider_state.get("steps") or [])
    manifest_yaml: str | None = None
    if not include_discovery:
        manifest_path = _repo_root() / manifest
        if manifest_path.exists():
            manifest_yaml = manifest_path.read_text(encoding="utf-8")
    return OnboardingSource(
        provider=provider,
        manifest=manifest,
        include_discovery=include_discovery,
        manifest_yaml=manifest_yaml,
    )


def _execute_run_loop(
    *,
    source: OnboardingSource,
    output_dir: Path,
    state_path: Path,
    state: dict[str, Any],
    provider_state: dict[str, Any],
    until: str,
    domain: str | None,
    doi_prefix: str | None,
) -> dict[str, Any]:
    _run_artifacts(
        source=source,
        output_dir=output_dir,
        domain=domain,
        doi_prefix=doi_prefix,
    )
    state["agent_cli"] = _worker_dispatcher_label() or state.get("agent_cli")
    executed: list[str] = []
    try:
        while True:
            task = _next_pending_step(provider_state)
            if task is None:
                failed_steps = _failed_steps(provider_state)
                if failed_steps:
                    failed_task = failed_steps[0]
                    provider_state["current_step"] = failed_task
                    provider_state["status"] = "blocked"
                    state["active_provider"] = source.provider
                    _write_json(state_path, state)
                    failure = (
                        provider_state.get("runs", {})
                        .get(failed_task, {})
                        .get("failure", {})
                    )
                    raise ToolError(
                        str(failure.get("code") or "TASK_PREVIOUSLY_FAILED"),
                        f"onboarding run cannot continue while task {failed_task} is failed.",
                        retryable=bool(failure.get("retryable", True)),
                        provider=source.provider,
                        manifest=source.manifest,
                        task_id=f"{source.provider}-run-{failed_task}",
                        details={
                            "failed_task": failed_task,
                            "failed_steps": failed_steps,
                            "failure": failure if isinstance(failure, dict) else {},
                        },
                    )
                break
            if task in {DISCOVER_STEP, IMPLEMENT_STEP}:
                brief_name = (
                    "discover-manifest.yml"
                    if task == DISCOVER_STEP
                    else "implement-provider.yml"
                )
                if task == DISCOVER_STEP:
                    _prepare_discovery_for_runner(
                        provider=source.provider,
                        domain=domain,
                        doi_prefix=doi_prefix,
                        output_dir=output_dir,
                    )
                _dispatch_worker(
                    provider=source.provider,
                    task=task,
                    brief_path=output_dir / "briefs" / brief_name,
                    output_dir=output_dir,
                    provider_state=provider_state,
                )
                if task == DISCOVER_STEP:
                    _autofix_manifest_for_runner(
                        provider=source.provider,
                        manifest=source.manifest,
                        output_dir=output_dir,
                        targeted=False,
                    )
            else:
                _execute_local_task(
                    provider=source.provider,
                    task=task,
                    provider_state=provider_state,
                    state=state,
                    state_path=state_path,
                    output_dir=output_dir,
                )
                if task == PROPOSE_CLEANING_STEP:
                    _write_implementation_brief(output_dir=output_dir, source=source)
            executed.append(task)
            _mark_step_completed(
                state,
                provider_state,
                provider=source.provider,
                task=task,
            )
            _write_json(state_path, state)
            if task == until:
                break
    except ToolError:
        failed_task = provider_state.get("current_step")
        if isinstance(failed_task, str):
            _mark_step_failed(
                state,
                provider_state,
                provider=source.provider,
                task=failed_task,
            )
            _write_json(state_path, state)
        raise

    _write_json(state_path, state)
    return {
        "provider": source.provider,
        "manifest": source.manifest,
        "executed": executed,
        "until": until,
        "status": provider_state["status"],
        "current_step": provider_state.get("current_step"),
        "state": str(state_path),
        "output_dir": str(output_dir),
    }


def _record_run(
    provider_state: dict[str, Any],
    *,
    task: str,
    commands: list[list[str]],
    result: str,
    failure: dict[str, Any] | None = None,
) -> None:
    runs = provider_state.setdefault("runs", {})
    entry: dict[str, Any] = {
        "dry_run": False,
        "commands": commands,
        "result": result,
    }
    if failure is not None:
        entry["failure"] = failure
    runs[task] = entry


def _failure_from_tool_error(
    exc: ToolError,
    *,
    commands: list[list[str]],
) -> dict[str, Any]:
    structured = error_payload(
        exc.code,
        exc.message,
        provider=exc.provider,
        manifest=exc.manifest,
        task_id=exc.task_id,
        retryable=exc.retryable,
        details=exc.details,
        extras=exc.extras,
    )
    return {
        "code": exc.code,
        "command": commands[0] if commands else [],
        "returncode": 1,
        "stdout_tail": "",
        "stderr_tail": json.dumps(structured, ensure_ascii=False, sort_keys=True),
        "structured_error": structured,
    }


def _mark_step_failed(
    state: dict[str, Any],
    provider_state: dict[str, Any],
    *,
    provider: str,
    task: str,
) -> None:
    provider_state["task_statuses"][task] = "failed"
    provider_state["current_step"] = task
    provider_state["status"] = "blocked"
    state["active_provider"] = provider


def _mark_step_completed(
    state: dict[str, Any],
    provider_state: dict[str, Any],
    *,
    provider: str,
    task: str,
) -> str | None:
    task_statuses = provider_state["task_statuses"]
    task_statuses[task] = "completed"
    completed_steps = provider_state["completed_steps"]
    if task not in completed_steps:
        completed_steps.append(task)
    provider_state["current_step"] = None
    next_step = _next_pending_step(provider_state)
    if next_step is None:
        failed_steps = _failed_steps(provider_state)
        if failed_steps:
            provider_state["current_step"] = failed_steps[0]
            provider_state["status"] = "blocked"
            state["active_provider"] = provider
        else:
            provider_state["status"] = "merge_ready"
            state["active_provider"] = None
    else:
        provider_state["status"] = "in_progress"
        state["active_provider"] = provider
    return next_step
