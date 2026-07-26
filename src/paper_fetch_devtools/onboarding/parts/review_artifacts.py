# ruff: noqa
from __future__ import annotations


def _manifest_review_samples(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    contracts = (
        manifest.get("markdown_contract")
        if isinstance(manifest.get("markdown_contract"), dict)
        else {}
    )
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict) or not sample.get("doi"):
            continue
        contract = contracts.get(purpose)
        samples.append(
            {
                "purpose": str(purpose),
                "doi": _normalized_doi(str(sample["doi"])),
                "contract": contract if isinstance(contract, dict) else {},
                "fixture_family": "golden",
            }
        )
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict) or not sample.get("doi"):
                continue
            contract = sample.get("markdown_contract")
            samples.append(
                {
                    "purpose": str(sample.get("purpose") or f"extra_fixtures[{index}]"),
                    "doi": _normalized_doi(str(sample["doi"])),
                    "contract": contract if isinstance(contract, dict) else {},
                    "fixture_family": "golden",
                }
            )
    return samples


def _assertions_from_markdown_contract(contract: dict[str, Any]) -> list[str]:
    assertions: list[str] = []
    for value in contract.get("must_include") or ():
        assertions.append(f"must include {value}")
    for value in contract.get("must_not_include") or ():
        assertions.append(f"must not include {value}")
    for value in contract.get("must_match") or ():
        assertions.append(f"must match {value}")
    count_equals = contract.get("count_equals")
    if isinstance(count_equals, dict):
        for key, value in sorted(count_equals.items()):
            assertions.append(f"count {key} equals {value}")
    return assertions or ["baseline Markdown passed final batch review"]


def _contract_issues_for_markdown(
    contract: dict[str, Any], markdown_text: str
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, value in enumerate(contract.get("must_include") or (), start=1):
        if str(value) not in markdown_text:
            issues.append(
                {
                    "id": f"missing-include-{index}",
                    "severity": "high",
                    "summary": f"extracted Markdown is missing required text: {value}",
                }
            )
    for index, value in enumerate(contract.get("must_not_include") or (), start=1):
        if str(value) in markdown_text:
            issues.append(
                {
                    "id": f"forbidden-text-{index}",
                    "severity": "high",
                    "summary": f"extracted Markdown contains forbidden text: {value}",
                }
            )
    for index, pattern in enumerate(contract.get("must_match") or (), start=1):
        try:
            matched = re.search(str(pattern), markdown_text) is not None
        except re.error:
            matched = False
        if not matched:
            issues.append(
                {
                    "id": f"missing-pattern-{index}",
                    "severity": "high",
                    "summary": f"extracted Markdown does not match required pattern: {pattern}",
                }
            )
    count_equals = contract.get("count_equals")
    if isinstance(count_equals, dict):
        for index, (text, expected) in enumerate(sorted(count_equals.items()), start=1):
            try:
                expected_count = int(expected)
            except (TypeError, ValueError):
                expected_count = -1
            actual_count = markdown_text.count(str(text))
            if actual_count != expected_count:
                issues.append(
                    {
                        "id": f"count-mismatch-{index}",
                        "severity": "high",
                        "summary": (
                            f"extracted Markdown count for {text} is {actual_count}, "
                            f"expected {expected_count}"
                        ),
                    }
                )
    return issues


def _review_fixture_assets(
    *,
    provider: str,
    doi: str,
    task_id: str,
) -> dict[str, Any]:
    golden_manifest = _load_golden_manifest()
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is missing from golden criteria manifest.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=task_id,
            details={"doi": doi, "sample_id": _doi_slug(doi)},
        )
    sample_id, sample = sample_entry
    fixture_root = _fixture_root_for_sample(sample_id, sample)
    paths = {
        "expected": fixture_root / "expected.json",
        "markdown": fixture_root / "extracted.md",
        "prompt": fixture_root / "markdown-quality-prompt.md",
        "quality": fixture_root / "markdown-quality.json",
    }
    for key, path in paths.items():
        if not path.is_file():
            code = (
                "MARKDOWN_QUALITY_FAILED"
                if key in {"prompt", "quality"}
                else "EXPECTED_SNAPSHOT_FAILED"
            )
            raise ToolError(
                code,
                f"final review requires fixture artifact {path.name}.",
                retryable=True,
                provider=provider,
                manifest=default_manifest_path(provider),
                task_id=task_id,
                details={"doi": doi, "path": _rel(path)},
            )
    return {
        "sample_id": sample_id,
        "sample": sample,
        "fixture_root": fixture_root,
        **paths,
    }


def _quality_report_for_final_review(
    *,
    provider: str,
    doi: str,
    quality_path: Path,
    markdown_path: Path,
    prompt_path: Path,
    task_id: str,
) -> dict[str, Any]:
    quality = _read_json_object(
        quality_path,
        code="MARKDOWN_QUALITY_FAILED",
        task_id=task_id,
        provider=provider,
    )
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
            task_id=task_id,
            details={
                "doi": doi,
                "markdown_quality_path": _rel(quality_path),
                "validation_errors": validation_errors,
            },
        )
    blocking = blocking_markdown_quality_issues(quality)
    if quality.get("status") != "pass" or blocking:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Final review cannot be signed while markdown-quality.json is not pass.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=task_id,
            details={
                "doi": doi,
                "markdown_quality_path": _rel(quality_path),
                "status": quality.get("status"),
                "issues": blocking,
            },
        )
    return quality


