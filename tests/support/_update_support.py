from __future__ import annotations

import json
from pathlib import Path

from paper_fetch import update

REPO_ROOT = Path(__file__).resolve().parents[2]


def installation(
    root: Path, system: str = "linux", tag: str = "cp313"
) -> update.Installation:
    installer = json.loads((REPO_ROOT / "installer/manifest.json").read_text())
    packages = installer["packages"]
    manifest = {
        "schema_version": 3,
        "name": packages[f"{system}_manifest_name"],
        "project": "paper-fetch-skill",
        "entrypoint": packages["windows_setup_base_name"] + ".exe"
        if system == "windows"
        else "install-offline.sh",
        "target": {
            "platform": system,
            "arch": "arm64" if system == "macos" else "x86_64",
            "python_tag": tag,
        },
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "offline-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8-sig"
    )
    (root / "installer").mkdir()
    (root / "installer/manifest.json").write_text(
        json.dumps(installer), encoding="utf-8-sig"
    )
    (root / "runtime").mkdir()
    (root / "runtime" / ("python.exe" if system == "windows" else "python-bin")).touch()
    return update.Installation(root, manifest, packages)


def release(*names: str, version: str = "v8.0.0") -> dict:
    return {
        "tag_name": version,
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": name,
                "browser_download_url": f"https://github.com/{update.REPOSITORY}/releases/download/{version}/{name}",
            }
            for name in names
        ],
    }
