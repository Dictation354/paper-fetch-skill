# ruff: noqa
from __future__ import annotations


def build_discover_brief(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    output_manifest: str,
    evidence_pack: str | None = None,
) -> dict[str, Any]:
    """Build the worker input for the manifest discovery task."""
    provider_name = _provider_slug(provider)
    access_review = default_access_review_path(provider_name)
    evidence_pack_path = evidence_pack or default_evidence_pack_path(provider_name)
    return {
        "task_id": f"{provider_name}-{DISCOVER_STEP}",
        "current_step": DISCOVER_STEP,
        "runtime": "coding-agent-subagent",
        "provider_seed": {
            "name": provider_name,
            "domain": domain,
            "doi_prefix_hint": doi_prefix,
        },
        "output_manifest": output_manifest,
        "evidence_pack": {
            "path": evidence_pack_path,
            "producer": "prepare-discovery",
            "required_before_worker": True,
            "worker_should_use_as_evidence_not_manifest_source": True,
        },
        "contract_templates": _contract_templates_for_discovery(),
        "autofix_policy": {
            "coordinator_runs_before_validate": True,
            "allowed_fixes": [
                "missing structural containers",
                "empty success_criteria and extraction_hints defaults",
                "generation.source_queries coverage for discovery_proof queries",
                "discovery_proof selected_doi synchronization",
                "missing route, markdown, and figure asset contracts",
                "high-confidence DOI sample replacement from evidence pack",
            ],
            "will_not_set_access_approval": True,
            "will_not_mark_markdown_semantic_reviewed": True,
            "low_confidence_candidates": "record proof and rejection reasons only",
        },
        "access_review": access_review,
        "access_policy_constraints": {
            "source": access_review,
            "operator_gate": ACCESS_PREFLIGHT_STEP,
            "worker_must_not_infer_access_policy": True,
            "discovery_may_only_use_review_as_constraints": True,
        },
        "schema": SCHEMA_PATH,
        "hard_constraints": HARD_CONSTRAINTS_PATH,
        "search_requirements": {
            "routing": ROUTING_REQUIREMENTS,
            "doi_sample_purposes": DOI_SAMPLE_PURPOSES,
            "mandatory_discovery_proof": {
                "purposes": MANDATORY_DISCOVERY_PROOF_PURPOSES,
                "minimum_queries_per_purpose": 3,
                "query_must_include": [
                    "provider name, provider domain, or DOI prefix",
                    "purpose keyword",
                ],
                "candidate_pool_required": True,
                "worker_must_search_beyond_seed_doi": True,
                "record_rejections_by_doi": True,
                "selected_doi_must_match_doi_samples": True,
            },
        },
        "output_requirements": {
            "generation_generated_by": "ai_discovery",
            "doi_sample_evidence_keys": [
                "doi",
                "evidence_url",
                "evidence_reason",
                "observed_signals",
                "confidence",
            ],
            "required_non_null_sample_purposes": [
                "structure",
                "figure",
                "references",
            ],
            "optional_null_sample_purposes_require_discovery_proof": (
                MANDATORY_DISCOVERY_PROOF_PURPOSES
            ),
            "null_discovery_proof_requires": [
                "exhausted: true",
                "at least three recorded queries",
                "rejected candidate DOI reasons",
                "evidence_reason more specific than no sample found",
            ],
            "retry_error_code": "UNSUITABLE_DOI_SAMPLE",
        },
        "files_allowed_to_modify": [output_manifest],
        "files_must_not_modify": FILES_MUST_NOT_MODIFY,
        "no_commit": True,
    }


def _implementation_allowed_files(provider: str, manifest: str) -> list[str]:
    provider_name = _provider_slug(provider)
    return [
        manifest,
        f"src/paper_fetch/providers/{provider_name}.py",
        f"src/paper_fetch/providers/_{provider_name}_html.py",
        f"src/paper_fetch/providers/_{provider_name}_*.py",
        f"src/paper_fetch/providers/{provider_name}/**",
        f"tests/unit/test_{provider_name}_provider.py",
        f"tests/unit/test_{provider_name}_*.py",
        f"onboarding/reviews/{provider_name}.yml",
    ]


def _implementation_forbidden_files() -> list[str]:
    return [
        *SHARED_FILES_MUST_NOT_MODIFY,
        "src/paper_fetch/provider_catalog.py",
        *CENTRAL_PROVIDER_LOGIC_PATHS,
    ]


def _compact_cleaning_proposal_for_brief(provider: str) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    proposal_ref = default_cleaning_proposal_path(provider_name)
    evidence_ref = default_cleaning_evidence_path(provider_name)
    path = _repo_root() / proposal_ref
    base = {
        "artifact": proposal_ref,
        "evidence_artifact": evidence_ref,
        "producer_task": PROPOSE_CLEANING_STEP,
    }
    if not path.exists():
        return {
            **base,
            "status": "missing",
            "action": f"run python3 scripts/propose_cleaning_chain.py --provider {provider_name} --write",
        }
    try:
        proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {**base, "status": "invalid_yaml", "error": str(exc)}
    if not isinstance(proposal, dict):
        return {
            **base,
            "status": "invalid_shape",
            "error": "proposal root is not a mapping",
        }
    if proposal.get("schema_version") != 2:
        return {
            **base,
            "status": "legacy_schema",
            "schema_version": proposal.get("schema_version"),
            "action": f"rerun {PROPOSE_CLEANING_STEP} before implementation",
        }
    return {"status": "ready", "producer_task": PROPOSE_CLEANING_STEP, **proposal}


