from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from ._manifest_sync import (
    REPO_ROOT,
    iter_manifest_cases,
    serialize_bundle_sync_back,
)


def test_manifest_sync_back_round_trips_runtime_bundle_fields(tmp_path: Path) -> None:
    case = next(case for case in iter_manifest_cases() if case.provider == "wiley")
    tmp_manifest = tmp_path / "wiley.yml"
    tmp_manifest.write_text(
        case.manifest_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    manifest_payload = yaml.safe_load(tmp_manifest.read_text(encoding="utf-8"))
    manifest_payload["extraction_hints"]["datalayer_signal_set"] = None
    tmp_manifest.write_text(
        yaml.safe_dump(manifest_payload, sort_keys=False),
        encoding="utf-8",
    )

    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "manifest_sync_back.py"),
            "--provider",
            case.provider,
            "--manifest",
            str(tmp_manifest),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    summary = json.loads(result.stdout)
    assert summary["status"] == "OK"
    assert summary["provider"] == "wiley"
    assert summary["manifest_path"] == str(tmp_manifest)
    assert "extraction_hints.datalayer_signal_set" in summary["updated_fields"]

    updated = yaml.safe_load(tmp_manifest.read_text(encoding="utf-8"))
    assert isinstance(updated, dict)
    assert updated["extraction_hints"] == serialize_bundle_sync_back(case.bundle)
    assert set(case.manifest["main_path"]) <= set(updated["success_criteria"])
    for step in case.manifest["main_path"]:
        assert updated["success_criteria"][step] is not None


def test_manifest_sync_back_sync_docs_updates_marker_entries(tmp_path: Path) -> None:
    case = next(case for case in iter_manifest_cases() if case.provider == "arxiv")
    tmp_manifest = tmp_path / "onboarding" / "manifests" / "arxiv.yml"
    tmp_manifest.parent.mkdir(parents=True)
    tmp_manifest.write_text(
        case.manifest_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    onboarding_dir = tmp_path / "onboarding"
    onboarding_dir.mkdir(parents=True, exist_ok=True)
    (onboarding_dir / "known-providers.yml").write_text(
        "providers:\n"
        "  - name: crossref\n"
        "    display_source: crossref\n"
        "    status: infrastructure\n"
        "    manifest_path: null\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "providers.md").write_text(
        "# Providers\n\n"
        "<!-- SCAFFOLD: providers-capability-matrix -->\n"
        "| Provider | 元数据 | 全文主路径 | 资产下载 | Markdown 能力 | 备注 |\n"
        "| --- | --- | --- | --- | --- | --- |\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "extraction-rules.md").write_text(
        "# Extraction Rules\n\n"
        "<!-- SCAFFOLD: extraction-rules-unstable-doi -->\n"
        "| 规则 | 当前证据状态 | 后续补样本触发 | 下一步候选 fixture |\n"
        "| --- | --- | --- | --- |\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n\n<!-- SCAFFOLD: changelog-unreleased -->\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "manifest_sync_back.py"),
            "--provider",
            "arxiv",
            "--manifest",
            str(tmp_manifest),
            "--sync-docs",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    summary = json.loads(result.stdout)
    known = yaml.safe_load(
        (onboarding_dir / "known-providers.yml").read_text(encoding="utf-8")
    )

    assert "docs.providers_matrix" in summary["updated_fields"]
    assert "docs.extraction_rules" in summary["updated_fields"]
    assert "docs.changelog" in summary["updated_fields"]
    assert known["providers"][-1]["name"] == "arxiv"
    assert known["providers"][-1]["manifest_path"] == ("onboarding/manifests/arxiv.yml")
    assert "arXiv | arXiv ID" in (tmp_path / "docs" / "providers.md").read_text(
        encoding="utf-8"
    )
    assert "`arxiv` docs sync" in (tmp_path / "docs" / "extraction-rules.md").read_text(
        encoding="utf-8"
    )
