from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.skill_integrity import (
    SkillManifestError,
    build_skill_bundle_manifest,
    require_valid_skill_bundle,
    verify_skill_bundle,
)


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _manifest_for(skill: Path, manifest: Path) -> None:
    bundle = build_skill_bundle_manifest(
        skill,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )
    _write(manifest, json.dumps({"skill_bundle": bundle}))


def test_verifier_rejects_missing_extra_symlink_and_hash_drift(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write(source / "SKILL.md", "# Skill\n")
    _write(source / "references" / "workflow.md", "workflow\n")
    manifest = tmp_path / "offline-manifest.json"
    _manifest_for(source, manifest)

    installed = tmp_path / "installed"
    _write(installed / "SKILL.md", "changed\n")
    _write(installed / "extra.md", "extra\n")
    (installed / "linked.md").symlink_to(installed / "SKILL.md")

    report = verify_skill_bundle(manifest, skill_dir=installed)

    assert report["status"] == "drift"
    assert report["missing_files"] == ["references/workflow.md"]
    assert report["unexpected_files"] == ["extra.md"]
    assert report["symlink_files"] == ["linked.md"]
    assert [item["path"] for item in report["hash_mismatches"]] == ["SKILL.md"]
    with pytest.raises(SkillManifestError, match="integrity check failed"):
        require_valid_skill_bundle(manifest, skill_dir=installed)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO requires POSIX")
def test_verifier_rejects_special_files(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    _write(skill / "SKILL.md", "# Skill\n")
    manifest = tmp_path / "offline-manifest.json"
    _manifest_for(skill, manifest)
    os.mkfifo(skill / "special.fifo")

    report = verify_skill_bundle(manifest, skill_dir=skill)

    assert report["status"] == "drift"
    assert report["special_files"] == ["special.fifo"]
