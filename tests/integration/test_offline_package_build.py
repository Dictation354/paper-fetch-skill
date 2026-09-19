from __future__ import annotations
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "build-offline-package.sh"
BUILD_OFFLINE_PACKAGE_WINDOWS = (
    REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"
)
VERIFY_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "verify-offline-package.sh"


def _shell_function(script: str, name: str, next_name: str) -> str:
    start = script.index(f"{name}()")
    end = script.index(f"{next_name}()", start)
    return script[start:end]


def _copy_posix_builder_fixture(
    root: Path,
    *,
    name_prefix: str = "paper-fetch-test",
) -> Path:
    fixture_repo = root / "fixture-repo"
    scripts_dir = fixture_repo / "scripts"
    installer_dir = fixture_repo / "installer"
    scripts_dir.mkdir(parents=True)
    installer_dir.mkdir()
    shutil.copy2(BUILD_OFFLINE_PACKAGE, scripts_dir / BUILD_OFFLINE_PACKAGE.name)
    (installer_dir / "manifest.json").write_text(
        json.dumps(
            {
                "packages": {
                    "linux_offline_name_prefix": name_prefix,
                    "macos_offline_name_prefix": name_prefix,
                }
            }
        ),
        encoding="utf-8",
    )
    return fixture_repo


