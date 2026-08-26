#!/usr/bin/env python3
"""Validate provider routes, manifests, fixtures, docs, and complexity together."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(1, str(REPO_ROOT))

from scripts.check_complexity_budget import (  # noqa: E402
    DEFAULT_BUDGET,
    budget_regressions,
    collect_violations,
    load_budget,
)


POLICY_PATH = REPO_ROOT / "quality" / "provider-governance.yml"
CATALOG_SNAPSHOT_PATH = REPO_ROOT / "quality" / "provider-catalog.json"
ROUTE_DOC_PATH = REPO_ROOT / "docs" / "provider-routes.generated.md"
KNOWN_PROVIDERS_PATH = REPO_ROOT / "onboarding" / "known-providers.yml"
GOLDEN_MANIFEST_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
)
FIXTURE_MANIFEST_SCHEMA_PATH = REPO_ROOT / "quality" / "fixture-manifest.schema.json"
PROVIDERS_DOC_PATH = REPO_ROOT / "docs" / "providers.md"
PROVIDERS_MATRIX_MARKER = "<!-- SCAFFOLD: providers-capability-matrix -->"
PRODUCTION_MANIFEST_STATUSES = frozenset({"implemented", "ready", "live"})
FULLTEXT_ROUTE_KINDS = frozenset({"html", "xml", "pdf"})


@dataclass(frozen=True)
class GovernanceReport:
    errors: tuple[str, ...]
    provider_count: int
    route_count: int
    route_family_count: int
    waived_route_family_count: int
    negative_coverage_count: int
    waived_negative_coverage_count: int
    executable_replay_count: int
    synthetic_fixture_count: int
    unit_only_fixture_count: int
    manifest_only_fixture_count: int
    unexecutable_fixture_count: int
    negative_replay_count: int
    complexity_violation_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "OK" if not self.errors else "ERROR",
            "errors": list(self.errors),
            "provider_count": self.provider_count,
            "route_count": self.route_count,
            "route_family_count": self.route_family_count,
            "waived_route_family_count": self.waived_route_family_count,
            "negative_coverage_count": self.negative_coverage_count,
            "waived_negative_coverage_count": self.waived_negative_coverage_count,
            "executable_replay_count": self.executable_replay_count,
            "synthetic_fixture_count": self.synthetic_fixture_count,
            "unit_only_fixture_count": self.unit_only_fixture_count,
            "manifest_only_fixture_count": self.manifest_only_fixture_count,
            "unexecutable_fixture_count": self.unexecutable_fixture_count,
            "negative_replay_count": self.negative_replay_count,
            "complexity_violation_count": self.complexity_violation_count,
        }


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(REPO_ROOT)} must contain a mapping")
    return payload


def _known_provider_entries() -> tuple[dict[str, Any], ...]:
    entries = _load_yaml(KNOWN_PROVIDERS_PATH).get("providers")
    if not isinstance(entries, list):
        raise ValueError("onboarding/known-providers.yml providers must be a list")
    return tuple(dict(entry) for entry in entries if isinstance(entry, dict))


def _manifest_payloads(
    entries: tuple[dict[str, Any], ...],
) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for entry in entries:
        manifest_path = entry.get("manifest_path")
        if manifest_path is None:
            continue
        manifests[str(entry["name"])] = _load_yaml(REPO_ROOT / str(manifest_path))
    return manifests


def _fixture_manifest() -> dict[str, Any]:
    payload = json.loads(GOLDEN_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("samples"), dict):
        raise ValueError("golden criteria manifest must contain a samples mapping")
    return payload


def _check_fixture_manifest_schema(payload: dict[str, Any], errors: list[str]) -> None:
    schema = json.loads(FIXTURE_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for error in sorted(
        validator.iter_errors(payload), key=lambda item: list(item.path)
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"fixture manifest schema {location}: {error.message}")


def _springer_html_family(sample: dict[str, Any]) -> str:
    from paper_fetch.providers.springer import springer_site_family_profile

    return springer_site_family_profile(
        str(sample.get("source_url") or sample.get("landing_url") or ""),
        str(sample.get("doi") or ""),
    ).name


def _required_route_families(specs: tuple[Any, ...]) -> set[str]:
    required: set[str] = set()
    for spec in specs:
        if not spec.official:
            continue
        for route in spec.routes:
            if (
                route.implementation_status != "available"
                or route.kind not in FULLTEXT_ROUTE_KINDS
            ):
                continue
            if spec.name == "springer" and route.kind == "html":
                required.update(
                    f"springer:html:{family}"
                    for family in ("nature", "springerlink", "bmc")
                )
            else:
                required.add(f"{spec.name}:{route.kind}")
    return required


def _covered_route_families(fixtures: tuple[Any, ...]) -> set[str]:
    covered: set[str] = set()
    route_aliases = {"official": "xml", "pdf_fallback": "pdf"}
    for fixture in fixtures:
        sample = fixture.sample
        provider = fixture.provider
        route_kind = route_aliases.get(
            fixture.route_kind,
            fixture.route_kind,
        )
        if route_kind not in FULLTEXT_ROUTE_KINDS:
            continue
        if provider == "springer" and route_kind == "html":
            covered.add(f"springer:html:{_springer_html_family(sample)}")
        else:
            covered.add(f"{provider}:{route_kind}")
    return covered


def _required_negative_coverage(specs: tuple[Any, ...]) -> set[str]:
    from paper_fetch.provider_catalog import provider_has_browser_route

    required: set[str] = set()
    for spec in specs:
        if not spec.official:
            continue
        if provider_has_browser_route(spec.name):
            required.add(f"{spec.name}:access_block")
        if any(
            route.kind == "xml" and route.implementation_status == "available"
            for route in spec.routes
        ):
            required.add(f"{spec.name}:xml_empty_or_abstract")
    return required


def _covered_negative_coverage(
    specs: tuple[Any, ...], errors: list[str]
) -> tuple[set[str], int]:
    from tests.block_fixtures import execute_block_fixture, iter_block_samples

    specs_by_name = {spec.name: spec for spec in specs}
    covered: set[str] = set()
    replay_count = 0
    for fixture in iter_block_samples():
        prefix = f"block replay {fixture.sample_id}"
        if fixture.sample.get("origin_kind") != "real_replay":
            errors.append(f"{prefix}: negative route evidence must be a real replay")
            continue
        try:
            route = next(
                route
                for route in specs_by_name[fixture.provider].routes
                if route.name == fixture.provider_route
            )
        except (KeyError, StopIteration):
            errors.append(
                f"{prefix}: unknown provider route {fixture.provider}:{fixture.provider_route}"
            )
            continue
        if route.source != fixture.source_identity:
            errors.append(
                f"{prefix}: source identity {fixture.source_identity!r} does not match "
                f"catalog source {route.source!r}"
            )
            continue
        try:
            result = execute_block_fixture(fixture)
        except Exception as exc:  # noqa: BLE001 - governance reports fixture failure.
            errors.append(
                f"{prefix}: current extractor cannot execute raw replay: {exc}"
            )
            continue
        mismatches = {
            "accepted": (result.accepted, False),
            "reason": (result.reason, fixture.expected_reason),
            "failure_code": (
                result.failure_code,
                fixture.expected_failure_code,
            ),
            "content_kind": (
                result.content_kind,
                fixture.expected_content_kind,
            ),
        }
        mismatch_text = [
            f"{field}={actual!r} expected {expected!r}"
            for field, (actual, expected) in mismatches.items()
            if actual != expected
        ]
        if mismatch_text:
            errors.append(f"{prefix}: " + ", ".join(mismatch_text))
            continue
        replay_count += 1
        covered.add(f"{fixture.provider}:{fixture.negative_case_kind}")
    return covered, replay_count


def _validated_waiver_keys(
    policy: dict[str, Any],
    field: str,
    errors: list[str],
    expiry_owners: dict[date, str],
) -> set[str]:
    entries = policy.get(field)
    if not isinstance(entries, list):
        errors.append(f"quality/provider-governance.yml {field} must be a list")
        return set()
    keys: set[str] = set()
    today = date.today()
    for index, entry in enumerate(entries):
        prefix = f"quality/provider-governance.yml {field}[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        expected_fields = {
            "key",
            "owner",
            "restriction",
            "evidence_plan",
            "reviewed_at",
            "expires_at",
            "reason",
        }
        if set(entry) != expected_fields:
            errors.append(
                f"{prefix} fields differ: missing={sorted(expected_fields - set(entry))}, "
                f"extra={sorted(set(entry) - expected_fields)}"
            )
            continue
        key = str(entry.get("key") or "").strip()
        owner = str(entry.get("owner") or "").strip()
        restriction = str(entry.get("restriction") or "").strip()
        evidence_plan = str(entry.get("evidence_plan") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        try:
            reviewed_at = date.fromisoformat(str(entry.get("reviewed_at") or ""))
            expires_at = date.fromisoformat(str(entry.get("expires_at") or ""))
        except ValueError:
            errors.append(f"{prefix} reviewed_at/expires_at must be ISO dates")
            continue
        if not key or key in keys:
            errors.append(f"{prefix} key must be non-empty and unique")
        elif len(owner) < 3:
            errors.append(f"{prefix} owner must identify the responsible maintainer")
        elif restriction not in {
            "credentials",
            "copyright",
            "redistribution_review",
            "source_stability",
        }:
            errors.append(f"{prefix} restriction is invalid")
        elif len(evidence_plan) < 40:
            errors.append(f"{prefix} evidence_plan must be concrete and route-specific")
        elif len(reason) < 20:
            errors.append(f"{prefix} reason must explain the reviewed gap")
        elif reviewed_at > today:
            errors.append(f"{prefix} reviewed_at cannot be in the future")
        elif expires_at < today:
            errors.append(f"{prefix} expired on {expires_at.isoformat()}")
        elif expires_at <= reviewed_at:
            errors.append(f"{prefix} expires_at must follow reviewed_at")
        elif expires_at > reviewed_at + timedelta(days=183):
            errors.append(f"{prefix} waiver lifetime cannot exceed 183 days")
        elif expires_at in expiry_owners:
            errors.append(
                f"{prefix} shares expires_at={expires_at.isoformat()} with "
                f"{expiry_owners[expires_at]}; batch-expiry waivers are forbidden"
            )
        else:
            expiry_owners[expires_at] = f"{field}:{key}"
            keys.add(key)
    return keys


def _provider_matrix_names() -> tuple[str, ...]:
    text = PROVIDERS_DOC_PATH.read_text(encoding="utf-8")
    _, marker, tail = text.partition(PROVIDERS_MATRIX_MARKER)
    if not marker:
        return ()
    names: list[str] = []
    for line in tail.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if names:
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0].lower() == "provider" or set(cells[0]) <= {"-", ":"}:
            continue
        name = cells[0].replace("`", "").strip()
        if name:
            names.append(name)
    return tuple(names)


def _load_factory(profile_path: str) -> Any:
    module_name, _, attribute = profile_path.partition(":")
    return getattr(importlib.import_module(module_name), attribute)


def _check_browser_profile_sync(specs: tuple[Any, ...], errors: list[str]) -> None:
    from paper_fetch.providers.browser_workflow.profile import (
        browser_profile_catalog_mismatches,
    )

    for spec in specs:
        factory = _load_factory(spec.client_factory_path)
        profile = getattr(factory, "profile", None)
        if profile is None:
            continue
        mismatches = browser_profile_catalog_mismatches(profile)
        if mismatches:
            errors.append(
                f"{spec.name}: browser profile/catalog drift: {', '.join(mismatches)}"
            )


def _check_manifests(
    entries: tuple[dict[str, Any], ...],
    manifests: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    from scripts.manifest_sync_back import serialize_bundle_sync_back
    from paper_fetch.providers._registry import provider_bundle

    for entry in entries:
        provider = str(entry.get("name") or "")
        status = str(entry.get("status") or "")
        if status not in PRODUCTION_MANIFEST_STATUSES:
            continue
        manifest = manifests.get(provider)
        if manifest is None:
            errors.append(f"{provider}: production provider has no manifest")
            continue
        main_path = manifest.get("main_path")
        criteria = manifest.get("success_criteria")
        if not isinstance(main_path, list) or not main_path:
            errors.append(f"{provider}: manifest main_path must be non-empty")
            continue
        if not isinstance(criteria, dict):
            errors.append(f"{provider}: manifest success_criteria must be a mapping")
        else:
            missing = [step for step in main_path if step not in criteria]
            if missing:
                errors.append(
                    f"{provider}: success_criteria missing {', '.join(missing)}"
                )
        bundle = provider_bundle(provider)
        expected_hints = serialize_bundle_sync_back(bundle)
        actual_hints = manifest.get("extraction_hints")
        if not isinstance(actual_hints, dict):
            errors.append(f"{provider}: manifest extraction_hints must be a mapping")
            continue
        for field, expected in expected_hints.items():
            if actual_hints.get(field) != expected:
                errors.append(
                    f"{provider}: extraction_hints.{field} differs from ProviderBundle"
                )


def _check_route_specs(specs: tuple[Any, ...], errors: list[str]) -> None:
    from paper_fetch.provider_catalog import sources_by_provider

    source_map = sources_by_provider()
    for spec in specs:
        if [route.order for route in spec.routes] != list(range(len(spec.routes))):
            errors.append(f"{spec.name}: route orders are not contiguous")
        for route in spec.routes:
            if not route.source:
                errors.append(f"{spec.name}:{route.name}: route source is empty")
            if (
                route.kind in FULLTEXT_ROUTE_KINDS
                and route.implementation_status == "available"
            ):
                if route.source not in source_map.get(spec.name, frozenset()):
                    errors.append(
                        f"{spec.name}:{route.name}: source {route.source!r} is not registered"
                    )
            if not route.acceptance_policy:
                errors.append(f"{spec.name}:{route.name}: acceptance policy is empty")
            if route.timeout_seconds is None or route.concurrency is None:
                errors.append(
                    f"{spec.name}:{route.name}: timeout/concurrency is incomplete"
                )


def _check_benchmarks(specs: tuple[Any, ...], errors: list[str]) -> None:
    from tests.provider_benchmark_samples import PROVIDER_BENCHMARK_SAMPLES

    expected = {spec.name for spec in specs if spec.official}
    actual = set(PROVIDER_BENCHMARK_SAMPLES)
    if actual != expected:
        errors.append(
            "benchmark providers differ from official catalog: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    offenders = sorted(
        sample.provider
        for sample in PROVIDER_BENCHMARK_SAMPLES.values()
        if "CROSSREF_MAILTO" in sample.required_env
    )
    if offenders:
        errors.append(
            "CROSSREF_MAILTO is recommended, not required, for: " + ", ".join(offenders)
        )


def generated_catalog_text() -> str:
    from paper_fetch.mcp.provider_catalog import provider_catalog_resource_payload

    return (
        json.dumps(
            provider_catalog_resource_payload(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def generated_route_docs(specs: tuple[Any, ...]) -> str:
    lines = [
        "# Provider 路由清单（自动生成）",
        "",
        "本文件由 `scripts/check_provider_governance.py --update` 从运行时 "
        "`ProviderSpec.routes` 生成，请勿手工编辑。",
        "",
        "| Provider | 顺序 | Route | Kind / Source / Transport | 状态 / Runtime | 限制 | Acceptance / Assets |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for spec in specs:
        for route in spec.routes:
            runtime = (
                "browser-required"
                if route.browser_required
                else "browser-optional"
                if route.browser_optional
                else "direct"
            )
            limits = (
                f"{route.timeout_seconds}s; c={route.concurrency}; "
                f"qps={route.qps if route.qps is not None else 'provider'}; "
                f"wait={route.rate_limit_wait_budget_seconds}s"
            )
            lines.append(
                "| "
                f"`{spec.name}` | {route.order} | `{route.name}` | "
                f"`{route.kind}` / `{route.source}` / `{route.transport}` | "
                f"`{route.implementation_status}` / `{runtime}` | "
                f"{limits} | `{route.acceptance_policy}` / `{route.asset_scope}` |"
            )
    lines.extend(
        [
            "",
            "机器可读快照见 [`../quality/provider-catalog.json`](../quality/provider-catalog.json)。",
            "",
        ]
    )
    return "\n".join(lines)


def _check_generated_file(
    path: Path,
    expected: str,
    label: str,
    errors: list[str],
) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != expected:
        errors.append(
            f"{label} is stale; run scripts/check_provider_governance.py --update"
        )


def collect_report(*, check_generated: bool = True) -> GovernanceReport:
    from paper_fetch.provider_catalog import ordered_provider_specs
    from tests.golden_corpus import golden_corpus_replay_inventory

    errors: list[str] = []
    specs = ordered_provider_specs()
    entries = _known_provider_entries()
    manifests = _manifest_payloads(entries)
    fixture_manifest = _fixture_manifest()
    _check_fixture_manifest_schema(fixture_manifest, errors)
    replay_inventory = golden_corpus_replay_inventory()
    replay_fixtures = replay_inventory.replay_fixtures
    for record in replay_inventory.records:
        if record.category == "unexecutable":
            errors.append(
                f"golden replay {record.sample_id} is not executable: {record.reason}"
            )
    policy = _load_yaml(POLICY_PATH)
    if policy.get("schema_version") != 2:
        errors.append("quality/provider-governance.yml schema_version must be 2")

    official = {spec.name for spec in specs if spec.official}
    manifested = set(manifests)
    if manifested != official:
        errors.append(
            "manifest providers differ from official catalog: "
            f"missing={sorted(official - manifested)}, extra={sorted(manifested - official)}"
        )
    matrix_names = set(_provider_matrix_names())
    catalog_names = {spec.name for spec in specs}
    if matrix_names != catalog_names:
        errors.append(
            "docs provider matrix differs from catalog: "
            f"missing={sorted(catalog_names - matrix_names)}, "
            f"extra={sorted(matrix_names - catalog_names)}"
        )

    _check_route_specs(specs, errors)
    _check_browser_profile_sync(specs, errors)
    _check_manifests(entries, manifests, errors)
    _check_benchmarks(specs, errors)

    route_required = _required_route_families(specs)
    route_covered = _covered_route_families(replay_fixtures)
    expiry_owners: dict[date, str] = {}
    route_waivers = _validated_waiver_keys(
        policy, "route_family_waivers", errors, expiry_owners
    )
    route_missing = route_required - route_covered
    if route_missing != route_waivers:
        errors.append(
            "route-family waiver drift: "
            f"unwaived={sorted(route_missing - route_waivers)}, "
            f"stale={sorted(route_waivers - route_missing)}"
        )

    negative_required = _required_negative_coverage(specs)
    negative_covered, negative_replay_count = _covered_negative_coverage(specs, errors)
    negative_waivers = _validated_waiver_keys(
        policy,
        "negative_fixture_waivers",
        errors,
        expiry_owners,
    )
    negative_missing = negative_required - negative_covered
    if negative_missing != negative_waivers:
        errors.append(
            "negative-fixture waiver drift: "
            f"unwaived={sorted(negative_missing - negative_waivers)}, "
            f"stale={sorted(negative_waivers - negative_missing)}"
        )

    if check_generated:
        _check_generated_file(
            CATALOG_SNAPSHOT_PATH,
            generated_catalog_text(),
            "machine-readable provider catalog",
            errors,
        )
        _check_generated_file(
            ROUTE_DOC_PATH,
            generated_route_docs(specs),
            "generated provider route docs",
            errors,
        )

    complexity = collect_violations()
    if not DEFAULT_BUDGET.is_file():
        errors.append("complexity budget is missing")
    else:
        regressions = budget_regressions(load_budget(DEFAULT_BUDGET), complexity)
        if regressions:
            errors.append(
                "complexity regressions: "
                + ", ".join(
                    f"{item.path}:{item.symbol}:{item.code}={item.value}"
                    for item in regressions
                )
            )

    return GovernanceReport(
        errors=tuple(errors),
        provider_count=len(specs),
        route_count=sum(len(spec.routes) for spec in specs),
        route_family_count=len(route_required),
        waived_route_family_count=len(route_waivers),
        negative_coverage_count=len(negative_required),
        waived_negative_coverage_count=len(negative_waivers),
        executable_replay_count=replay_inventory.count("real_replay"),
        synthetic_fixture_count=replay_inventory.count("synthetic"),
        unit_only_fixture_count=replay_inventory.count("unit_only"),
        manifest_only_fixture_count=replay_inventory.count("manifest_only"),
        unexecutable_fixture_count=replay_inventory.count("unexecutable"),
        negative_replay_count=negative_replay_count,
        complexity_violation_count=len(complexity),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate provider-catalog.json and provider-routes.generated.md.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the governance report as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.update:
        from paper_fetch.provider_catalog import ordered_provider_specs

        CATALOG_SNAPSHOT_PATH.write_text(
            generated_catalog_text(),
            encoding="utf-8",
        )
        ROUTE_DOC_PATH.write_text(
            generated_route_docs(ordered_provider_specs()),
            encoding="utf-8",
        )
    report = collect_report()
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    elif report.errors:
        print("Provider governance failed:", file=sys.stderr)
        for error in report.errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print(
            "Provider governance passed "
            f"({report.provider_count} providers, {report.route_count} routes, "
            f"{report.route_family_count} route families)."
        )
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