def build_human_preflight_digest(
    *,
    provider: str,
    domain: str | None = None,
    doi_prefix: str | None = None,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    manifest_path = _manifest_path_for_provider(provider_name)
    manifest: dict[str, Any] = {}
    manifest_status = "missing"
    if manifest_path.exists():
        manifest = _read_manifest(manifest_path)
        manifest_status = "present"
    access = _access_review_summary(provider_name)
    fixtures = _manifest_fixture_summary(manifest) if manifest else []
    purpose_status = {
        str(item.get("purpose")): {
            "doi": item.get("doi"),
            "proof_status": item.get("proof_status"),
            "confidence": item.get("confidence"),
            "null_reason": item.get("null_reason"),
            "discovery_proof": item.get("discovery_proof"),
        }
        for item in fixtures
        if isinstance(item, dict)
    }
    missing_purposes = [
        purpose for purpose in DOI_SAMPLE_PURPOSES if purpose not in purpose_status
    ]
    route_contract = (
        manifest.get("route_contract")
        if isinstance(manifest.get("route_contract"), dict)
        else {}
    )
    route_sources = (
        manifest.get("route_sources")
        if isinstance(manifest.get("route_sources"), dict)
        else {}
    )
    main_path = (
        manifest.get("main_path") if isinstance(manifest.get("main_path"), list) else []
    )
    waterfall = [
        {
            "step": step,
            "source": route_sources.get(step) or manifest.get("display_source"),
            "success_requires": (
                route_contract.get(step, {}).get("success_requires")
                if isinstance(route_contract.get(step), dict)
                else []
            ),
            "reject_if_any": (
                route_contract.get(step, {}).get("reject_if_any")
                if isinstance(route_contract.get(step), dict)
                else []
            ),
        }
        for step in main_path
    ]
    return {
        "provider": provider_name,
        "gate": HUMAN_PREFLIGHT_REVIEW_GATE,
        "manifest": {
            "path": default_manifest_path(provider_name),
            "status": manifest_status,
            "display_source": manifest.get("display_source"),
            "routing": manifest.get("routing"),
            "main_path": main_path,
            "route_sources": route_sources,
        },
        "seed": {
            "domain": domain,
            "doi_prefix": doi_prefix,
        },
        "access_review": access,
        "waterfall": waterfall,
        "purpose_coverage": {
            "purposes": purpose_status,
            "missing_purposes": missing_purposes,
            "mandatory_discovery_proof_purposes": MANDATORY_DISCOVERY_PROOF_PURPOSES,
        },
        "asset_contract": manifest.get("asset_contract"),
        "operator_checklist": [
            "access review reflects legal access and allowed runtime",
            "waterfall order and route success/rejection rules are plausible",
            "table/formula/supplementary are either selected or have exhausted discovery proof",
            "strong local fixture signals are promoted or rejected with concrete reasons",
            "figure asset contract is body/download unless a concrete exception applies",
        ],
        "next_prompt": f"确认预检后对 agent 说：继续 {provider_name} provider",
    }


def finalize_review_artifact(
    *,
    provider: str,
    reviewed_by: str,
    confirmed_final_quality: bool,
    run_fresh_review: bool = True,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    task_id = f"{provider_name}-{FINAL_MARKDOWN_QUALITY_REVIEW_GATE}"
    if not confirmed_final_quality:
        raise ToolError(
            "FINAL_MARKDOWN_REVIEW_NOT_CONFIRMED",
            "Final Markdown review requires explicit --confirmed-final-quality.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"required_flag": "--confirmed-final-quality"},
        )
    manifest_path = _manifest_path_for_provider(provider_name)
    manifest = _read_manifest(manifest_path)
    samples = _manifest_review_samples(manifest)
    if not samples:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "Manifest does not contain non-null DOI fixtures for final review.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"manifest": default_manifest_path(provider_name)},
        )
    review_path = _repo_root() / "onboarding" / "reviews" / f"{provider_name}.yml"
    if review_path.exists():
        review = yaml.safe_load(review_path.read_text(encoding="utf-8"))
        if not isinstance(review, dict):
            raise ToolError(
                "REVIEW_ARTIFACT_INVALID",
                "Review artifact root must be a mapping.",
                retryable=True,
                provider=provider_name,
                manifest=default_manifest_path(provider_name),
                task_id=task_id,
                details={"path": _rel(review_path)},
            )
    else:
        review = {
            "schema_version": 2,
            "provider": provider_name,
            "fixtures": [],
        }
    existing_items = (
        review.get("fixtures") if isinstance(review.get("fixtures"), list) else []
    )
    existing = {
        (str(item.get("purpose")), _normalized_doi(str(item.get("doi") or ""))): item
        for item in existing_items
        if isinstance(item, dict)
    }
    finalized: list[dict[str, Any]] = []
    fresh_reports: list[str] = []
    for sample in samples:
        purpose = str(sample["purpose"])
        doi = str(sample["doi"])
        assets = _review_fixture_assets(
            provider=provider_name, doi=doi, task_id=task_id
        )
        quality = _quality_report_for_final_review(
            provider=provider_name,
            doi=doi,
            quality_path=assets["quality"],
            markdown_path=assets["markdown"],
            prompt_path=assets["prompt"],
            task_id=task_id,
        )
        if run_fresh_review:
            fresh = _run_fresh_markdown_quality_review(
                provider=provider_name,
                doi=doi,
                sample_id=str(assets["sample_id"]),
                purpose=purpose,
                markdown_path=assets["markdown"],
                prompt_path=assets["prompt"],
                task_id=task_id,
            )
            fresh_blocking = _fresh_markdown_quality_blocking_issues(fresh.report)
            if fresh.report.get("status") != "pass" or fresh_blocking:
                raise ToolError(
                    "MARKDOWN_QUALITY_FAILED",
                    "Fresh Markdown quality review found blocking issues before final signoff.",
                    retryable=True,
                    provider=provider_name,
                    manifest=default_manifest_path(provider_name),
                    task_id=task_id,
                    details={
                        "doi": doi,
                        "fresh_markdown_quality_path": _rel(fresh.report_path),
                        "fresh_markdown_quality_status": fresh.report.get("status"),
                        "issues": fresh_blocking,
                    },
                )
            fresh_reports.append(_rel(fresh.report_path))
        markdown_text = assets["markdown"].read_text(encoding="utf-8", errors="replace")
        contract_issues = _contract_issues_for_markdown(
            sample["contract"], markdown_text
        )
        if contract_issues:
            raise ToolError(
                "MARKDOWN_CONTRACT_DRIFT",
                "Final review cannot be signed while markdown_contract does not match extracted.md.",
                retryable=True,
                provider=provider_name,
                manifest=default_manifest_path(provider_name),
                task_id=task_id,
                details={
                    "doi": doi,
                    "purpose": purpose,
                    "baseline_markdown_path": _rel(assets["markdown"]),
                    "issues": contract_issues,
                },
            )
        current = existing.get((purpose, doi), {})
        finalized.append(
            {
                "fixture": _rel(assets["fixture_root"]),
                "purpose": purpose,
                "doi": doi,
                "baseline_markdown_path": _rel(assets["markdown"]),
                "baseline_markdown_sha256": _sha256_file(assets["markdown"]),
                "markdown_quality_path": _rel(assets["quality"]),
                "markdown_quality_sha256": _sha256_file(assets["quality"]),
                "review_notes": (
                    f"Final batch Markdown quality review confirmed by {reviewed_by}; "
                    f"persistent quality status={quality.get('status')}."
                ),
                "sample_representative": True,
                "markdown_semantic_reviewed": True,
                "issues": [],
                "assertions": current.get("assertions")
                if isinstance(current.get("assertions"), list)
                and current.get("assertions")
                else _assertions_from_markdown_contract(sample["contract"]),
                "fixes": [],
            }
        )
    now = _utc_now_iso()
    review["schema_version"] = 2
    review["provider"] = provider_name
    review["reviewed_at"] = now
    review["reviewed_by"] = reviewed_by
    review["final_markdown_quality_review"] = {
        "confirmed": True,
        "confirmed_by": reviewed_by,
        "confirmed_at": now,
        "method": FINAL_MARKDOWN_QUALITY_REVIEW_GATE,
        "fixture_count": len(finalized),
        "fresh_markdown_quality_reports": fresh_reports,
    }
    review["fixtures"] = finalized
    write_text(review_path, yaml.safe_dump(review, allow_unicode=True, sort_keys=False))
    return {
        "provider": provider_name,
        "review_path": _rel(review_path),
        "fixture_count": len(finalized),
        "fresh_markdown_quality_reports": fresh_reports,
        "result": "finalized",
    }


def _verify_commands(
    provider: str, task: str, *, include_live: bool = True
) -> list[list[str]]:
    provider_name = _provider_slug(provider)
    command_map: dict[str, list[list[str]]] = {
        ACCESS_PREFLIGHT_STEP: [
            [
                "test",
                "-f",
                default_access_review_path(provider_name),
            ],
        ],
        "validate-manifest": [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_manifest_schema.py",
                "tests/unit/test_known_providers_sync.py",
                "-q",
            ]
        ],
        "capture-fixtures": [
            [
                "python3",
                "scripts/capture_fixture.py",
                "--from-manifest",
                default_manifest_path(provider_name),
                "--all",
                "--auto-via",
                "--fail-fast",
                "--dry-run",
            ]
        ],
        PROPOSE_CLEANING_STEP: [
            [
                "python3",
                "scripts/propose_cleaning_chain.py",
                "--provider",
                provider_name,
                "--write",
            ]
        ],
        "scaffold": [
            [
                "python3",
                "scripts/scaffold_provider.py",
                "--from-manifest",
                default_manifest_path(provider_name),
                "--merge-existing=safe",
            ]
        ],
        IMPLEMENT_STEP: [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                f"tests/unit/test_{provider_name}_provider.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_markdown_review_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_asset_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_route_contract.py",
                "-q",
            ],
            [
                "git",
                "grep",
                "-n",
                provider_name,
                "--",
                *CENTRAL_PROVIDER_LOGIC_PATHS,
            ],
        ],
        SHARED_INTEGRATION_STEP: [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_manifest_bundle_sync.py",
                "tests/unit/test_golden_corpus_adapters.py",
                "tests/unit/test_provider_benchmark_samples.py",
                "tests/devtools/test_golden_criteria_live.py",
                "-q",
            ]
        ],
        "manifest-sync-back": [
            [
                "python3",
                "scripts/manifest_sync_back.py",
                "--provider",
                provider_name,
                "--manifest",
                default_manifest_path(provider_name),
                "--sync-docs",
            ]
        ],
        "provider-local-acceptance": [
            [
                "python3",
                "scripts/onboard_from_manifests.py",
                "check-cleaning-proposal",
                "--provider",
                provider_name,
            ],
            [
                "python3",
                "scripts/propose_cleaning_chain.py",
                "--provider",
                provider_name,
                "--check-contract",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                f"tests/unit/test_{provider_name}_provider.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_markdown_review_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_asset_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_route_contract.py",
                "-q",
            ],
            [
                "git",
                "grep",
                "-n",
                provider_name,
                "--",
                *CENTRAL_PROVIDER_LOGIC_PATHS,
            ],
        ],
        "global-lint": [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_manifest_bundle_sync.py",
                "tests/unit/test_provider_owner_reuse.py",
                "tests/unit/test_provider_bundle_completeness.py",
                "tests/unit/test_import_boundaries.py",
                "tests/unit/test_extraction_rules_validator.py",
                "-q",
            ]
        ],
        "merge-ready": [
            [
                "git",
                "diff",
                "--",
                default_manifest_path(provider_name),
                "onboarding/known-providers.yml",
                "docs/providers.md",
                "CHANGELOG.md",
            ]
        ],
    }
    if task == SNAPSHOT_EXPECTED_STEP:
        return _snapshot_expected_commands(provider_name)
    if (
        include_live
        and task == "provider-local-acceptance"
        and _provider_requires_live_review(provider_name)
    ):
        command_map["provider-local-acceptance"].append(
            [
                "PAPER_FETCH_RUN_LIVE=1",
                "python3",
                "scripts/run_golden_criteria_live_review.py",
                "--providers",
                provider_name,
            ]
        )
    return command_map.get(task, [])