def build_implementation_brief(
    *,
    provider: str,
    manifest: str,
    manifest_yaml: str | None = None,
) -> dict[str, Any]:
    """Build the worker input for provider implementation."""
    provider_name = _provider_slug(provider)
    access_review = default_access_review_path(provider_name)
    brief: dict[str, Any] = {
        "task_id": f"{provider_name}-{IMPLEMENT_STEP}",
        "provider_manifest": manifest,
        "current_step": IMPLEMENT_STEP,
        "runtime": "coding-agent-subagent",
        "access_review": access_review,
        "access_policy_constraints": {
            "source": access_review,
            "must_follow_operator_review": True,
            "do_not_auto_login": True,
            "do_not_solve_captcha": True,
            "do_not_bypass_paywall_or_challenge": True,
            "challenge_or_permission_uncertainty": "stop_and_report",
        },
        "upstream_artifacts": {
            "task_dag": "task-dag.json",
            "capture_commands": f"onboarding/capture-commands/{provider_name}.txt",
            "cleaning_proposal": default_cleaning_proposal_path(provider_name),
            "cleaning_proposal_evidence": default_cleaning_evidence_path(provider_name),
            "scaffold_summary": f"onboarding/scaffold/{provider_name}.json",
        },
        "cleaning_proposal": _compact_cleaning_proposal_for_brief(provider_name),
        "hard_constraints": HARD_CONSTRAINTS_PATH,
        "human_review_policy": {
            "required_gates": [
                HUMAN_PREFLIGHT_REVIEW_GATE,
                FINAL_MARKDOWN_QUALITY_REVIEW_GATE,
            ],
            "fixture_level_operator_review": False,
            "operator_reviews_final_markdown_batch": True,
            "finalize_command": (
                "python3 scripts/onboard_from_manifests.py "
                f"finalize-review-artifact --provider {provider_name} "
                "--confirmed-final-quality"
            ),
        },
        "markdown_review_loop": {
            "required": True,
            "fixture_source": (
                "provider_manifest.fixtures.doi_samples + "
                "provider_manifest.extra_fixtures"
            ),
            "route_contract_source": "provider_manifest.route_contract",
            "markdown_contract_source": "provider_manifest.markdown_contract",
            "operator_review_granularity": "final_batch_only",
            "worker_prepares_review_artifact": True,
            "require_each_non_null_purpose_asserted": True,
            "require_positive_and_negative_markdown_assertions": True,
            "forbid_skipped_scaffold_placeholder": True,
        },
        "coordinator_integration_scope": {
            "route_sources": (
                "provider_manifest.route_sources maps main_path steps to "
                "runtime sources."
            ),
            "extra_fixtures": (
                "provider_manifest.extra_fixtures extends capture and Markdown "
                "review beyond fixed purpose slots."
            ),
            "post_worker_integrations": [
                "golden corpus adapter wiring",
                "runtime source/schema registration",
                "manifest/bundle sync-back",
            ],
        },
        "output_requirements": {
            "review_artifact": f"onboarding/reviews/{provider_name}.yml",
            "reviewed_fixtures": (
                "one entry per non-null provider_manifest.fixtures.doi_samples "
                "purpose and per provider_manifest.extra_fixtures item"
            ),
            "human_signoff": (
                "final batch signoff is written only by finalize-review-artifact "
                "after --confirmed-final-quality"
            ),
            "reviewed_fixture_fields": [
                "fixture",
                "purpose",
                "current_quality_status",
                "assertion",
                "final_signoff_state",
            ],
        },
        "acceptance": {
            "pytest": [
                f"PYTHONPATH=src python3 -m pytest tests/unit/test_{provider_name}_provider.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_markdown_review_contract.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_asset_contract.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_route_contract.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_bundle_completeness.py "
                "tests/unit/test_provider_owner_reuse.py -q",
            ],
            "grep_must_be_empty": [
                {
                    "pattern": provider_name,
                    "paths": CENTRAL_PROVIDER_LOGIC_PATHS,
                }
            ],
            "cleaning_contract_gate": [
                f"python3 scripts/onboard_from_manifests.py check-cleaning-proposal --provider {provider_name}",
                f"python3 scripts/propose_cleaning_chain.py --provider {provider_name} --check-contract",
            ],
            "live_review": {
                "required_for_provider_acceptance": _provider_requires_live_review(
                    provider_name
                ),
                "policy": (
                    "Future providers default to one provider subset live assets review; "
                    "legacy non-risk providers are exempt."
                ),
                "command": (
                    "PAPER_FETCH_RUN_LIVE=1 python3 "
                    f"scripts/run_golden_criteria_live_review.py --providers {provider_name}"
                ),
                "source_contract": "provider_manifest.route_sources",
                "markdown_contract": "provider_manifest.markdown_contract",
            },
        },
        "files_allowed_to_modify": _implementation_allowed_files(
            provider_name, manifest
        ),
        "files_must_not_modify": _implementation_forbidden_files(),
        "failure_recovery": {
            "policy": FAILURE_RECOVERY_PATH,
            "max_retries": MAX_WORKER_RETRIES,
            "forbidden_write_code": "WORKER_MODIFIED_FORBIDDEN_FILE",
            "acceptance_failure_retry_task": IMPLEMENT_STEP,
            "blocked_after_retry_exhaustion": True,
        },
        "manifest_adjustment_policy": {
            "allowed_only_for_failure_code": "MARKDOWN_CONTRACT_DRIFT",
            "allowed_path": manifest,
            "allowed_fields": ["markdown_contract.<purpose>"],
            "forbidden_fields": [
                "routing",
                "main_path",
                "route_contract",
                "fixtures",
                "extra_fixtures",
                "probe",
                "access_policy",
            ],
            "must_match_current_provider": provider_name,
        },
        "no_commit": True,
    }
    if manifest_yaml is not None:
        brief["manifest_yaml"] = manifest_yaml
    return brief