class OfflinePackageBuildTests(unittest.TestCase):
    def test_posix_package_name_rejects_path_traversal_before_build_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            protected = root / "protected"
            protected.mkdir()
            sentinel = protected / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            env = os.environ.copy()
            env["PAPER_FETCH_OFFLINE_BUILD_DIR"] = str(root / "build")

            for package_name in ("../protected", "nested/package", "/absolute"):
                with self.subTest(package_name=package_name):
                    result = subprocess.run(
                        [
                            "bash",
                            str(BUILD_OFFLINE_PACKAGE),
                            "--package-name",
                            package_name,
                            "--output-dir",
                            str(root / "dist"),
                        ],
                        cwd=REPO_ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Unsafe package name", result.stderr)
                    self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_posix_build_rejects_repository_as_build_directory_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_repo = _copy_posix_builder_fixture(Path(tmpdir))
            source_dir = fixture_repo / "src"
            source_dir.mkdir()
            sentinel = source_dir / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            env = os.environ.copy()
            env["PAPER_FETCH_OFFLINE_BUILD_DIR"] = str(fixture_repo)
            env["PYTHON_BIN"] = sys.executable

            result = subprocess.run(
                [
                    "bash",
                    str(fixture_repo / "scripts" / BUILD_OFFLINE_PACKAGE.name),
                    "--package-name",
                    "src",
                ],
                cwd=fixture_repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "must not be the repository or one of its ancestors",
                result.stderr,
            )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_posix_build_rejects_nonempty_unowned_staging_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_dir = root / "build"
            staging = build_dir / "safe-package"
            staging.mkdir(parents=True)
            sentinel = staging / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            env = os.environ.copy()
            env["PAPER_FETCH_OFFLINE_BUILD_DIR"] = str(build_dir)
            env["PYTHON_BIN"] = sys.executable

            result = subprocess.run(
                [
                    "bash",
                    str(BUILD_OFFLINE_PACKAGE),
                    "--package-name",
                    "safe-package",
                    "--output-dir",
                    str(root / "dist"),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "without a valid ownership marker",
                result.stderr,
            )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_posix_build_rejects_output_directory_inside_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            build_dir = root / "build"
            output_dir = build_dir / "safe-package" / "dist"
            env = os.environ.copy()
            env["PAPER_FETCH_OFFLINE_BUILD_DIR"] = str(build_dir)
            env["PYTHON_BIN"] = sys.executable

            result = subprocess.run(
                [
                    "bash",
                    str(BUILD_OFFLINE_PACKAGE),
                    "--package-name",
                    "safe-package",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "must not equal or be inside staging",
                result.stderr,
            )
            self.assertFalse(output_dir.exists())

    def test_posix_build_validates_manifest_derived_package_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture_repo = _copy_posix_builder_fixture(
                root,
                name_prefix="../unsafe",
            )
            env = os.environ.copy()
            env["PAPER_FETCH_OFFLINE_BUILD_DIR"] = str(root / "build")
            env["PYTHON_BIN"] = sys.executable

            result = subprocess.run(
                ["bash", str(fixture_repo / "scripts" / BUILD_OFFLINE_PACKAGE.name)],
                cwd=fixture_repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsafe package name", result.stderr)
            self.assertFalse((root / "unsafe").exists())

    def test_posix_checksum_inventory_rejects_payload_symlinks(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        checksums_block = _shell_function(
            script,
            "write_checksums",
            "write_manifest_and_checksums",
        )
        formula_block = _shell_function(
            script,
            "bundle_formula_tools",
            "copy_macos_library_licenses",
        )

        self.assertIn(
            'rm -rf "$formula_tools/node_modules/.bin"',
            formula_block,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for link_kind in ("file", "directory"):
                with self.subTest(link_kind=link_kind):
                    staging = root / link_kind
                    staging.mkdir()
                    target = root / f"{link_kind}-target"
                    if link_kind == "file":
                        target.write_text("outside\n", encoding="utf-8")
                    else:
                        target.mkdir()
                    (staging / "linked-payload").symlink_to(
                        target,
                        target_is_directory=link_kind == "directory",
                    )
                    harness = (
                        f'set -euo pipefail\n{checksums_block}\nwrite_checksums "$1"\n'
                    )

                    result = subprocess.run(
                        [
                            "bash",
                            "-c",
                            harness,
                            "paper-fetch-checksum-test",
                            str(staging),
                        ],
                        env={
                            **os.environ,
                            "PYTHON_BIN": sys.executable,
                            "STAGING_OWNERSHIP_MARKER_NAME": (
                                ".paper-fetch-offline-staging-owner"
                            ),
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(
                        "offline payload symlink is not allowed: './linked-payload'",
                        result.stderr,
                    )
                    self.assertFalse((staging / "sha256sums.txt").exists())

    def test_posix_staging_marker_binds_repo_path_and_package(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        function_blocks = (
            _shell_function(
                script,
                "canonical_path",
                "path_is_same_or_ancestor",
            ),
            _shell_function(
                script,
                "path_is_same_or_ancestor",
                "path_is_strict_descendant",
            ),
            _shell_function(
                script,
                "path_is_strict_descendant",
                "validate_build_directory",
            ),
            _shell_function(
                script,
                "directory_is_empty",
                "staging_marker_value",
            ),
            _shell_function(
                script,
                "staging_marker_value",
                "staging_is_owned",
            ),
            _shell_function(
                script,
                "staging_is_owned",
                "prepare_owned_staging",
            ),
            script[
                script.index("prepare_owned_staging()") : script.index(
                    '\n[ -z "$PACKAGE_NAME" ]',
                    script.index("prepare_owned_staging()"),
                )
            ],
        )
        harness = (
            "set -euo pipefail\n"
            'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
            'PYTHON_BIN="$1"\n'
            'BUILD_DIR="$2"\n'
            'REPO_DIR="$3"\n'
            'STAGING_OWNERSHIP_MARKER_NAME=".paper-fetch-offline-staging-owner"\n'
            'STAGING_OWNERSHIP_MARKER_MAGIC="paper-fetch-offline-staging-v1"\n'
            + "\n".join(function_blocks)
            + '\nprepare_owned_staging "$4" "$5"\n'
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            for field in ("repo", "staging", "package"):
                with self.subTest(field=field):
                    case_root = root / f"wrong-{field}"
                    repo = case_root / "repo"
                    build_dir = case_root / "build"
                    staging = build_dir / "safe-package"
                    repo.mkdir(parents=True)
                    staging.mkdir(parents=True)
                    sentinel = staging / "keep.txt"
                    sentinel.write_text("keep\n", encoding="utf-8")
                    values = {
                        "repo": str(repo),
                        "staging": str(staging),
                        "package": "safe-package",
                    }
                    values[field] += "-wrong"
                    (staging / ".paper-fetch-offline-staging-owner").write_text(
                        "paper-fetch-offline-staging-v1\n"
                        f"repo={values['repo']}\n"
                        f"staging={values['staging']}\n"
                        f"package={values['package']}\n",
                        encoding="utf-8",
                    )

                    result = subprocess.run(
                        [
                            "bash",
                            "-c",
                            harness,
                            "paper-fetch-marker-test",
                            sys.executable,
                            str(build_dir),
                            str(repo),
                            str(staging),
                            "safe-package",
                        ],
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(
                        sentinel.read_text(encoding="utf-8"),
                        "keep\n",
                    )

            valid_root = root / "valid"
            repo = valid_root / "repo"
            build_dir = valid_root / "build"
            staging = build_dir / "safe-package"
            sibling = build_dir / "keep-sibling.txt"
            repo.mkdir(parents=True)
            staging.mkdir(parents=True)
            sibling.write_text("keep\n", encoding="utf-8")
            (staging / "stale.txt").write_text("stale\n", encoding="utf-8")
            (staging / ".paper-fetch-offline-staging-owner").write_text(
                "paper-fetch-offline-staging-v1\n"
                f"repo={repo}\n"
                f"staging={staging}\n"
                "package=safe-package\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    harness,
                    "paper-fetch-marker-test",
                    sys.executable,
                    str(build_dir),
                    str(repo),
                    str(staging),
                    "safe-package",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((staging / "stale.txt").exists())
            self.assertTrue((staging / ".paper-fetch-offline-staging-owner").is_file())
            self.assertEqual(sibling.read_text(encoding="utf-8"), "keep\n")

            symlink_root = root / "symlink"
            repo = symlink_root / "repo"
            build_dir = symlink_root / "build"
            outside = symlink_root / "outside"
            repo.mkdir(parents=True)
            build_dir.mkdir()
            outside.mkdir()
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            staging_link = build_dir / "safe-package"
            staging_link.symlink_to(outside, target_is_directory=True)

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    harness,
                    "paper-fetch-marker-test",
                    sys.executable,
                    str(build_dir),
                    str(repo),
                    str(staging_link),
                    "safe-package",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not be a symbolic link", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_posix_archive_excludes_staging_ownership_marker(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        archive_function = _shell_function(script, "create_archive", "main")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            staging_parent = root / "staging"
            package_root = staging_parent / "safe-package"
            output_dir = root / "output"
            package_root.mkdir(parents=True)
            (package_root / "payload.txt").write_text("payload\n", encoding="utf-8")
            (package_root / ".paper-fetch-offline-staging-owner").write_text(
                "owner\n",
                encoding="utf-8",
            )
            harness = (
                "set -euo pipefail\n"
                "log() { :; }\n"
                'STAGING_OWNERSHIP_MARKER_NAME=".paper-fetch-offline-staging-owner"\n'
                f"{archive_function}\n"
                'create_archive "$1" "safe-package" "$2"\n'
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    harness,
                    "paper-fetch-archive-test",
                    str(staging_parent),
                    str(output_dir),
                ],
                env={**os.environ, "PYTHON_BIN": sys.executable},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            archive_path = output_dir / "safe-package.tar.gz"
            with tarfile.open(archive_path, "r:gz") as archive:
                names = archive.getnames()
            self.assertIn("safe-package/payload.txt", names)
            self.assertNotIn(
                "safe-package/.paper-fetch-offline-staging-owner",
                names,
            )
            self.assertEqual(archive_path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(list(output_dir.iterdir()), [archive_path])

    def test_posix_release_publish_failure_preserves_existing_artifact(
        self,
    ) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        functions = (
            (
                "create_self_extracting_installer",
                "create_archive",
                ".sh",
            ),
            (
                "create_archive",
                "main",
                ".tar.gz",
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            staging_parent = root / "staging"
            package_root = staging_parent / "safe-package"
            fake_bin = root / "fake-bin"
            package_root.mkdir(parents=True)
            fake_bin.mkdir()
            fake_tar = fake_bin / "tar"
            fake_tar.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
output=""
while (($#)); do
  case "$1" in
    -czf)
      shift
      output="$1"
      ;;
  esac
  shift
done
[ -n "$output" ]
printf 'partial artifact\\n' > "$output"
exit 73
""",
                encoding="utf-8",
            )
            fake_tar.chmod(0o755)

            for function_name, next_function_name, extension in functions:
                with self.subTest(function=function_name):
                    output_dir = root / f"output-{function_name}"
                    output_dir.mkdir()
                    output_path = output_dir / f"safe-package{extension}"
                    output_path.write_text("existing artifact\n", encoding="utf-8")
                    function = _shell_function(
                        script,
                        function_name,
                        next_function_name,
                    )
                    harness = (
                        "set -euo pipefail\n"
                        "log() { :; }\n"
                        'STAGING_OWNERSHIP_MARKER_NAME=".owner"\n'
                        f"{function}\n"
                        f'{function_name} "$1" "safe-package" "$2"\n'
                    )
                    result = subprocess.run(
                        [
                            "bash",
                            "-c",
                            harness,
                            "paper-fetch-publish-test",
                            str(staging_parent),
                            str(output_dir),
                        ],
                        env={
                            **os.environ,
                            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                            "PYTHON_BIN": sys.executable,
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(
                        output_path.read_text(encoding="utf-8"),
                        "existing artifact\n",
                    )
                    self.assertEqual(list(output_dir.iterdir()), [output_path])

    def test_posix_release_publish_rejects_directory_destinations(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        functions = (
            (
                "create_self_extracting_installer",
                "create_archive",
                ".sh",
            ),
            (
                "create_archive",
                "main",
                ".tar.gz",
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            staging_parent = root / "staging"
            package_root = staging_parent / "safe-package"
            package_root.mkdir(parents=True)
            (package_root / "payload.txt").write_text("payload\n", encoding="utf-8")

            for function_name, next_function_name, extension in functions:
                function = _shell_function(
                    script,
                    function_name,
                    next_function_name,
                )
                for destination_kind in ("directory", "directory-symlink"):
                    with self.subTest(
                        function=function_name,
                        destination=destination_kind,
                    ):
                        case_root = root / f"{function_name}-{destination_kind}"
                        output_dir = case_root / "output"
                        output_dir.mkdir(parents=True)
                        output_path = output_dir / f"safe-package{extension}"
                        if destination_kind == "directory":
                            destination = output_path
                            destination.mkdir()
                        else:
                            destination = case_root / "destination"
                            destination.mkdir()
                            output_path.symlink_to(
                                destination,
                                target_is_directory=True,
                            )
                        sentinel = destination / "keep.txt"
                        sentinel.write_text("keep\n", encoding="utf-8")
                        harness = (
                            "set -euo pipefail\n"
                            "log() { :; }\n"
                            'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
                            'STAGING_OWNERSHIP_MARKER_NAME=".owner"\n'
                            f"{function}\n"
                            f'{function_name} "$1" "safe-package" "$2"\n'
                        )

                        result = subprocess.run(
                            [
                                "bash",
                                "-c",
                                harness,
                                "paper-fetch-publish-destination-test",
                                str(staging_parent),
                                str(output_dir),
                            ],
                            env={**os.environ, "PYTHON_BIN": sys.executable},
                            text=True,
                            capture_output=True,
                            check=False,
                        )

                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(
                            "output path must not be a directory",
                            result.stderr,
                        )
                        self.assertEqual(
                            sentinel.read_text(encoding="utf-8"),
                            "keep\n",
                        )
                        self.assertEqual(list(output_dir.iterdir()), [output_path])

    def test_macos_binary_checks_do_not_accept_arm64_from_path_text(self) -> None:
        scripts_and_functions = (
            (
                BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8"),
                "verify_macos_arm64_binary",
                "sign_macos_playwright_node",
            ),
            (
                VERIFY_OFFLINE_PACKAGE.read_text(encoding="utf-8"),
                "verify_macos_macho_file",
                "verify_macos_macho_dependencies",
            ),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / "macos-arm64-cp314" / "node"
            candidate.parent.mkdir()
            candidate.write_text("plain text, not a Mach-O binary\n", encoding="utf-8")

            for script, function_name, next_function_name in scripts_and_functions:
                with self.subTest(function=function_name):
                    function = _shell_function(
                        script,
                        function_name,
                        next_function_name,
                    )
                    harness = (
                        "set -euo pipefail\n"
                        'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
                        f"{function}\n"
                        f'{function_name} "$1" "test candidate"\n'
                    )
                    result = subprocess.run(
                        ["bash", "-c", harness, "paper-fetch-test", str(candidate)],
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("not a Mach-O binary", result.stderr)

    def test_macos_dependency_containment_rejects_escape_symlink_and_nonregular(
        self,
    ) -> None:
        script = VERIFY_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        containment_function = _shell_function(
            script,
            "macos_contained_path",
            "macos_rpaths",
        )
        resolver_function = _shell_function(
            script,
            "resolve_macos_macho_dependency",
            "verify_macos_macho_dependencies",
        )
        harness = (
            "set -euo pipefail\n"
            'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
            f"HOST_PYTHON_BIN={shlex.quote(sys.executable)}\n"
            f"{containment_function}\n"
            f"{resolver_function}\n"
            'resolve_macos_macho_dependency "$1" "$2" "$3" "$4" ""\n'
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle = root / "bundle"
            owner = bundle / "bin" / "tool"
            library_dir = bundle / "lib"
            owner.parent.mkdir(parents=True)
            library_dir.mkdir()
            owner.write_bytes(b"tool")
            outside = root / "outside.dylib"
            outside.write_bytes(b"outside")
            symlink = library_dir / "linked.dylib"
            symlink.symlink_to(outside)

            cases = (
                ("@loader_path/../../outside.dylib", "escapes the bundle"),
                (
                    "/System/Library/../../tmp/outside.dylib",
                    "parent-directory traversal",
                ),
                ("@loader_path/../lib/linked.dylib", "symlink is not allowed"),
                ("@loader_path/../lib", "path is not a regular file"),
            )
            for dependency, diagnostic in cases:
                with self.subTest(dependency=dependency):
                    result = subprocess.run(
                        [
                            "bash",
                            "-c",
                            harness,
                            "paper-fetch-test",
                            str(owner),
                            dependency,
                            str(bundle),
                            str(owner.parent),
                        ],
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(diagnostic, result.stderr)

    def test_macos_rpath_parser_rejects_absolute_build_host_path(self) -> None:
        script = VERIFY_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        containment_function = _shell_function(
            script,
            "macos_contained_path",
            "macos_rpaths",
        )
        rpath_function = _shell_function(
            script,
            "macos_rpaths",
            "resolve_macos_macho_dependency",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle = root / "bundle"
            binary = bundle / "bin" / "tool"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"tool")
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            fake_otool = fake_bin / "otool"
            fake_otool.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    cat <<'OUT'
                    Load command 1
                              cmd LC_RPATH
                          cmdsize 48
                             path /opt/build-host/lib (offset 12)
                    OUT
                    """
                ),
                encoding="utf-8",
            )
            fake_otool.chmod(0o755)
            harness = (
                "set -euo pipefail\n"
                'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
                f"HOST_PYTHON_BIN={shlex.quote(sys.executable)}\n"
                f"{containment_function}\n"
                f"{rpath_function}\n"
                'macos_rpaths "$1" "$2" "$3"\n'
            )
            env = {
                **os.environ,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            }

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    harness,
                    "paper-fetch-test",
                    str(binary),
                    str(bundle),
                    str(binary.parent),
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("absolute/build-host LC_RPATH", result.stderr)

    def test_posix_offline_verifier_rejects_malicious_tar_members_before_extraction(
        self,
    ) -> None:
        cases: dict[str, tuple[tuple[str, str, str], ...]] = {
            "absolute": (("file", "/outside.txt", ""),),
            "dot-dot": (("file", "paper-fetch/../../outside.txt", ""),),
            "multiple-top-level": (
                ("file", "paper-fetch/a.txt", ""),
                ("file", "other/b.txt", ""),
            ),
            "fifo": (("fifo", "paper-fetch/pipe", ""),),
            "escaping-symlink": (("symlink", "paper-fetch/link", "../../outside.txt"),),
            "escaping-hardlink": (("hardlink", "paper-fetch/hard", "../outside.txt"),),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for case_name, entries in cases.items():
                with self.subTest(case=case_name):
                    archive_path = root / f"{case_name}.tar.gz"
                    with tarfile.open(archive_path, "w:gz") as archive:
                        for kind, member_name, link_name in entries:
                            member = tarfile.TarInfo(member_name)
                            if kind == "file":
                                content = b"test\n"
                                member.size = len(content)
                                archive.addfile(member, io.BytesIO(content))
                            elif kind == "fifo":
                                member.type = tarfile.FIFOTYPE
                                archive.addfile(member)
                            else:
                                member.type = (
                                    tarfile.SYMTYPE
                                    if kind == "symlink"
                                    else tarfile.LNKTYPE
                                )
                                member.linkname = link_name
                                archive.addfile(member)

                    outside = root / "outside.txt"
                    result = subprocess.run(
                        [
                            "bash",
                            str(VERIFY_OFFLINE_PACKAGE),
                            str(archive_path),
                            "--archive-preflight-only",
                        ],
                        cwd=REPO_ROOT,
                        env={
                            **os.environ,
                            "PAPER_FETCH_OFFLINE_PYTHON_BIN": sys.executable,
                        },
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("unsafe offline archive", result.stderr)
                    self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
