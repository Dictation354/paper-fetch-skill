from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

from scripts.generate_offline_evidence import generate_evidence


def _install_fake_distribution(site_packages: Path, name: str, version: str) -> None:
    package_name = name.replace("-", "_")
    package = site_packages / package_name
    metadata = site_packages / f"{package_name}-{version}.dist-info"
    package.mkdir(parents=True)
    metadata.mkdir()
    (package / "__init__.py").write_text(
        f"__version__ = {version!r}\n", encoding="utf-8"
    )
    (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    with (metadata / "RECORD").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([f"{package_name}/__init__.py", "", ""])
        writer.writerow([f"{metadata.name}/METADATA", "", ""])
        writer.writerow([f"{metadata.name}/RECORD", "", ""])


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    staging = tmp_path / "staging"
    site_packages = staging / "runtime" / "Lib" / "site-packages"
    _install_fake_distribution(site_packages, "paper-fetch-skill", "5.6.0")
    _install_fake_distribution(site_packages, "camoufox", "0.5.7")

    formula_package = staging / "formula-tools" / "node_modules" / "katex"
    formula_package.mkdir(parents=True)
    (formula_package / "package.json").write_text(
        json.dumps({"name": "katex", "version": "0.18.4"}),
        encoding="utf-8",
    )
    formula_bin = staging / "formula-tools" / "bin"
    formula_bin.mkdir(parents=True)
    (formula_bin / "texmath.exe").write_bytes(b"fake texmath binary")
    playwright_driver = site_packages / "playwright" / "driver"
    playwright_driver.mkdir(parents=True)
    (playwright_driver / "package.json").write_text(
        json.dumps({"name": "playwright-core", "version": "1.58.0"}),
        encoding="utf-8",
    )
    (playwright_driver / "node.exe").write_bytes(b"fake playwright node")
    (staging / "runtime" / "python.exe").write_bytes(b"fake embedded python")

    expected = "a" * 64
    offline_manifest = staging / "offline-manifest.json"
    offline_manifest.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "target": {
                    "platform": "windows",
                    "arch": "x86_64",
                    "python_tag": "cp313",
                    "embedded_runtime": {
                        "implementation": "CPython",
                        "version": "3.13.13",
                        "architecture": "x86_64",
                        "archive": "python-3.13.13-embed-amd64.zip",
                        "url": "https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip",
                        "expected_sha256": expected,
                        "actual_sha256": expected,
                    },
                },
                "setup_components": {
                    "windows_uninsis_i386": {
                        "name": "UninsIS.dll",
                        "version": "1.7.0",
                        "architecture": "i386",
                        "archive": "UninsIS-1.7.0.zip",
                        "archive_url": (
                            "https://github.com/Bill-Stewart/UninsIS/releases/"
                            "download/v1.7.0/UninsIS-1.7.0.zip"
                        ),
                        "archive_sha256": "b" * 64,
                        "expected_sha256": "c" * 64,
                        "actual_sha256": "c" * 64,
                        "license": "LGPL-3.0-or-later",
                        "license_expected_sha256": "d" * 64,
                        "license_actual_sha256": "d" * 64,
                        "usage": "setup-time-uninstall-synchronization",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return staging, site_packages, offline_manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_evidence_is_derived_from_actual_staged_target(tmp_path: Path) -> None:
    staging, site_packages, offline_manifest = _fixture(tmp_path)

    dependency_path, sbom_path = generate_evidence(
        staging=staging,
        site_packages=site_packages,
        offline_manifest_path=offline_manifest,
        output_dir=staging,
        target="windows-x86_64-cp313",
        cyclonedx_python=sys.executable,
    )

    dependency = json.loads(dependency_path.read_text(encoding="utf-8"))
    assert dependency["source"] == "actual-staged-target"
    assert dependency["target"] == "windows-x86_64-cp313"
    assert {
        (item["name"], item["version"]) for item in dependency["python_packages"]
    } == {
        ("camoufox", "0.5.7"),
        ("paper-fetch-skill", "5.6.0"),
    }
    assert {item["name"] for item in dependency["node_packages"]} == {
        "katex",
        "playwright-core",
    }
    assert {item["name"] for item in dependency["native_components"]} == {
        "playwright-driver-node",
        "texmath.exe",
    }
    assert dependency["browser"] == {
        "camoufox_python_package": {"name": "camoufox", "version": "0.5.7"},
        "browser_binary": "not_bundled",
    }
    assert dependency["embedded_runtime"]["actual_sha256"] == "a" * 64
    assert dependency["embedded_runtime"]["runtime_executable_sha256"] == _sha256(
        staging / "runtime" / "python.exe"
    )
    assert dependency["setup_components"] == [
        {
            "id": "windows_uninsis_i386",
            "name": "UninsIS.dll",
            "version": "1.7.0",
            "architecture": "i386",
            "archive": "UninsIS-1.7.0.zip",
            "archive_url": (
                "https://github.com/Bill-Stewart/UninsIS/releases/"
                "download/v1.7.0/UninsIS-1.7.0.zip"
            ),
            "archive_sha256": "b" * 64,
            "expected_sha256": "c" * 64,
            "actual_sha256": "c" * 64,
            "license": "LGPL-3.0-or-later",
            "license_expected_sha256": "d" * 64,
            "license_actual_sha256": "d" * 64,
            "usage": "setup-time-uninstall-synchronization",
        }
    ]

    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    assert sbom["specVersion"] == "1.6"
    component_names = {component["name"] for component in sbom["components"]}
    assert {
        "camoufox",
        "paper-fetch-skill",
        "katex",
        "playwright-core",
        "playwright-driver-node",
        "texmath.exe",
        "CPython embedded runtime",
        "UninsIS.dll",
    } <= component_names
    runtime_component = next(
        component
        for component in sbom["components"]
        if component["name"] == "CPython embedded runtime"
    )
    runtime_properties = {
        item["name"]: item["value"] for item in runtime_component["properties"]
    }
    assert runtime_component["version"] == "3.13.13"
    assert runtime_component["externalReferences"] == [
        {
            "type": "distribution",
            "url": "https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip",
        }
    ]
    assert runtime_properties["paper-fetch:expected-archive-sha256"] == "a" * 64
    assert runtime_properties["paper-fetch:actual-archive-sha256"] == "a" * 64
    uninsis_component = next(
        component
        for component in sbom["components"]
        if component["name"] == "UninsIS.dll"
    )
    uninsis_properties = {
        item["name"]: item["value"] for item in uninsis_component["properties"]
    }
    assert uninsis_component["version"] == "1.7.0"
    assert uninsis_component["hashes"] == [
        {"alg": "SHA-256", "content": "c" * 64}
    ]
    assert uninsis_component["licenses"] == [
        {"expression": "LGPL-3.0-or-later"}
    ]
    assert uninsis_properties["paper-fetch:component-category"] == "setup-time"
    assert uninsis_properties["paper-fetch:archive-sha256"] == "b" * 64

    updated = json.loads(offline_manifest.read_text(encoding="utf-8"))
    assert updated["dependency_evidence"] == {
        "source": "actual-staged-target",
        "dependency_manifest": "dependency-manifest.json",
        "dependency_manifest_sha256": _sha256(dependency_path),
        "sbom": "paper-fetch-sbom.cdx.json",
        "sbom_sha256": _sha256(sbom_path),
    }


def test_embedded_runtime_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    staging, site_packages, offline_manifest = _fixture(tmp_path)
    payload = json.loads(offline_manifest.read_text(encoding="utf-8"))
    payload["target"]["embedded_runtime"]["actual_sha256"] = "b" * 64
    offline_manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError, match="embedded runtime expected and actual SHA-256 must match"
    ):
        generate_evidence(
            staging=staging,
            site_packages=site_packages,
            offline_manifest_path=offline_manifest,
            output_dir=staging,
            target="windows-x86_64-cp313",
            cyclonedx_python=sys.executable,
        )
    assert not (staging / "dependency-manifest.json").exists()
    assert not (staging / "paper-fetch-sbom.cdx.json").exists()


def test_setup_component_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    staging, site_packages, offline_manifest = _fixture(tmp_path)
    payload = json.loads(offline_manifest.read_text(encoding="utf-8"))
    payload["setup_components"]["windows_uninsis_i386"]["actual_sha256"] = (
        "e" * 64
    )
    offline_manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="setup component windows_uninsis_i386 expected and actual SHA-256",
    ):
        generate_evidence(
            staging=staging,
            site_packages=site_packages,
            offline_manifest_path=offline_manifest,
            output_dir=staging,
            target="windows-x86_64-cp313",
            cyclonedx_python=sys.executable,
        )

    assert not (staging / "dependency-manifest.json").exists()
    assert not (staging / "paper-fetch-sbom.cdx.json").exists()


def test_python_inventory_hashes_distribution_data_outside_site_packages(
    tmp_path: Path,
) -> None:
    staging, site_packages, offline_manifest = _fixture(tmp_path)
    shared = staging / "share" / "paper-fetch" / "installed.txt"
    shared.parent.mkdir(parents=True)
    shared.write_text("first", encoding="utf-8")
    record = site_packages / "paper_fetch_skill-5.6.0.dist-info" / "RECORD"
    with record.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(
            ["../../../share/paper-fetch/installed.txt", "", ""]
        )

    dependency_path, _ = generate_evidence(
        staging=staging,
        site_packages=site_packages,
        offline_manifest_path=offline_manifest,
        output_dir=staging,
        target="windows-x86_64-cp313",
        cyclonedx_python=sys.executable,
    )
    first = json.loads(dependency_path.read_text(encoding="utf-8"))
    first_package = next(
        item for item in first["python_packages"] if item["name"] == "paper-fetch-skill"
    )

    shared.write_text("second", encoding="utf-8")
    generate_evidence(
        staging=staging,
        site_packages=site_packages,
        offline_manifest_path=offline_manifest,
        output_dir=staging,
        target="windows-x86_64-cp313",
        cyclonedx_python=sys.executable,
    )
    second = json.loads(dependency_path.read_text(encoding="utf-8"))
    second_package = next(
        item
        for item in second["python_packages"]
        if item["name"] == "paper-fetch-skill"
    )

    assert first_package["file_count"] == second_package["file_count"]
    assert first_package["content_sha256"] != second_package["content_sha256"]


def test_evidence_rejects_symlinked_python_distribution_file(tmp_path: Path) -> None:
    staging, site_packages, offline_manifest = _fixture(tmp_path)
    package_file = site_packages / "paper_fetch_skill" / "__init__.py"
    package_file.unlink()
    outside = tmp_path / "outside-python.py"
    outside.write_text("secret = True\n", encoding="utf-8")
    package_file.symlink_to(outside)

    with pytest.raises(ValueError, match="Python distribution contains symlink"):
        generate_evidence(
            staging=staging,
            site_packages=site_packages,
            offline_manifest_path=offline_manifest,
            output_dir=staging,
            target="windows-x86_64-cp313",
            cyclonedx_python=sys.executable,
        )

    assert not (staging / "dependency-manifest.json").exists()
    assert not (staging / "paper-fetch-sbom.cdx.json").exists()


def test_evidence_rejects_symlinked_native_payload(tmp_path: Path) -> None:
    staging, site_packages, offline_manifest = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    (staging / "formula-tools" / "bin" / "linked").symlink_to(outside)

    with pytest.raises(ValueError, match="rejects symlink"):
        generate_evidence(
            staging=staging,
            site_packages=site_packages,
            offline_manifest_path=offline_manifest,
            output_dir=staging,
            target="windows-x86_64-cp313",
            cyclonedx_python=sys.executable,
        )