def _load_golden_manifest() -> dict[str, Any]:
    path = _repo_root() / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "golden criteria manifest cannot be loaded.",
            retryable=True,
            task_id=SNAPSHOT_EXPECTED_STEP,
            details={
                "path": path.relative_to(_repo_root()).as_posix(),
                "reason": str(exc),
            },
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("samples"), dict):
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "golden criteria manifest must contain samples.",
            retryable=True,
            task_id=SNAPSHOT_EXPECTED_STEP,
            details={"path": path.relative_to(_repo_root()).as_posix()},
        )
    return data


def _golden_sample_for_doi(
    doi: str, manifest: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    slug = _doi_slug(doi)
    samples = manifest.get("samples", {})
    sample = samples.get(slug)
    if isinstance(sample, dict):
        return slug, sample
    normalized = _normalized_doi(doi)
    for sample_id, item in samples.items():
        if (
            isinstance(item, dict)
            and _normalized_doi(str(item.get("doi") or "")) == normalized
        ):
            return str(sample_id), item
    return None


def _fixture_root_for_sample(sample_id: str, sample: dict[str, Any]) -> Path:
    family = str(sample.get("fixture_family") or "golden")
    if family == "block":
        assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
        for value in assets.values():
            path = _repo_root() / str(value)
            if "tests/fixtures/block/" in path.as_posix():
                return path.parent
        return (
            _repo_root()
            / "tests"
            / "fixtures"
            / "block"
            / sample_id.removesuffix("__block")
        )
    return _repo_root() / "tests" / "fixtures" / "golden_criteria" / sample_id


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json_object(
    path: Path, *, code: str, task_id: str, provider: str | None = None
) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            code,
            f"JSON file cannot be loaded: {_rel(path)}",
            retryable=True,
            provider=provider,
            task_id=task_id,
            details={"path": _rel(path), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            code,
            f"JSON file root must be an object: {_rel(path)}",
            retryable=True,
            provider=provider,
            task_id=task_id,
            details={"path": _rel(path)},
        )
    return data


def _markdown_quality_report_errors(
    report: Any,
    *,
    markdown_path: Path,
    prompt_path: Path,
) -> list[str]:
    errors = validate_markdown_quality_report(report)
    if isinstance(report, dict):
        if report.get("markdown_path") != _rel(markdown_path):
            errors.append("markdown_path must point to extracted.md")
        if report.get("prompt_path") != _rel(prompt_path):
            errors.append("prompt_path must point to markdown-quality-prompt.md")
    else:
        errors.append("markdown quality report root must be an object")
    return errors


class FreshMarkdownQualityReview(NamedTuple):
    report: dict[str, Any]
    report_path: Path
    attempt_dir: Path


def _fresh_markdown_quality_attempt_dir(
    *,
    provider: str,
    doi: str,
    output_dir: Path | None,
) -> Path:
    base_dir = output_dir or (
        _repo_root() / f".paper-fetch-runs/{provider}-markdown-quality-audit"
    )
    if not base_dir.is_absolute():
        base_dir = _repo_root() / base_dir
    review_root = base_dir / _doi_slug(doi)
    existing: list[int] = []
    if review_root.is_dir():
        for child in review_root.iterdir():
            match = re.fullmatch(r"attempt-(\d+)", child.name)
            if match and child.is_dir():
                existing.append(int(match.group(1)))
    return review_root / f"attempt-{max(existing, default=0) + 1}"


def _parse_json_object_from_stdout(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_fresh_markdown_quality_review(
    *,
    provider: str,
    doi: str,
    sample_id: str,
    markdown_path: Path,
    prompt_path: Path,
    purpose: str | None = None,
    output_dir: Path | None = None,
    task_id: str | None = None,
) -> FreshMarkdownQualityReview:
    provider_name = _provider_slug(provider)
    normalized_doi = _normalized_doi(doi)
    argv = _agent_argv(
        provider=provider_name,
        task="fresh-markdown-quality-review",
        manifest=default_manifest_path(provider_name),
    )
    attempt_dir = _fresh_markdown_quality_attempt_dir(
        provider=provider_name,
        doi=normalized_doi,
        output_dir=output_dir,
    )
    attempt_dir.mkdir(parents=True, exist_ok=True)
    report_path = attempt_dir / "fresh-markdown-quality.json"
    prompt = build_fresh_markdown_quality_prompt(
        provider=provider_name,
        doi=normalized_doi,
        sample_id=sample_id,
        purpose=purpose,
        markdown_path=_rel(markdown_path),
        prompt_path=_rel(prompt_path),
        report_path=_rel(report_path),
        markdown_sha256=_sha256_file(markdown_path),
    )
    completed, before, after = _run_agent_with_scope(
        argv=argv,
        prompt=prompt,
        attempt_dir=attempt_dir,
        prefix="fresh-quality-agent",
        allowed_scope=[_rel(report_path)],
    )
    disallowed = _disallowed_changes(before, after, [_rel(report_path)])
    if disallowed:
        raise ToolError(
            "WORKER_MODIFIED_FORBIDDEN_FILE",
            "fresh markdown quality worker modified files outside its report path.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "forbidden_paths": disallowed,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    if completed.returncode != 0:
        raise ToolError(
            "WORKER_AGENT_FAILED",
            "fresh markdown quality worker failed.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    if not report_path.is_file():
        stdout_report = _parse_json_object_from_stdout(completed.stdout)
        if stdout_report is not None:
            write_text(
                report_path, json.dumps(stdout_report, indent=2, sort_keys=True) + "\n"
            )
    if not report_path.is_file():
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "fresh markdown quality worker did not write its report.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "fresh markdown quality report cannot be loaded.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "reason": str(exc),
            },
        ) from exc
    validation_errors = _markdown_quality_report_errors(
        report,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
    )
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "fresh markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "validation_errors": validation_errors,
            },
        )
    return FreshMarkdownQualityReview(
        report=report,
        report_path=report_path,
        attempt_dir=attempt_dir,
    )


