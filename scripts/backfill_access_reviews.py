#!/usr/bin/env python3
"""Backfill blocked draft access reviews for implemented or seeded providers."""

from __future__ import annotations

import argparse
from datetime import datetime, UTC
import json
from pathlib import Path
import sys
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

KNOWN_PROVIDERS_PATH = "onboarding/known-providers.yml"
ACCESS_REVIEW_DIR = "onboarding/access-reviews"
FORBIDDEN_BEHAVIORS = (
    "automatic_login",
    "captcha_solving",
    "paywall_bypass",
    "challenge_bypass",
)


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


def _display_source(provider: str, value: str | None = None) -> str:
    source = (value or "").strip()
    return source or f"{_provider_slug(provider)}_html"


def _repo_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _provider_bundle(provider: str) -> Any | None:
    try:
        import paper_fetch.providers as providers
        from paper_fetch.providers._registry import provider_bundle

        providers.import_provider_entry_modules()
        return provider_bundle(provider)
    except (ImportError, KeyError):
        return None


def _catalog_runtime_requirements(catalog: Any) -> tuple[bool, bool]:
    routes = tuple(getattr(catalog, "routes", ()) or ())
    return (
        any(
            bool(getattr(route, "browser_required", False))
            or bool(getattr(route, "browser_optional", False))
            for route in routes
        ),
        any(bool(getattr(route, "requires_playwright", False)) for route in routes),
    )


def _runtime_suggestions(manifest: dict[str, Any], bundle: Any | None) -> list[str]:
    runtimes: set[str] = {"http"}
    probe = manifest.get("probe") if isinstance(manifest.get("probe"), dict) else {}
    requires_browser = bool(probe.get("requires_browser_runtime"))
    requires_playwright = bool(probe.get("requires_playwright"))
    catalog = getattr(bundle, "catalog", None)
    if catalog is not None:
        requires_browser, requires_playwright = _catalog_runtime_requirements(catalog)
    if requires_browser:
        runtimes.add("browser")
    if requires_playwright:
        runtimes.add("playwright")
    return [
        runtime for runtime in ("http", "browser", "playwright") if runtime in runtimes
    ]


def _fixture_evidence(manifest: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in sorted(doi_samples.items()):
        if not isinstance(sample, dict) or not sample.get("doi"):
            continue
        reason = str(sample.get("evidence_reason") or "").strip()
        confidence = str(sample.get("confidence") or "unknown").strip()
        doi = str(sample["doi"]).strip()
        if reason:
            evidence.append(
                f"manifest fixture {purpose} DOI {doi} ({confidence} confidence): {reason}"
            )
        else:
            evidence.append(
                f"manifest fixture {purpose} DOI {doi} ({confidence} confidence)"
            )
    return evidence


def _legal_access_evidence(
    *,
    provider: str,
    manifest_path: str,
    manifest: dict[str, Any],
    bundle: Any | None,
    source_note: str | None = None,
) -> list[str]:
    evidence = []
    if source_note:
        evidence.append(source_note)
    else:
        evidence.append(
            f"{KNOWN_PROVIDERS_PATH} marks {provider} as implemented with manifest {manifest_path}."
        )
    evidence.append(
        f"{manifest_path} declares display_source={manifest.get('display_source')} "
        f"and main_path={manifest.get('main_path')}."
    )
    routing = manifest.get("routing")
    if isinstance(routing, dict):
        primary = routing.get("primary")
        domains = routing.get("domains")
        doi_prefixes = routing.get("doi_prefixes")
        evidence.append(
            f"routing seed primary={primary}; domains={domains}; doi_prefixes={doi_prefixes}."
        )
    if bundle is not None:
        sources = ", ".join(getattr(bundle, "sources", ()) or ()) or "none"
        catalog = getattr(bundle, "catalog", None)
        runtime_bits: list[str] = []
        if catalog is not None:
            requires_browser, requires_playwright = _catalog_runtime_requirements(
                catalog
            )
            runtime_bits.append(
                f"requires_browser_runtime={requires_browser}"
            )
            runtime_bits.append(
                f"requires_playwright={requires_playwright}"
            )
        evidence.append(
            "registered provider bundle "
            f"sources={sources}"
            + (f"; {'; '.join(runtime_bits)}." if runtime_bits else ".")
        )
    evidence.extend(_fixture_evidence(manifest)[:8])
    return evidence


def build_access_review_draft(
    provider: str,
    manifest: dict[str, Any],
    bundle: Any | None = None,
    *,
    manifest_path: str | None = None,
    reviewed_at: str | None = None,
    source_note: str | None = None,
) -> dict[str, Any]:
    """Build a blocked operator review draft from local manifest and bundle facts."""
    provider_name = _provider_slug(provider)
    manifest_ref = manifest_path or f"onboarding/manifests/{provider_name}.yml"
    timestamp = reviewed_at or datetime.now(UTC).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "provider": provider_name,
        "status": "blocked",
        "reviewed_at": timestamp,
        "reviewed_by": "operator-required",
        "legal_access": {
            "mode": "blocked",
            "evidence": _legal_access_evidence(
                provider=provider_name,
                manifest_path=manifest_ref,
                manifest=manifest,
                bundle=bundle,
                source_note=source_note,
            ),
        },
        "allowed_runtimes": _runtime_suggestions(manifest, bundle),
        "forbidden_behaviors": list(FORBIDDEN_BEHAVIORS),
        "challenge_policy": {
            "captcha": "stop and report; do not solve automatically",
            "access_challenge": "stop and report; do not bypass challenge pages",
            "rate_limit": "retry only within normal provider retry budget or stop for operator review",
        },
        "site_temporary_policy": {
            "summary": "No temporary exception is approved by this generated draft.",
            "expires_at": None,
        },
        "may_continue": False,
        "notes": (
            "Generated draft only. Operator must review legal access, runtime, "
            "challenge policy, and site policy before changing status to approved "
            "or may_continue to true."
        ),
    }


