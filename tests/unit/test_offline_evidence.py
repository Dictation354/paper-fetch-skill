from __future__ import annotations
import csv
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

    formula_package = staging / "formula-tools" / "node_modules" / "mathml-to-latex"
    formula_package.mkdir(parents=True)
    (formula_package / "package.json").write_text(
        json.dumps({"name": "mathml-to-latex", "version": "1.8.0"}),
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
    payload["setup_components"]["windows_uninsis_i386"]["actual_sha256"] = "e" * 64
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
