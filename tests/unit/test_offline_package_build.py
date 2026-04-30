from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "build-offline-package.sh"


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


if __name__ == "__main__":
    unittest.main()
