# ruff: noqa
from __future__ import annotations


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    onboarding_state.write_json(path, data, write_text=write_text)


def _state_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return _repo_root() / path


def _default_state() -> dict[str, Any]:
    return onboarding_state.default_state(agent_cli=_worker_dispatcher_label())


def _load_state(path: Path) -> dict[str, Any]:
    return onboarding_state.load_state(
        path,
        agent_cli=_worker_dispatcher_label(),
        default_factory=_default_state,
    )


def _dag_step_ids(include_discovery: bool) -> tuple[str, ...]:
    return tuple(
        step.id for step in TASK_DAG if include_discovery or step.id != DISCOVER_STEP
    )


def _task_statuses(step_ids: tuple[str, ...]) -> dict[str, str]:
    return {
        step_id: "in_progress" if index == 0 else "pending"
        for index, step_id in enumerate(step_ids)
    }


def _ensure_single_active_provider(state: dict[str, Any], provider: str) -> None:
    active_provider = state.get("active_provider")
    if active_provider not in {None, provider}:
        providers = state.get("providers", {})
        active_state = providers.get(active_provider, {})
        if active_state.get("status") == "in_progress":
            raise ToolError(
                "TASK_BRIEF_INVALID",
                "another provider is already in_progress: "
                f"{active_provider}; finish or block it before starting {provider}",
                retryable=False,
                provider=provider,
                task_id=f"{provider}-coordinator-state-conflict",
                details={"active_provider": active_provider},
            )


def _ensure_provider_state(
    state: dict[str, Any],
    *,
    provider: str,
    manifest: str | None = None,
    include_discovery: bool = True,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    _ensure_single_active_provider(state, provider_name)
    providers = state["providers"]
    current = providers.get(provider_name)
    if isinstance(current, dict):
        return current
    step_ids = _dag_step_ids(include_discovery)
    provider_state = {
        "provider": provider_name,
        "manifest": manifest or default_manifest_path(provider_name),
        "status": "in_progress",
        "current_step": step_ids[0],
        "steps": list(step_ids),
        "completed_steps": [],
        "task_statuses": _task_statuses(step_ids),
        "retry_counts": {step_id: 0 for step_id in step_ids},
        "verifications": {},
    }
    providers[provider_name] = provider_state
    state["active_provider"] = provider_name
    return provider_state


def _next_pending_step(provider_state: dict[str, Any]) -> str | None:
    task_statuses = provider_state["task_statuses"]
    for step_id in provider_state["steps"]:
        if task_statuses.get(step_id) == "in_progress":
            return str(step_id)
    for step_id in provider_state["steps"]:
        if task_statuses.get(step_id) == "pending":
            task_statuses[step_id] = "in_progress"
            provider_state["current_step"] = step_id
            return str(step_id)
    provider_state["current_step"] = None
    return None


def _failed_steps(provider_state: dict[str, Any]) -> list[str]:
    task_statuses = provider_state.get("task_statuses")
    steps = provider_state.get("steps")
    if not isinstance(task_statuses, dict) or not isinstance(steps, list):
        return []
    return [
        str(step_id)
        for step_id in steps
        if task_statuses.get(step_id) in {"failed", "blocked"}
    ]


def _provider_requires_live_review(provider: str) -> bool:
    provider_name = _provider_slug(provider)
    manifest_path = _repo_root() / default_manifest_path(provider)
    if not manifest_path.exists():
        return provider_name not in LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS
    try:
        manifest = _read_manifest(manifest_path)
    except ToolError:
        return provider_name not in LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS
    probe = manifest.get("probe") if isinstance(manifest.get("probe"), dict) else {}
    if bool(probe.get("requires_browser_runtime")) or bool(
        probe.get("requires_playwright")
    ):
        return True
    return provider_name not in LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS


def _manifest_path_for_provider(provider: str) -> Path:
    return _repo_root() / default_manifest_path(provider)


def _normalized_doi(value: str) -> str:
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


def _doi_slug(value: str) -> str:
    return _normalized_doi(value).replace("/", "_")


def _manifest_dois(manifest: dict[str, Any]) -> list[str]:
    dois: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        doi = _normalized_doi(value)
        if doi and doi not in seen:
            seen.add(doi)
            dois.append(doi)

    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for sample in doi_samples.values():
        if isinstance(sample, dict):
            add(sample.get("doi"))

    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for sample in extra_fixtures:
            if isinstance(sample, dict):
                add(sample.get("doi"))
    return dois


def _snapshot_expected_commands(
    provider: str, manifest_path: str | None = None
) -> list[list[str]]:
    if manifest_path is None:
        path = _manifest_path_for_provider(provider)
    else:
        path = Path(manifest_path)
        if not path.is_absolute():
            path = _repo_root() / path
    manifest = _read_manifest(path)
    commands: list[list[str]] = []
    for doi in _manifest_dois(manifest):
        commands.append(
            [
                "PYTHONPATH=src",
                "python3",
                "scripts/snapshot_expected.py",
                "--doi",
                doi,
                "--review",
            ]
        )
        commands.append(
            [
                "PYTHONPATH=src",
                "python3",
                "scripts/snapshot_expected.py",
                "--doi",
                doi,
            ]
        )
        commands.append(
            [
                "PYTHONPATH=src",
                "python3",
                "scripts/onboard_from_manifests.py",
                "check-snapshot",
                "--provider",
                provider,
                "--doi",
                doi,
            ]
        )
    return commands


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
