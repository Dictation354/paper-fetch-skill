# ruff: noqa
from __future__ import annotations


def _write_implementation_brief(*, output_dir: Path, source: OnboardingSource) -> None:
    manifest_yaml = source.manifest_yaml
    manifest_path = _repo_root() / source.manifest
    if manifest_yaml is None and manifest_path.exists():
        manifest_yaml = manifest_path.read_text(encoding="utf-8")
    implementation_brief = build_implementation_brief(
        provider=source.provider,
        manifest=source.manifest,
        manifest_yaml=manifest_yaml,
    )
    write_text(
        output_dir / "briefs" / "implement-provider.yml",
        to_yaml(implementation_brief) + "\n",
    )


def _discovery_no_network_requested() -> bool:
    value = os.environ.get(DISCOVERY_NO_NETWORK_ENV)
    if value is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _runner_evidence_pack_path(*, provider: str, output_dir: Path) -> Path:
    path = Path(default_evidence_pack_path(provider, output_dir))
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _prepare_discovery_for_runner(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    output_dir: Path,
) -> dict[str, Any]:
    return prepare_manifest_discovery(
        provider=provider,
        domain=domain,
        doi_prefix=doi_prefix,
        output_dir=output_dir,
        no_network=_discovery_no_network_requested(),
    )


def _autofix_manifest_for_runner(
    *,
    provider: str,
    manifest: str,
    output_dir: Path | None,
    targeted: bool = False,
) -> dict[str, Any]:
    manifest_path = Path(manifest)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    if not manifest_path.exists():
        return {
            "changed": False,
            "changed_paths": [],
            "targeted": targeted,
            "skipped": "manifest_missing",
            "manifest": manifest_path.as_posix(),
        }
    evidence_path = (
        _runner_evidence_pack_path(
            provider=provider,
            output_dir=output_dir,
        )
        if output_dir is not None
        else None
    )
    if evidence_path is None or not evidence_path.exists():
        return {
            "changed": False,
            "changed_paths": [],
            "targeted": targeted,
            "skipped": "evidence_pack_missing",
            "manifest": manifest_path.as_posix(),
            "evidence_pack": evidence_path.as_posix() if evidence_path else None,
        }
    return autofix_manifest_file(
        manifest_path=manifest_path,
        evidence_pack_path=evidence_path,
        write=True,
        targeted=targeted,
    )


def _run_artifacts(
    *,
    source: OnboardingSource,
    output_dir: Path,
    domain: str | None,
    doi_prefix: str | None,
) -> None:
    dag = build_dag(
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
        dry_run=False,
    )
    write_text(
        output_dir / "task-dag.json",
        json.dumps(dag, indent=2, sort_keys=True) + "\n",
    )
    if source.include_discovery:
        evidence_pack = default_evidence_pack_path(source.provider, output_dir)
        discover_brief = build_discover_brief(
            provider=source.provider,
            domain=domain,
            doi_prefix=doi_prefix,
            output_manifest=source.manifest,
            evidence_pack=evidence_pack,
        )
        write_text(
            output_dir / "briefs" / "discover-manifest.yml",
            to_yaml(discover_brief) + "\n",
        )
    _write_implementation_brief(output_dir=output_dir, source=source)


def _workspace_changed_paths() -> set[str]:
    root = _repo_root()
    paths: set[str] = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        paths.update(line.strip() for line in diff.stdout.splitlines() if line.strip())
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip() if len(line) > 3 else line.strip()
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[-1]
            if path:
                paths.add(path)
    return paths


def _matches_forbidden(path: str, forbidden: list[str]) -> bool:
    return onboarding_dispatch.matches_forbidden(path, forbidden)


def _forbidden_changes(
    before: set[str], after: set[str], forbidden: list[str]
) -> list[str]:
    return onboarding_dispatch.forbidden_changes(before, after, forbidden)


def _matches_scope(path: str, scope: list[str]) -> bool:
    return onboarding_dispatch.matches_scope(path, scope)


def _disallowed_changes(
    before: set[str], after: set[str], allowed: list[str]
) -> list[str]:
    return onboarding_dispatch.disallowed_changes(before, after, allowed)


