# ruff: noqa
from __future__ import annotations


def _fixture_path_for_doi(doi: str) -> str | None:
    try:
        golden_manifest = _load_golden_manifest()
    except ToolError:
        return None
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        return None
    sample_id, sample = sample_entry
    return (
        _fixture_root_for_sample(sample_id, sample).relative_to(_repo_root()).as_posix()
    )


def _fixture_asset_paths_for_doi(doi: str) -> dict[str, Any]:
    try:
        golden_manifest = _load_golden_manifest()
    except ToolError:
        return {}
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        return {}
    _sample_id, sample = sample_entry
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    raw_path = None
    for name in (
        "original.xml",
        "original.pdf",
        "original.html",
        "raw.html",
        "article.html",
    ):
        value = assets.get(name)
        if isinstance(value, str) and value:
            raw_path = value
            break
    quality_path_value = assets.get("markdown-quality.json")
    quality_status = None
    if isinstance(quality_path_value, str) and quality_path_value:
        quality_path = _repo_root() / quality_path_value
        if quality_path.is_file():
            try:
                quality = json.loads(quality_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                quality_status = "invalid"
            else:
                quality_status = (
                    quality.get("status") if isinstance(quality, dict) else "invalid"
                )
        else:
            quality_status = "missing"
    return {
        "raw_path": raw_path,
        "extracted_markdown_path": assets.get("extracted.md"),
        "markdown_quality_path": quality_path_value,
        "markdown_quality_status": quality_status,
        "expected_json_path": assets.get("expected.json"),
        "expected_outcome": sample.get("expected_outcome"),
        "route_kind": sample.get("route_kind"),
        "content_type": sample.get("content_type"),
    }


def _discovery_proof_summary(
    manifest_fixtures: dict[str, Any],
    purpose: str,
    doi: str | None,
) -> dict[str, Any] | None:
    proof_map = (
        manifest_fixtures.get("discovery_proof")
        if isinstance(manifest_fixtures.get("discovery_proof"), dict)
        else {}
    )
    proof = proof_map.get(purpose)
    if not isinstance(proof, dict):
        return None
    queries = proof.get("queries") if isinstance(proof.get("queries"), list) else []
    candidates = (
        proof.get("candidates") if isinstance(proof.get("candidates"), list) else []
    )
    rejections = (
        proof.get("rejections") if isinstance(proof.get("rejections"), dict) else {}
    )
    selected_doi = proof.get("selected_doi")
    evidence_summary = normalize_text(str(proof.get("evidence_summary") or ""))
    exhausted = proof.get("exhausted")
    complete = (
        bool(evidence_summary)
        and len(queries) >= 3
        and len(candidates) >= 3
        and (selected_doi == doi if doi else exhausted is True)
        and (not doi or selected_doi in candidates)
        and bool(rejections)
    )
    return {
        "status": "complete" if complete else "needs_review",
        "queries_count": len(queries),
        "candidates": candidates,
        "selected_doi": selected_doi,
        "rejection_count": len(rejections),
        "exhausted": exhausted,
        "evidence_summary": evidence_summary or None,
    }


def _manifest_fixture_summary(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    manifest_fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        manifest_fixtures.get("doi_samples")
        if isinstance(manifest_fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict):
            continue
        doi = sample.get("doi")
        asset_paths = _fixture_asset_paths_for_doi(str(doi)) if doi else {}
        proof_summary = _discovery_proof_summary(
            manifest_fixtures,
            str(purpose),
            str(doi) if doi else None,
        )
        item = {
            "purpose": purpose,
            "doi": doi,
            "confidence": sample.get("confidence"),
            "observed_signals": sample.get("observed_signals") or [],
            "evidence_url": sample.get("evidence_url"),
            "evidence_reason": sample.get("evidence_reason"),
            "fixture_path": _fixture_path_for_doi(str(doi)) if doi else None,
            "raw_path": asset_paths.get("raw_path"),
            "extracted_markdown_path": asset_paths.get("extracted_markdown_path"),
            "markdown_quality_path": asset_paths.get("markdown_quality_path"),
            "markdown_quality_status": asset_paths.get("markdown_quality_status"),
            "expected_json_path": asset_paths.get("expected_json_path"),
            "expected_outcome": asset_paths.get("expected_outcome"),
            "route_kind": asset_paths.get("route_kind"),
            "content_type": asset_paths.get("content_type"),
            "proof_status": (
                proof_summary["status"]
                if proof_summary is not None
                else "fixture_captured"
                if doi and asset_paths.get("raw_path")
                else "human_review_required"
            ),
            "discovery_proof": proof_summary,
            "null_reason": None if doi else sample.get("evidence_reason"),
        }
        fixtures.append(item)
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict):
                continue
            doi = sample.get("doi")
            asset_paths = _fixture_asset_paths_for_doi(str(doi)) if doi else {}
            fixtures.append(
                {
                    "purpose": sample.get("purpose") or f"extra_fixtures[{index}]",
                    "doi": doi,
                    "confidence": sample.get("confidence"),
                    "observed_signals": sample.get("observed_signals") or [],
                    "evidence_url": sample.get("evidence_url"),
                    "evidence_reason": sample.get("evidence_reason"),
                    "fixture_path": _fixture_path_for_doi(str(doi)) if doi else None,
                    "raw_path": asset_paths.get("raw_path"),
                    "extracted_markdown_path": asset_paths.get(
                        "extracted_markdown_path"
                    ),
                    "markdown_quality_path": asset_paths.get("markdown_quality_path"),
                    "markdown_quality_status": asset_paths.get(
                        "markdown_quality_status"
                    ),
                    "expected_json_path": asset_paths.get("expected_json_path"),
                    "expected_outcome": asset_paths.get("expected_outcome"),
                    "route_kind": asset_paths.get("route_kind"),
                    "content_type": asset_paths.get("content_type"),
                    "proof_status": (
                        "extra_fixture_captured"
                        if doi and asset_paths.get("raw_path")
                        else "human_review_required"
                    ),
                    "discovery_proof": None,
                    "null_reason": None if doi else sample.get("evidence_reason"),
                }
            )
    return fixtures


def _review_artifact_summary(provider: str) -> dict[str, Any]:
    path = _repo_root() / "onboarding" / "reviews" / f"{provider}.yml"
    if not path.exists():
        return {
            "status": "missing",
            "path": path.relative_to(_repo_root()).as_posix(),
            "fixtures": [],
        }
    try:
        review = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {
            "status": "invalid_yaml",
            "path": path.relative_to(_repo_root()).as_posix(),
            "error": str(exc),
            "fixtures": [],
        }
    fixtures = review.get("fixtures") if isinstance(review, dict) else None
    summaries: list[dict[str, Any]] = []
    if isinstance(fixtures, list):
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue
            fixes = (
                fixture.get("fixes") if isinstance(fixture.get("fixes"), list) else []
            )
            issues = (
                fixture.get("issues") if isinstance(fixture.get("issues"), list) else []
            )
            quality_status = None
            quality_path_value = fixture.get("markdown_quality_path")
            if isinstance(quality_path_value, str) and quality_path_value:
                quality_path = _repo_root() / quality_path_value
                if quality_path.is_file():
                    try:
                        quality = json.loads(quality_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        quality_status = "invalid"
                    else:
                        quality_status = (
                            quality.get("status")
                            if isinstance(quality, dict)
                            else "invalid"
                        )
                else:
                    quality_status = "missing"
            summaries.append(
                {
                    "fixture": fixture.get("fixture"),
                    "purpose": fixture.get("purpose"),
                    "doi": fixture.get("doi"),
                    "issue_ids": [
                        issue.get("id")
                        for issue in issues
                        if isinstance(issue, dict) and issue.get("id")
                    ],
                    "fix_ids": [
                        fix.get("id")
                        for fix in fixes
                        if isinstance(fix, dict) and fix.get("id")
                    ],
                    "test_names": sorted(
                        {
                            str(test_name)
                            for fix in fixes
                            if isinstance(fix, dict)
                            for test_name in (fix.get("test_names") or [])
                        }
                    ),
                    "markdown_semantic_reviewed": fixture.get(
                        "markdown_semantic_reviewed"
                    ),
                    "markdown_quality_status": quality_status,
                }
            )
    reviewed_values = [
        item.get("markdown_semantic_reviewed")
        for item in summaries
        if "markdown_semantic_reviewed" in item
    ]
    quality_values = [
        item.get("markdown_quality_status")
        for item in summaries
        if item.get("markdown_quality_status") is not None
    ]
    return {
        "status": "present",
        "path": path.relative_to(_repo_root()).as_posix(),
        "semantic_review_status": (
            "complete"
            if reviewed_values and all(value is True for value in reviewed_values)
            else "pending"
        ),
        "markdown_quality_status": (
            "pass"
            if quality_values and all(value == "pass" for value in quality_values)
            else "pending"
            if not quality_values
            or any(value == PENDING_STATUS for value in quality_values)
            else "fail"
        ),
        "fixtures": summaries,
    }


def build_provider_summary(
    *,
    provider: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    provider_state = (
        providers.get(provider_name) if isinstance(providers, dict) else None
    )
    if not isinstance(provider_state, dict):
        provider_state = {
            "provider": provider_name,
            "manifest": default_manifest_path(provider_name),
            "status": "not_started",
            "current_step": None,
        }
    manifest_path = _repo_root() / str(
        provider_state.get("manifest") or default_manifest_path(provider_name)
    )
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = _read_manifest(manifest_path)
    runs = (
        provider_state.get("runs")
        if isinstance(provider_state.get("runs"), dict)
        else {}
    )
    verifications = (
        provider_state.get("verifications")
        if isinstance(provider_state.get("verifications"), dict)
        else {}
    )
    repairs = (
        provider_state.get("repairs")
        if isinstance(provider_state.get("repairs"), dict)
        else {}
    )
    markdown_quality_repairs = (
        repairs.get("markdown_quality")
        if isinstance(repairs.get("markdown_quality"), list)
        else []
    )
    diagnosis = diagnose_provider_state(provider_state)
    summary: dict[str, Any] = {
        "provider": provider_name,
        "status": provider_state.get("status"),
        "current_step": provider_state.get("current_step"),
        "failed_task": diagnosis["failure"].get("task"),
        "failure_code": diagnosis["failure"].get("code"),
        "failure_recovery_action": diagnosis["failure"].get("action"),
        "access_review": diagnosis["access_review"],
        "manifest": {
            "path": manifest_path.relative_to(_repo_root()).as_posix(),
            "main_path": manifest.get("main_path"),
            "route_sources": manifest.get("route_sources"),
            "display_source": manifest.get("display_source"),
        },
        "fixture_coverage": _manifest_fixture_summary(manifest) if manifest else [],
        "review_artifact": _review_artifact_summary(provider_name),
        "markdown_quality_repairs": [
            repair for repair in markdown_quality_repairs if isinstance(repair, dict)
        ][-5:],
        "run_checks": [
            {
                "task": task,
                "result": run.get("result"),
                "commands": run.get("commands"),
                "failure_code": (
                    run.get("failure", {}).get("code")
                    if isinstance(run.get("failure"), dict)
                    else None
                ),
            }
            for task, run in runs.items()
            if isinstance(run, dict)
        ],
        "verification_plans": [
            {
                "task": task,
                "result": plan.get("result"),
                "commands": plan.get("commands"),
            }
            for task, plan in verifications.items()
            if isinstance(plan, dict)
        ],
        "operator_action": None,
        "merge_ready_pr_draft": None,
    }
    if provider_state.get("status") == "blocked":
        plan = plan_resume_blocked(provider_state)
        summary["operator_action"] = (
            diagnosis["failure"].get("action")
            or "; ".join(plan["blockers"])
            or "inspect blocked provider state"
        )
    if provider_state.get("status") == "merge_ready":
        summary["merge_ready_pr_draft"] = (
            f"Add {provider_name} provider onboarding artifacts and local verification summary."
        )
    return summary


def normalize_agent_target(target: str | None) -> str:
    normalized = str(target or "local-ready").strip().lower().replace("_", "-")
    if normalized not in AGENT_TARGET_STEPS:
        raise ValueError(
            "target must be one of: " + ", ".join(sorted(AGENT_TARGET_STEPS))
        )
    return normalized


def agent_target_step(target: str | None) -> str:
    return AGENT_TARGET_STEPS[normalize_agent_target(target)]


def _provider_state_for_agent_summary(
    provider: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    provider_state = (
        providers.get(provider_name) if isinstance(providers, dict) else None
    )
    if isinstance(provider_state, dict):
        return provider_state
    return {
        "provider": provider_name,
        "manifest": default_manifest_path(provider_name),
        "status": "not_started",
        "current_step": None,
        "steps": list(_dag_step_ids(include_discovery=True)),
        "completed_steps": [],
        "task_statuses": {},
        "retry_counts": {},
        "verifications": {},
    }


def _step_completed(provider_state: dict[str, Any], step: str) -> bool:
    task_statuses = (
        provider_state.get("task_statuses")
        if isinstance(provider_state.get("task_statuses"), dict)
        else {}
    )
    completed_steps = (
        provider_state.get("completed_steps")
        if isinstance(provider_state.get("completed_steps"), list)
        else []
    )
    return task_statuses.get(step) == "completed" or step in completed_steps


def _agent_target_complete(provider_state: dict[str, Any], target: str) -> bool:
    target_name = normalize_agent_target(target)
    if target_name == "local-ready":
        return provider_state.get("status") != "blocked" and _step_completed(
            provider_state, AGENT_TARGET_STEPS[target_name]
        )
    return provider_state.get("status") == "merge_ready" or _step_completed(
        provider_state,
        AGENT_TARGET_STEPS[target_name],
    )


def _semantic_review_gate_pending(
    summary: dict[str, Any],
    provider_state: dict[str, Any],
    target: str,
) -> bool:
    if normalize_agent_target(target) != "merge-ready":
        return False
    review = summary.get("review_artifact")
    if not isinstance(review, dict) or review.get("status") != "present":
        return False
    if review.get("semantic_review_status") == "complete":
        return False
    return any(
        _step_completed(provider_state, step)
        for step in (
            SNAPSHOT_EXPECTED_STEP,
            "manifest-sync-back",
            "provider-local-acceptance",
            "global-lint",
        )
    )


def _agent_failure_action(summary: dict[str, Any]) -> str | None:
    code = summary.get("failure_code")
    if isinstance(code, str) and code in AGENT_FAILURE_USER_ACTIONS:
        return AGENT_FAILURE_USER_ACTIONS[code]
    action = summary.get("failure_recovery_action")
    return str(action) if action else None


def _agent_phase(
    summary: dict[str, Any],
    provider_state: dict[str, Any],
    target: str,
) -> str:
    status = summary.get("status")
    failure_code = summary.get("failure_code")
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    if status == "merge_ready":
        return "merge-ready"
    if _agent_target_complete(provider_state, target):
        return normalize_agent_target(target)
    if _semantic_review_gate_pending(summary, provider_state, target):
        return "user-gate"
    if status == "not_started":
        return (
            "user-gate" if access.get("status") not in {None, "missing"} else "intake"
        )
    if status == "blocked":
        if failure_code in OPERATOR_REQUIRED_FAILURE_CODES or not access.get(
            "approved"
        ):
            return "user-gate"
        return "blocked"
    if not access.get("approved") and access.get("status") not in {None, "missing"}:
        return "user-gate"
    if summary.get("current_step") == ACCESS_PREFLIGHT_STEP:
        return "preflight"
    return "running"


def _agent_completed_items(
    summary: dict[str, Any],
    provider_state: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    if access.get("approved"):
        items.append("access review 已批准")
    manifest = (
        summary.get("manifest") if isinstance(summary.get("manifest"), dict) else {}
    )
    manifest_path = manifest.get("path")
    if isinstance(manifest_path, str) and (_repo_root() / manifest_path).exists():
        items.append("manifest 已生成")
    if any(
        item.get("raw_path")
        for item in summary.get("fixture_coverage", [])
        if isinstance(item, dict)
    ):
        items.append("至少一个 fixture 已捕获")
    if _step_completed(provider_state, "scaffold"):
        items.append("provider-owned skeleton 已生成")
    if _step_completed(provider_state, "provider-local-acceptance"):
        items.append("最小 provider-local 验证通过")
    if provider_state.get("status") == "merge_ready":
        items.append("merge-ready 本地 gate 已完成")
    return items


def _compact_agent_samples(summary: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for item in summary.get("fixture_coverage", []):
        if not isinstance(item, dict):
            continue
        samples.append(
            {
                "purpose": item.get("purpose"),
                "doi": item.get("doi"),
                "confidence": item.get("confidence"),
                "proof_status": item.get("proof_status"),
                "evidence": item.get("evidence_reason") or item.get("null_reason"),
                "fixture_path": item.get("fixture_path"),
                "extracted_markdown_path": item.get("extracted_markdown_path"),
                "markdown_quality_status": item.get("markdown_quality_status"),
            }
        )
    return samples


def _markdown_review_user_summary(summary: dict[str, Any]) -> dict[str, Any]:
    review = summary.get("review_artifact")
    if not isinstance(review, dict):
        return {"status": "missing", "fixtures": []}
    return {
        "status": review.get("status"),
        "path": review.get("path"),
        "semantic_review_status": review.get("semantic_review_status"),
        "markdown_quality_status": review.get("markdown_quality_status"),
        "fixtures": review.get("fixtures")
        if isinstance(review.get("fixtures"), list)
        else [],
    }


def _agent_related_files(
    provider: str,
    summary: dict[str, Any],
    state_path: Path,
) -> list[str]:
    provider_name = _provider_slug(provider)
    files: list[str] = []
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    for value in (
        access.get("path"),
        summary.get("manifest", {}).get("path")
        if isinstance(summary.get("manifest"), dict)
        else None,
        summary.get("review_artifact", {}).get("path")
        if isinstance(summary.get("review_artifact"), dict)
        else None,
        str(state_path),
        f".paper-fetch-runs/{provider_name}-onboarding/",
    ):
        if isinstance(value, str) and value and value not in files:
            files.append(value)
    for sample in _compact_agent_samples(summary):
        for key in ("extracted_markdown_path", "fixture_path"):
            value = sample.get(key)
            if isinstance(value, str) and value and value not in files:
                files.append(value)
                break
        if len(files) >= 8:
            break
    return files


def build_agent_user_summary(
    *,
    provider: str,
    state: dict[str, Any],
    target: str | None = None,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    target_name = normalize_agent_target(target)
    state_ref = _state_path(str(state_path))
    provider_state = _provider_state_for_agent_summary(provider_name, state)
    summary = build_provider_summary(provider=provider_name, state=state)
    phase = _agent_phase(summary, provider_state, target_name)
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    failure_action = _agent_failure_action(summary)
    review = _markdown_review_user_summary(summary)
    if phase == "local-ready":
        why_stopped = (
            "已达到默认目标 local-ready：主路径本地可用，最小 provider-local 验证通过。"
        )
        next_action = (
            f"如需完整合入标准，请告诉我：继续 {provider_name} provider 到 merge-ready"
        )
    elif phase == "merge-ready":
        why_stopped = "已达到 merge-ready：完整本地 acceptance 和人工语义签字均已完成。"
        next_action = "未发现必需的下一步。"
    elif phase == "user-gate" and not access.get("approved"):
        why_stopped = "access review 还没有人工批准，agent 不能替你批准合法访问策略。"
        next_action = (
            f"打开 {access.get('path') or default_access_review_path(provider_name)}，"
            f"确认 allowed_runtimes、challenge_policy、status、may_continue；确认后对我说：继续 {provider_name} provider"
        )
    elif phase == "user-gate" and review.get("semantic_review_status") != "complete":
        why_stopped = (
            "Markdown semantic review 需要人工基于当前 extracted.md 和质量报告签字。"
        )
        next_action = (
            "阅读 extracted.md、markdown-quality.json 和 "
            f"{review.get('path') or f'onboarding/reviews/{provider_name}.yml'}；"
            f"确认后对我说：继续 {provider_name} provider 到 merge-ready"
        )
    elif phase in {"blocked", "user-gate"}:
        why_stopped = failure_action or "runner 停在需要诊断的 blocked state。"
        next_action = (
            failure_action
            or f"查看相关 artifact 后对我说：诊断 {provider_name} provider 为什么卡住"
        )
    elif phase == "intake":
        why_stopped = "还没有足够的 provider 启动信息。"
        next_action = (
            f"请提供 domain，例如：添加 {provider_name} provider，domain 是 example.org"
        )
    else:
        why_stopped = "没有停在人工 gate；项目 runner 可以继续推进。"
        next_action = f"继续运行项目 runner 到下一个人工 gate 或 {target_name}"
    return {
        "provider": provider_name,
        "target": target_name,
        "target_step": agent_target_step(target_name),
        "phase": phase,
        "status": summary.get("status"),
        "current_step": summary.get("current_step"),
        "failed_task": summary.get("failed_task"),
        "failure_code": summary.get("failure_code"),
        "why_stopped": why_stopped,
        "completed": _agent_completed_items(summary, provider_state),
        "next_user_action": next_action,
        "related_files": _agent_related_files(provider_name, summary, state_ref),
        "samples": _compact_agent_samples(summary),
        "markdown_review": review,
        "operator_action": summary.get("operator_action"),
    }


def render_agent_user_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "当前状态:",
        f"- provider: {payload.get('provider')}",
        f"- 目标: {payload.get('target')}",
        f"- 阶段: {payload.get('phase')}",
    ]
    if payload.get("current_step"):
        lines.append(f"- 当前 task: {payload.get('current_step')}")
    if payload.get("failure_code"):
        lines.append(f"- failure code: {payload.get('failure_code')}")
    lines.extend(["", "为什么停:", f"- {payload.get('why_stopped')}"])
    completed = (
        payload.get("completed") if isinstance(payload.get("completed"), list) else []
    )
    lines.extend(["", "已完成:"])
    if completed:
        lines.extend(f"- {item}" for item in completed)
    else:
        lines.append("- 暂无可确认的完成项")
    if payload.get("phase") == "local-ready":
        lines.extend(
            [
                "",
                "尚未承诺:",
                "- 完整 fixture coverage",
                "- Markdown semantic review",
                "- expected snapshots",
                "- shared docs / changelog",
                "- global lint / merge-ready acceptance",
            ]
        )
    samples = payload.get("samples") if isinstance(payload.get("samples"), list) else []
    if samples:
        lines.extend(["", "样本候选:"])
        for sample in samples[:8]:
            if not isinstance(sample, dict):
                continue
            evidence = sample.get("evidence")
            evidence_suffix = f"，证据: {evidence}" if evidence else ""
            lines.append(
                "- "
                f"{sample.get('purpose')}: {sample.get('doi') or 'null'} "
                f"confidence={sample.get('confidence')} "
                f"proof={sample.get('proof_status')}"
                f"{evidence_suffix}"
            )
    markdown_review = payload.get("markdown_review")
    if isinstance(markdown_review, dict) and markdown_review.get("status") != "missing":
        lines.extend(
            [
                "",
                "Markdown review:",
                f"- artifact: {markdown_review.get('path')}",
                f"- semantic: {markdown_review.get('semantic_review_status')}",
                f"- quality: {markdown_review.get('markdown_quality_status')}",
            ]
        )
    lines.extend(["", "下一步:", f"- {payload.get('next_user_action')}"])
    related = (
        payload.get("related_files")
        if isinstance(payload.get("related_files"), list)
        else []
    )
    if related:
        lines.extend(["", "相关文件:"])
        lines.extend(f"- {path}" for path in related)
    return "\n".join(lines) + "\n"


def _markdown_scalar(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_command(command: Any) -> str:
    if isinstance(command, list):
        return shlex.join(str(part) for part in command)
    if isinstance(command, str):
        return command
    return _markdown_scalar(command)


def _append_markdown_commands(lines: list[str], commands: Any) -> None:
    if not isinstance(commands, list) or not commands:
        lines.append("  - commands: []")
        return
    for command in commands:
        lines.append(f"  - command: `{_markdown_command(command)}`")


def render_provider_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# {summary['provider']} onboarding summary",
        "",
        f"- status: {summary.get('status')}",
        f"- current_step: {summary.get('current_step')}",
        f"- failed_task: {summary.get('failed_task')}",
        f"- failure_code: {summary.get('failure_code')}",
        f"- failure_recovery_action: {summary.get('failure_recovery_action')}",
        f"- access_review: {summary['access_review'].get('status')}",
        "",
        "## Manifest",
        "",
        f"- path: {summary['manifest'].get('path')}",
        f"- display_source: {summary['manifest'].get('display_source')}",
        f"- main_path: {summary['manifest'].get('main_path')}",
        f"- route_sources: {summary['manifest'].get('route_sources')}",
        "",
        "## Fixture Coverage",
        "",
    ]
    for fixture in summary.get("fixture_coverage", []):
        lines.append(
            "- "
            f"{fixture.get('purpose')}: doi={fixture.get('doi')} "
            f"fixture={fixture.get('fixture_path')} "
            f"expected={fixture.get('expected_outcome')}"
        )

    review = summary.get("review_artifact")
    lines.extend(["", "## Review Artifact", ""])
    if not isinstance(review, dict):
        lines.append("- missing review artifact summary")
    else:
        lines.append(f"- status: {review.get('status')}")
        lines.append(f"- path: {review.get('path')}")
        lines.append(
            f"- semantic_review_status: {review.get('semantic_review_status')}"
        )
        lines.append(
            f"- markdown_quality_status: {review.get('markdown_quality_status')}"
        )
        fixtures = (
            review.get("fixtures") if isinstance(review.get("fixtures"), list) else []
        )
        if not fixtures:
            lines.append("- no review fixture summaries")
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue
            lines.append(
                "- "
                f"{fixture.get('fixture')}/{fixture.get('purpose')}: "
                f"doi={fixture.get('doi')} "
                f"reviewed={fixture.get('markdown_semantic_reviewed')} "
                f"quality={fixture.get('markdown_quality_status')} "
                f"issue_ids={_markdown_scalar(fixture.get('issue_ids') or [])} "
                f"fix_ids={_markdown_scalar(fixture.get('fix_ids') or [])} "
                f"tests={_markdown_scalar(fixture.get('test_names') or [])}"
            )

    lines.extend(["", "## Markdown Quality Repairs", ""])
    repairs = summary.get("markdown_quality_repairs") or []
    if not repairs:
        lines.append("- no recorded markdown quality repairs")
    for repair in repairs:
        if not isinstance(repair, dict):
            continue
        failure = (
            repair.get("failure") if isinstance(repair.get("failure"), dict) else {}
        )
        lines.append(
            "- "
            f"doi={repair.get('doi')} "
            f"status={repair.get('status')} "
            f"attempts={repair.get('attempts')} "
            f"quality={repair.get('quality_status')} "
            f"failure={failure.get('code')} "
            f"run_dir={repair.get('run_dir')}"
        )

    lines.extend(["", "## Run Checks", ""])
    run_checks = summary.get("run_checks") or []
    if not run_checks:
        lines.append("- no recorded run-check results")
    for run in run_checks:
        lines.append(
            f"- {run.get('task')}: result={run.get('result')} failure_code={run.get('failure_code')}"
        )
        _append_markdown_commands(lines, run.get("commands"))

    lines.extend(["", "## Verification Plans", ""])
    verification_plans = summary.get("verification_plans") or []
    if not verification_plans:
        lines.append("- no recorded verification plans")
    for plan in verification_plans:
        lines.append(f"- {plan.get('task')}: result={plan.get('result')}")
        _append_markdown_commands(lines, plan.get("commands"))

    lines.extend(["", "## Operator Action", ""])
    lines.append(f"- {summary.get('operator_action') or 'none recorded'}")
    if summary.get("merge_ready_pr_draft"):
        lines.extend(["", "## PR Draft", "", str(summary["merge_ready_pr_draft"])])
    return "\n".join(lines) + "\n"


def run_diagnose(args: argparse.Namespace) -> int:
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    if args.provider:
        provider_name = _provider_slug(args.provider)
        provider_state = providers.get(provider_name)
        if not isinstance(provider_state, dict):
            raise ToolError(
                "TASK_BRIEF_INVALID",
                f"provider is missing from state: {provider_name}",
                retryable=False,
                provider=provider_name,
                task_id=f"{provider_name}-diagnose",
            )
        diagnoses = [diagnose_provider_state(provider_state)]
    else:
        diagnoses = [
            diagnose_provider_state(provider_state)
            for provider_state in providers.values()
            if isinstance(provider_state, dict)
        ]
    print(
        json.dumps(
            {
                "state": str(state_path),
                "providers": diagnoses,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_resume_blocked(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    provider_state = providers.get(provider)
    if not isinstance(provider_state, dict):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"provider is missing from state: {provider}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-resume-blocked",
        )
    plan = plan_resume_blocked(provider_state)
    payload = {"resume_plan": {**plan, "until": args.until}, "state": str(state_path)}
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not plan["resumable"]:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            "blocked provider is not resumable without operator action.",
            retryable=False,
            provider=provider,
            manifest=provider_state.get("manifest"),
            task_id=f"{provider}-resume-blocked",
            details=payload,
        )
    steps = (
        provider_state.get("steps")
        if isinstance(provider_state.get("steps"), list)
        else []
    )
    if args.until not in steps:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"--until must name a task in the provider state DAG: {args.until}",
            retryable=False,
            provider=provider,
            manifest=provider_state.get("manifest"),
            task_id=f"{provider}-resume-blocked",
            details={"until": args.until, "steps": steps},
        )
    next_task = str(plan["next_task"])
    task_statuses = provider_state.setdefault("task_statuses", {})
    task_statuses[next_task] = "in_progress"
    provider_state["current_step"] = next_task
    provider_state["status"] = "in_progress"
    state["active_provider"] = provider
    _write_json(state_path, state)
    source = _source_from_provider_state(provider_state)
    output_dir = Path(args.output_dir or f".paper-fetch-runs/{provider}-onboarding")
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    run_payload = _execute_run_loop(
        source=source,
        output_dir=output_dir,
        state_path=state_path,
        state=state,
        provider_state=provider_state,
        until=args.until,
        domain=None,
        doi_prefix=None,
    )
    print(json.dumps({**payload, "run": run_payload}, indent=2, sort_keys=True))
    return 0


def run_summarize(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    if args.format in {"agent-json", "agent-markdown"}:
        summary = build_agent_user_summary(
            provider=provider,
            state=state,
            target=args.target,
            state_path=state_path,
        )
    else:
        summary = build_provider_summary(provider=provider, state=state)
    if args.format in {"json", "agent-json"}:
        content = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    elif args.format == "agent-markdown":
        content = render_agent_user_summary_markdown(summary)
    else:
        content = render_provider_summary_markdown(summary)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = _repo_root() / output_path
        write_text(output_path, content)
    else:
        print(content, end="")
    return 0


def run_prepare_human_preflight(args: argparse.Namespace) -> int:
    payload = build_human_preflight_digest(
        provider=args.provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
    )
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = _repo_root() / output_path
        write_text(output_path, content)
    else:
        print(content, end="")
    return 0


def run_finalize_review_artifact(args: argparse.Namespace) -> int:
    reviewed_by = args.reviewed_by or os.environ.get("USER") or "operator"
    payload = finalize_review_artifact(
        provider=args.provider,
        reviewed_by=reviewed_by,
        confirmed_final_quality=args.confirmed_final_quality,
        run_fresh_review=True,
    )
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end=""
    )
    return 0


def run_advance(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    task_statuses = provider_state["task_statuses"]
    if args.task not in task_statuses:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"unknown task for provider {provider}: {args.task}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-advance-{args.task}",
            details={"task": args.task},
        )
    if args.task == ACCESS_PREFLIGHT_STEP:
        validate_access_review(provider)
    elif (
        args.task == DISCOVER_STEP
        and ACCESS_PREFLIGHT_STEP not in provider_state["completed_steps"]
    ):
        validate_access_review(provider)
        raise ToolError(
            "ACCESS_REVIEW_NOT_APPROVED",
            "operator-access-preflight must be completed before discover-manifest.",
            retryable=False,
            provider=provider,
            manifest=provider_state.get("manifest"),
            task_id=f"{provider}-advance-{args.task}",
            details={
                "required_completed_step": ACCESS_PREFLIGHT_STEP,
                "task": args.task,
            },
        )
    task_statuses[args.task] = "completed"
    completed_steps = provider_state["completed_steps"]
    if args.task not in completed_steps:
        completed_steps.append(args.task)
    provider_state["current_step"] = None
    next_step = _next_pending_step(provider_state)
    if next_step is None:
        provider_state["status"] = "merge_ready"
        state["active_provider"] = None
    else:
        provider_state["status"] = "in_progress"
        state["active_provider"] = provider
    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "advanced": args.task,
                "status": provider_state["status"],
                "next_step": next_step,
                "state": str(state_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0
