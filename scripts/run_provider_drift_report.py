#!/usr/bin/env python3
"""Run a local route-source drift report for provider onboarding manifests."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from collections.abc import Callable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paper_fetch.models import RenderOptions  # noqa: E402
from paper_fetch.publisher_identity import normalize_doi  # noqa: E402
from paper_fetch.service import FetchStrategy, fetch_paper  # noqa: E402
from paper_fetch.utils import normalize_text  # noqa: E402


RUN_LIVE_ENV_VAR = "PAPER_FETCH_RUN_LIVE"
MANIFEST_DIR = "onboarding/manifests"
KNOWN_PROVIDERS_PATH = "onboarding/known-providers.yml"
FULLTEXT = "fulltext"


RunnerResult = dict[str, Any]
Runner = Callable[[str, str], RunnerResult]


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _provider_slug(provider: str) -> str:
    slug = provider.strip().lower()
    if not slug:
        raise ValueError("provider must not be empty")
    return slug


def _repo_rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def manifest_path_for_provider(provider: str) -> Path:
    return REPO_ROOT / MANIFEST_DIR / f"{_provider_slug(provider)}.yml"


def browser_risk_providers() -> list[str]:
    known = _load_yaml(REPO_ROOT / KNOWN_PROVIDERS_PATH)
    providers: list[str] = []
    for entry in known.get("providers") or []:
        if not isinstance(entry, dict) or entry.get("status") != "implemented":
            continue
        manifest_path = entry.get("manifest_path")
        if not manifest_path:
            continue
        manifest = _load_yaml(REPO_ROOT / str(manifest_path))
        probe = manifest.get("probe") if isinstance(manifest.get("probe"), dict) else {}
        if bool(probe.get("requires_browser_runtime")) or bool(
            probe.get("requires_playwright")
        ):
            providers.append(str(entry["name"]))
    return providers


def _expected_source_for_sample(manifest: dict[str, Any], purpose: str) -> str | None:
    route_sources = manifest.get("route_sources")
    if not isinstance(route_sources, dict):
        return normalize_text(str(manifest.get("display_source") or "")) or None
    if purpose == "pdf_fallback":
        return normalize_text(route_sources.get("pdf_fallback")) or None
    main_path = (
        manifest.get("main_path") if isinstance(manifest.get("main_path"), list) else []
    )
    for step in main_path:
        step_name = normalize_text(str(step))
        if step_name in {"article_html", "landing_html", "xml"} and route_sources.get(
            step_name
        ):
            return normalize_text(route_sources.get(step_name))
    return normalize_text(str(manifest.get("display_source") or "")) or None


def collect_manifest_samples(manifest: dict[str, Any]) -> list[dict[str, Any]]:
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
        if not isinstance(sample, dict) or not sample.get("doi"):
            continue
        samples.append(
            {
                "purpose": str(purpose),
                "doi": normalize_doi(str(sample["doi"])),
                "expected_source": _expected_source_for_sample(manifest, str(purpose)),
            }
        )
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict) or not sample.get("doi"):
                continue
            purpose = str(sample.get("purpose") or f"extra_fixtures[{index}]")
            samples.append(
                {
                    "purpose": purpose,
                    "doi": normalize_doi(str(sample["doi"])),
                    "expected_source": _expected_source_for_sample(manifest, purpose),
                }
            )
    return samples


def fake_runner(*, source: str, status: str = FULLTEXT, markdown: str = "") -> Runner:
    def run(provider: str, doi: str) -> RunnerResult:
        del provider
        return {
            "doi": doi,
            "status": status,
            "source": source,
            "markdown": markdown,
            "warnings": [],
            "source_trail": [source] if source else [],
            "error_code": None,
            "error_message": None,
        }

    return run


def live_runner(provider: str, doi: str) -> RunnerResult:
    try:
        envelope = fetch_paper(
            doi,
            strategy=FetchStrategy(
                preferred_providers=[provider], asset_profile="none"
            ),
            render=RenderOptions(
                include_refs="all", asset_profile="none", max_tokens="full_text"
            ),
        )
    except Exception as exc:
        return {
            "doi": doi,
            "status": "error",
            "source": None,
            "markdown": "",
            "warnings": [],
            "source_trail": [],
            "error_code": type(exc).__name__,
            "error_message": str(exc),
        }
    return {
        "doi": doi,
        "status": FULLTEXT
        if getattr(envelope, "article", None) is not None
        else "metadata_only",
        "source": getattr(envelope, "source", None),
        "markdown": getattr(envelope, "markdown", None) or "",
        "warnings": list(getattr(envelope, "warnings", []) or []),
        "source_trail": list(getattr(envelope, "source_trail", []) or []),
        "error_code": None,
        "error_message": None,
    }


def _markdown_contract_for_sample(
    manifest: dict[str, Any],
    *,
    purpose: str,
    doi: str,
) -> dict[str, Any] | None:
    markdown_contract = manifest.get("markdown_contract")
    if isinstance(markdown_contract, dict):
        contract = markdown_contract.get(purpose)
        if isinstance(contract, dict) and normalize_doi(
            str(contract.get("doi") or "")
        ) == normalize_doi(doi):
            return contract
    for extra in manifest.get("extra_fixtures") or []:
        if not isinstance(extra, dict):
            continue
        if normalize_doi(str(extra.get("doi") or "")) != normalize_doi(doi):
            continue
        contract = extra.get("markdown_contract")
        if isinstance(contract, dict):
            return contract
    return None


def classify_markdown_contract(
    contract: dict[str, Any] | None, markdown: str
) -> dict[str, Any]:
    if contract is None:
        return {
            "status": "missing_contract",
            "missing_must_include": [],
            "present_must_not_include": [],
        }
    normalized = normalize_text(markdown)
    missing = [
        str(token)
        for token in contract.get("must_include") or []
        if normalize_text(str(token)) not in normalized
    ]
    present_negative = [
        str(token)
        for token in contract.get("must_not_include") or []
        if normalize_text(str(token)) and normalize_text(str(token)) in normalized
    ]
    status = "ok" if not missing and not present_negative else "issue"
    return {
        "status": status,
        "missing_must_include": missing,
        "present_must_not_include": present_negative,
    }


def _operator_action(categories: list[str]) -> str:
    if "access_gate" in categories or "challenge_or_rate_limit" in categories:
        return (
            "rerun live later or update access review/runtime after operator inspection"
        )
    if "metadata_only_degradation" in categories:
        return "repair provider route or replace DOI sample if full text is no longer available"
    if (
        "pdf_fallback_silent_degradation" in categories
        or "source_mismatch" in categories
    ):
        return "repair provider route-source handling before accepting live drift"
    if "markdown_contract_issue" in categories:
        return "inspect Markdown output and update provider cleanup or contract after review"
    return "none"


def evaluate_sample(
    *,
    provider: str,
    manifest: dict[str, Any],
    sample: dict[str, Any],
    runner: Runner,
) -> dict[str, Any]:
    result = runner(provider, str(sample["doi"]))
    actual_source = normalize_text(result.get("source")) or None
    expected_source = sample.get("expected_source")
    categories: list[str] = []
    status = str(result.get("status") or "")
    error_blob = " ".join(
        normalize_text(str(value)).lower()
        for value in (
            result.get("error_code"),
            result.get("error_message"),
            *(result.get("warnings") or []),
        )
        if value
    )
    if expected_source and actual_source and actual_source != expected_source:
        categories.append("source_mismatch")
    if (
        sample["purpose"] != "pdf_fallback"
        and actual_source
        and re.search(r"(?:^|_)pdf(?:_|$)", actual_source)
    ):
        categories.append("pdf_fallback_silent_degradation")
    if status == "metadata_only" or actual_source == "metadata_only":
        categories.append("metadata_only_degradation")
    if any(token in error_blob for token in ("challenge", "captcha", "rate", "429")):
        categories.append("challenge_or_rate_limit")
    if any(token in error_blob for token in ("access", "forbidden", "403", "paywall")):
        categories.append("access_gate")
    contract = _markdown_contract_for_sample(
        manifest,
        purpose=str(sample["purpose"]),
        doi=str(sample["doi"]),
    )
    contract_result = classify_markdown_contract(
        contract, str(result.get("markdown") or "")
    )
    if contract_result["status"] == "issue":
        categories.append("markdown_contract_issue")
    categories = list(dict.fromkeys(categories))
    return {
        "purpose": sample["purpose"],
        "doi": sample["doi"],
        "expected_source": expected_source,
        "actual_source": actual_source,
        "status": status,
        "source_mismatch": "source_mismatch" in categories,
        "pdf_fallback_silent_degradation": "pdf_fallback_silent_degradation"
        in categories,
        "metadata_only_degradation": "metadata_only_degradation" in categories,
        "challenge_rate_limit_or_access_gate": any(
            category in categories
            for category in ("challenge_or_rate_limit", "access_gate")
        ),
        "markdown_contract": contract_result,
        "issue_categories": categories,
        "operator_action": _operator_action(categories),
        "error_code": result.get("error_code"),
        "error_message": result.get("error_message"),
    }


def build_provider_report(
    *,
    provider: str,
    manifest: dict[str, Any],
    manifest_path: Path,
    runner: Runner,
) -> dict[str, Any]:
    samples = collect_manifest_samples(manifest)
    sample_results = [
        evaluate_sample(
            provider=provider, manifest=manifest, sample=sample, runner=runner
        )
        for sample in samples
    ]
    return {
        "provider": provider,
        "manifest_path": _repo_rel(manifest_path),
        "main_path": manifest.get("main_path"),
        "route_sources": manifest.get("route_sources"),
        "samples": sample_results,
        "status_counts": _count_result_categories(sample_results),
    }


def _count_result_categories(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        for category in result.get("issue_categories") or ["ok"]:
            counts[category] = counts.get(category, 0) + 1
    return counts


def build_drift_report(*, providers: list[str], runner: Runner) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for provider in providers:
        provider_name = _provider_slug(provider)
        manifest_path = manifest_path_for_provider(provider_name)
        manifest = _load_yaml(manifest_path)
        reports.append(
            build_provider_report(
                provider=provider_name,
                manifest=manifest,
                manifest_path=manifest_path,
                runner=runner,
            )
        )
    return {
        "schema_version": 1,
        "live_gate": f"{RUN_LIVE_ENV_VAR}=1",
        "providers": reports,
        "ci": "not_configured",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local provider route-source drift report."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--provider", help="provider name")
    source.add_argument(
        "--all-browser-risk",
        action="store_true",
        help="run every implemented provider requiring browser runtime or Playwright",
    )
    parser.add_argument("--output", help="output JSON path; stdout when omitted")
    parser.add_argument("--fake-source", help="test-only fake FetchEnvelope.source")
    parser.add_argument(
        "--fake-status", default=FULLTEXT, help="test-only fake fetch status"
    )
    parser.add_argument(
        "--fake-markdown", default="", help="test-only fake markdown text"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    providers = (
        browser_risk_providers()
        if args.all_browser_risk
        else [_provider_slug(args.provider)]
    )
    if args.fake_source:
        runner = fake_runner(
            source=args.fake_source,
            status=args.fake_status,
            markdown=args.fake_markdown,
        )
    else:
        if os.environ.get(RUN_LIVE_ENV_VAR) != "1":
            raise SystemExit(
                f"Set {RUN_LIVE_ENV_VAR}=1 to run live provider drift report."
            )
        runner = live_runner
    report = build_drift_report(providers=providers, runner=runner)
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