def _agent_argv(
    *,
    provider: str,
    task: str,
    manifest: str | None = None,
) -> list[str]:
    return _worker_dispatcher(provider=provider, task=task, manifest=manifest).argv


def _load_brief(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"worker brief must load as a mapping: {path}")
    return data


def _worker_prompt(
    *,
    provider: str,
    task: str,
    brief: dict[str, Any],
) -> str:
    root = _repo_root()
    parts = [
        f"# Provider onboarding worker task: {provider} / {task}",
        "",
        "Follow the YAML task brief exactly. Do not commit changes.",
        "",
        "## Task Brief",
        "```yaml",
        to_yaml(brief),
        "```",
    ]
    access_path = root / default_access_review_path(provider)
    if access_path.exists():
        parts.extend(
            [
                "",
                "## Access Review",
                "```yaml",
                access_path.read_text(encoding="utf-8"),
                "```",
            ]
        )
    hard_constraints = root / HARD_CONSTRAINTS_PATH
    if hard_constraints.exists():
        parts.extend(
            [
                "",
                "## Hard Constraints",
                "```markdown",
                hard_constraints.read_text(encoding="utf-8"),
                "```",
            ]
        )
    if task == DISCOVER_STEP:
        evidence_ref = brief.get("evidence_pack")
        evidence_path_value = (
            evidence_ref.get("path") if isinstance(evidence_ref, dict) else evidence_ref
        )
        if isinstance(evidence_path_value, str):
            evidence_path = Path(evidence_path_value)
            if not evidence_path.is_absolute():
                evidence_path = root / evidence_path
            if evidence_path.exists():
                try:
                    evidence_pack = _load_evidence_pack(evidence_path)
                    parts.extend(
                        [
                            "",
                            "## Discovery Evidence Pack Summary",
                            "```json",
                            json.dumps(
                                _compact_evidence_pack_summary(evidence_pack),
                                indent=2,
                                sort_keys=True,
                            ),
                            "```",
                            "",
                            f"Full evidence pack: `{evidence_path_value}`",
                        ]
                    )
                except ToolError:
                    parts.extend(
                        [
                            "",
                            "## Discovery Evidence Pack Summary",
                            f"Evidence pack was declared but could not be loaded: `{evidence_path_value}`",
                        ]
                    )
        schema = root / SCHEMA_PATH
        if schema.exists():
            parts.extend(
                [
                    "",
                    "## Provider Manifest Schema",
                    "```json",
                    schema.read_text(encoding="utf-8"),
                    "```",
                ]
            )
    if task == IMPLEMENT_STEP:
        manifest_path = root / str(
            brief.get("provider_manifest") or default_manifest_path(provider)
        )
        if manifest_path.exists():
            parts.extend(
                [
                    "",
                    "## Provider Manifest",
                    "```yaml",
                    manifest_path.read_text(encoding="utf-8"),
                    "```",
                ]
            )
        proposal_path = root / default_cleaning_proposal_path(provider)
        if proposal_path.exists():
            parts.extend(
                [
                    "",
                    "## Compact Cleaning Proposal",
                    "```yaml",
                    proposal_path.read_text(encoding="utf-8"),
                    "```",
                ]
            )
    return "\n".join(parts) + "\n"


