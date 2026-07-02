#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, UTC
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from _structured_errors import ToolError, emit_error, error_payload  # noqa: E402
from paper_fetch.markdown_quality import (  # noqa: E402
    PENDING_STATUS,
    blocking_markdown_quality_issues,
    validate_markdown_quality_report,
)


PROVIDER_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _provider_slug(value: str) -> str:
    provider = value.strip().lower()
    if not PROVIDER_RE.fullmatch(provider):
        raise ValueError("provider must be snake_case starting with a lowercase letter")
    return provider


def _normalized_doi(value: str) -> str:
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


def _doi_slug(value: str) -> str:
    return _normalized_doi(value).replace("/", "_")


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ToolError(
            "MANIFEST_NOT_FOUND",
            "Provider manifest was not found.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="bootstrap-review-artifact",
            details={"path": path.as_posix()},
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest root must be an object.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="bootstrap-review-artifact",
            details={"path": path.as_posix()},
        )
    return data


def _iter_review_samples(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if isinstance(sample, dict) and sample.get("doi"):
            samples.append(
                {"purpose": str(purpose), "doi": str(sample["doi"]), "sample": sample}
            )
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for sample in extra_fixtures:
            if isinstance(sample, dict) and sample.get("doi"):
                samples.append(
                    {
                        "purpose": str(sample.get("purpose") or "extra"),
                        "doi": str(sample["doi"]),
                        "sample": sample,
                    }
                )
    return samples


def _contract_for_sample(
    manifest: dict[str, Any], sample: dict[str, Any]
) -> dict[str, Any]:
    raw_sample = sample["sample"]
    if isinstance(raw_sample, dict) and isinstance(
        raw_sample.get("markdown_contract"), dict
    ):
        return dict(raw_sample["markdown_contract"])
    contracts = (
        manifest.get("markdown_contract")
        if isinstance(manifest.get("markdown_contract"), dict)
        else {}
    )
    contract = contracts.get(sample["purpose"])
    return dict(contract) if isinstance(contract, dict) else {}


def _assertions_from_contract(contract: dict[str, Any]) -> list[str]:
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
    return assertions or ["baseline markdown exists for semantic review"]


def _classifier_issues(
    contract: dict[str, Any], baseline_text: str
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, value in enumerate(contract.get("must_include") or (), start=1):
        if str(value) not in baseline_text:
            issues.append(
                {
                    "id": f"missing-include-{index}",
                    "severity": "medium",
                    "summary": f"baseline is missing required Markdown text: {value}",
                }
            )
    for index, value in enumerate(contract.get("must_not_include") or (), start=1):
        if str(value) in baseline_text:
            issues.append(
                {
                    "id": f"forbidden-text-{index}",
                    "severity": "medium",
                    "summary": f"baseline contains forbidden Markdown text: {value}",
                }
            )
    for index, pattern in enumerate(contract.get("must_match") or (), start=1):
        try:
            matched = re.search(str(pattern), baseline_text) is not None
        except re.error:
            matched = False
        if not matched:
            issues.append(
                {
                    "id": f"missing-pattern-{index}",
                    "severity": "medium",
                    "summary": f"baseline does not match required pattern: {pattern}",
                }
            )
    count_equals = contract.get("count_equals")
    if isinstance(count_equals, dict):
        for index, (value, expected) in enumerate(
            sorted(count_equals.items()), start=1
        ):
            try:
                expected_count = int(expected)
            except (TypeError, ValueError):
                expected_count = -1
            actual_count = baseline_text.count(str(value))
            if actual_count != expected_count:
                issues.append(
                    {
                        "id": f"count-mismatch-{index}",
                        "severity": "medium",
                        "summary": (
                            f"baseline count for {value} is {actual_count}, "
                            f"expected {expected_count}"
                        ),
                    }
                )
    return issues


def _load_golden_manifest(root: Path) -> dict[str, Any]:
    path = root / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"samples": {}}
    return data if isinstance(data, dict) else {"samples": {}}


def _artifact_path(root: Path, doi: str, asset_name: str) -> Path:
    slug = _doi_slug(doi)
    manifest = _load_golden_manifest(root)
    samples = (
        manifest.get("samples") if isinstance(manifest.get("samples"), dict) else {}
    )
    sample = samples.get(slug)
    if not isinstance(sample, dict):
        for sample_id, item in samples.items():
            if (
                isinstance(item, dict)
                and _normalized_doi(str(item.get("doi") or "")) == doi
            ):
                slug = str(sample_id)
                sample = item
                break
    if isinstance(sample, dict):
        assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
        asset_path = assets.get(asset_name)
        if isinstance(asset_path, str) and asset_path:
            return root / asset_path
        family = str(sample.get("fixture_family") or "golden")
        if family == "block":
            return (
                root
                / "tests"
                / "fixtures"
                / "block"
                / slug.removesuffix("__block")
                / asset_name
            )
    return root / "tests" / "fixtures" / "golden_criteria" / slug / asset_name


def _baseline_path(root: Path, doi: str) -> Path:
    return _artifact_path(root, doi, "extracted.md")


def _quality_path(root: Path, doi: str) -> Path:
    return _artifact_path(root, doi, "markdown-quality.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_quality_report(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report cannot be loaded.",
            retryable=True,
            task_id="bootstrap-review-artifact",
            details={"path": path.as_posix(), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report root must be an object.",
            retryable=True,
            task_id="bootstrap-review-artifact",
            details={"path": path.as_posix()},
        )
    validation_errors = validate_markdown_quality_report(data)
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            task_id="bootstrap-review-artifact",
            details={"path": path.as_posix(), "validation_errors": validation_errors},
        )
    return data


def _review_issues_from_quality(quality: dict[str, Any]) -> list[dict[str, str]]:
    if quality.get("status") == PENDING_STATUS:
        return [
            {
                "id": "agent-markdown-review-pending",
                "severity": "high",
                "summary": (
                    "Markdown quality report is pending agent review; "
                    "run markdown-quality-prompt.md and write pass/fail JSON."
                ),
            }
        ]
    issues: list[dict[str, str]] = []
    for issue in blocking_markdown_quality_issues(quality):
        issues.append(
            {
                "id": str(issue.get("id") or "markdown-quality-failed"),
                "severity": str(issue.get("severity") or "high"),
                "summary": str(
                    issue.get("summary") or "Markdown quality check failed."
                ),
            }
        )
    return issues


def build_review(
    *,
    root: Path,
    provider: str,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    manifest_provider = str(manifest.get("name") or "")
    if manifest_provider != provider:
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest provider must match --provider.",
            retryable=False,
            provider=provider,
            manifest=manifest_path.as_posix(),
            task_id=f"{provider}-bootstrap-review-artifact",
            details={"expected": provider, "actual": manifest_provider},
        )
    fixture_reviews: list[dict[str, Any]] = []
    for sample in _iter_review_samples(manifest):
        doi = _normalized_doi(sample["doi"])
        slug = _doi_slug(doi)
        baseline = _baseline_path(root, doi)
        if not baseline.is_file():
            raise ToolError(
                "EXPECTED_SNAPSHOT_FAILED",
                "Review artifact bootstrap requires an extracted Markdown snapshot.",
                retryable=True,
                provider=provider,
                manifest=manifest_path.as_posix(),
                task_id=f"{provider}-bootstrap-review-artifact",
                details={
                    "doi": doi,
                    "baseline_markdown_path": baseline.relative_to(root).as_posix(),
                },
            )
        quality_report = _quality_path(root, doi)
        if not quality_report.is_file():
            raise ToolError(
                "MARKDOWN_QUALITY_FAILED",
                "Review artifact bootstrap requires a Markdown quality report.",
                retryable=True,
                provider=provider,
                manifest=manifest_path.as_posix(),
                task_id=f"{provider}-bootstrap-review-artifact",
                details={
                    "doi": doi,
                    "markdown_quality_path": quality_report.relative_to(
                        root
                    ).as_posix(),
                },
            )
        quality = _load_quality_report(quality_report)
        contract = _contract_for_sample(manifest, sample)
        baseline_text = baseline.read_text(encoding="utf-8", errors="replace")
        issues = _classifier_issues(
            contract, baseline_text
        ) + _review_issues_from_quality(quality)
        fixture_reviews.append(
            {
                "fixture": f"tests/fixtures/golden_criteria/{slug}",
                "purpose": sample["purpose"],
                "doi": doi,
                "baseline_markdown_path": baseline.relative_to(root).as_posix(),
                "baseline_markdown_sha256": _sha256(baseline),
                "markdown_quality_path": quality_report.relative_to(root).as_posix(),
                "markdown_quality_sha256": _sha256(quality_report),
                "review_notes": (
                    "Automated bootstrap found contract issues; semantic signoff pending."
                    if issues
                    else "Automated bootstrap created draft from manifest contract; semantic signoff pending."
                ),
                "sample_representative": True,
                "markdown_semantic_reviewed": False,
                "issues": issues,
                "assertions": _assertions_from_contract(contract),
                "fixes": [],
            }
        )
    if not fixture_reviews:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "Manifest does not contain non-null DOI fixtures for review bootstrap.",
            retryable=True,
            provider=provider,
            manifest=manifest_path.as_posix(),
            task_id=f"{provider}-bootstrap-review-artifact",
            details={"manifest": manifest_path.as_posix()},
        )
    return {
        "schema_version": 2,
        "provider": provider,
        "reviewed_at": datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "reviewed_by": "bootstrap_review_artifact.py",
        "fixtures": fixture_reviews,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap a provider Markdown review artifact from manifest fixtures."
    )
    parser.add_argument("--provider", required=True, help="provider name")
    parser.add_argument("--manifest", required=True, help="provider manifest YAML path")
    parser.add_argument(
        "--output-dir",
        default=_repo_root(),
        help="repo root to resolve fixture snapshots and write review artifact",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing review artifact"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    provider = _provider_slug(args.provider)
    root = Path(args.output_dir).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    output_path = root / "onboarding" / "reviews" / f"{provider}.yml"
    try:
        if output_path.exists() and not args.force:
            print(
                json.dumps(
                    {
                        "status": "EXISTS",
                        "provider": provider,
                        "review_path": output_path.relative_to(root).as_posix(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        review = build_review(root=root, provider=provider, manifest_path=manifest_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.safe_dump(review, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    except ToolError as exc:
        emit_error(
            error_payload(
                exc.code,
                exc.message,
                provider=exc.provider or provider,
                manifest=exc.manifest or args.manifest,
                task_id=exc.task_id or f"{provider}-bootstrap-review-artifact",
                retryable=exc.retryable,
                details=exc.details,
            )
        )
        return 1
    except Exception as exc:
        emit_error(
            error_payload(
                "REVIEW_ARTIFACT_BOOTSTRAP_FAILED",
                str(exc),
                provider=provider,
                manifest=args.manifest,
                task_id=f"{provider}-bootstrap-review-artifact",
                retryable=False,
                details={"reason": str(exc)},
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "OK",
                "provider": provider,
                "review_path": output_path.relative_to(root).as_posix(),
                "fixture_count": len(review["fixtures"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
