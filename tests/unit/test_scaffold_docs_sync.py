from __future__ import annotations

from pathlib import Path

from ._scaffold_support import run_scaffold as _run_scaffold


def test_scaffold_provider_syncs_docs_placeholders_by_default(tmp_path: Path) -> None:
    result = _run_scaffold(
        tmp_path,
        "--name",
        "newpub",
        "--doi",
        "10.1234/sample",
    )

    providers = (tmp_path / "docs/providers.md").read_text(encoding="utf-8")
    extraction = (tmp_path / "docs/extraction-rules.md").read_text(encoding="utf-8")
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    assert (
        "| `newpub` | TODO | TODO | TODO | TODO | <!-- TODO(scaffold-newpub): fill --> |"
        in providers
    )
    assert (
        "<!-- TODO(scaffold-newpub): fill routing / waterfall / asset_profile / status docs. -->"
        in providers
    )
    assert "| `newpub` | <!-- TODO(scaffold-newpub): fill --> |" in extraction
    assert (
        "<!-- TODO(scaffold-newpub): fill --> Add `newpub` provider scaffold docs"
        in changelog
    )
    assert "Docs placeholders to fill:" in result.stdout
    assert "- docs/providers.md" in result.stdout
    assert "- docs/extraction-rules.md" in result.stdout
    assert "- CHANGELOG.md" in result.stdout


def test_scaffold_provider_no_sync_docs_skips_docs_and_stdout(tmp_path: Path) -> None:
    result = _run_scaffold(
        tmp_path,
        "--name",
        "newpub",
        "--doi",
        "10.1234/sample",
        "--no-sync-docs",
    )

    assert not (tmp_path / "docs/providers.md").exists()
    assert not (tmp_path / "docs/extraction-rules.md").exists()
    assert not (tmp_path / "CHANGELOG.md").exists()
    assert "Docs placeholders to fill:" not in result.stdout