def build_dag(
    *,
    provider: str | None,
    manifest: str | None,
    include_discovery: bool,
    dry_run: bool,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider) if provider else None
    steps: list[dict[str, Any]] = []
    previous_step: str | None = None
    for step in TASK_DAG:
        if step.id == DISCOVER_STEP and not include_discovery:
            continue
        item: dict[str, Any] = {
            "id": step.id,
            "type": step.type,
            "owner": step.owner,
            "depends_on": [previous_step] if previous_step else [],
            "retry_limit": MAX_WORKER_RETRIES if step.type == "worker-brief" else 0,
        }
        if step.brief is not None:
            item["brief"] = step.brief
        if step.command:
            item["command"] = list(step.command)
        if step.id == ACCESS_PREFLIGHT_STEP and provider_name is not None:
            item["produces"] = [default_access_review_path(provider_name)]
        if step.id == DISCOVER_STEP and manifest is not None:
            item["produces"] = [manifest]
        if step.id == PROPOSE_CLEANING_STEP and provider_name is not None:
            item["produces"] = [
                default_cleaning_proposal_path(provider_name),
                default_cleaning_evidence_path(provider_name),
            ]
        steps.append(item)
        previous_step = step.id
    return {
        "provider": provider_name,
        "manifest": manifest,
        "dry_run": dry_run,
        "runtime": "coding-agent-subagent",
        "human_gates": [
            {
                "id": HUMAN_PREFLIGHT_REVIEW_GATE,
                "purpose": "operator reviews access policy, route waterfall, runtime constraints, and purpose coverage plan before automated fixture work",
                "command": (
                    "python3 scripts/onboard_from_manifests.py "
                    f"prepare-human-preflight --provider {provider_name}"
                    if provider_name is not None
                    else None
                ),
                "blocks": DISCOVER_STEP,
                "operator_must_edit": default_access_review_path(provider_name)
                if provider_name is not None
                else None,
            },
            {
                "id": FINAL_MARKDOWN_QUALITY_REVIEW_GATE,
                "purpose": "operator reviews final extracted.md quality summary once automated quality checks pass",
                "command": (
                    "python3 scripts/onboard_from_manifests.py "
                    f"finalize-review-artifact --provider {provider_name} "
                    "--confirmed-final-quality"
                    if provider_name is not None
                    else None
                ),
                "blocks": "merge-ready",
                "operator_must_review": [
                    "tests/fixtures/**/extracted.md",
                    "tests/fixtures/**/markdown-quality.json",
                    f"onboarding/reviews/{provider_name}.yml"
                    if provider_name is not None
                    else "onboarding/reviews/<provider>.yml",
                ],
            },
        ],
        "agent_cli_env": AGENT_CLI_ENV,
        "worker_dispatch": {
            "default": DEFAULT_CODEX_AGENT_CLI,
            "override_env": AGENT_CLI_ENV,
            "prompt_transport": "stdin",
        },
        "state_schema": STATE_SCHEMA_PATH,
        "serial": {
            "single_provider": True,
            "single_task": True,
            "no_matrix": True,
        },
        "steps": steps,
    }


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if "\n" in text or "\r" in text:
        return json.dumps(text)
    if text in {"-", "?", ":"} or text.startswith(("- ", "? ", ": ")):
        return json.dumps(text)
    if any(
        char in text
        for char in [
            ":",
            "#",
            "{",
            "}",
            "[",
            "]",
            ",",
            "&",
            "*",
            "!",
            "|",
            ">",
            "'",
            '"',
        ]
    ):
        return json.dumps(text)
    if text.lower() in {"null", "true", "false", "yes", "no"}:
        return json.dumps(text)
    return text


def to_yaml(data: Any, *, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(to_yaml(value, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    elif isinstance(data, list):
        if not data:
            lines.append(f"{prefix}[]")
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(to_yaml(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(data)}")
    return "\n".join(lines)
