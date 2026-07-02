from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.script_modules import load_script_module


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_manifest(root: Path, sample: dict[str, object]) -> None:
    manifest_path = root / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"samples": {"10.1234_example": sample}}, indent=2) + "\n",
        encoding="utf-8",
    )


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "doi": "10.1234/example",
        "review": False,
        "output_dir": str(tmp_path),
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_snapshot_expected_writes_existing_golden_schema_and_updates_manifest(
    tmp_path: Path,
) -> None:
    module = load_script_module("snapshot_expected")
    fixture_dir = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "10.1234_example"
    )
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "original.html").write_text(
        """
        <html>
          <head>
            <meta name="citation_title" content="Recorded fixture">
            <meta name="citation_author" content="Ada Lovelace">
            <meta name="description" content="Short abstract.">
          </head>
          <body>
            <h1>Recorded fixture</h1>
            <h2>Methods</h2>
            <figure><img src="fig.png"></figure>
            <table><tr><td>x</td></tr></table>
            <math><mi>x</mi></math>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    _write_manifest(
        tmp_path,
        {
            "doi": "10.1234/example",
            "publisher": "examplepub",
            "source_url": "https://example.test/article",
            "fixture_family": "golden",
            "route_kind": "html",
            "content_type": "text/html",
            "expected_outcome": "pending",
            "assets": {
                "original.html": "tests/fixtures/golden_criteria/10.1234_example/original.html",
            },
        },
    )

    expected, wrote = module.snapshot_expected(_args(tmp_path))

    expected_path = fixture_dir / "expected.json"
    markdown_path = fixture_dir / "extracted.md"
    prompt_path = fixture_dir / "markdown-quality-prompt.md"
    quality_path = fixture_dir / "markdown-quality.json"
    manifest = json.loads(
        (
            tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
        ).read_text()
    )
    written = json.loads(expected_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))

    assert wrote is True
    assert expected == written
    assert markdown_path.read_text(encoding="utf-8").startswith("# Recorded fixture\n")
    assert prompt_path.is_file()
    assert "Markdown Quality Agent Review" in prompt_path.read_text(encoding="utf-8")
    assert quality["schema_version"] == 2
    assert quality["review_method"] == "agent_prompt"
    assert quality["status"] == "pending_agent_review"
    assert (
        quality["markdown_path"]
        == "tests/fixtures/golden_criteria/10.1234_example/extracted.md"
    )
    assert (
        quality["prompt_path"]
        == "tests/fixtures/golden_criteria/10.1234_example/markdown-quality-prompt.md"
    )
    assert set(written) == {"has", "counts", "expected_content_kind"}
    assert written["has"]["title"] is True
    assert written["has"]["authors"] is True
    assert written["has"]["body"] is True
    assert written["counts"]["tables"] == 1
    assert written["counts"]["figures"] == 1
    assert written["expected_content_kind"] == "fulltext"
    assert manifest["samples"]["10.1234_example"]["expected_outcome"] == "fulltext"
    assert manifest["samples"]["10.1234_example"]["assets"]["expected.json"] == (
        "tests/fixtures/golden_criteria/10.1234_example/expected.json"
    )
    assert manifest["samples"]["10.1234_example"]["assets"]["extracted.md"] == (
        "tests/fixtures/golden_criteria/10.1234_example/extracted.md"
    )
    assert manifest["samples"]["10.1234_example"]["assets"][
        "markdown-quality-prompt.md"
    ] == ("tests/fixtures/golden_criteria/10.1234_example/markdown-quality-prompt.md")
    assert manifest["samples"]["10.1234_example"]["assets"][
        "markdown-quality.json"
    ] == ("tests/fixtures/golden_criteria/10.1234_example/markdown-quality.json")


def test_snapshot_expected_review_print_shape_without_writing(tmp_path: Path) -> None:
    module = load_script_module("snapshot_expected")
    fixture_dir = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "10.1234_example"
    )
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "original.html").write_text(
        "<html><head><title>T</title><meta name='description' content='Abstract'></head><body></body></html>",
        encoding="utf-8",
    )
    sample = {
        "doi": "10.1234/example",
        "publisher": "examplepub",
        "source_url": "https://example.test/article",
        "fixture_family": "golden",
        "route_kind": "html",
        "content_type": "text/html",
        "expected_outcome": "pending",
        "assets": {
            "original.html": "tests/fixtures/golden_criteria/10.1234_example/original.html",
        },
    }
    _write_manifest(tmp_path, sample)
    before = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    ).read_text(encoding="utf-8")

    payload, wrote = module.snapshot_expected(_args(tmp_path, review=True))

    after = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    ).read_text(encoding="utf-8")
    assert wrote is False
    assert set(payload) == {
        "expected",
        "review",
        "markdown_quality_prompt",
        "markdown_quality_report",
    }
    assert set(payload["expected"]) == {"has", "counts", "expected_content_kind"}
    assert payload["review"]["title"] == "T"
    assert "Markdown Quality Agent Review" in payload["markdown_quality_prompt"]
    assert payload["markdown_quality_report"]["status"] == "pending_agent_review"
    assert not (fixture_dir / "expected.json").exists()
    assert not (fixture_dir / "extracted.md").exists()
    assert not (fixture_dir / "markdown-quality-prompt.md").exists()
    assert not (fixture_dir / "markdown-quality.json").exists()
    assert after == before


def test_snapshot_expected_missing_fixture_review_returns_placeholder(
    tmp_path: Path,
) -> None:
    module = load_script_module("snapshot_expected")

    payload, wrote = module.snapshot_expected(
        _args(tmp_path, doi="10.0000/probe", review=True)
    )

    assert wrote is False
    assert payload["doi"] == "10.0000/probe"
    assert payload["available"] is False
    assert payload["summary"] is None
