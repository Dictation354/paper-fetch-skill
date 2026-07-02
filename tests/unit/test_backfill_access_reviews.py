from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts import backfill_access_reviews as backfill


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "backfill_access_reviews.py"
ACCESS_REVIEW_SCHEMA_PATH = REPO_ROOT / "onboarding" / "access-review.schema.json"


def _write_minimal_onboarding_root(root: Path) -> None:
    docs = root / "onboarding"
    (docs / "manifests").mkdir(parents=True)
    (docs / "access-reviews").mkdir(parents=True)
    (docs / "known-providers.yml").write_text(
        yaml.safe_dump(
            {
                "providers": [
                    {
                        "name": "crossref",
                        "status": "infrastructure",
                        "manifest_path": None,
                    },
                    {
                        "name": "mdpi",
                        "status": "implemented",
                        "manifest_path": "onboarding/manifests/mdpi.yml",
                    },
                    {
                        "name": "wiley",
                        "status": "implemented",
                        "manifest_path": "onboarding/manifests/wiley.yml",
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    manifest = {
        "name": "wiley",
        "display_source": "wiley_browser",
        "main_path": ["article_html", "pdf_fallback"],
        "probe": {
            "requires_browser_runtime": True,
            "requires_playwright": True,
        },
        "fixtures": {
            "doi_samples": {
                "structure": {
                    "doi": "10.1111/example",
                    "evidence_reason": "Local fixture records article HTML body sections.",
                    "confidence": "high",
                }
            }
        },
    }
    (docs / "manifests" / "wiley.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    mdpi_manifest = dict(manifest)
    mdpi_manifest["name"] = "mdpi"
    mdpi_manifest["display_source"] = "mdpi_html"
    mdpi_manifest["probe"] = {
        "requires_browser_runtime": True,
        "requires_playwright": True,
    }
    (docs / "manifests" / "mdpi.yml").write_text(
        yaml.safe_dump(mdpi_manifest, sort_keys=False),
        encoding="utf-8",
    )
    (docs / "access-reviews" / "mdpi.yml").write_text(
        "schema_version: 1\nprovider: mdpi\nstatus: approved\n",
        encoding="utf-8",
    )


def test_build_access_review_draft_matches_schema_and_stays_blocked() -> None:
    manifest = yaml.safe_load(
        (REPO_ROOT / "onboarding" / "manifests" / "wiley.yml").read_text(
            encoding="utf-8"
        )
    )

    draft = backfill.build_access_review_draft(
        "wiley",
        manifest,
        reviewed_at="2026-05-21T00:00:00Z",
    )

    schema = json.loads(ACCESS_REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(draft),
        key=lambda error: error.json_path,
    )
    assert not errors
    assert draft["status"] == "blocked"
    assert draft["may_continue"] is False
    assert draft["reviewed_by"] == "operator-required"
    assert draft["legal_access"]["mode"] == "blocked"
    assert {"http", "browser", "playwright"} <= set(draft["allowed_runtimes"])
    assert {
        "automatic_login",
        "captcha_solving",
        "paywall_bypass",
        "challenge_bypass",
    } <= set(draft["forbidden_behaviors"])
    assert any(
        "manifest fixture structure DOI" in item
        for item in draft["legal_access"]["evidence"]
    )


def test_committed_access_reviews_match_schema_and_generated_drafts_stay_blocked() -> (
    None
):
    schema = json.loads(ACCESS_REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
    paths = sorted((REPO_ROOT / "onboarding" / "access-reviews").glob("*.yml"))

    assert paths
    for path in paths:
        review = yaml.safe_load(path.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schema).iter_errors(review),
            key=lambda error: error.json_path,
        )
        assert not errors, [
            f"{path}: {error.json_path}: {error.message}" for error in errors
        ]
        if review.get("reviewed_by") == "operator-required":
            assert review["status"] == "blocked"
            assert review["may_continue"] is False


def test_backfill_dry_run_reports_missing_reviews_without_writing(
    tmp_path: Path,
) -> None:
    _write_minimal_onboarding_root(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--all",
            "--dry-run",
            "--repo-root",
            str(tmp_path),
        ],
        check=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    results = {item["provider"]: item for item in payload["results"]}
    assert results["mdpi"]["action"] == "skipped_exists"
    assert results["wiley"]["action"] == "would_write"
    assert results["wiley"]["draft"]["status"] == "blocked"
    assert not (tmp_path / "onboarding" / "access-reviews" / "wiley.yml").exists()


def test_backfill_write_skips_existing_review_unless_forced(tmp_path: Path) -> None:
    _write_minimal_onboarding_root(tmp_path)
    existing = tmp_path / "onboarding" / "access-reviews" / "mdpi.yml"
    before = existing.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--all",
            "--write",
            "--repo-root",
            str(tmp_path),
        ],
        check=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    results = {item["provider"]: item for item in payload["results"]}
    written = tmp_path / "onboarding" / "access-reviews" / "wiley.yml"
    draft = yaml.safe_load(written.read_text(encoding="utf-8"))

    assert results["mdpi"]["action"] == "skipped_exists"
    assert results["wiley"]["action"] == "written"
    assert existing.read_text(encoding="utf-8") == before
    assert draft["provider"] == "wiley"
    assert draft["status"] == "blocked"
    assert draft["may_continue"] is False


def test_backfill_write_can_seed_new_provider_draft(tmp_path: Path) -> None:
    _write_minimal_onboarding_root(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--provider",
            "plos",
            "--domain",
            "journals.plos.org",
            "--doi-prefix",
            "10.1371",
            "--write",
            "--repo-root",
            str(tmp_path),
        ],
        check=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    results = {item["provider"]: item for item in payload["results"]}
    written = tmp_path / "onboarding" / "access-reviews" / "plos.yml"
    draft = yaml.safe_load(written.read_text(encoding="utf-8"))

    assert results["plos"]["action"] == "written"
    assert draft["provider"] == "plos"
    assert draft["status"] == "blocked"
    assert draft["may_continue"] is False
    assert draft["legal_access"]["mode"] == "blocked"
    assert draft["allowed_runtimes"] == ["http"]
    assert any("not listed" in item for item in draft["legal_access"]["evidence"])
    assert any(
        "journals.plos.org" in item for item in draft["legal_access"]["evidence"]
    )
    assert any("10.1371/" in item for item in draft["legal_access"]["evidence"])


def test_backfill_new_provider_requires_domain(tmp_path: Path) -> None:
    _write_minimal_onboarding_root(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--provider",
            "plos",
            "--dry-run",
            "--repo-root",
            str(tmp_path),
        ],
        check=False,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "provide --domain" in result.stderr