def _dispatch_worker(
    *,
    provider: str,
    task: str,
    brief_path: Path,
    output_dir: Path,
    provider_state: dict[str, Any],
) -> None:
    dispatcher = _worker_dispatcher(
        provider=provider,
        task=task,
        manifest=provider_state.get("manifest"),
    )
    brief = _load_brief(brief_path)
    prompt = _worker_prompt(provider=provider, task=task, brief=brief)
    allowed = [str(value) for value in brief.get("files_allowed_to_modify") or ()]
    forbidden = [str(value) for value in brief.get("files_must_not_modify") or ()]
    worker_dir = output_dir / "workers"
    worker_dir.mkdir(parents=True, exist_ok=True)
    argv = dispatcher.argv

    retry_counts = provider_state.setdefault("retry_counts", {})
    attempt_start = int(retry_counts.get(task, 0)) + 1
    commands = [argv]
    last_failure: dict[str, Any] | None = None
    for attempt in range(attempt_start, MAX_WORKER_RETRIES + 1):
        before = _workspace_changed_paths()
        completed = subprocess.run(
            argv,
            cwd=_repo_root(),
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
        prefix = worker_dir / f"{task}-attempt-{attempt}"
        write_text(prefix.with_suffix(".prompt.md"), prompt)
        write_text(prefix.with_suffix(".stdout.log"), completed.stdout)
        write_text(prefix.with_suffix(".stderr.log"), completed.stderr)
        after = _workspace_changed_paths()
        forbidden_paths = _forbidden_changes(before, after, forbidden)
        if forbidden_paths:
            retry_counts[task] = attempt
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "forbidden_paths": forbidden_paths,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            _record_run(
                provider_state,
                task=task,
                commands=commands,
                result="failed",
                failure=last_failure,
            )
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "worker modified files outside its allowed scope.",
                retryable=True,
                provider=provider,
                manifest=provider_state.get("manifest"),
                task_id=f"{provider}-{task}",
                details=last_failure,
            )
        disallowed_paths = (
            _disallowed_changes(before, after, allowed) if allowed else []
        )
        if disallowed_paths:
            retry_counts[task] = attempt
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "disallowed_paths": disallowed_paths,
                "allowed_scope": allowed,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            _record_run(
                provider_state,
                task=task,
                commands=commands,
                result="failed",
                failure=last_failure,
            )
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "worker modified files outside its allowed scope.",
                retryable=True,
                provider=provider,
                manifest=provider_state.get("manifest"),
                task_id=f"{provider}-{task}",
                details=last_failure,
            )
        if completed.returncode == 0:
            _record_run(provider_state, task=task, commands=commands, result="passed")
            return
        retry_counts[task] = attempt
        last_failure = {
            "code": "WORKER_AGENT_FAILED",
            "attempt": attempt,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    _record_run(
        provider_state,
        task=task,
        commands=commands,
        result="failed",
        failure=last_failure,
    )
    raise ToolError(
        "TASK_RETRY_EXHAUSTED",
        f"worker task {task} failed after {MAX_WORKER_RETRIES} attempts.",
        retryable=False,
        provider=provider,
        manifest=provider_state.get("manifest"),
        task_id=f"{provider}-{task}",
        details=last_failure or {"task": task},
    )


def _run_task_commands(
    provider: str,
    task: str,
    *,
    manifest: str | None = None,
) -> list[list[str]]:
    provider_name = _provider_slug(provider)
    manifest_path = manifest or default_manifest_path(provider_name)
    if task == "validate-manifest":
        return [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_manifest_schema.py",
                "-q",
            ]
        ]
    if task == "capture-fixtures":
        return [
            [
                "python3",
                "scripts/capture_fixture.py",
                "--from-manifest",
                manifest_path,
                "--all",
                "--auto-via",
                "--fail-fast",
            ]
        ]
    if task == PROPOSE_CLEANING_STEP:
        return [
            [
                "python3",
                "scripts/propose_cleaning_chain.py",
                "--provider",
                provider_name,
                "--write",
            ]
        ]
    if task == "scaffold":
        return [
            [
                "python3",
                "scripts/scaffold_provider.py",
                "--from-manifest",
                manifest_path,
                "--merge-existing=safe",
            ]
        ]
    if task == "manifest-sync-back":
        return [
            [
                "python3",
                "scripts/manifest_sync_back.py",
                "--provider",
                provider_name,
                "--manifest",
                manifest_path,
                "--sync-docs",
            ]
        ]
    if task == SNAPSHOT_EXPECTED_STEP:
        commands = _snapshot_expected_commands(provider_name, manifest_path)
        commands.append(
            [
                "python3",
                "scripts/bootstrap_review_artifact.py",
                "--provider",
                provider_name,
                "--manifest",
                manifest_path,
            ]
        )
        return commands
    return _verify_commands(provider_name, task)


def _payload_from_stderr(stderr: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stderr)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _payload_from_stdout_yaml(stdout: str) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(stdout)
    except yaml.YAMLError:
        return None
    return payload if isinstance(payload, dict) else None


