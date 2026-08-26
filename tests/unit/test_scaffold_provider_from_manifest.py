from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "scaffold_provider.py"
ARXIV_MANIFEST = REPO_ROOT / "onboarding" / "manifests" / "arxiv.yml"
WILEY_MANIFEST = REPO_ROOT / "onboarding" / "manifests" / "wiley.yml"


def _run_from_manifest(
    tmp_path: Path,
    manifest_path: Path = ARXIV_MANIFEST,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--from-manifest",
            str(manifest_path),
            "--output-dir",
            str(tmp_path),
            *extra_args,
        ],
        check=True,
        text=True,
        capture_output=True,
    )


def _load_arxiv_manifest() -> dict[str, object]:
    data = yaml.safe_load(ARXIV_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_help_includes_from_manifest() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "--from-manifest" in result.stdout


def test_from_manifest_generates_scaffold_and_json_summary(tmp_path: Path) -> None:
    result = _run_from_manifest(tmp_path)
    summary = json.loads(result.stdout)
    manifest = _load_arxiv_manifest()
    doi_samples = manifest["fixtures"]["doi_samples"]  # type: ignore[index]
    non_null_dois = {
        sample["doi"] for sample in doi_samples.values() if sample["doi"] is not None
    }

    assert summary["status"] == "OK"
    assert summary["provider"] == "arxiv"
    assert "src/paper_fetch/providers/_arxiv_html.py" in summary["generated_files"]
    assert "src/paper_fetch/providers/arxiv.py" in summary["generated_files"]
    assert "onboarding/capture-commands/arxiv.txt" in summary["generated_files"]

    assert (tmp_path / "src/paper_fetch/providers/_arxiv_html.py").is_file()
    assert (tmp_path / "src/paper_fetch/providers/arxiv.py").is_file()
    assert (tmp_path / "tests/unit/test_arxiv_provider.py").is_file()
    generated_test = (tmp_path / "tests/unit/test_arxiv_provider.py").read_text(
        encoding="utf-8"
    )
    assert "test_markdown_review_loop_contract_placeholder" not in generated_test
    assert (
        "# markdown-review: purpose=structure doi=10.48550/arxiv.2605.06663v1"
        in generated_test
    )
    assert 'assert "## Abstract" in markdown' in generated_test
    assert 'assert "Download PDF" not in markdown' in generated_test
    assert "pytest.mark.skip" not in generated_test
    assert "test_provider_golden_replay_placeholder" not in generated_test
    for doi in non_null_dois:
        assert (
            tmp_path
            / "tests"
            / "fixtures"
            / "golden_criteria"
            / doi.replace("/", "_")
            / ".gitkeep"
        ).is_file()

    generated_manifest = json.loads(
        (tmp_path / "tests/fixtures/golden_criteria/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(generated_manifest["samples"]) == {
        doi.replace("/", "_") for doi in non_null_dois
    }
    assert generated_manifest["samples"]["10.48550_arxiv.2605.06663v1"][
        "fixture_purposes"
    ] == ["structure", "table", "references"]

    providers_doc = (tmp_path / "docs/providers.md").read_text(encoding="utf-8")
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    extraction_rules = (tmp_path / "docs/extraction-rules.md").read_text(
        encoding="utf-8"
    )
    assert manifest["docs"]["providers_md_capability_row"] in providers_doc  # type: ignore[index]
    assert "<!-- TODO(scaffold-arxiv): fill -->" in providers_doc
    assert manifest["docs"]["changelog_summary"] in changelog  # type: ignore[index]
    assert "skipped: manifest docs.extraction_rules_summary is null" in extraction_rules

    capture_commands = (tmp_path / "onboarding/capture-commands/arxiv.txt").read_text(
        encoding="utf-8"
    )
    assert "--from-manifest" in capture_commands
    assert str(ARXIV_MANIFEST) in capture_commands
    assert "--all" in capture_commands
    assert "Null DOI purposes are skipped automatically by --all." in capture_commands

    client_text = (tmp_path / "src/paper_fetch/providers/arxiv.py").read_text(
        encoding="utf-8"
    )
    labels = re.findall(r'label="([^"]+)"', client_text)
    assert labels == manifest["main_path"]
    assert "arxiv_fetch_article_html_step" in client_text
    assert "arxiv_fetch_pdf_fallback_step" in client_text
    assert "arxiv_fetch_metadata_only_step" in client_text


def test_from_manifest_capture_commands_include_extra_fixtures(tmp_path: Path) -> None:
    manifest = _load_arxiv_manifest()
    manifest["extra_fixtures"] = [
        {
            "purpose": "structure",
            "doi": "10.48550/arxiv.2605.06556v1",
            "evidence_url": "https://arxiv.org/html/2605.06556v1",
            "evidence_reason": "Additional replay sample for scaffold capture command coverage.",
            "observed_signals": ["html_article"],
            "confidence": "high",
        }
    ]
    manifest_path = tmp_path / "arxiv-extra.yml"
    output_dir = tmp_path / "out"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    _run_from_manifest(output_dir, manifest_path)

    capture_commands = (output_dir / "onboarding/capture-commands/arxiv.txt").read_text(
        encoding="utf-8"
    )
    assert "--from-manifest" in capture_commands
    assert "--all" in capture_commands
    generated_manifest = json.loads(
        (output_dir / "tests/fixtures/golden_criteria/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert generated_manifest["samples"]["10.48550_arxiv.2605.06556v1"][
        "fixture_purposes"
    ] == ["structure"]


def test_from_manifest_generated_provider_modules_import(tmp_path: Path) -> None:
    manifest = _load_arxiv_manifest()
    manifest["name"] = "newmanifest"
    manifest["display_source"] = "newmanifest_html"
    manifest["routing"]["domains"] = ["newmanifest.example"]  # type: ignore[index]
    manifest["routing"]["publisher_aliases"] = ["newmanifest"]  # type: ignore[index]
    manifest["routing"]["doi_prefixes"] = ["10.99999/"]  # type: ignore[index]
    manifest_path = tmp_path / "newmanifest.yml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    out_dir = tmp_path / "out"

    _run_from_manifest(out_dir, manifest_path)

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib
from pathlib import Path

import paper_fetch.providers as provider_entries
from paper_fetch.providers._registry import provider_bundle

provider_entries.__path__ = [
    str(Path({str(out_dir)!r}) / "src/paper_fetch/providers"),
    *list(provider_entries.__path__),
]
importlib.import_module("paper_fetch.providers._newmanifest_html")
client_module = importlib.import_module("paper_fetch.providers.newmanifest")
bundle = provider_bundle("newmanifest")
assert bundle.catalog.name == "newmanifest"
assert bundle.catalog.doi_prefixes == ("10.99999/",)
assert bundle.catalog.asset_default == "body"
assert [step.label for step in client_module.NewmanifestClient.waterfall_steps] == [
    "article_html",
    "pdf_fallback",
    "metadata_only",
]
""",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )

    assert probe.returncode == 0, probe.stderr


def test_from_manifest_existing_outputs_return_merge_plan_json(tmp_path: Path) -> None:
    existing = tmp_path / "src" / "paper_fetch" / "providers" / "_arxiv_html.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("# existing provider module\n", encoding="utf-8")

    result = _run_from_manifest(tmp_path)
    summary = json.loads(result.stdout)

    assert summary["status"] == "MERGE_PLAN"
    assert summary["provider"] == "arxiv"
    assert "src/paper_fetch/providers/_arxiv_html.py" in summary["existing_files"]
    assert summary["generated_files"] == []
    action = next(
        item
        for item in summary["merge_plan"]
        if item.get("path") == "src/paper_fetch/providers/_arxiv_html.py"
    )
    assert action["action"] == "manual_merge"
    assert action["diff_preview"]


def test_from_manifest_safe_merge_reuses_complete_existing_outputs(
    tmp_path: Path,
) -> None:
    _run_from_manifest(tmp_path)

    result = _run_from_manifest(tmp_path, ARXIV_MANIFEST, "--merge-existing=safe")
    summary = json.loads(result.stdout)

    assert summary["status"] == "OK"
    assert (
        "src/paper_fetch/providers/_arxiv_html.py" in summary["reused_existing_files"]
    )
    assert "src/paper_fetch/providers/arxiv.py" in summary["reused_existing_files"]
    assert "tests/unit/test_arxiv_provider.py" in summary["reused_existing_files"]
    assert (tmp_path / "onboarding/scaffold/arxiv.json").is_file()


def test_from_manifest_reuses_existing_fixture_samples_without_merge_plan(
    tmp_path: Path,
) -> None:
    manifest = _load_arxiv_manifest()
    doi = manifest["fixtures"]["doi_samples"]["structure"]["doi"]  # type: ignore[index]
    slug = str(doi).replace("/", "_")
    fixture_dir = tmp_path / "tests" / "fixtures" / "golden_criteria" / slug
    fixture_dir.mkdir(parents=True)
    (fixture_dir / ".gitkeep").write_text("", encoding="utf-8")
    manifest_path = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    )
    manifest_path.write_text(
        json.dumps({"samples": {slug: {"doi": doi, "assets": {}}}}) + "\n",
        encoding="utf-8",
    )

    result = _run_from_manifest(tmp_path)
    summary = json.loads(result.stdout)

    assert summary["status"] == "OK"
    assert slug in summary["reused_fixture_samples"]
    assert "src/paper_fetch/providers/_arxiv_html.py" in summary["generated_files"]
    assert "tests/fixtures/golden_criteria/manifest.json" in summary["generated_files"]
    assert (tmp_path / "src/paper_fetch/providers/_arxiv_html.py").is_file()


def test_from_manifest_routing_and_probe_fields_enter_provider_spec(
    tmp_path: Path,
) -> None:
    _run_from_manifest(tmp_path)

    html_text = (tmp_path / "src/paper_fetch/providers/_arxiv_html.py").read_text(
        encoding="utf-8"
    )

    assert 'domains=("arxiv.org",)' in html_text
    assert 'doi_prefixes=("10.48550/",)' in html_text
    assert "domain_suffixes=()" in html_text
    assert 'publisher_aliases=("arxiv",)' in html_text
    assert 'asset_default="body"' in html_text
    assert "env_requirements=()" in html_text
    assert "requires_playwright=False" in html_text
    assert "requires_browser_runtime=False" in html_text
    assert "status_order=999" in html_text


def test_from_manifest_probe_requirements_enter_provider_spec(tmp_path: Path) -> None:
    _run_from_manifest(tmp_path, WILEY_MANIFEST)

    html_text = (tmp_path / "src/paper_fetch/providers/_wiley_html.py").read_text(
        encoding="utf-8"
    )

    assert "env_requirements=()" in html_text
    assert "requires_playwright=True" in html_text
    assert "requires_browser_runtime=True" in html_text
    assert '# body=("figures", "body_tables", "formula_images")' in html_text
    assert '# all=("figures", "body_tables", "formula_images", "supplementary")' in (
        html_text
    )


@pytest.mark.parametrize(
    "extra_args, expected_flag",
    [
        (("--name", "arxiv"), "--name"),
        (("--doi", "10.48550/arxiv.2605.06663v1"), "--doi"),
        (("--source", "arxiv_html"), "--source"),
        (("--fulltext-client",), "--fulltext-client"),
        (("--html-capable=false",), "--html-capable"),
    ],
)
def test_from_manifest_rejects_mixed_legacy_flags(
    tmp_path: Path,
    extra_args: tuple[str, ...],
    expected_flag: str,
) -> None:
    def run_with(*extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--from-manifest",
                str(ARXIV_MANIFEST),
                "--output-dir",
                str(tmp_path),
                *extra_args,
            ],
            check=False,
            text=True,
            capture_output=True,
        )

    result = run_with(*extra_args)

    assert result.returncode != 0
    assert f"--from-manifest cannot be combined with {expected_flag}" in result.stderr


def test_invalid_manifest_outputs_json_stderr(tmp_path: Path) -> None:
    invalid_manifest = tmp_path / "invalid.yml"
    invalid_manifest.write_text("schema_version: 1\nname: invalid\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--from-manifest",
            str(invalid_manifest),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    error = json.loads(result.stderr)
    assert error["status"] == "MANIFEST_SCHEMA_INVALID"
    assert error["reason"]


def test_from_manifest_does_not_modify_manifest_file(tmp_path: Path) -> None:
    before = ARXIV_MANIFEST.read_text(encoding="utf-8")

    _run_from_manifest(tmp_path)

    assert ARXIV_MANIFEST.read_text(encoding="utf-8") == before