def _fresh_markdown_quality_blocking_issues(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    blocking = blocking_markdown_quality_issues(report)
    if blocking:
        return blocking
    if report.get("status") == "fail":
        issues = report.get("issues")
        return (
            [issue for issue in issues if isinstance(issue, dict)]
            if isinstance(issues, list)
            else []
        )
    return []


def _synthetic_persistent_quality_issue(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "markdown-quality-report-not-pass",
        "severity": "high",
        "blocking": True,
        "summary": "Persistent markdown-quality.json is not pass for the current fixture.",
        "evidence": f"status={report.get('status')!r}",
    }


def _effective_markdown_repair_report(
    *,
    persistent_report: dict[str, Any],
    fresh_report: dict[str, Any],
) -> dict[str, Any]:
    fresh_issues = _fresh_markdown_quality_blocking_issues(fresh_report)
    if fresh_report.get("status") != "pass" or fresh_issues:
        return fresh_report
    persistent_issues = _markdown_repair_issues(persistent_report)
    if persistent_report.get("status") != "pass" or persistent_issues:
        if persistent_issues:
            return persistent_report
        report = dict(persistent_report)
        report["status"] = "fail"
        report["issues"] = [_synthetic_persistent_quality_issue(persistent_report)]
        report["blocking_issue_count"] = 1
        return report
    return persistent_report


def _manifest_fixture_for_doi(
    manifest: dict[str, Any],
    doi: str,
) -> tuple[str | None, dict[str, Any]]:
    normalized = _normalized_doi(doi)
    manifest_contract = manifest.get("markdown_contract")
    manifest_contract = manifest_contract if isinstance(manifest_contract, dict) else {}
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict):
            continue
        if _normalized_doi(str(sample.get("doi") or "")) != normalized:
            continue
        contract = manifest_contract.get(purpose)
        return str(purpose), contract if isinstance(contract, dict) else {}
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict):
                continue
            if _normalized_doi(str(sample.get("doi") or "")) != normalized:
                continue
            contract = sample.get("markdown_contract")
            purpose = sample.get("purpose") or f"extra_fixtures[{index}]"
            return str(purpose), contract if isinstance(contract, dict) else {}
    return None, {}


