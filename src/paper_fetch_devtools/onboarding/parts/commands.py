# ruff: noqa
from __future__ import annotations


def run_run(args: argparse.Namespace) -> int:
    if args.manifest:
        source = _manifest_source(args.manifest)
    else:
        source = _provider_source(
            provider=args.provider,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
        )
    output_dir = Path(
        args.output_dir or f".paper-fetch-runs/{source.provider}-onboarding"
    )
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    step_ids = _dag_step_ids(source.include_discovery)
    if args.until not in step_ids:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"--until must name a task in the active DAG: {args.until}",
            retryable=False,
            provider=source.provider,
            manifest=source.manifest,
            task_id=f"{source.provider}-run",
            details={"until": args.until, "steps": list(step_ids)},
        )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(
        state,
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
    )
    print(
        json.dumps(
            _execute_run_loop(
                source=source,
                output_dir=output_dir,
                state_path=state_path,
                state=state,
                provider_state=provider_state,
                until=args.until,
                domain=args.domain,
                doi_prefix=args.doi_prefix,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_discover(args: argparse.Namespace) -> int:
    brief = build_discover_brief(
        provider=args.provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
        output_manifest=args.output,
        evidence_pack=getattr(args, "evidence_pack", None),
    )
    print(to_yaml(brief))
    return 0


def run_prepare_discovery(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    pack = prepare_manifest_discovery(
        provider=args.provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
        output_dir=output_dir,
        no_network=args.no_network,
        browser_fallback=args.browser_fallback,
    )
    payload = {
        "provider": _provider_slug(args.provider),
        "evidence_pack": default_evidence_pack_path(args.provider, output_dir),
        "network_enabled": bool(pack.get("network", {}).get("enabled"))
        if isinstance(pack.get("network"), dict)
        else None,
        "browser_fallback": pack.get("browser_fallback"),
        "query_plan_purposes": sorted((pack.get("query_plan") or {}).keys()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def run_autofix_manifest(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    evidence_pack_path = Path(args.evidence_pack)
    if not evidence_pack_path.is_absolute():
        evidence_pack_path = _repo_root() / evidence_pack_path
    result = autofix_manifest_file(
        manifest_path=manifest_path,
        evidence_pack_path=evidence_pack_path,
        write=args.write,
        targeted=bool(getattr(args, "targeted", False)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run_inspect_discovery(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    evidence_pack_path = Path(args.evidence_pack)
    if not evidence_pack_path.is_absolute():
        evidence_pack_path = _repo_root() / evidence_pack_path
    manifest = _read_manifest_for_autofix(manifest_path)
    evidence_pack = _load_evidence_pack(evidence_pack_path)
    result = inspect_manifest_discovery(manifest=manifest, evidence_pack=evidence_pack)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run_start(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    if args.manifest:
        source = _manifest_source(args.manifest)
    else:
        source = _provider_source(
            provider=args.provider,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
        )

    dag = build_dag(
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
        dry_run=args.dry_run,
    )
    implementation_brief = build_implementation_brief(
        provider=source.provider,
        manifest=source.manifest,
        manifest_yaml=source.manifest_yaml,
    )
    write_text(
        output_dir / "task-dag.json",
        json.dumps(dag, indent=2, sort_keys=True) + "\n",
    )
    write_text(
        output_dir / "briefs" / "implement-provider.yml",
        to_yaml(implementation_brief) + "\n",
    )

    if source.include_discovery:
        evidence_pack = default_evidence_pack_path(source.provider, output_dir)
        discover_brief = build_discover_brief(
            provider=source.provider,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
            output_manifest=source.manifest,
            evidence_pack=evidence_pack,
        )
        write_text(
            output_dir / "briefs" / "discover-manifest.yml",
            to_yaml(discover_brief) + "\n",
        )
    if args.dry_run:
        return 0

    state_path = _state_path(args.state)
    state = _load_state(state_path)
    _ensure_provider_state(
        state,
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
    )
    _write_json(state_path, state)
    return 0


def run_next(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    step_id = _next_pending_step(provider_state)
    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "status": provider_state["status"],
                "current_step": step_id,
                "state": str(state_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_verify(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    if args.task not in _dag_step_ids(include_discovery=True):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"unknown task for provider {provider}: {args.task}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-verify-{args.task}",
            details={"task": args.task},
        )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    if args.task in {ACCESS_PREFLIGHT_STEP, DISCOVER_STEP}:
        validate_access_review(provider)
    commands = _verify_commands(provider, args.task)
    verifications = provider_state.setdefault("verifications", {})
    verifications[args.task] = {
        "dry_run": True,
        "commands": commands,
        "result": "planned",
    }
    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "task": args.task,
                "dry_run": True,
                "commands": commands,
                "result": "planned",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_check_snapshot(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    doi = _normalized_doi(args.doi)
    provider_manifest = _read_manifest(_manifest_path_for_provider(provider))
    if doi not in _manifest_dois(provider_manifest):
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is not registered in provider manifest fixtures.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi},
        )
    golden_manifest = _load_golden_manifest()
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is missing from golden criteria manifest.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi, "sample_id": _doi_slug(doi)},
        )
    sample_id, sample = sample_entry
    fixture_root = _fixture_root_for_sample(sample_id, sample)
    expected_path = fixture_root / "expected.json"
    markdown_path = fixture_root / "extracted.md"
    prompt_path = fixture_root / "markdown-quality-prompt.md"
    quality_path = fixture_root / "markdown-quality.json"
    if not fixture_root.is_dir():
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "fixture directory is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "fixture_dir": fixture_root.relative_to(_repo_root()).as_posix(),
            },
        )
    if not expected_path.is_file():
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "expected snapshot file is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "expected_path": expected_path.relative_to(_repo_root()).as_posix(),
            },
        )
    if not markdown_path.is_file():
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "extracted Markdown baseline is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "baseline_markdown_path": markdown_path.relative_to(
                    _repo_root()
                ).as_posix(),
            },
        )
    if not prompt_path.is_file():
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality agent prompt is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_prompt_path": prompt_path.relative_to(
                    _repo_root()
                ).as_posix(),
            },
        )
    if not quality_path.is_file():
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
            },
        )
    try:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report cannot be loaded.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "reason": str(exc),
            },
        ) from exc
    validation_errors = _markdown_quality_report_errors(
        quality,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
    )
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "validation_errors": validation_errors,
            },
        )
    fresh = _run_fresh_markdown_quality_review(
        provider=provider,
        doi=doi,
        sample_id=sample_id,
        purpose=str(sample.get("purpose") or ""),
        markdown_path=markdown_path,
        prompt_path=prompt_path,
        task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
    )
    fresh_blocking_issues = _fresh_markdown_quality_blocking_issues(fresh.report)
    if fresh.report.get("status") != "pass" or fresh_blocking_issues:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Fresh Markdown quality review found blocking issues in extracted.md.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "baseline_markdown_path": markdown_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_status": quality.get("status")
                if isinstance(quality, dict)
                else None,
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "issues": fresh_blocking_issues,
            },
        )
    if isinstance(quality, dict) and quality.get("status") == PENDING_STATUS:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report is pending agent review; run the prompt and write a pass/fail report.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_prompt_path": prompt_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "status": quality.get("status"),
            },
        )
    blocking_issues = blocking_markdown_quality_issues(quality)
    if (
        not isinstance(quality, dict)
        or quality.get("status") != "pass"
        or blocking_issues
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report contains blocking issues.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "status": quality.get("status") if isinstance(quality, dict) else None,
                "issues": blocking_issues,
            },
        )
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    expected_assets = {
        "expected.json": expected_path,
        "extracted.md": markdown_path,
        "markdown-quality-prompt.md": prompt_path,
        "markdown-quality.json": quality_path,
    }
    missing_asset_entries = [
        name
        for name, path in expected_assets.items()
        if assets.get(name) != path.relative_to(_repo_root()).as_posix()
    ]
    if missing_asset_entries:
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "fixture manifest assets do not register all snapshot artifacts.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi, "missing_assets": missing_asset_entries},
        )
    if sample.get("expected_outcome") == "pending":
        raise ToolError(
            "EXPECTED_OUTCOME_PENDING",
            "fixture manifest expected_outcome is still pending.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi, "sample_id": sample_id},
        )
    print(
        json.dumps(
            {
                "provider": provider,
                "doi": doi,
                "sample_id": sample_id,
                "expected_path": expected_path.relative_to(_repo_root()).as_posix(),
                "baseline_markdown_path": markdown_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_prompt_path": prompt_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "markdown_quality_status": quality.get("status"),
                "expected_outcome": sample.get("expected_outcome"),
                "result": "passed",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_check_cleaning_proposal(args: argparse.Namespace) -> int:
    proposal_path = Path(args.proposal) if args.proposal else None
    if proposal_path is not None and not proposal_path.is_absolute():
        proposal_path = _repo_root() / proposal_path
    print(
        json.dumps(
            check_cleaning_proposal_freshness(
                args.provider, proposal_path=proposal_path
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_run_checks(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    if bool(args.task) == bool(args.all_local):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            "run-checks requires exactly one of --task or --all-local.",
            retryable=True,
            provider=provider,
            task_id=f"{provider}-run-checks",
            details={"task": args.task, "all_local": args.all_local},
        )
    all_step_ids = _dag_step_ids(include_discovery=True)
    if args.task and args.task not in all_step_ids:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"unknown task for provider {provider}: {args.task}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-run-checks-{args.task}",
            details={"task": args.task},
        )

    tasks = (
        [
            ACCESS_PREFLIGHT_STEP,
            "validate-manifest",
            "provider-local-acceptance",
            SHARED_INTEGRATION_STEP,
            "global-lint",
        ]
        if args.all_local
        else [args.task]
    )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    completed_tasks: list[str] = []

    for task in tasks:
        commands = _verify_commands(provider, task, include_live=not args.all_local)
        if task in {ACCESS_PREFLIGHT_STEP, DISCOVER_STEP}:
            try:
                validate_access_review(provider)
            except ToolError as exc:
                _record_run(
                    provider_state,
                    task=task,
                    commands=commands,
                    result="failed",
                    failure=_failure_from_tool_error(exc, commands=commands),
                )
                _write_json(state_path, state)
                raise
        for command in commands:
            completed = _run_env_command(command)
            if _command_failed(command, completed):
                failure_code = _failure_code_for_task(task, command)
                structured = _payload_from_stderr(completed.stderr)
                if structured and isinstance(structured.get("code"), str):
                    failure_code = str(structured["code"])
                failure = {
                    "code": failure_code,
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                }
                if structured:
                    failure["structured_error"] = structured
                if _is_cleaning_contract_command(command):
                    contract_payload = _payload_from_stdout_yaml(completed.stdout)
                    if contract_payload is not None:
                        failure["contract_check"] = contract_payload
                _record_run(
                    provider_state,
                    task=task,
                    commands=commands,
                    result="failed",
                    failure=failure,
                )
                _write_json(state_path, state)
                raise ToolError(
                    failure_code,
                    f"onboarding local check failed for task {task}.",
                    retryable=bool(structured.get("retryable")) if structured else True,
                    provider=provider,
                    manifest=default_manifest_path(provider),
                    task_id=f"{provider}-run-checks-{task}",
                    details=failure,
                )
        _record_run(provider_state, task=task, commands=commands, result="passed")
        completed_tasks.append(task)

    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "tasks": completed_tasks,
                "result": "passed",
                "state": str(state_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _record_markdown_quality_repair(
    provider_state: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    repairs = provider_state.setdefault("repairs", {})
    if not isinstance(repairs, dict):
        repairs = {}
        provider_state["repairs"] = repairs
    markdown_repairs = repairs.setdefault("markdown_quality", [])
    if not isinstance(markdown_repairs, list):
        markdown_repairs = []
        repairs["markdown_quality"] = markdown_repairs
    markdown_repairs.append(entry)


def _run_agent_with_scope(
    *,
    argv: list[str],
    prompt: str,
    attempt_dir: Path,
    prefix: str,
    allowed_scope: list[str],
) -> tuple[subprocess.CompletedProcess[str], set[str], set[str]]:
    write_text(attempt_dir / f"{prefix}.prompt.md", prompt)
    before = _workspace_changed_paths()
    completed = subprocess.run(
        argv,
        cwd=_repo_root(),
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    after = _workspace_changed_paths()
    write_text(attempt_dir / f"{prefix}.stdout.log", completed.stdout)
    write_text(attempt_dir / f"{prefix}.stderr.log", completed.stderr)
    write_text(
        attempt_dir / f"{prefix}.changed-before.json",
        json.dumps(sorted(before), indent=2, sort_keys=True) + "\n",
    )
    write_text(
        attempt_dir / f"{prefix}.changed-after.json",
        json.dumps(sorted(after), indent=2, sort_keys=True) + "\n",
    )
    disallowed = _disallowed_changes(before, after, allowed_scope)
    if disallowed:
        write_text(
            attempt_dir / f"{prefix}.forbidden-paths.json",
            json.dumps(disallowed, indent=2, sort_keys=True) + "\n",
        )
    return completed, before, after


def _run_repair_command(
    command: list[str],
    *,
    attempt_dir: Path,
    index: int,
) -> tuple[bool, dict[str, Any]]:
    completed = _run_env_command(command)
    command_dir = attempt_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{index:02d}"
    write_text(command_dir / f"{stem}.command.txt", _markdown_command(command) + "\n")
    write_text(command_dir / f"{stem}.stdout.log", completed.stdout)
    write_text(command_dir / f"{stem}.stderr.log", completed.stderr)
    failed = _command_failed(command, completed)
    details = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }
    structured = _payload_from_stderr(completed.stderr)
    if structured:
        details["structured_error"] = structured
    return not failed, details


def _load_quality_after_review(
    ctx: MarkdownQualityRepairContext,
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        quality = json.loads(ctx.quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"Markdown quality report cannot be loaded: {exc}"]
    errors = validate_markdown_quality_report(quality)
    if isinstance(quality, dict):
        if quality.get("markdown_path") != _rel(ctx.markdown_path):
            errors.append("markdown_path must point to extracted.md")
        if quality.get("prompt_path") != _rel(ctx.prompt_path):
            errors.append("prompt_path must point to markdown-quality-prompt.md")
    else:
        errors.append("markdown quality report root must be an object")
        quality = None
    return quality, errors


def _load_fresh_markdown_repair_context(
    provider: str,
    doi: str,
    *,
    output_dir: Path,
) -> MarkdownQualityRepairContext:
    base_ctx = _load_markdown_repair_context(
        provider,
        doi,
        allow_passing_report=True,
        allow_pending_report=True,
    )
    fresh = _run_fresh_markdown_quality_review(
        provider=base_ctx.provider,
        doi=base_ctx.doi,
        sample_id=base_ctx.sample_id,
        purpose=base_ctx.purpose,
        markdown_path=base_ctx.markdown_path,
        prompt_path=base_ctx.prompt_path,
        output_dir=output_dir / "fresh-review",
        task_id=f"{base_ctx.provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
    )
    effective = _effective_markdown_repair_report(
        persistent_report=base_ctx.persistent_quality_report,
        fresh_report=fresh.report,
    )
    if effective.get("status") == "pass" and not blocking_markdown_quality_issues(
        effective
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_REPAIR_NOT_REQUIRED",
            "Fresh Markdown quality review and persistent report are already passing.",
            retryable=False,
            provider=base_ctx.provider,
            manifest=default_manifest_path(base_ctx.provider),
            task_id=f"{base_ctx.provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
            details={
                "doi": base_ctx.doi,
                "markdown_quality_path": _rel(base_ctx.quality_path),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
            },
        )
    return base_ctx._replace(
        quality_report=effective,
        fresh_quality_path=fresh.report_path,
    )


def _update_review_artifact_hashes(ctx: MarkdownQualityRepairContext) -> bool:
    if not ctx.review_path.is_file():
        return False
    try:
        review = yaml.safe_load(ctx.review_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return False
    if not isinstance(review, dict):
        return False
    fixtures = review.get("fixtures")
    if not isinstance(fixtures, list):
        return False
    quality_rel = _rel(ctx.quality_path)
    markdown_rel = _rel(ctx.markdown_path)
    changed = False
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        fixture_doi = _normalized_doi(str(fixture.get("doi") or ""))
        matches_doi = fixture_doi == ctx.doi
        matches_quality = fixture.get("markdown_quality_path") == quality_rel
        matches_markdown = fixture.get("baseline_markdown_path") == markdown_rel
        if not (matches_doi or matches_quality or matches_markdown):
            continue
        fixture["markdown_quality_sha256"] = _sha256_file(ctx.quality_path)
        if ctx.markdown_path.is_file():
            fixture["baseline_markdown_sha256"] = _sha256_file(ctx.markdown_path)
        changed = True
    if changed:
        write_text(
            ctx.review_path,
            yaml.safe_dump(review, sort_keys=False, allow_unicode=True),
        )
    return changed


def run_repair_markdown_quality(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    doi = _normalized_doi(args.doi)
    max_attempts = int(args.max_attempts)
    if max_attempts < 1:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            "--max-attempts must be at least 1.",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
            details={"max_attempts": max_attempts},
        )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    output_dir = Path(
        args.output_dir or f".paper-fetch-runs/{provider}-markdown-repair"
    )
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    repair_dir = output_dir / "markdown-quality" / _doi_slug(doi)
    ctx = _load_markdown_repair_context(
        provider,
        doi,
        allow_passing_report=True,
        allow_pending_report=True,
    )
    dispatcher = _worker_dispatcher(
        provider=provider,
        task=REPAIR_MARKDOWN_QUALITY_STEP,
        manifest=_rel(ctx.manifest_path),
    )
    state["agent_cli"] = dispatcher.agent_cli
    argv = dispatcher.argv
    initial_issue_ids: list[str] = []
    changed_paths: set[str] = set()
    executed_commands: list[list[str]] = []
    command_details: list[dict[str, Any]] = []
    last_failure: dict[str, Any] | None = None
    attempts_run = 0
    quality_status = ctx.quality_report.get("status")

    for attempt in range(1, max_attempts + 1):
        attempts_run = attempt
        ctx = _load_fresh_markdown_repair_context(provider, doi, output_dir=repair_dir)
        issues = _markdown_repair_issues(ctx.quality_report)
        if not initial_issue_ids:
            initial_issue_ids = [
                str(issue.get("id"))
                for issue in issues
                if isinstance(issue.get("id"), str) and issue.get("id")
            ]
        domains = _infer_markdown_repair_domains(issues)
        allowed_scope = _markdown_repair_allowed_scope(ctx, domains)
        attempt_dir = repair_dir / f"attempt-{attempt}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        brief = _markdown_repair_brief(
            ctx,
            attempt=attempt,
            max_attempts=max_attempts,
            domains=domains,
            allowed_scope=allowed_scope,
        )
        write_text(attempt_dir / "repair-brief.yml", to_yaml(brief) + "\n")
        worker_prompt = _markdown_repair_worker_prompt(ctx, brief)
        completed, before, after = _run_agent_with_scope(
            argv=argv,
            prompt=worker_prompt,
            attempt_dir=attempt_dir,
            prefix="repair-agent",
            allowed_scope=allowed_scope,
        )
        changed_paths.update(after - before)
        disallowed = _disallowed_changes(before, after, allowed_scope)
        if disallowed:
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "forbidden_paths": disallowed,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            entry = {
                "provider": provider,
                "doi": doi,
                "sample_id": ctx.sample_id,
                "attempts": attempts_run,
                "status": "failed",
                "issue_ids": initial_issue_ids,
                "changed_paths": sorted(changed_paths),
                "commands": executed_commands,
                "command_results": command_details,
                "quality_status": quality_status,
                "run_dir": _rel(repair_dir),
                "failure": last_failure,
            }
            _record_markdown_quality_repair(provider_state, entry)
            _write_json(state_path, state)
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "repair worker modified files outside the inferred allowed scope.",
                retryable=True,
                provider=provider,
                manifest=_rel(ctx.manifest_path),
                task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
                details=last_failure,
            )
        if completed.returncode != 0:
            last_failure = {
                "code": "WORKER_AGENT_FAILED",
                "attempt": attempt,
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            continue

        commands = _markdown_repair_commands(ctx)
        pre_review_commands = commands[:2]
        post_review_command = commands[2]
        command_failed = False
        for index, command in enumerate(pre_review_commands, start=1):
            ok, details = _run_repair_command(
                command, attempt_dir=attempt_dir, index=index
            )
            executed_commands.append(command)
            command_details.append(details)
            if not ok:
                command_failed = True
                last_failure = {
                    "code": "LOCAL_CHECK_FAILED",
                    "attempt": attempt,
                    **details,
                }
                break
        if command_failed:
            continue

        review_prompt = _markdown_quality_review_prompt(ctx)
        review_completed, review_before, review_after = _run_agent_with_scope(
            argv=argv,
            prompt=review_prompt,
            attempt_dir=attempt_dir,
            prefix="quality-review-agent",
            allowed_scope=[_rel(ctx.quality_path)],
        )
        changed_paths.update(review_after - review_before)
        review_disallowed = _disallowed_changes(
            review_before, review_after, [_rel(ctx.quality_path)]
        )
        if review_disallowed:
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "forbidden_paths": review_disallowed,
                "stdout_tail": _tail(review_completed.stdout),
                "stderr_tail": _tail(review_completed.stderr),
            }
            entry = {
                "provider": provider,
                "doi": doi,
                "sample_id": ctx.sample_id,
                "attempts": attempts_run,
                "status": "failed",
                "issue_ids": initial_issue_ids,
                "changed_paths": sorted(changed_paths),
                "commands": executed_commands,
                "command_results": command_details,
                "quality_status": quality_status,
                "run_dir": _rel(repair_dir),
                "failure": last_failure,
            }
            _record_markdown_quality_repair(provider_state, entry)
            _write_json(state_path, state)
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "quality review worker modified files outside markdown-quality.json.",
                retryable=True,
                provider=provider,
                manifest=_rel(ctx.manifest_path),
                task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
                details=last_failure,
            )
        if review_completed.returncode != 0:
            last_failure = {
                "code": "WORKER_AGENT_FAILED",
                "attempt": attempt,
                "returncode": review_completed.returncode,
                "stdout_tail": _tail(review_completed.stdout),
                "stderr_tail": _tail(review_completed.stderr),
            }
            continue

        ok, details = _run_repair_command(
            post_review_command, attempt_dir=attempt_dir, index=3
        )
        executed_commands.append(post_review_command)
        command_details.append(details)
        quality, quality_errors = _load_quality_after_review(ctx)
        quality_status = (
            quality.get("status") if isinstance(quality, dict) else "invalid"
        )
        write_text(
            attempt_dir / "quality-status.json",
            json.dumps(
                {
                    "status": quality_status,
                    "errors": quality_errors,
                    "blocking_issues": blocking_markdown_quality_issues(quality)
                    if isinstance(quality, dict)
                    else [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        if (
            ok
            and isinstance(quality, dict)
            and not quality_errors
            and quality.get("status") == "pass"
            and not blocking_markdown_quality_issues(quality)
        ):
            review_updated = _update_review_artifact_hashes(ctx)
            if review_updated:
                changed_paths.add(_rel(ctx.review_path))
            entry = {
                "provider": provider,
                "doi": doi,
                "sample_id": ctx.sample_id,
                "attempts": attempts_run,
                "status": "passed",
                "issue_ids": initial_issue_ids,
                "changed_paths": sorted(changed_paths),
                "commands": executed_commands,
                "command_results": command_details,
                "quality_status": quality_status,
                "run_dir": _rel(repair_dir),
                "review_artifact_updated": review_updated,
            }
            _record_markdown_quality_repair(provider_state, entry)
            _write_json(state_path, state)
            print(
                json.dumps(
                    {**entry, "state": str(state_path)}, indent=2, sort_keys=True
                )
            )
            return 0
        last_failure = {
            "code": "MARKDOWN_QUALITY_FAILED",
            "attempt": attempt,
            "quality_status": quality_status,
            "quality_errors": quality_errors,
            "check_snapshot": details,
        }

    entry = {
        "provider": provider,
        "doi": doi,
        "sample_id": ctx.sample_id,
        "attempts": attempts_run,
        "status": "failed",
        "issue_ids": initial_issue_ids,
        "changed_paths": sorted(changed_paths),
        "commands": executed_commands,
        "command_results": command_details,
        "quality_status": quality_status,
        "run_dir": _rel(repair_dir),
        "failure": last_failure or {"code": "MARKDOWN_QUALITY_REPAIR_FAILED"},
    }
    _record_markdown_quality_repair(provider_state, entry)
    _write_json(state_path, state)
    raise ToolError(
        "MARKDOWN_QUALITY_REPAIR_FAILED",
        f"Markdown quality repair did not pass after {max_attempts} attempts.",
        retryable=False,
        provider=provider,
        manifest=_rel(ctx.manifest_path),
        task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
        details=entry,
    )
