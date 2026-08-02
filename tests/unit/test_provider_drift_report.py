from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from scripts import run_provider_drift_report as drift


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_provider_drift_report.py"


def _load_mdpi_manifest() -> dict:
    return yaml.safe_load(
        (REPO_ROOT / "onboarding" / "manifests" / "mdpi.yml").read_text(
            encoding="utf-8"
        )
    )


def test_fake_drift_report_marks_matching_source_ok() -> None:
    manifest = _load_mdpi_manifest()
    sample = {
        "purpose": "structure",
        "doi": "10.3390/membranes15030093",
        "accepted_sources": ["mdpi_html"],
    }

    result = drift.evaluate_sample(
        provider="mdpi",
        manifest=manifest,
        sample=sample,
        runner=drift.fake_runner(
            source="mdpi_html",
            markdown="## Abstract\n\nBody\n\nReferences",
        ),
    )

    assert result["source_mismatch"] is False
    assert result["pdf_fallback_silent_degradation"] is False
    assert result["metadata_only_degradation"] is False
    assert result["markdown_contract"]["status"] == "ok"
    assert result["operator_action"] == "none"


def test_fake_drift_report_marks_pdf_fallback_source_mismatch() -> None:
    manifest = _load_mdpi_manifest()
    sample = {
        "purpose": "structure",
        "doi": "10.3390/membranes15030093",
        "accepted_sources": ["mdpi_html"],
    }

    result = drift.evaluate_sample(
        provider="mdpi",
        manifest=manifest,
        sample=sample,
        runner=drift.fake_runner(source="mdpi_pdf", markdown="PDF text"),
    )

    assert result["source_mismatch"] is True
    assert result["pdf_fallback_silent_degradation"] is True
    assert result["markdown_contract"]["missing_must_include"] == ["## Abstract"]
    assert "repair provider route-source" in result["operator_action"]


def test_declared_pdf_fallback_source_is_not_reported_as_drift() -> None:
    manifest = _load_mdpi_manifest()
    sample = {
        "purpose": "structure",
        "doi": "10.3390/membranes15030093",
        "accepted_sources": ["mdpi_html", "mdpi_pdf"],
    }

    result = drift.evaluate_sample(
        provider="mdpi",
        manifest=manifest,
        sample=sample,
        runner=drift.fake_runner(source="mdpi_pdf", markdown="PDF text"),
    )

    assert result["source_mismatch"] is False
    assert result["pdf_fallback_silent_degradation"] is False


def test_browser_risk_selection_uses_manifest_probe_flags() -> None:
    providers = set(drift.browser_risk_providers())

    assert {"ams", "mdpi", "wiley", "science", "pnas"} <= providers
    assert "elsevier" not in providers


def test_drift_report_cli_requires_live_env_without_fake_runner(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PAPER_FETCH_RUN_LIVE", None)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--provider",
            "mdpi",
            "--output",
            str(tmp_path / "report.json"),
        ],
        check=False,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "Set PAPER_FETCH_RUN_LIVE=1" in result.stderr


def test_drift_report_cli_fake_runner_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--provider",
            "mdpi",
            "--fake-source",
            "mdpi_pdf",
            "--fake-markdown",
            "PDF text",
            "--output",
            str(output),
        ],
        check=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    mdpi = report["providers"][0]
    assert report["ci"] == "not_configured"
    assert mdpi["provider"] == "mdpi"
    assert mdpi["route_sources"]["article_html"] == "mdpi_html"
    assert any(sample["source_mismatch"] for sample in mdpi["samples"])
