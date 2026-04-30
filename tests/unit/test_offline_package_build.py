from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "build-offline-package.sh"
BUILD_OFFLINE_PACKAGE_WINDOWS = REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"


class OfflinePackageBuildTests(unittest.TestCase):
    def test_default_package_name_uses_detected_python_tag(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")

        self.assertIn('package_name="${PACKAGE_NAME:-paper-fetch-skill-offline-linux-x86_64-$python_tag}"', script)
        self.assertNotIn('PACKAGE_NAME="paper-fetch-skill-offline-linux-x86_64-cp311"', script)

    def test_supported_cpython_tags_are_whitelisted(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        start = script.index("is_supported_python_tag()")
        end = script.index("check_target()", start)
        block = script[start:end]

        for tag in ("cp311", "cp312", "cp313", "cp314"):
            self.assertIn(tag, block)

    def test_manifest_python_tag_is_not_hardcoded(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        start = script.index("write_manifest_and_checksums()")
        end = script.index("create_archive()", start)
        block = script[start:end]

        self.assertIn('"python_tag": python_tag', block)
        self.assertNotIn('"python_tag": "cp311"', block)

    def test_source_snapshot_excludes_tests_directory(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        start = script.index("copy_source_snapshot()")
        end = script.index("build_project_wheelhouse()", start)
        block = script[start:end]

        self.assertIn("--exclude='./tests'", block)

    def test_flaresolverr_wheelhouse_builds_source_only_dependencies(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        start = script.index('log "Bundling FlareSolverr dependency wheelhouse"')
        end = script.index('log "Copying patched FlareSolverr source snapshot"', start)
        block = script[start:end]

        self.assertIn("-m pip wheel", block)
        self.assertIn("--wheel-dir", block)
        self.assertNotIn("--only-binary=:all:", block)

    def test_flaresolverr_bundle_keeps_only_extracted_release_directory(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        start = script.index('mkdir -p "$staging/vendor/flaresolverr/.flaresolverr/$flare_version"')
        end = script.index("write_manifest_and_checksums()", start)
        block = script[start:end]

        self.assertIn('"$flare_downloads/$flare_version/flaresolverr"', block)
        self.assertIn('tar -C "$flare_downloads/$flare_version" -cf - flaresolverr', block)
        self.assertNotIn('tar -C "$flare_downloads/$flare_version" -cf - .', block)
        self.assertNotIn("flaresolverr_linux_x64.tar.gz", block)

    def test_windows_default_package_name_uses_detected_python_tag(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")

        self.assertIn('paper-fetch-skill-offline-windows-x86_64-$pythonTag', script)
        self.assertIn("$Name.zip", script)

    def test_windows_supported_cpython_tags_are_whitelisted(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        start = script.index("function Test-SupportedPythonTag")
        end = script.index("function Assert-Target", start)
        block = script[start:end]

        for tag in ("cp311", "cp312", "cp313", "cp314"):
            self.assertIn(tag, block)

    def test_windows_manifest_target_fields_are_windows_specific(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        start = script.index("target = [ordered]@{")
        end = script.index("entrypoint = ", start)
        block = script[start:end]

        self.assertIn('platform = "windows"', block)
        self.assertIn('arch = "x86_64"', block)
        self.assertIn("python_tag = $PythonTag", block)
        self.assertIn('entrypoint = "install-offline.ps1"', script)

    def test_windows_flaresolverr_bundle_is_built_from_patched_source(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")

        self.assertIn("git clone --depth 1 --branch $flareVersion", script)
        self.assertIn("return-image-payload.patch", script)
        self.assertIn(".\\build_package.py", script)
        self.assertIn("flaresolverr_windows_x64.zip", script)
        self.assertIn("Expand-Archive", script)

    def test_windows_native_command_output_does_not_pollute_return_values(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        start = script.index("function Invoke-Native")
        end = script.index("function Get-PythonTag", start)
        block = script[start:end]

        self.assertIn("| ForEach-Object { Write-Host $_ }", block)
        self.assertIn("$exitCode = $LASTEXITCODE", block)


if __name__ == "__main__":
    unittest.main()
