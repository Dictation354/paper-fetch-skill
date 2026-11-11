#!/usr/bin/env python3
"""Stage the official Node executable and license pinned by the installer manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


def stage_node_runtime(
    staging: Path, *, target: str, manifest_path: Path, cache_dir: Path
) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime = manifest["embedded_runtimes"][target]
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / runtime["archive"]
    if not archive.is_file():
        with tempfile.TemporaryDirectory(dir=cache_dir) as temporary:
            download = Path(temporary) / runtime["archive"]
            with urlopen(runtime["url"], timeout=120) as response:
                with download.open("wb") as output:
                    shutil.copyfileobj(response, output)
            download.replace(archive)
    with archive.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual != runtime["sha256"]:
        raise ValueError(f"Node archive SHA-256 mismatch: {archive}")

    destination = staging / "runtime/node"
    executable = destination / runtime["executable"]
    executable.parent.mkdir(parents=True, exist_ok=True)
    members = {
        f"{runtime['archive_root']}/{runtime['executable']}": executable,
        f"{runtime['archive_root']}/LICENSE": destination / "LICENSE",
    }
    if archive.suffix == ".zip":
        with ZipFile(archive) as source:
            for name, output in members.items():
                output.write_bytes(source.read(name))
    else:
        with tarfile.open(archive) as source:
            for name, output in members.items():
                member = source.getmember(name)
                if not member.isfile():
                    raise ValueError(
                        f"Node archive member must be a regular file: {name}"
                    )
                with source.extractfile(member) as stream:
                    output.write_bytes(stream.read())
    executable.chmod(0o755)
    record = {
        **{
            key: runtime[key]
            for key in (
                "implementation",
                "version",
                "architecture",
                "archive",
                "url",
                "license",
            )
        },
        "expected_sha256": runtime["sha256"],
        "actual_sha256": actual,
        "runtime_executable": executable.relative_to(staging).as_posix(),
        "license_path": "runtime/node/LICENSE",
    }
    (destination / "node-runtime.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument(
        "--target",
        required=True,
        choices=("linux_node_x86_64", "macos_node_arm64", "windows_node_x86_64"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "installer/manifest.json",
    )
    parser.add_argument("--cache-dir", required=True, type=Path)
    args = parser.parse_args()
    stage_node_runtime(
        args.staging,
        target=args.target,
        manifest_path=args.manifest,
        cache_dir=args.cache_dir,
    )


if __name__ == "__main__":
    main()