def _load_markdown_repair_context(
    provider: str,
    doi: str,
    *,
    quality_report_override: dict[str, Any] | None = None,
    fresh_quality_path: Path | None = None,
    allow_passing_report: bool = False,
    allow_pending_report: bool = False,
) -> MarkdownQualityRepairContext:
    provider_name = _provider_slug(provider)
    normalized_doi = _normalized_doi(doi)
    task_id = f"{provider_name}-{REPAIR_MARKDOWN_QUALITY_STEP}"
    manifest_path = _manifest_path_for_provider(provider_name)
    manifest = _read_manifest(manifest_path)
    if normalized_doi not in _manifest_dois(manifest):
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is not registered in provider manifest fixtures.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"doi": normalized_doi},
        )

    golden_manifest = _load_golden_manifest()
    sample_entry = _golden_sample_for_doi(normalized_doi, golden_manifest)
    if sample_entry is None:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is missing from golden criteria manifest.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"doi": normalized_doi, "sample_id": _doi_slug(normalized_doi)},
        )
    sample_id, sample = sample_entry
    fixture_root = _fixture_root_for_sample(sample_id, sample)
    expected_path = fixture_root / "expected.json"
    markdown_path = fixture_root / "extracted.md"
    prompt_path = fixture_root / "markdown-quality-prompt.md"
    quality_path = fixture_root / "markdown-quality.json"
    for path, error_code, message in (
        (
            expected_path,
            "EXPECTED_SNAPSHOT_FAILED",
            "expected snapshot file is missing.",
        ),
        (
            markdown_path,
            "EXPECTED_SNAPSHOT_FAILED",
            "extracted Markdown baseline is missing.",
        ),
        (
            prompt_path,
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality agent prompt is missing.",
        ),
        (
            quality_path,
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report is missing.",
        ),
    ):
        if not path.is_file():
            raise ToolError(
                error_code,
                message,
                retryable=True,
                provider=provider_name,
                manifest=default_manifest_path(provider_name),
                task_id=task_id,
                details={"doi": normalized_doi, "path": _rel(path)},
            )

    quality = _read_json_object(
        quality_path,
        code="MARKDOWN_QUALITY_FAILED",
        task_id=task_id,
        provider=provider_name,
    )
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
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_path": _rel(quality_path),
                "validation_errors": validation_errors,
            },
        )
    if quality.get("status") == PENDING_STATUS and not allow_pending_report:
        raise ToolError(
            "MARKDOWN_QUALITY_REVIEW_PENDING",
            "Markdown quality report is pending agent review; complete the quality review before repair.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_prompt_path": _rel(prompt_path),
                "markdown_quality_path": _rel(quality_path),
                "status": quality.get("status"),
            },
        )
    effective_quality = quality_report_override or quality
    blocking_issues = blocking_markdown_quality_issues(effective_quality)
    if (
        effective_quality.get("status") == "pass"
        and not blocking_issues
        and not allow_passing_report
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_REPAIR_NOT_REQUIRED",
            "Markdown quality report is already passing.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_path": _rel(quality_path),
            },
        )
    if (
        effective_quality.get("status") != "fail"
        and not blocking_issues
        and not (
            allow_pending_report and effective_quality.get("status") == PENDING_STATUS
        )
        and not allow_passing_report
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must be fail or contain blocking issues before repair.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_path": _rel(quality_path),
                "status": effective_quality.get("status"),
            },
        )

    purpose, contract = _manifest_fixture_for_doi(manifest, normalized_doi)
    return MarkdownQualityRepairContext(
        provider=provider_name,
        doi=normalized_doi,
        sample_id=sample_id,
        fixture_root=fixture_root,
        expected_path=expected_path,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
        quality_path=quality_path,
        manifest_path=manifest_path,
        review_path=_repo_root() / "onboarding" / "reviews" / f"{provider_name}.yml",
        manifest=manifest,
        golden_sample=sample,
        purpose=purpose,
        markdown_contract=contract,
        quality_report=effective_quality,
        persistent_quality_report=quality,
        fresh_quality_path=fresh_quality_path,
    )


