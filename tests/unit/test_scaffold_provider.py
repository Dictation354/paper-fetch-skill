from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from ._scaffold_support import (
    REPO_ROOT,
    SCAFFOLD_PROVIDER_SCRIPT as SCRIPT,
    run_scaffold as _run_scaffold,
)


def _register_call_line(module_text: str) -> int:
    tree = ast.parse(module_text)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_provider_bundle"
        ):
            return node.lineno
    raise AssertionError("register_provider_bundle call not found")


def test_scaffold_provider_generates_repo_like_structure(tmp_path: Path) -> None:
    result = _run_scaffold(
        tmp_path,
        "--name",
        "newpub",
        "--doi",
        "10.1234/sample",
        "--source",
        "newpub_source",
        "--fulltext-client",
    )

    html_module = tmp_path / "src/paper_fetch/providers/_newpub_html.py"
    client_module = tmp_path / "src/paper_fetch/providers/newpub.py"
    test_module = tmp_path / "tests/unit/test_newpub_provider.py"
    fixture_keep = tmp_path / "tests/fixtures/golden_criteria/10.1234_sample/.gitkeep"
    manifest_path = tmp_path / "tests/fixtures/golden_criteria/manifest.json"

    assert html_module.is_file()
    assert client_module.is_file()
    assert test_module.is_file()
    assert fixture_keep.is_file()
    assert manifest_path.is_file()
    assert "PR-checklist TODO:" in result.stdout
    assert "src/paper_fetch/providers/_newpub_html.py" in result.stdout
    assert (
        "Generate baseline Markdown for every non-null manifest fixture purpose."
        in result.stdout
    )
    assert "positive Markdown assertions" in result.stdout
    assert "negative Markdown assertions" in result.stdout
    assert "Ensure each non-null fixture purpose is named or asserted" in result.stdout
    assert "provider discovery" not in result.stdout

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["samples"]["10.1234_sample"] == {
        "doi": "10.1234/sample",
        "publisher": "newpub",
        "title": "TODO: fill golden criteria title",
        "source_url": "",
        "landing_url": "",
        "route_kind": "html",
        "content_type": "text/html",
        "origin_kind": "placeholder",
        "usage_kind": "content",
        "fixture_family": "golden",
        "expected_outcome": "pending",
        "assets": {},
    }

    client_text = client_module.read_text(encoding="utf-8")
    assert "WaterfallStep" in client_text
    assert "waterfall_steps = (" in client_text
    assert "newpub_fetch_html_step" in client_text

    html_text = html_module.read_text(encoding="utf-8")
    assert "def newpub_fetch_html_step(client" in html_text

    test_text = test_module.read_text(encoding="utf-8")
    assert "test_markdown_review_loop_contract_placeholder" in test_text
    assert "pytest.mark.skip" not in test_text
    assert "test_provider_golden_replay_placeholder" not in test_text


def test_scaffold_provider_places_bundle_registration_after_imports(
    tmp_path: Path,
) -> None:
    _run_scaffold(tmp_path, "--name", "newpub", "--doi", "10.1234/sample")

    module_text = (tmp_path / "src/paper_fetch/providers/_newpub_html.py").read_text(
        encoding="utf-8"
    )
    lines = module_text.splitlines()

    assert _register_call_line(module_text) == 13
    assert lines[12] == "register_provider_bundle("
    assert (
        "def newpub_before_block_normalization(container: Any) -> Any:" in module_text
    )
    assert "def newpub_normalize_markdown(text: str) -> str:" in module_text
    assert "def extract_authors(html_text: str) -> list[str]:" in module_text
    assert "# kept for compatibility" not in module_text


def test_scaffold_provider_html_capable_bundle_satisfies_s4_shape(
    tmp_path: Path,
) -> None:
    _run_scaffold(tmp_path, "--name", "newpub", "--doi", "10.1234/sample")

    module_text = (tmp_path / "src/paper_fetch/providers/_newpub_html.py").read_text(
        encoding="utf-8"
    )

    assert "html_capable=False" not in module_text
    assert "html_rules=ProviderHtmlRules(" in module_text
    assert "availability=AvailabilityPolicy(" in module_text
    assert "no_signals=True" in module_text

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib
from pathlib import Path

import paper_fetch.providers as provider_entries
from paper_fetch.extraction.html.availability_policy import AvailabilityPolicy
from paper_fetch.extraction.html.provider_rules import ProviderCleanupRules, ProviderFrontMatterRules, ProviderHtmlRules
from paper_fetch.providers._registry import provider_bundle

provider_entries.__path__ = [
    str(Path({str(tmp_path)!r}) / "src/paper_fetch/providers"),
    *list(provider_entries.__path__),
]
importlib.import_module("paper_fetch.providers._newpub_html")
bundle = provider_bundle("newpub")
assert bundle.catalog.name == "newpub"
assert bundle.catalog.html_capable is True
assert bundle.html_rules is not None
assert isinstance(bundle.html_rules, ProviderHtmlRules)
assert isinstance(bundle.html_rules.cleanup, ProviderCleanupRules)
assert isinstance(bundle.html_rules.front_matter, ProviderFrontMatterRules)
assert isinstance(bundle.html_rules.availability, AvailabilityPolicy)
assert bundle.html_rules.availability.no_signals is True
""",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert probe.returncode == 0, probe.stderr


def test_scaffold_provider_non_html_bundle_satisfies_s4_shape(
    tmp_path: Path,
) -> None:
    _run_scaffold(
        tmp_path,
        "--name",
        "newpub",
        "--doi",
        "10.1234/sample",
        "--html-capable=false",
    )

    module_text = (tmp_path / "src/paper_fetch/providers/_newpub_html.py").read_text(
        encoding="utf-8"
    )
    test_text = (tmp_path / "tests/unit/test_newpub_provider.py").read_text(
        encoding="utf-8"
    )
    manifest = json.loads(
        (tmp_path / "tests/fixtures/golden_criteria/manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert "html_capable=False" in module_text
    assert "html_rules=ProviderHtmlRules(" not in module_text
    assert "AvailabilityPolicy" not in module_text
    assert "assert bundle.html_rules is None" in test_text
    assert "assert bundle.catalog.html_capable is False" in test_text
    assert "test_markdown_review_loop_contract_placeholder" in test_text
    assert "pytest.mark.skip" not in test_text
    assert "test_provider_golden_replay_placeholder" not in test_text
    assert manifest["samples"]["10.1234_sample"]["route_kind"] == "official"


def test_scaffold_provider_refuses_existing_files_and_manifest_samples(
    tmp_path: Path,
) -> None:
    _run_scaffold(tmp_path, "--name", "newpub", "--doi", "10.1234/sample")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(tmp_path),
            "--name",
            "newpub",
            "--doi",
            "10.1234/sample",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "refusing to overwrite existing path" in result.stderr


def test_scaffold_provider_fulltext_client_imports(tmp_path: Path) -> None:
    _run_scaffold(
        tmp_path,
        "--name",
        "newpub",
        "--doi",
        "10.1234/sample",
        "--fulltext-client",
    )

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib
from pathlib import Path

import paper_fetch.providers as provider_entries

provider_entries.__path__ = [
    str(Path({str(tmp_path)!r}) / "src/paper_fetch/providers"),
    *list(provider_entries.__path__),
]
module = importlib.import_module("paper_fetch.providers.newpub")
assert module.NewpubClient.waterfall_steps
assert module.NewpubClient.waterfall_steps[1].label == "html"
""",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert probe.returncode == 0, probe.stderr