def _known_provider_entries(root: Path) -> list[dict[str, Any]]:
    known = _load_yaml(root / KNOWN_PROVIDERS_PATH)
    providers = known.get("providers")
    if not isinstance(providers, list):
        raise ValueError(f"{KNOWN_PROVIDERS_PATH} must contain providers list")
    return [item for item in providers if isinstance(item, dict)]


def _target_providers(args: argparse.Namespace, root: Path) -> list[dict[str, Any]]:
    entries = _known_provider_entries(root)
    if args.provider:
        provider_name = _provider_slug(args.provider)
        for item in entries:
            if item.get("name") == provider_name:
                if not item.get("manifest_path"):
                    raise ValueError(f"provider has no manifest_path: {provider_name}")
                return [item]
        domain = str(args.domain or "").strip()
        if not domain:
            raise ValueError(
                f"unknown provider in {KNOWN_PROVIDERS_PATH}: {provider_name}; "
                "provide --domain to generate a blocked seed draft"
            )
        return [
            {
                "name": provider_name,
                "status": "seed",
                "manifest_path": f"onboarding/manifests/{provider_name}.yml",
                "display_source": _display_source(provider_name, args.display_source),
                "domain": domain,
                "doi_prefix": args.doi_prefix,
            }
        ]
    targets = [
        item
        for item in entries
        if item.get("status") == "implemented" and item.get("manifest_path")
    ]
    return targets


def _seed_manifest(entry: dict[str, Any]) -> dict[str, Any]:
    provider = _provider_slug(str(entry["name"]))
    domain = str(entry.get("domain") or "").strip()
    doi_prefix = str(entry.get("doi_prefix") or "").strip()
    doi_prefixes = (
        [doi_prefix if doi_prefix.endswith("/") else f"{doi_prefix}/"]
        if doi_prefix
        else []
    )
    return {
        "name": provider,
        "display_source": _display_source(
            provider,
            str(entry.get("display_source") or ""),
        ),
        "routing": {
            "primary": "doi_prefix" if doi_prefix else "domain",
            "doi_prefixes": doi_prefixes,
            "domains": [domain] if domain else [],
            "domain_suffixes": [],
            "publisher_aliases": [provider.replace("_", " ")],
            "crossref_publisher": None,
        },
        "main_path": ["article_html", "metadata_only"],
        "probe": {
            "env_requirements": [],
            "requires_playwright": False,
            "requires_browser_runtime": False,
            "ping_url": f"https://{domain}" if domain else None,
        },
        "fixtures": {"doi_samples": {}},
    }


def _draft_for_entry(
    entry: dict[str, Any],
    root: Path,
    *,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    provider = _provider_slug(str(entry["name"]))
    manifest_path = str(entry["manifest_path"])
    manifest_file = root / manifest_path
    seed_status = entry.get("status") == "seed"
    manifest = (
        _seed_manifest(entry)
        if seed_status and not manifest_file.exists()
        else _load_yaml(manifest_file)
    )
    bundle = _provider_bundle(provider)
    source_note = None
    if seed_status:
        source_note = (
            f"{provider} is not listed in {KNOWN_PROVIDERS_PATH}; this blocked draft was "
            "generated from explicit operator seed fields and does not approve access."
        )
    return build_access_review_draft(
        provider,
        manifest,
        bundle,
        manifest_path=manifest_path,
        reviewed_at=reviewed_at,
        source_note=source_note,
    )


def write_access_review_draft(
    *,
    root: Path,
    provider: str,
    draft: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    path = root / ACCESS_REVIEW_DIR / f"{provider_name}.yml"
    if path.exists() and not force:
        return {
            "provider": provider_name,
            "path": _repo_path(path, root),
            "action": "skipped_exists",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return {
        "provider": provider_name,
        "path": _repo_path(path, root),
        "action": "written",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate blocked draft provider access reviews from local onboarding facts."
    )
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument(
        "--all", action="store_true", help="process every implemented provider"
    )
    targets.add_argument("--provider", help="single provider name")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned drafts without writing files",
    )
    mode.add_argument("--write", action="store_true", help="write missing draft files")
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing review file"
    )
    parser.add_argument(
        "--domain",
        help="required when --provider names a new provider not yet listed in known-providers.yml",
    )
    parser.add_argument(
        "--doi-prefix",
        help="optional DOI prefix seed for a new provider draft, for example 10.1371",
    )
    parser.add_argument(
        "--display-source",
        help="optional display source seed for a new provider draft; defaults to <provider>_html",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    targets = _target_providers(args, root)
    results: list[dict[str, Any]] = []
    for entry in targets:
        provider = _provider_slug(str(entry["name"]))
        path = root / ACCESS_REVIEW_DIR / f"{provider}.yml"
        if args.all and path.exists() and not args.force:
            results.append(
                {
                    "provider": provider,
                    "path": _repo_path(path, root),
                    "action": "skipped_exists",
                }
            )
            continue
        draft = _draft_for_entry(entry, root)
        if args.dry_run:
            results.append(
                {
                    "provider": provider,
                    "path": _repo_path(path, root),
                    "action": "would_write"
                    if not path.exists() or args.force
                    else "skipped_exists",
                    "draft": draft,
                }
            )
        else:
            results.append(
                write_access_review_draft(
                    root=root,
                    provider=provider,
                    draft=draft,
                    force=args.force,
                )
            )
    print(json.dumps({"results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