def _markdown_repair_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    blocking = blocking_markdown_quality_issues(report)
    if blocking:
        return blocking
    issues = report.get("issues")
    return (
        [issue for issue in issues if isinstance(issue, dict)]
        if isinstance(issues, list)
        else []
    )


def _infer_markdown_repair_domains(issues: list[dict[str, Any]]) -> list[str]:
    matches: list[str] = []

    def add(domain: str) -> None:
        if domain not in matches:
            matches.append(domain)

    for issue in issues:
        text = " ".join(
            str(issue.get(field) or "") for field in ("id", "summary", "evidence")
        ).lower()
        if re.search(r"\b(table|row|column|cell|header)\b|\|", text):
            add("table")
        if re.search(r"\b(formula|equation|math|latex|tex)\b", text):
            add("formula")
        if re.search(
            r"\b(figure|fig\.|image|caption|asset|media|supplementary)\b", text
        ):
            add("figure/asset")
        if re.search(
            r"\b(reference|references|citation|bibliography|doi-only|scholar)\b", text
        ):
            add("references")
        if re.search(
            r"\b(chrome|boilerplate|navigation|cookie|license|download|toolbar|metrics)\b",
            text,
        ):
            add("chrome/boilerplate")
        if re.search(
            r"javascript|template|placeholder|unresolved|\{\{|ocr|noise", text
        ):
            add("javascript/unresolved text")
        if re.search(
            r"\b(duplicate|duplicated|missing|section|abstract|title|body|empty)\b",
            text,
        ):
            add("duplicate/missing section")
    if not matches:
        matches.append("generic markdown corruption")
    return matches


