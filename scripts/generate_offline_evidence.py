#!/usr/bin/env python3
"""Generate dependency evidence from an already staged offline target.

The input is the installable staging tree, not ``uv.lock`` or a resolver
snapshot.  Python distributions are inspected from the staged site-packages;
Node, browser-driver, formula, image and native components are hashed from the
files that will actually be packaged. Setup-time inputs that live outside the
runtime staging tree must carry matching builder-verified expected/actual
digests in the offline manifest. CycloneDX's maintained Python tooling creates
and validates the base BOM before those non-Python components are added and the
complete document is validated again.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import Distribution, distributions
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
from collections.abc import Iterable
from urllib.parse import quote


DEPENDENCY_MANIFEST_NAME = "dependency-manifest.json"
SBOM_NAME = "paper-fetch-sbom.cdx.json"
_IGNORED_NODE_DIRECTORIES = {".bin", ".cache"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _relative_regular_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"staged dependency evidence rejects symlink: {path}")
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _tree_digest(root: Path, files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _distribution_files(distribution: Distribution, staging: Path) -> list[Path]:
    paths: list[Path] = []
    staging = staging.resolve()
    for entry in distribution.files or ():
        located = Path(distribution.locate_file(entry))
        if located.is_symlink():
            raise ValueError(f"staged Python distribution contains symlink: {located}")
        candidate = located.resolve()
        try:
            candidate.relative_to(staging)
        except ValueError as exc:
            raise ValueError(
                f"distribution file escapes staged package: {candidate}"
            ) from exc
        if candidate.is_file():
            paths.append(candidate)
    return sorted(set(paths), key=lambda item: item.relative_to(staging).as_posix())


def _distribution_metadata_path(
    distribution: Distribution, site_packages: Path
) -> Path:
    candidates = {
        Path(distribution.locate_file(entry)).resolve().parent
        for entry in distribution.files or ()
        if Path(str(entry)).name in {"METADATA", "PKG-INFO"}
    }
    if len(candidates) != 1:
        raise ValueError(
            "staged Python distribution must expose exactly one metadata directory"
        )
    metadata_path = next(iter(candidates))
    try:
        metadata_path.relative_to(site_packages.resolve())
    except ValueError as exc:
        raise ValueError(
            f"distribution metadata escapes staged site-packages: {metadata_path}"
        ) from exc
    return metadata_path


def _python_inventory(staging: Path, site_packages: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for distribution in distributions(path=[str(site_packages)]):
        name = str(distribution.metadata.get("Name") or "").strip()
        version = str(distribution.version or "").strip()
        if not name or not version:
            raise ValueError("staged Python distribution is missing name or version")
        files = _distribution_files(distribution, staging)
        metadata_path = _distribution_metadata_path(distribution, site_packages)
        metadata_relative = metadata_path.relative_to(staging.resolve())
        inventory.append(
            {
                "name": name,
                "version": version,
                "metadata_path": metadata_relative.as_posix(),
                "file_count": len(files),
                "content_sha256": _tree_digest(staging, files),
            }
        )
    inventory.sort(key=lambda item: (item["name"].casefold(), item["version"]))
    if not inventory:
        raise ValueError("staged site-packages contains no installed distributions")
    return inventory


def _node_inventory(staging: Path) -> list[dict[str, Any]]:
    roots = (
        staging / "formula-tools",
        staging / "runtime" / "site-packages" / "playwright" / "driver",
        staging / "runtime" / "Lib" / "site-packages" / "playwright" / "driver",
    )
    inventory: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.rglob("package.json")):
            if any(part in _IGNORED_NODE_DIRECTORIES for part in manifest_path.parts):
                continue
            resolved = manifest_path.resolve()
            if resolved in seen or manifest_path.is_symlink():
                continue
            seen.add(resolved)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            name = str(payload.get("name") or "").strip()
            version = str(payload.get("version") or "").strip()
            if not name or not version:
                continue
            inventory.append(
                {
                    "name": name,
                    "version": version,
                    "path": manifest_path.relative_to(staging).as_posix(),
                    "manifest_sha256": _sha256(manifest_path),
                }
            )
    inventory.sort(key=lambda item: (item["name"], item["version"], item["path"]))
    return inventory


def _native_inventory(staging: Path) -> list[dict[str, Any]]:
    roots = (
        (staging / "formula-tools", "formula-tool"),
        (staging / "image-tools", "image-tool"),
    )
    inventory: list[dict[str, Any]] = []
    for root, category in roots:
        for path in _relative_regular_files(root):
            if "node_modules" in path.relative_to(root).parts:
                continue
            inventory.append(
                {
                    "name": path.name,
                    "path": path.relative_to(staging).as_posix(),
                    "category": category,
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )

    for relative in (
        Path("runtime/site-packages/playwright/driver/node"),
        Path("runtime/Lib/site-packages/playwright/driver/node.exe"),
    ):
        path = staging / relative
        if path.is_file():
            inventory.append(
                {
                    "name": "playwright-driver-node",
                    "path": relative.as_posix(),
                    "category": "browser-driver",
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    inventory.sort(key=lambda item: item["path"])
    return inventory


def _embedded_runtime_inventory(
    staging: Path, offline_manifest: dict[str, Any]
) -> dict[str, Any] | None:
    target = offline_manifest.get("target") or {}
    runtime = target.get("embedded_runtime")
    if not isinstance(runtime, dict):
        return None
    expected = str(runtime.get("expected_sha256") or "").lower()
    actual = str(runtime.get("actual_sha256") or "").lower()
    if len(expected) != 64 or expected != actual:
        raise ValueError("embedded runtime expected and actual SHA-256 must match")
    executable = staging / "runtime" / "python.exe"
    if not executable.is_file():
        raise ValueError("Windows staged runtime is missing runtime/python.exe")
    return {
        **runtime,
        "runtime_executable": "runtime/python.exe",
        "runtime_executable_sha256": _sha256(executable),
    }


def _setup_component_inventory(
    offline_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_components = offline_manifest.get("setup_components")
    if raw_components is None:
        return []
    if not isinstance(raw_components, dict):
        raise ValueError("setup_components must be an object")

    inventory: list[dict[str, Any]] = []
    for component_id, raw_component in raw_components.items():
        if not isinstance(component_id, str) or not isinstance(raw_component, dict):
            raise ValueError("setup_components entries must be named objects")
        expected = str(raw_component.get("expected_sha256") or "").lower()
        actual = str(raw_component.get("actual_sha256") or "").lower()
        license_expected = str(
            raw_component.get("license_expected_sha256") or ""
        ).lower()
        license_actual = str(
            raw_component.get("license_actual_sha256") or ""
        ).lower()
        archive_digest = str(raw_component.get("archive_sha256") or "").lower()
        if len(expected) != 64 or expected != actual:
            raise ValueError(
                f"setup component {component_id} expected and actual SHA-256 must match"
            )
        if len(license_expected) != 64 or license_expected != license_actual:
            raise ValueError(
                f"setup component {component_id} license SHA-256 must match"
            )
        if len(archive_digest) != 64:
            raise ValueError(
                f"setup component {component_id} archive SHA-256 must be pinned"
            )
        required = {
            field: str(raw_component.get(field) or "")
            for field in (
                "name",
                "version",
                "architecture",
                "archive",
                "archive_url",
                "license",
                "usage",
            )
        }
        missing = sorted(field for field, value in required.items() if not value)
        if missing:
            raise ValueError(
                f"setup component {component_id} is missing {', '.join(missing)}"
            )
        inventory.append(
            {
                "id": component_id,
                **required,
                "archive_sha256": archive_digest,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "license_expected_sha256": license_expected,
                "license_actual_sha256": license_actual,
            }
        )
    inventory.sort(key=lambda item: item["id"])
    return inventory


def _component_properties(path: str, category: str) -> list[dict[str, str]]:
    return [
        {"name": "paper-fetch:staged-path", "value": path},
        {"name": "paper-fetch:component-category", "value": category},
    ]


def _augment_sbom(
    sbom: dict[str, Any],
    *,
    node: list[dict[str, Any]],
    native: list[dict[str, Any]],
    embedded_runtime: dict[str, Any] | None,
    setup_components: list[dict[str, Any]],
    python_packages: list[dict[str, Any]],
) -> None:
    components = sbom.setdefault("components", [])
    python_by_name = {
        str(item.get("name") or "").casefold(): item for item in components
    }
    for installed in python_packages:
        component = python_by_name.get(installed["name"].casefold())
        if component is None:
            continue
        component.setdefault("properties", []).extend(
            [
                {
                    "name": "paper-fetch:installed-file-count",
                    "value": str(installed["file_count"]),
                },
                {
                    "name": "paper-fetch:installed-content-sha256",
                    "value": installed["content_sha256"],
                },
                {
                    "name": "paper-fetch:staged-metadata-path",
                    "value": installed["metadata_path"],
                },
            ]
        )

    for package in node:
        escaped_name = quote(package["name"], safe="/")
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:npm/{escaped_name}@{quote(package['version'], safe='')}",
                "name": package["name"],
                "version": package["version"],
                "purl": f"pkg:npm/{escaped_name}@{quote(package['version'], safe='')}",
                "hashes": [{"alg": "SHA-256", "content": package["manifest_sha256"]}],
                "properties": _component_properties(package["path"], "node"),
            }
        )
    for component in native:
        bom_ref = f"paper-fetch:staged-native:{component['sha256']}:{component['path']}"
        components.append(
            {
                "type": "application",
                "bom-ref": bom_ref,
                "name": component["name"],
                "hashes": [{"alg": "SHA-256", "content": component["sha256"]}],
                "properties": _component_properties(
                    component["path"], component["category"]
                ),
            }
        )
    if embedded_runtime is not None:
        version = str(embedded_runtime["version"])
        components.append(
            {
                "type": "platform",
                "bom-ref": f"pkg:generic/cpython@{quote(version, safe='')}?arch=x86_64",
                "name": "CPython embedded runtime",
                "version": version,
                "hashes": [
                    {
                        "alg": "SHA-256",
                        "content": embedded_runtime["actual_sha256"],
                    }
                ],
                "externalReferences": [
                    {"type": "distribution", "url": embedded_runtime["url"]}
                ],
                "properties": [
                    {
                        "name": "paper-fetch:archive",
                        "value": embedded_runtime["archive"],
                    },
                    {
                        "name": "paper-fetch:archive-url",
                        "value": embedded_runtime["url"],
                    },
                    {
                        "name": "paper-fetch:expected-archive-sha256",
                        "value": embedded_runtime["expected_sha256"],
                    },
                    {
                        "name": "paper-fetch:actual-archive-sha256",
                        "value": embedded_runtime["actual_sha256"],
                    },
                    {
                        "name": "paper-fetch:runtime-executable-sha256",
                        "value": embedded_runtime["runtime_executable_sha256"],
                    },
                ],
            }
        )

    for component in setup_components:
        version = component["version"]
        component_id = quote(component["id"], safe="")
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:generic/{component_id}@{quote(version, safe='')}",
                "name": component["name"],
                "version": version,
                "hashes": [
                    {"alg": "SHA-256", "content": component["actual_sha256"]}
                ],
                "licenses": [{"expression": component["license"]}],
                "externalReferences": [
                    {"type": "distribution", "url": component["archive_url"]}
                ],
                "properties": [
                    {
                        "name": "paper-fetch:component-category",
                        "value": "setup-time",
                    },
                    {
                        "name": "paper-fetch:architecture",
                        "value": component["architecture"],
                    },
                    {
                        "name": "paper-fetch:usage",
                        "value": component["usage"],
                    },
                    {
                        "name": "paper-fetch:archive",
                        "value": component["archive"],
                    },
                    {
                        "name": "paper-fetch:archive-sha256",
                        "value": component["archive_sha256"],
                    },
                    {
                        "name": "paper-fetch:expected-sha256",
                        "value": component["expected_sha256"],
                    },
                    {
                        "name": "paper-fetch:license-sha256",
                        "value": component["license_actual_sha256"],
                    },
                ],
            }
        )

    components.sort(
        key=lambda item: (
            str(item.get("type") or ""),
            str(item.get("name") or "").casefold(),
            str(item.get("version") or ""),
            str(item.get("bom-ref") or ""),
        )
    )


def _generate_cyclonedx(
    requirements: Path,
    output: Path,
    python_executable: str,
) -> dict[str, Any]:
    subprocess.run(
        [
            python_executable,
            "-m",
            "cyclonedx_py",
            "requirements",
            str(requirements),
            "--spec-version",
            "1.6",
            "--output-format",
            "JSON",
            "--output-reproducible",
            "--output-file",
            str(output),
            "--validate",
        ],
        check=True,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _validate_sbom(payload: dict[str, Any]) -> None:
    from cyclonedx.schema import SchemaVersion
    from cyclonedx.validation.json import JsonStrictValidator

    diagnostic = JsonStrictValidator(SchemaVersion.V1_6).validate_str(
        json.dumps(payload, ensure_ascii=False)
    )
    if diagnostic is not None:
        raise ValueError(f"generated CycloneDX SBOM is invalid: {diagnostic}")


def generate_evidence(
    *,
    staging: Path,
    site_packages: Path,
    offline_manifest_path: Path,
    output_dir: Path,
    target: str,
    cyclonedx_python: str,
) -> tuple[Path, Path]:
    staging = staging.resolve()
    site_packages = site_packages.resolve()
    offline_manifest_path = offline_manifest_path.resolve()
    try:
        site_packages.relative_to(staging)
        offline_manifest_path.relative_to(staging)
    except ValueError as exc:
        raise ValueError("evidence inputs must be inside the staged package") from exc

    offline_manifest = json.loads(offline_manifest_path.read_text(encoding="utf-8"))
    python_packages = _python_inventory(staging, site_packages)
    node_packages = _node_inventory(staging)
    native_components = _native_inventory(staging)
    embedded_runtime = _embedded_runtime_inventory(staging, offline_manifest)
    setup_components = _setup_component_inventory(offline_manifest)
    camoufox = next(
        (
            package
            for package in python_packages
            if package["name"].casefold() == "camoufox"
        ),
        None,
    )

    dependency_manifest = {
        "schema_version": 1,
        "source": "actual-staged-target",
        "target": target,
        "offline_target": offline_manifest.get("target"),
        "python_packages": python_packages,
        "node_packages": node_packages,
        "native_components": native_components,
        "setup_components": setup_components,
        "browser": {
            "camoufox_python_package": (
                {"name": camoufox["name"], "version": camoufox["version"]}
                if camoufox is not None
                else None
            ),
            "browser_binary": "not_bundled",
        },
        **(
            {"embedded_runtime": embedded_runtime}
            if embedded_runtime is not None
            else {}
        ),
    }
    dependency_manifest_path = output_dir / DEPENDENCY_MANIFEST_NAME
    _write_json_atomic(dependency_manifest_path, dependency_manifest)

    with tempfile.TemporaryDirectory(prefix="paper-fetch-staged-sbom-") as temp_dir:
        requirements = Path(temp_dir) / "actual-python-packages.txt"
        requirements.write_text(
            "".join(
                f"{package['name']}=={package['version']}\n"
                for package in python_packages
            ),
            encoding="utf-8",
        )
        temporary_sbom = Path(temp_dir) / SBOM_NAME
        sbom = _generate_cyclonedx(requirements, temporary_sbom, cyclonedx_python)

    _augment_sbom(
        sbom,
        node=node_packages,
        native=native_components,
        embedded_runtime=embedded_runtime,
        setup_components=setup_components,
        python_packages=python_packages,
    )
    _validate_sbom(sbom)
    sbom_path = output_dir / SBOM_NAME
    _write_json_atomic(sbom_path, sbom)

    offline_manifest["dependency_evidence"] = {
        "source": "actual-staged-target",
        "dependency_manifest": DEPENDENCY_MANIFEST_NAME,
        "dependency_manifest_sha256": _sha256(dependency_manifest_path),
        "sbom": SBOM_NAME,
        "sbom_sha256": _sha256(sbom_path),
    }
    _write_json_atomic(offline_manifest_path, offline_manifest)
    return dependency_manifest_path, sbom_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--site-packages", required=True, type=Path)
    parser.add_argument("--offline-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--cyclonedx-python", default=sys.executable)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    generate_evidence(
        staging=args.staging,
        site_packages=args.site_packages,
        offline_manifest_path=args.offline_manifest,
        output_dir=args.output_dir,
        target=args.target,
        cyclonedx_python=args.cyclonedx_python,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