def _execute_local_task(
    *,
    provider: str,
    task: str,
    provider_state: dict[str, Any],
    state: dict[str, Any] | None = None,
    state_path: Path | None = None,
    output_dir: Path | None = None,
) -> None:
    manifest_path = str(
        provider_state.get("manifest") or default_manifest_path(provider)
    )
    commands = _run_task_commands(provider, task, manifest=manifest_path)
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
            raise
    validate_autofix: dict[str, Any] | None = None
    if task == "validate-manifest":
        validate_autofix = _autofix_manifest_for_runner(
            provider=provider,
            manifest=manifest_path,
            output_dir=output_dir,
            targeted=False,
        )
    for command in commands:
        targeted_autofix: dict[str, Any] | None = None
        completed = _run_env_command(command)
        if _command_failed(command, completed):
            failure_code = _failure_code_for_task(task, command)
            structured = _payload_from_stderr(completed.stderr)
            if structured and isinstance(structured.get("code"), str):
                failure_code = str(structured["code"])
            if (
                task == SNAPSHOT_EXPECTED_STEP
                and failure_code == "MARKDOWN_QUALITY_FAILED"
                and state_path is not None
                and "check-snapshot" in command
            ):
                try:
                    doi_index = command.index("--doi") + 1
                    repair_doi = command[doi_index]
                except (ValueError, IndexError):
                    repair_doi = None
                if repair_doi:
                    try:
                        run_repair_markdown_quality(
                            argparse.Namespace(
                                provider=provider,
                                doi=repair_doi,
                                state=str(state_path),
                                output_dir=f".paper-fetch-runs/{provider}-markdown-repair",
                                max_attempts=MAX_WORKER_RETRIES,
                            )
                        )
                    except ToolError as exc:
                        failure = {
                            "code": exc.code,
                            "command": command,
                            "returncode": completed.returncode,
                            "stdout_tail": _tail(completed.stdout),
                            "stderr_tail": _tail(completed.stderr),
                            "auto_repair_failure": {
                                "code": exc.code,
                                "message": exc.message,
                                "details": exc.details,
                            },
                        }
                        if structured:
                            failure["structured_error"] = structured
                        _record_run(
                            provider_state,
                            task=task,
                            commands=commands,
                            result="failed",
                            failure=failure,
                        )
                        raise ToolError(
                            exc.code,
                            "snapshot Markdown quality auto-repair failed.",
                            retryable=exc.retryable,
                            provider=provider,
                            manifest=manifest_path,
                            task_id=f"{provider}-run-{task}",
                            details=failure,
                        ) from exc
                    if state is not None:
                        fresh_state = _load_state(state_path)
                        fresh_provider_state = fresh_state.get("providers", {}).get(
                            provider
                        )
                        if isinstance(fresh_provider_state, dict):
                            provider_state.clear()
                            provider_state.update(fresh_provider_state)
                            state["agent_cli"] = fresh_state.get("agent_cli")
                            state["active_provider"] = fresh_state.get(
                                "active_provider"
                            )
                            state.setdefault("providers", {})[provider] = provider_state
                    completed = _run_env_command(command)
                    if not _command_failed(command, completed):
                        continue
                    failure_code = _failure_code_for_task(task, command)
                    structured = _payload_from_stderr(completed.stderr)
                    if structured and isinstance(structured.get("code"), str):
                        failure_code = str(structured["code"])
            if (
                task == "validate-manifest"
                and failure_code == "MANIFEST_SCHEMA_INVALID"
            ):
                targeted_autofix = _autofix_manifest_for_runner(
                    provider=provider,
                    manifest=manifest_path,
                    output_dir=output_dir,
                    targeted=True,
                )
                rerun = _run_env_command(command)
                if not _command_failed(command, rerun):
                    continue
                completed = rerun
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
            if validate_autofix is not None:
                failure["pre_validate_autofix"] = validate_autofix
            if targeted_autofix is not None:
                failure["targeted_autofix"] = targeted_autofix
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
            raise ToolError(
                failure_code,
                f"onboarding run failed for task {task}.",
                retryable=bool(structured.get("retryable")) if structured else True,
                provider=provider,
                manifest=manifest_path,
                task_id=f"{provider}-run-{task}",
                details=failure,
            )
    _record_run(provider_state, task=task, commands=commands, result="passed")