def _provider_owned_repair_scope(ctx: MarkdownQualityRepairContext) -> list[str]:
    provider = ctx.provider
    return [
        f"src/paper_fetch/providers/{provider}.py",
        f"src/paper_fetch/providers/_{provider}_*.py",
        f"tests/unit/test_{provider}_provider.py",
        f"{_rel(ctx.fixture_root)}/**",
        f"onboarding/reviews/{provider}.yml",
    ]


def _markdown_repair_allowed_scope(
    ctx: MarkdownQualityRepairContext, domains: list[str]
) -> list[str]:
    allowed = _provider_owned_repair_scope(ctx)
    for domain in domains:
        for path in SHARED_MARKDOWN_REPAIR_SCOPES.get(domain, []):
            if path not in allowed:
                allowed.append(path)
    return allowed


def _markdown_repair_forbidden_scope(ctx: MarkdownQualityRepairContext) -> list[str]:
    return [
        "onboarding/access-reviews/",
        "onboarding/known-providers.yml",
        "docs/providers.md",
        "docs/extraction-rules.md",
        "CHANGELOG.md",
        _rel(ctx.manifest_path),
    ]


def _markdown_repair_commands(ctx: MarkdownQualityRepairContext) -> list[list[str]]:
    return [
        [
            "PYTHONPATH=src",
            "python3",
            "-m",
            "pytest",
            f"tests/unit/test_{ctx.provider}_provider.py",
            "tests/unit/test_provider_markdown_review_contract.py",
            "tests/unit/test_provider_asset_contract.py",
            "-q",
        ],
        [
            "PYTHONPATH=src",
            "python3",
            "scripts/snapshot_expected.py",
            "--doi",
            ctx.doi,
        ],
        [
            "PYTHONPATH=src",
            "python3",
            "scripts/onboard_from_manifests.py",
            "check-snapshot",
            "--provider",
            ctx.provider,
            "--doi",
            ctx.doi,
        ],
    ]


def _markdown_repair_brief(
    ctx: MarkdownQualityRepairContext,
    *,
    attempt: int,
    max_attempts: int,
    domains: list[str],
    allowed_scope: list[str],
) -> dict[str, Any]:
    assets = (
        ctx.golden_sample.get("assets")
        if isinstance(ctx.golden_sample.get("assets"), dict)
        else {}
    )
    issues = _markdown_repair_issues(ctx.quality_report)
    issue_payload = [
        {
            "id": issue.get("id"),
            "severity": issue.get("severity"),
            "blocking": issue.get("blocking"),
            "summary": issue.get("summary"),
            "evidence": issue.get("evidence"),
            "domain": domain,
        }
        for issue, domain in zip(
            issues,
            domains + [domains[-1]] * max(0, len(issues) - len(domains)),
            strict=False,
        )
    ]
    return {
        "task_id": f"{ctx.provider}-{REPAIR_MARKDOWN_QUALITY_STEP}-{ctx.sample_id}",
        "current_step": REPAIR_MARKDOWN_QUALITY_STEP,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "runtime": "coding-agent-subagent",
        "provider": ctx.provider,
        "provider_manifest": _rel(ctx.manifest_path),
        "review_artifact": _rel(ctx.review_path),
        "doi": ctx.doi,
        "sample_id": ctx.sample_id,
        "purpose": ctx.purpose,
        "fixture": {
            "root": _rel(ctx.fixture_root),
            "expected": _rel(ctx.expected_path),
            "markdown": _rel(ctx.markdown_path),
            "markdown_sha256": _sha256_file(ctx.markdown_path),
            "quality_prompt": _rel(ctx.prompt_path),
            "quality_report": _rel(ctx.quality_path),
            "fresh_quality_report": _rel(ctx.fresh_quality_path)
            if ctx.fresh_quality_path
            else None,
            "assets": assets,
        },
        "markdown_contract": ctx.markdown_contract,
        "repair_domains": domains,
        "quality_issues": issue_payload,
        "required_order": [
            "Add or update a provider-local regression test for each issue before changing implementation.",
            "Prefer provider-owned implementation files; use shared renderer paths only when the inferred domain explicitly allows them.",
            "Regenerate the DOI snapshot with scripts/snapshot_expected.py --doi after the implementation fix.",
            "Do not mark markdown_semantic_reviewed true; semantic signoff remains operator controlled.",
        ],
        "files_allowed_to_modify": allowed_scope,
        "files_must_not_modify": _markdown_repair_forbidden_scope(ctx),
        "verification_commands": _markdown_repair_commands(ctx),
        "no_commit": True,
    }


def _markdown_excerpt(path: Path, *, limit: int = 6000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    head = text[: limit // 2].rstrip()
    tail = text[-limit // 2 :].lstrip()
    return f"{head}\n\n[... markdown excerpt truncated ...]\n\n{tail}"


def _markdown_repair_worker_prompt(
    ctx: MarkdownQualityRepairContext,
    brief: dict[str, Any],
) -> str:
    return (
        f"# Markdown quality repair worker: {ctx.provider} / {ctx.doi}\n"
        "\n"
        "Fix the failing Markdown baseline by changing implementation and tests, not by editing the quality report.\n"
        "Do not commit changes.\n"
        "\n"
        "## Repair Brief\n"
        "```yaml\n"
        f"{to_yaml(brief)}\n"
        "```\n"
        "\n"
        "## Current Markdown Quality Report\n"
        "```json\n"
        f"{json.dumps(ctx.quality_report, indent=2, sort_keys=True)}\n"
        "```\n"
        "\n"
        "## Extracted Markdown Excerpt\n"
        "```markdown\n"
        f"{_markdown_excerpt(ctx.markdown_path)}\n"
        "```\n"
    )


def _markdown_quality_review_prompt(ctx: MarkdownQualityRepairContext) -> str:
    prompt_text = ctx.prompt_path.read_text(encoding="utf-8", errors="replace")
    return (
        f"# Markdown quality repair review: {ctx.provider} / {ctx.doi}\n"
        "\n"
        "Read the current extracted Markdown and write the pass/fail report requested below.\n"
        f"You may modify only `{_rel(ctx.quality_path)}`. Do not modify code, tests, expected snapshots, or extracted Markdown.\n"
        "\n"
        "## Existing Review Prompt\n"
        "```markdown\n"
        f"{prompt_text}\n"
        "```\n"
    )


def _run_env_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    argv = list(command)
    while argv and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[0]):
        key, value = argv.pop(0).split("=", 1)
        env[key] = value
    if not argv:
        raise ValueError("command must contain an executable")
    return subprocess.run(
        argv,
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else _repo_root() / path


def check_cleaning_proposal_freshness(
    provider: str,
    *,
    proposal_path: Path | None = None,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    proposal_ref = default_cleaning_proposal_path(provider_name)
    path = proposal_path or (_repo_root() / proposal_ref)
    if not path.exists():
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal is missing; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": "missing_proposal",
            },
        )
    try:
        proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal YAML is invalid; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": str(exc),
            },
        ) from exc
    if not isinstance(proposal, dict) or proposal.get("schema_version") != 2:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal is stale or legacy; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "schema_version": proposal.get("schema_version")
                if isinstance(proposal, dict)
                else None,
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": "proposal_schema_not_compact",
            },
        )
    digest_items = proposal.get("fixtures_digest")
    if not isinstance(digest_items, list) or not digest_items:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal has no fixture digest; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": "missing_fixtures_digest",
            },
        )

    stale: list[dict[str, Any]] = []
    checked = 0
    for item in digest_items:
        if not isinstance(item, dict):
            stale.append({"reason": "invalid_digest_item", "item": item})
            continue
        raw_path = item.get("raw_path")
        expected_sha = item.get("sha256")
        if not raw_path or not expected_sha:
            stale.append(
                {
                    "purpose": item.get("purpose"),
                    "doi": item.get("doi"),
                    "raw_path": raw_path,
                    "reason": "missing_digest_path_or_sha256",
                }
            )
            continue
        fixture_path = _resolve_repo_path(str(raw_path))
        if not fixture_path.exists():
            stale.append(
                {
                    "purpose": item.get("purpose"),
                    "doi": item.get("doi"),
                    "raw_path": raw_path,
                    "reason": "fixture_missing",
                }
            )
            continue
        actual_sha = _sha256_file(fixture_path)
        checked += 1
        if actual_sha != str(expected_sha):
            stale.append(
                {
                    "purpose": item.get("purpose"),
                    "doi": item.get("doi"),
                    "raw_path": raw_path,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "reason": "sha256_mismatch",
                }
            )
    if stale:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal fixture digest is stale; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "stale_fixtures_digest": stale,
            },
        )
    return {
        "provider": provider_name,
        "proposal": path.as_posix(),
        "fixtures_checked": checked,
        "result": "passed",
    }
