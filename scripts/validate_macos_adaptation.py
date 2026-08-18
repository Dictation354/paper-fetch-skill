from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "macos-adaptation-contract.toml"

CHANGE_ID_RE = re.compile(r"^MAC-V4-\d{3}$")
AUDIT_ID_RE = re.compile(r"\bMAC-AUD-\d{3}\b")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
FULL_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
PINNED_ACTION_USE_RE = re.compile(
    r"^(?P<indent>\s*)(?:-\s+)?uses:\s*"
    r"(?P<action>[^@\s]+)@(?P<sha>[^\s#]+)"
    r"(?:\s+#\s*(?P<version>\S+))?\s*$"
)

EXPECTED_CHANGE_IDS = {f"MAC-V4-{index:03d}" for index in range(1, 10)}
EXPECTED_AUDIT_IDS = {f"MAC-AUD-{index:03d}" for index in range(1, 14)}
EXPECTED_PYTHON_VERSIONS = ["3.11", "3.12", "3.13", "3.14"]
EXPECTED_PYTHON_TAGS = ["cp311", "cp312", "cp313", "cp314"]
EXPECTED_BASELINE_REVISION = "fc3bd96e8d781667a2e86e90dc6e8e35a8a26fa7"
EXPECTED_CONTRACT_VERSION = "4.1.0"
EXPECTED_CAMOUFOX_SPECIFIER = ">=0.5.4,<0.6"
EXPECTED_FORMULA_SETUP_ACTION = "haskell-actions/setup"
EXPECTED_FORMULA_SETUP_VERSION = "v2.12.0"
EXPECTED_FORMULA_SETUP_SHA = "6037f33647c3f17758a2356c80fc4a53d7e0685d"
EXPECTED_FORMULA_GHC_VERSION = "9.10.3"
EXPECTED_FORMULA_CABAL_VERSION = "3.12.1.0"
EXPECTED_FORMULA_WORKFLOW_USES = {
    ".github/workflows/ci.yml": 1,
    ".github/workflows/offline.yml": 2,
}
EXPECTED_FORMULA_NODE_DEPENDENCIES = {
    "katex": "0.18.4",
    "mathml-to-latex": "1.8.0",
}
EXPECTED_FORMULA_PACKAGE_MANIFESTS = [
    "package.json",
    "src/paper_fetch/resources/formula/package.json",
]
EXPECTED_FORMULA_PACKAGE_LOCKS = [
    "package-lock.json",
    "src/paper_fetch/resources/formula/package-lock.json",
]
EXPECTED_RELEASE_ATTESTATION_ACTION = "actions/attest-build-provenance"
EXPECTED_RELEASE_ATTESTATION_VERSION = "v4.2.2"
EXPECTED_RELEASE_ATTESTATION_SHA = "4d101475d8b20a2381f78447822ac1eab6504dd8"
EXPECTED_RELEASE_ATTESTATION_USES = 1
EXPECTED_RELEASE_ATTESTATION_SUBJECT_PATH = "release-assets/**/*"
EXPECTED_POSIX_TOOLING_PATHS = [
    "scripts/build-offline-package.sh",
    "install-offline.sh",
    "scripts/verify-offline-package.sh",
]
EXPECTED_WINDOWS_TOOLING_PATHS = ["scripts/build-offline-package-windows.ps1"]

ALLOWED_RISKS = {"P0", "P1", "P2"}
ALLOWED_STATUSES = {"implemented"}
ALLOWED_PORTABLE_VALIDATION = {"static", "simulated", "static_and_simulated"}


def _camoufox_version_is_supported(value: str) -> bool:
    try:
        version = Version(value)
    except InvalidVersion:
        return False
    return version in Requirement(f"camoufox{EXPECTED_CAMOUFOX_SPECIFIER}").specifier


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "contract_id",
    "contract_version",
    "platform",
    "change_document",
    "audit_document",
    "source_baseline",
    "support",
    "build_safety",
    "install_safety",
    "components",
    "native_verifier",
    "shell",
    "native_gate",
    "portable_ci",
    "release_tooling",
    "development_surfaces",
    "changes",
}
REQUIRED_OFFLINE_SUPPORT = {
    "status",
    "minimum_os_version",
    "architectures",
    "python_implementation",
    "python_versions",
    "python_tags",
    "offline_asset_pattern",
    "ci_runner",
    "requires_admin",
    "workflow",
}
REQUIRED_ONLINE_SUPPORT = {"python_spec", "formula_tools_location"}
REQUIRED_BUILD_SAFETY = {
    "python_abi",
    "python_architecture",
    "package_name_policy",
    "build_directory_policy",
    "staging_ownership_marker",
    "output_directory_policy",
    "release_output_policy",
    "tooling_revision_policy",
}
REQUIRED_INSTALL_SAFETY = {
    "quarantine_scan",
    "quarantine_error_policy",
    "payload_inventory_policy",
    "host_python_isolation",
    "install_target_policy",
    "ownership_manifest_schema",
    "ownership_runtime_marker",
    "purge_symlink_policy",
    "purge_path_policy",
    "upgrade_preserves",
    "uninstall_removes_managed_user_config",
}
REQUIRED_NATIVE_VERIFIER = {
    "entrypoint",
    "archive_extraction",
    "macho_dependency_policy",
    "reject_absolute_lc_rpath",
    "quarantine_before_native_execution",
    "node_dependency_check",
    "node_launch_check",
    "covers_recursive_quarantine",
    "covers_zsh_symlink",
    "covers_user_config",
}
REQUIRED_PORTABLE_CI = {
    "workflow",
    "job",
    "runners",
    "linux_entrypoint",
    "windows_entrypoint",
    "native_equivalent",
}
REQUIRED_RELEASE_TOOLING = {
    "workflow",
    "trusted_ref_format",
    "source_tag_immutable",
    "adapted_release_requires_version_bump",
    "adapted_release_requires_new_tag",
    "source_contract_required_before_overlay",
    "legacy_source_without_contract",
    "overlay_copy_destinations_exclude_python_source",
    "manifest_records_tooling_revision",
    "trusted_posix_overlay_paths",
    "trusted_windows_overlay_paths",
}
REQUIRED_CHANGE_FIELDS = {
    "id",
    "title",
    "area",
    "status",
    "risk",
    "summary",
    "rationale",
    "implementation_paths",
    "test_nodes",
    "audit_cases",
    "portable_validation",
    "native_validation_required",
}

WINDOWS_STATIC_TEST_FILES = {
    "tests/unit/test_camoufox_backend.py",
    "tests/unit/test_camoufox_preparation.py",
    "tests/unit/test_ci_release_workflow.py",
    "tests/unit/test_formula_package_sync.py",
    "tests/unit/test_macos_adaptation_validator.py",
    "tests/unit/test_offline_package_build.py",
}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_nodes_for_surface(
    contract: dict[str, Any],
    surface: str,
) -> list[str]:
    seen: set[str] = set()
    all_nodes: list[str] = []
    for change in contract.get("changes", []):
        if not isinstance(change, dict):
            continue
        for node_id in change.get("test_nodes", []):
            if isinstance(node_id, str) and node_id not in seen:
                seen.add(node_id)
                all_nodes.append(node_id)

    surfaces = contract.get("development_surfaces", {})
    config = surfaces.get(surface, {}) if isinstance(surfaces, dict) else {}
    if not isinstance(config, dict):
        return []
    if config.get("selection") == "explicit":
        included = config.get("included_test_nodes", [])
        return [node_id for node_id in included if isinstance(node_id, str)]
    excluded = {
        node_id
        for node_id in config.get("excluded_test_nodes", [])
        if isinstance(node_id, str)
    }
    return [node_id for node_id in all_nodes if node_id not in excluded]


def _repo_path(
    value: object,
    *,
    field: str,
    repo_root: Path,
    errors: list[str],
) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty repository-relative path")
        return None
    relative = Path(value)
    if relative.is_absolute():
        errors.append(f"{field} must be repository-relative: {value}")
        return None
    candidate = (repo_root / relative).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError:
        errors.append(f"{field} escapes the repository: {value}")
        return None
    return candidate


def _read_repo_file(
    relative_path: str,
    *,
    repo_root: Path,
    errors: list[str],
) -> str:
    path = _repo_path(
        relative_path,
        field=relative_path,
        repo_root=repo_root,
        errors=errors,
    )
    if path is None:
        return ""
    if not path.is_file():
        errors.append(f"required repository file does not exist: {relative_path}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read required repository file {relative_path}: {exc}")
        return ""


def _test_node_exists(path: Path, selectors: list[str]) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return False

    if len(selectors) == 1:
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == selectors[0]
            for node in tree.body
        )
    if len(selectors) != 2:
        return False

    class_name, test_name = selectors
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        return any(
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name == test_name
            for child in node.body
        )
    return False


def _validate_required_keys(
    table: object,
    *,
    required: set[str],
    field: str,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(table, dict):
        errors.append(f"{field} must be a TOML table")
        return {}
    missing = sorted(required - set(table))
    if missing:
        errors.append(f"{field} is missing required keys: {', '.join(missing)}")
    return table


def _validate_unique_strings(
    value: object,
    *,
    field: str,
    allow_empty: bool,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "" if allow_empty else " non-empty"
        errors.append(f"{field} must be a{qualifier} list")
        return []
    if any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{field} must contain only non-empty strings")
        return []
    result = list(value)
    if len(result) != len(set(result)):
        errors.append(f"{field} must not contain duplicates")
    return result


def _require_fragments(
    text: str,
    expectations: tuple[tuple[str, str], ...],
    *,
    errors: list[str],
) -> None:
    for fragment, label in expectations:
        if fragment not in text:
            errors.append(f"{label} drifted from contract; missing `{fragment}`")


def _require_order(
    text: str,
    earlier: str,
    later: str,
    *,
    label: str,
    errors: list[str],
) -> None:
    earlier_index = text.find(earlier)
    later_index = text.find(later)
    if earlier_index < 0 or later_index < 0 or earlier_index >= later_index:
        errors.append(
            f"{label} drifted from contract; expected `{earlier}` before `{later}`"
        )


def _validate_source_baseline(
    contract: dict[str, Any],
    *,
    errors: list[str],
) -> None:
    baseline = _validate_required_keys(
        contract.get("source_baseline"),
        required={"repository", "revision", "version"},
        field="source_baseline",
        errors=errors,
    )
    if not baseline:
        return
    if baseline.get("repository") != (
        "https://github.com/Dictation354/paper-fetch-skill"
    ):
        errors.append("source_baseline.repository must identify Dictation354 upstream")
    revision = baseline.get("revision")
    if not isinstance(revision, str) or FULL_REVISION_RE.fullmatch(revision) is None:
        errors.append("source_baseline.revision must be a full 40-character git hash")
    elif revision != EXPECTED_BASELINE_REVISION:
        errors.append(
            "source_baseline.revision must remain the audited v4.1.0 baseline "
            f"{EXPECTED_BASELINE_REVISION}"
        )
    if baseline.get("version") != EXPECTED_CONTRACT_VERSION:
        errors.append(f"source_baseline.version must be {EXPECTED_CONTRACT_VERSION}")


def _validate_support_values(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    support = _validate_required_keys(
        contract.get("support"),
        required={"offline", "online"},
        field="support",
        errors=errors,
    )
    offline = _validate_required_keys(
        support.get("offline"),
        required=REQUIRED_OFFLINE_SUPPORT,
        field="support.offline",
        errors=errors,
    )
    online = _validate_required_keys(
        support.get("online"),
        required=REQUIRED_ONLINE_SUPPORT,
        field="support.online",
        errors=errors,
    )
    if not offline or not online:
        return

    expected_values = {
        "status": "supported",
        "minimum_os_version": "15.0",
        "architectures": ["arm64"],
        "python_implementation": "CPython",
        "python_versions": EXPECTED_PYTHON_VERSIONS,
        "python_tags": EXPECTED_PYTHON_TAGS,
        "offline_asset_pattern": (
            "paper-fetch-skill-offline-macos-arm64-{python_tag}.tar.gz"
        ),
        "ci_runner": "macos-15",
        "requires_admin": False,
        "workflow": ".github/workflows/offline.yml",
    }
    for key, expected in expected_values.items():
        if offline.get(key) != expected:
            errors.append(
                f"support.offline.{key} must be {expected!r}; got {offline.get(key)!r}"
            )
    if online.get("python_spec") != ">=3.11":
        errors.append("support.online.python_spec must be >=3.11")
    if online.get("formula_tools_location") != "platformdirs_user_data":
        errors.append(
            "support.online.formula_tools_location must be platformdirs_user_data"
        )

    pyproject_path = repo_root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"cannot load pyproject.toml: {exc}")
        return
    project = pyproject.get("project", {})
    project_version = project.get("version")
    baseline_version = contract.get("source_baseline", {}).get("version")
    try:
        parsed_project_version = Version(str(project_version))
        parsed_baseline_version = Version(str(baseline_version))
    except InvalidVersion:
        errors.append(
            "project.version and source_baseline.version must be valid versions"
        )
    else:
        if parsed_project_version <= parsed_baseline_version:
            errors.append(
                "project.version must be greater than source_baseline.version "
                "for an adapted release"
            )
    if project.get("requires-python") != online.get("python_spec"):
        errors.append("support.online.python_spec drifted from pyproject.toml")


def _validate_safety_values(
    contract: dict[str, Any],
    *,
    errors: list[str],
) -> None:
    build_safety = _validate_required_keys(
        contract.get("build_safety"),
        required=REQUIRED_BUILD_SAFETY,
        field="build_safety",
        errors=errors,
    )
    expected_build = {
        "python_abi": "standard-gil-cpython",
        "python_architecture": "must-match-target",
        "package_name_policy": "single-safe-path-component",
        "build_directory_policy": "canonical-safe-root",
        "staging_ownership_marker": ".paper-fetch-offline-staging-owner",
        "output_directory_policy": "outside-staging",
        "release_output_policy": "same-filesystem-atomic-rename",
        "tooling_revision_policy": "optional-full-commit-sha",
    }
    for key, expected in expected_build.items():
        if build_safety.get(key) != expected:
            errors.append(f"build_safety.{key} must be {expected!r}")

    install_safety = _validate_required_keys(
        contract.get("install_safety"),
        required=REQUIRED_INSTALL_SAFETY,
        field="install_safety",
        errors=errors,
    )
    expected_install = {
        "quarantine_scan": "recursive-bundle",
        "quarantine_error_policy": "fail-closed",
        "payload_inventory_policy": "exact-checksummed-regular-files-no-symlinks",
        "host_python_isolation": "all-direct-invocations",
        "install_target_policy": "missing-empty-or-owned",
        "ownership_manifest_schema": 3,
        "ownership_runtime_marker": "runtime/python-bin",
        "purge_symlink_policy": "reject",
        "purge_path_policy": "validated-normalized-path",
        "upgrade_preserves": [
            "offline.env",
            "user-config-unmanaged-content",
        ],
        "uninstall_removes_managed_user_config": True,
    }
    for key, expected in expected_install.items():
        if install_safety.get(key) != expected:
            errors.append(f"install_safety.{key} must be {expected!r}")

    native_verifier = _validate_required_keys(
        contract.get("native_verifier"),
        required=REQUIRED_NATIVE_VERIFIER,
        field="native_verifier",
        errors=errors,
    )
    expected_verifier = {
        "entrypoint": "scripts/verify-offline-package.sh",
        "archive_extraction": "tarfile-data-filter",
        "macho_dependency_policy": "canonical-bundle-closure",
        "reject_absolute_lc_rpath": True,
        "quarantine_before_native_execution": True,
        "node_dependency_check": "otool -L",
        "node_launch_check": "--version",
        "covers_recursive_quarantine": True,
        "covers_zsh_symlink": True,
        "covers_user_config": True,
    }
    for key, expected in expected_verifier.items():
        if native_verifier.get(key) != expected:
            errors.append(f"native_verifier.{key} must be {expected!r}")


def _validate_native_packaging(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    build_script = _read_repo_file(
        "scripts/build-offline-package.sh",
        repo_root=repo_root,
        errors=errors,
    )
    installer = _read_repo_file(
        "install-offline.sh",
        repo_root=repo_root,
        errors=errors,
    )
    camoufox_manager = _read_repo_file(
        "src/paper_fetch/providers/browser_runtime/camoufox_manager.py",
        repo_root=repo_root,
        errors=errors,
    )
    verifier = _read_repo_file(
        "scripts/verify-offline-package.sh",
        repo_root=repo_root,
        errors=errors,
    )
    config_source = _read_repo_file(
        "src/paper_fetch/config.py",
        repo_root=repo_root,
        errors=errors,
    )
    ci_workflow = _read_repo_file(
        ".github/workflows/ci.yml",
        repo_root=repo_root,
        errors=errors,
    )
    native_camoufox_test = _read_repo_file(
        "tests/integration/test_camoufox_native_macos.py",
        repo_root=repo_root,
        errors=errors,
    )

    _require_fragments(
        build_script,
        (
            ('MACOS_MINIMUM_OS_VERSION="15.0"', "build minimum macOS version"),
            ("macos:arm64)", "build Apple Silicon target"),
            (
                'export MACOSX_DEPLOYMENT_TARGET="$target_minimum_os_version"',
                "build deployment target export",
            ),
            ('"minimum_os_version": minimum_os_version', "manifest minimum OS"),
            ("stage_macos_formula_library", "Mach-O library staging"),
            ("bundle_macos_formula_libraries", "Mach-O formula bundle"),
            ('otool -L "$target"', "Mach-O dependency inspection"),
            (
                'install_name_tool -id "@rpath/$name"',
                "Mach-O dylib identity relocation",
            ),
            (
                'install_name_tool -change "$child" "@loader_path/$child_name"',
                "Mach-O child dependency relocation",
            ),
            (
                '"@loader_path/../lib/$name"',
                "texmath relative dylib relocation",
            ),
            (
                "codesign --force --sign - --timestamp=none",
                "ad-hoc Mach-O signing",
            ),
            (
                'if sys.abiflags or sysconfig.get_config_var("Py_GIL_DISABLED")',
                "build standard-GIL ABI guard",
            ),
            (
                'if not soabi.startswith(f"{expected_soabi}-")',
                "build standard CPython SOABI guard",
            ),
            ("detect_python_arch", "build interpreter architecture probe"),
            (
                '[ "$python_arch" = "$arch" ]',
                "build interpreter architecture match",
            ),
            (
                "*[!A-Za-z0-9._-]*)",
                "build package-name safe component policy",
            ),
            ("validate_package_name", "build package-name validation"),
            ("validate_build_directory", "build directory safety guard"),
            ("prepare_owned_staging", "owned staging preparation"),
            (
                "offline payload symlink is not allowed",
                "build payload symlink rejection",
            ),
            (
                'rm -rf "$formula_tools/node_modules/.bin"',
                "unused npm launcher symlink pruning",
            ),
            (
                "locked_camoufox_version",
                "build Camoufox lockfile version resolution",
            ),
            (
                "Camoufox dependency wheel must be exactly",
                "build Camoufox wheel metadata verification",
            ),
            (
                "Installed Camoufox runtime must be exactly",
                "build installed Camoufox version verification",
            ),
            (
                '"python_package_version": camoufox_version',
                "offline manifest Camoufox version evidence",
            ),
            (
                'STAGING_OWNERSHIP_MARKER_NAME=".paper-fetch-offline-staging-owner"',
                "staging ownership marker",
            ),
            (
                "PAPER_FETCH_OFFLINE_TOOLING_REVISION",
                "trusted tooling revision provenance",
            ),
            (
                '"tooling_revision": tooling_revision',
                "offline manifest tooling revision",
            ),
            (
                "Offline output directory must not equal or be inside staging",
                "build output/staging containment",
            ),
            ("mktemp", "atomic release temporary output"),
            (
                "os.replace(sys.argv[1], sys.argv[2])",
                "atomic release publish",
            ),
        ),
        errors=errors,
    )
    _require_fragments(
        camoufox_manager,
        (
            (
                "pkgman.camoufox_path(download_if_missing=False)",
                "Camoufox managed runtime no-download guard",
            ),
            (
                'launch_kwargs["executable_path"] = executable_path',
                "Camoufox explicit executable override",
            ),
            (
                "if executable_path is not None:",
                "Camoufox package-managed runtime selection",
            ),
        ),
        errors=errors,
    )
    if "pkgman.launch_path(" in camoufox_manager:
        errors.append(
            "Camoufox managed runtime must not be converted to a custom executable path"
        )
    _require_fragments(
        ci_workflow,
        (
            (
                "uv run python -m camoufox fetch official/152.0.4-beta.28",
                "pinned native Camoufox runtime preparation",
            ),
            (
                'PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST: "1"',
                "native Camoufox test opt-in",
            ),
            (
                "tests/integration/test_camoufox_native_macos.py -q -n 0",
                "serial native Camoufox bundle test",
            ),
        ),
        errors=errors,
    )
    _require_fragments(
        native_camoufox_test,
        (
            (
                'Path.home() / "Library" / "Caches" / "camoufox"',
                "fixed native Camoufox managed cache",
            ),
            (
                "assert compat_flag.is_file()",
                "Camoufox cache ownership marker guard",
            ),
            (
                "active_path.is_relative_to(browsers_dir.resolve(strict=True))",
                "Camoufox active browser containment guard",
            ),
            (
                "exclude_addons=list(DefaultAddons)",
                "Camoufox native test default-addon exclusion",
            ),
            (
                "Screen(max_width=1920, max_height=1080)",
                "Camoufox native test synthetic screen constraint",
            ),
            (
                'camoufox_addons,\n        "download_and_extract",',
                "Camoufox native test addon-download tripwire",
            ),
            ("@pytest.mark.browser", "native browser test marker"),
        ),
        errors=errors,
    )
    if "PAPER_FETCH_NATIVE_CAMOUFOX_INSTALL_DIR" in native_camoufox_test:
        errors.append("native Camoufox test must not accept an arbitrary install root")
    _require_order(
        build_script,
        '  rm -rf "$formula_tools/node_modules/.bin"\n',
        "  write_manifest_and_checksums \\\n",
        label="npm launcher symlink pruning before payload inventory",
        errors=errors,
    )
    _require_order(
        build_script,
        '  validate_package_name "$package_name"\n',
        '  staging="$(prepare_owned_staging',
        label="resolved package-name validation before staging cleanup",
        errors=errors,
    )
    _require_order(
        build_script,
        '  validate_build_directory "$BUILD_DIR"\n',
        '  staging="$(prepare_owned_staging',
        label="build-directory validation before staging cleanup",
        errors=errors,
    )
    _require_fragments(
        installer,
        (
            ("macos:arm64)", "installer Apple Silicon guard"),
            (
                "offline_manifest_value target.minimum_os_version",
                "installer manifest minimum OS",
            ),
            ("sw_vers -productVersion", "installer native OS version check"),
            ("check_macos_quarantine", "installer quarantine preflight"),
            ("com.apple.quarantine", "installer quarantine attribute"),
            ("xattr -r -s -v", "installer recursive quarantine scan"),
            (
                "grep -E -q ': com\\.apple\\.quarantine$' <<< \"$quarantine_output\"",
                "installer pipefail-safe quarantine match",
            ),
            (
                "Could not recursively inspect macOS quarantine attributes",
                "installer fail-closed quarantine diagnostics",
            ),
            ("check_install_target", "installer owned install target guard"),
            (
                "Validating bundled payload inventory",
                "installer exact payload inventory preflight",
            ),
            (
                "unsafe offline checksum inventory",
                "installer payload inventory fail-closed diagnostic",
            ),
            (
                "unlisted payload file(s)",
                "installer unlisted payload rejection",
            ),
            ("install_manifest_is_owned", "installer ownership manifest guard"),
            (
                'manifest.get("schema_version") == 3',
                "installer ownership manifest schema",
            ),
            (
                "runtime/python-bin",
                "installer ownership runtime marker",
            ),
            (
                '[ "$interpreter_arch" = "$HOST_ARCH" ]',
                "installer interpreter architecture match",
            ),
            (
                '[ "$abi_flags" = "-" ] && [ "$gil_disabled" = "0" ]',
                "installer standard-GIL ABI guard",
            ),
            ("check_purge_target", "installer safe purge guard"),
            (
                '[ ! -L "$lexical_install_root" ]',
                "installer purge symlink rejection",
            ),
            (
                'PURGE_INSTALL_ROOT="$lexical_install_root"',
                "installer validated normalized purge target",
            ),
            (
                'rm -rf -- "$PURGE_INSTALL_ROOT"',
                "installer normalized purge deletion",
            ),
            ("resolve_managed_file_target", "installer symlink preservation"),
            ("remove_user_config_blocks", "installer user-config cleanup"),
            (
                'cp "$INSTALL_ROOT/offline.env" "$env_backup"',
                "installer upgrade offline.env preservation",
            ),
            ("$HOME/.zshrc", "installer Zsh startup"),
            (
                "$HOME/Library/Application Support/paper-fetch/.env",
                "installer macOS user config path",
            ),
        ),
        errors=errors,
    )
    host_python_modes = re.findall(r'"\$PYTHON_BIN"\s+(-\S+)', installer)
    if not host_python_modes or any(mode != "-I" for mode in host_python_modes):
        errors.append(
            "every direct offline installer host-Python invocation must use -I"
        )
    _require_order(
        installer,
        "  verify_checksums\n",
        "  check_install_target\n",
        label="exact payload inventory before install target mutation",
        errors=errors,
    )
    _require_order(
        installer,
        "  check_install_target\n",
        "  install_runtime_payload\n",
        label="install target ownership guard before payload replacement",
        errors=errors,
    )
    _require_fragments(
        verifier,
        (
            ('VERIFY_SHELL="/bin/zsh"', "native verifier Zsh selection"),
            (
                "extract_offline_archive_safely",
                "native verifier safe archive extraction",
            ),
            (
                'bundle.extractall(destination, filter="data")',
                "native verifier tarfile data filter",
            ),
            (
                "--archive-preflight-only",
                "native verifier archive-only security probe",
            ),
            ("verify_macos_macho_file", "native verifier Mach-O file check"),
            (
                "verify_macos_macho_dependencies",
                "native verifier Mach-O dependency check",
            ),
            ("verify_macos_native_bundle", "native verifier bundle check"),
            ('file -b "$path"', "native verifier binary inspection"),
            ('lipo -archs "$path"', "native verifier architecture inspection"),
            ('otool -L "$canonical"', "native verifier dependency inspection"),
            ("macos_contained_path", "native verifier dependency containment"),
            ("macos_rpaths", "native verifier LC_RPATH validation"),
            (
                "absolute/build-host LC_RPATH",
                "native verifier build-host RPATH rejection",
            ),
            (
                'codesign --verify --strict "$path"',
                "native verifier signature check",
            ),
            ("verify_macos_node_runtime", "native verifier Node runtime check"),
            (
                "verify_macos_macho_dependencies",
                "native verifier recursive dependency closure",
            ),
            ('"$node" --version', "native verifier Node launch probe"),
            (
                "check_macos_bundle_quarantine",
                "native verifier pre-execution quarantine scan",
            ),
            (
                "grep -E -q ': com\\.apple\\.quarantine$' <<< \"$quarantine_output\"",
                "native verifier pipefail-safe quarantine match",
            ),
            (
                "Verifying recursive macOS quarantine rejection before user writes",
                "native verifier recursive quarantine case",
            ),
            (
                "Installer replaced the macOS Zsh startup symlink",
                "native verifier Zsh symlink case",
            ),
            (
                'USER_CONFIG_NOTE="keep"',
                "native verifier user-config preservation case",
            ),
            (
                "Uninstall left the managed macOS user-config block behind",
                "native verifier user-config cleanup case",
            ),
        ),
        errors=errors,
    )
    _require_order(
        verifier,
        "check_macos_bundle_quarantine\n",
        "verify_macos_native_bundle\n",
        label="native quarantine scan before bundled Mach-O execution",
        errors=errors,
    )
    _require_fragments(
        config_source,
        (
            ("from platformdirs import", "platformdirs import"),
            ("user_config_path", "platformdirs user config path"),
            ("user_data_path", "platformdirs user data path"),
        ),
        errors=errors,
    )

    shell = _validate_required_keys(
        contract.get("shell"),
        required={
            "default",
            "startup_file",
            "activation_shells",
            "preserve_startup_symlinks",
        },
        field="shell",
        errors=errors,
    )
    if shell:
        if shell.get("default") != "zsh" or shell.get("startup_file") != ".zshrc":
            errors.append("shell contract must keep zsh as default with .zshrc")
        if shell.get("activation_shells") != ["bash", "zsh"]:
            errors.append("shell.activation_shells must be exactly bash then zsh")
        if shell.get("preserve_startup_symlinks") is not True:
            errors.append("shell.preserve_startup_symlinks must be true")


def _validate_browser_boundary(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    components = _validate_required_keys(
        contract.get("components"),
        required={"formula_tools", "camoufox", "forbidden"},
        field="components",
        errors=errors,
    )
    camoufox = _validate_required_keys(
        components.get("camoufox"),
        required={
            "python_package",
            "python_package_specifier",
            "locked_version_source",
            "version_verification",
            "manifest_version_field",
            "browser_binary",
            "runtime_download_during_install",
            "browser_binary_prepare_command",
            "preflight_command",
            "preflight_downloads_browser",
            "auto_prepare_policy",
            "auto_prepare_overrides",
            "managed_runtime_maintenance",
            "update_check_interval_hours",
            "concurrency_control",
            "prepare_timeout_seconds",
            "prepare_progress",
            "prepare_cancellation",
            "managed_runtime_resolution",
            "explicit_binary_override",
            "explicit_binary_auto_prepare",
            "native_ci_runtime",
            "native_test_addon_policy",
            "native_test_screen_policy",
        },
        field="components.camoufox",
        errors=errors,
    )
    expected_camoufox = {
        "python_package": "bundled",
        "python_package_specifier": EXPECTED_CAMOUFOX_SPECIFIER,
        "locked_version_source": "uv.lock",
        "version_verification": "lock-wheel-installed-manifest",
        "manifest_version_field": "components.camoufox.python_package_version",
        "browser_binary": "not_bundled",
        "runtime_download_during_install": False,
        "browser_binary_prepare_command": (
            "<install>/runtime/paper-fetch-python -m camoufox fetch"
        ),
        "preflight_command": "paper-fetch browser-preflight",
        "preflight_downloads_browser": "cli-default-enabled-mcp-default-disabled",
        "auto_prepare_policy": ("cli-default-enabled-mcp-library-default-disabled"),
        "auto_prepare_overrides": ["environment", "request"],
        "managed_runtime_maintenance": ["install", "repair", "update"],
        "update_check_interval_hours": 24,
        "concurrency_control": "cross-process-file-lock",
        "prepare_timeout_seconds": 900,
        "prepare_progress": "cli-stderr-mcp-logging",
        "prepare_cancellation": "cooperative-child-termination",
        "managed_runtime_resolution": "camoufox-package-managed",
        "explicit_binary_override": "configured-executable-only",
        "explicit_binary_auto_prepare": False,
        "native_ci_runtime": "official/152.0.4-beta.28",
        "native_test_addon_policy": "exclude-default-addons",
        "native_test_screen_policy": "fixed-synthetic-screen",
    }
    for key, expected in expected_camoufox.items():
        if camoufox.get(key) != expected:
            errors.append(f"components.camoufox.{key} must be {expected!r}")
    if components.get("forbidden") != ["flaresolverr"]:
        errors.append("components.forbidden must contain only flaresolverr")

    formula_tools = _validate_required_keys(
        components.get("formula_tools"),
        required={
            "delivery",
            "architecture",
            "binary_format",
            "signature",
            "relocate_non_system_dylibs",
            "entrypoint",
            "setup_action",
            "setup_action_version",
            "setup_action_sha",
            "ghc_version",
            "cabal_version",
            "ci_workflow_uses",
            "offline_workflow_uses",
            "node_package_manifests",
            "node_package_locks",
            "katex_version",
            "mathml_to_latex_version",
        },
        field="components.formula_tools",
        errors=errors,
    )
    expected_formula = {
        "delivery": "bundled",
        "architecture": "arm64",
        "binary_format": "Mach-O",
        "signature": "adhoc",
        "relocate_non_system_dylibs": True,
        "entrypoint": "formula-tools/bin/texmath",
        "setup_action": EXPECTED_FORMULA_SETUP_ACTION,
        "setup_action_version": EXPECTED_FORMULA_SETUP_VERSION,
        "setup_action_sha": EXPECTED_FORMULA_SETUP_SHA,
        "ghc_version": EXPECTED_FORMULA_GHC_VERSION,
        "cabal_version": EXPECTED_FORMULA_CABAL_VERSION,
        "ci_workflow_uses": EXPECTED_FORMULA_WORKFLOW_USES[".github/workflows/ci.yml"],
        "offline_workflow_uses": EXPECTED_FORMULA_WORKFLOW_USES[
            ".github/workflows/offline.yml"
        ],
        "node_package_manifests": EXPECTED_FORMULA_PACKAGE_MANIFESTS,
        "node_package_locks": EXPECTED_FORMULA_PACKAGE_LOCKS,
        "katex_version": EXPECTED_FORMULA_NODE_DEPENDENCIES["katex"],
        "mathml_to_latex_version": EXPECTED_FORMULA_NODE_DEPENDENCIES[
            "mathml-to-latex"
        ],
    }
    for key, expected in expected_formula.items():
        if formula_tools.get(key) != expected:
            errors.append(f"components.formula_tools.{key} must be {expected!r}")
    setup_sha = formula_tools.get("setup_action_sha")
    if not isinstance(setup_sha, str) or FULL_REVISION_RE.fullmatch(setup_sha) is None:
        errors.append(
            "components.formula_tools.setup_action_sha must be a full "
            "40-character git hash"
        )
    _validate_formula_toolchain_workflows(repo_root=repo_root, errors=errors)
    _validate_formula_node_packages(repo_root=repo_root, errors=errors)

    build_script = _read_repo_file(
        "scripts/build-offline-package.sh",
        repo_root=repo_root,
        errors=errors,
    )
    installer = _read_repo_file(
        "install-offline.sh",
        repo_root=repo_root,
        errors=errors,
    )
    _require_fragments(
        build_script,
        (
            ('"browser_binary": "not_bundled"', "Camoufox browser boundary"),
            ("-m camoufox fetch", "Camoufox explicit browser preparation"),
            ("paper-fetch browser-preflight", "Camoufox browser preflight"),
        ),
        errors=errors,
    )
    for forbidden in (
        "playwright install",
        "camoufox fetch",
        "camoufox.ensure_runtime",
    ):
        invoking_lines = [
            line
            for line in installer.splitlines()
            if forbidden in line
            and not line.lstrip().startswith(("echo ", "printf ", "#"))
        ]
        if invoking_lines:
            errors.append(
                "offline installer must not download a browser runtime; "
                f"found `{forbidden}`"
            )

    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    optional = pyproject.get("project", {}).get("optional-dependencies", {})
    for extra_name in ("browser", "full"):
        dependencies = optional.get(extra_name, [])
        camoufox_requirements = [
            Requirement(dependency)
            for dependency in dependencies
            if Requirement(dependency).name.casefold() == "camoufox"
        ]
        if (
            len(camoufox_requirements) != 1
            or camoufox_requirements[0].specifier
            != Requirement(f"camoufox{EXPECTED_CAMOUFOX_SPECIFIER}").specifier
        ):
            errors.append(
                f"pyproject optional extra {extra_name} must require "
                f"camoufox{EXPECTED_CAMOUFOX_SPECIFIER}"
            )
    try:
        uv_lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"cannot load uv.lock: {exc}")
    else:
        locked_camoufox = [
            package
            for package in uv_lock.get("package", [])
            if package.get("name") == "camoufox"
        ]
        locked_version = (
            str(locked_camoufox[0].get("version") or "")
            if len(locked_camoufox) == 1
            else ""
        )
        if (
            len(locked_camoufox) != 1
            or not locked_version
            or not _camoufox_version_is_supported(locked_version)
        ):
            errors.append(
                "uv.lock must resolve exactly one Camoufox package satisfying "
                f"{EXPECTED_CAMOUFOX_SPECIFIER}"
            )
        project_lock = next(
            (
                package
                for package in uv_lock.get("package", [])
                if package.get("name") == "paper-fetch-skill"
            ),
            {},
        )
        locked_requirements = project_lock.get("metadata", {}).get("requires-dist", [])
        for extra_name in ("browser", "full"):
            expected_marker = f"extra == '{extra_name}'"
            if not any(
                requirement.get("name") == "camoufox"
                and requirement.get("marker") == expected_marker
                and requirement.get("specifier") == EXPECTED_CAMOUFOX_SPECIFIER
                for requirement in locked_requirements
            ):
                errors.append(
                    "uv.lock must preserve "
                    f"camoufox{EXPECTED_CAMOUFOX_SPECIFIER} for the {extra_name} extra"
                )

    active_paths = [
        repo_root / "pyproject.toml",
        repo_root / "install-offline.sh",
        repo_root / "scripts" / "build-offline-package.sh",
        repo_root / "scripts" / "build-offline-package-windows.ps1",
        repo_root / "scripts" / "verify-offline-package.sh",
        repo_root / "scripts" / "windows-installer-helper.ps1",
        repo_root / ".github" / "workflows" / "ci.yml",
        repo_root / ".github" / "workflows" / "offline.yml",
        *(repo_root / "src" / "paper_fetch").rglob("*.py"),
    ]
    for path in active_paths:
        try:
            payload = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if "flaresolverr" in payload.casefold():
            errors.append(
                "active runtime/build surface still references removed FlareSolverr: "
                f"{path.relative_to(repo_root).as_posix()}"
            )


def _validate_formula_toolchain_workflows(
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    version_patterns = {
        "ghc-version": (
            re.compile(r'^ghc-version:\s*["\']?([^"\'\s]+)["\']?\s*$'),
            EXPECTED_FORMULA_GHC_VERSION,
        ),
        "cabal-version": (
            re.compile(r'^cabal-version:\s*["\']?([^"\'\s]+)["\']?\s*$'),
            EXPECTED_FORMULA_CABAL_VERSION,
        ),
    }

    for relative_path, expected_count in EXPECTED_FORMULA_WORKFLOW_USES.items():
        workflow = _read_repo_file(
            relative_path,
            repo_root=repo_root,
            errors=errors,
        )
        lines = workflow.splitlines()
        setup_steps: list[tuple[int, re.Match[str]]] = []
        for index, line in enumerate(lines):
            match = PINNED_ACTION_USE_RE.fullmatch(line)
            if match and match.group("action") == EXPECTED_FORMULA_SETUP_ACTION:
                setup_steps.append((index, match))

        if len(setup_steps) != expected_count:
            errors.append(
                f"{relative_path} must use {EXPECTED_FORMULA_SETUP_ACTION} exactly "
                f"{expected_count} times; got {len(setup_steps)}"
            )

        for line_index, match in setup_steps:
            if match.group("sha") != EXPECTED_FORMULA_SETUP_SHA:
                errors.append(
                    f"{relative_path} {EXPECTED_FORMULA_SETUP_ACTION} SHA must be "
                    f"{EXPECTED_FORMULA_SETUP_SHA!r}"
                )
            if match.group("version") != EXPECTED_FORMULA_SETUP_VERSION:
                errors.append(
                    f"{relative_path} {EXPECTED_FORMULA_SETUP_ACTION} version comment "
                    f"must be {EXPECTED_FORMULA_SETUP_VERSION!r}"
                )

            step_indent = len(match.group("indent"))
            step_lines: list[str] = []
            for following in lines[line_index + 1 :]:
                stripped = following.strip()
                following_indent = len(following) - len(following.lstrip())
                if stripped.startswith("- ") and following_indent <= step_indent:
                    break
                step_lines.append(stripped)

            for field, (pattern, expected_version) in version_patterns.items():
                actual_versions = [
                    field_match.group(1)
                    for step_line in step_lines
                    if (field_match := pattern.fullmatch(step_line))
                ]
                if actual_versions != [expected_version]:
                    errors.append(
                        f"{relative_path} {EXPECTED_FORMULA_SETUP_ACTION} {field} "
                        f"must be {expected_version!r}; got {actual_versions!r}"
                    )


def _validate_formula_node_packages(
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    for relative_path in EXPECTED_FORMULA_PACKAGE_MANIFESTS:
        payload = _read_repo_file(
            relative_path,
            repo_root=repo_root,
            errors=errors,
        )
        try:
            package = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            errors.append(
                f"cannot load formula package manifest {relative_path}: {exc}"
            )
            continue
        dependencies = package.get("dependencies")
        if dependencies != EXPECTED_FORMULA_NODE_DEPENDENCIES:
            errors.append(
                f"{relative_path} dependencies must be "
                f"{EXPECTED_FORMULA_NODE_DEPENDENCIES!r}; got {dependencies!r}"
            )

    for relative_path in EXPECTED_FORMULA_PACKAGE_LOCKS:
        payload = _read_repo_file(
            relative_path,
            repo_root=repo_root,
            errors=errors,
        )
        try:
            lock = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot load formula package lock {relative_path}: {exc}")
            continue
        packages = lock.get("packages")
        if not isinstance(packages, dict):
            errors.append(f"{relative_path} packages must be an object")
            continue
        root_dependencies = packages.get("", {}).get("dependencies")
        if root_dependencies != EXPECTED_FORMULA_NODE_DEPENDENCIES:
            errors.append(
                f"{relative_path} root dependencies must be "
                f"{EXPECTED_FORMULA_NODE_DEPENDENCIES!r}; got {root_dependencies!r}"
            )
        for (
            package_name,
            expected_version,
        ) in EXPECTED_FORMULA_NODE_DEPENDENCIES.items():
            locked = packages.get(f"node_modules/{package_name}", {}).get("version")
            if locked != expected_version:
                errors.append(
                    f"{relative_path} must lock {package_name} to "
                    f"{expected_version!r}; got {locked!r}"
                )


def _validate_portable_and_release_tooling(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    portable_ci = _validate_required_keys(
        contract.get("portable_ci"),
        required=REQUIRED_PORTABLE_CI,
        field="portable_ci",
        errors=errors,
    )
    expected_portable = {
        "workflow": ".github/workflows/ci.yml",
        "job": "macos-contract-portable",
        "runners": ["ubuntu-latest", "windows-latest"],
        "linux_entrypoint": "scripts/test-macos-contract.sh",
        "windows_entrypoint": "scripts/test-macos-contract.ps1",
        "native_equivalent": False,
    }
    for key, expected in expected_portable.items():
        if portable_ci.get(key) != expected:
            errors.append(f"portable_ci.{key} must be {expected!r}")

    release_tooling = _validate_required_keys(
        contract.get("release_tooling"),
        required=REQUIRED_RELEASE_TOOLING,
        field="release_tooling",
        errors=errors,
    )
    expected_release = {
        "workflow": ".github/workflows/offline.yml",
        "trusted_ref_format": "full-commit-sha",
        "source_tag_immutable": True,
        "adapted_release_requires_version_bump": True,
        "adapted_release_requires_new_tag": True,
        "source_contract_required_before_overlay": True,
        "legacy_source_without_contract": "reject",
        "overlay_copy_destinations_exclude_python_source": True,
        "manifest_records_tooling_revision": True,
        "trusted_posix_overlay_paths": EXPECTED_POSIX_TOOLING_PATHS,
        "trusted_windows_overlay_paths": EXPECTED_WINDOWS_TOOLING_PATHS,
    }
    for key, expected in expected_release.items():
        if release_tooling.get(key) != expected:
            errors.append(f"release_tooling.{key} must be {expected!r}")

    ci_workflow = _read_repo_file(
        ".github/workflows/ci.yml",
        repo_root=repo_root,
        errors=errors,
    )
    _require_fragments(
        ci_workflow,
        (
            ("  macos-contract-portable:", "portable macOS contract CI job"),
            (
                "os: [ubuntu-latest, windows-latest]",
                "portable macOS contract runner matrix",
            ),
            (
                "scripts/test-macos-contract.sh",
                "portable Linux contract entrypoint",
            ),
            (
                "scripts/test-macos-contract.ps1 -Python .venv/Scripts/python.exe",
                "portable Windows contract entrypoint",
            ),
        ),
        errors=errors,
    )

    offline_workflow = _read_repo_file(
        ".github/workflows/offline.yml",
        repo_root=repo_root,
        errors=errors,
    )
    _require_fragments(
        offline_workflow,
        (
            (
                "Trusted commit whose POSIX builder, installer, and verifier",
                "trusted POSIX tooling scope",
            ),
            (
                "Validate immutable source macOS adaptation contract",
                "immutable source contract gate",
            ),
            ("path: .posix-release-tooling", "trusted POSIX tooling checkout"),
            (
                "posix_tooling_ref must be an immutable 40-character commit SHA.",
                "trusted POSIX tooling immutable revision",
            ),
            (
                "PAPER_FETCH_OFFLINE_TOOLING_REVISION",
                "trusted POSIX tooling provenance",
            ),
            (
                ".posix-release-tooling/scripts/build-offline-package.sh",
                "trusted POSIX builder overlay",
            ),
            (
                ".posix-release-tooling/install-offline.sh",
                "trusted POSIX installer overlay",
            ),
            (
                ".posix-release-tooling/scripts/verify-offline-package.sh",
                "trusted POSIX verifier overlay",
            ),
            (
                "working-directory: .posix-release-tooling",
                "trusted POSIX contract validation",
            ),
            (
                "inputs.posix_tooling_ref != ''",
                "trusted tooling contract validation with overlay",
            ),
        ),
        errors=errors,
    )
    _require_order(
        offline_workflow,
        "ref: ${{ inputs.ref || github.sha }}",
        "Validate immutable source macOS adaptation contract",
        label="immutable source checkout before source contract validation",
        errors=errors,
    )
    _require_order(
        offline_workflow,
        "Validate immutable source macOS adaptation contract",
        "path: .posix-release-tooling",
        label="source contract validation before trusted tooling checkout",
        errors=errors,
    )
    overlay_paths = sorted(
        set(
            re.findall(
                r"\.posix-release-tooling/([A-Za-z0-9_./-]+)",
                offline_workflow,
            )
        )
    )
    if overlay_paths != sorted(EXPECTED_POSIX_TOOLING_PATHS):
        errors.append(
            "trusted POSIX tooling overlay paths must be exactly "
            f"{EXPECTED_POSIX_TOOLING_PATHS!r}; got {overlay_paths!r}"
        )
    overlay_pairs = re.findall(
        r"install -m 0755 \\\n\s+\.posix-release-tooling/"
        r"([A-Za-z0-9_./-]+) \\\n\s+([A-Za-z0-9_./-]+)",
        offline_workflow,
    )
    expected_pairs = [(path, path) for path in EXPECTED_POSIX_TOOLING_PATHS]
    if sorted(overlay_pairs) != sorted(expected_pairs):
        errors.append(
            "trusted POSIX tooling overlay source/destination pairs must be exactly "
            f"{expected_pairs!r}; got {overlay_pairs!r}"
        )
    if "src/paper_fetch/formula/install.py" in offline_workflow:
        errors.append("release tooling overlay must not replace Python wheel source")
    windows_job = offline_workflow.split("\n  windows:", maxsplit=1)[-1]
    _require_fragments(
        windows_job,
        (
            (
                "windows_tooling_ref must be an immutable 40-character commit SHA.",
                "trusted Windows tooling immutable revision",
            ),
            (
                "Validate immutable source macOS adaptation contract",
                "Windows immutable source contract gate",
            ),
            (
                "PAPER_FETCH_OFFLINE_TOOLING_REVISION: ${{ inputs.windows_tooling_ref }}",
                "trusted Windows tooling provenance",
            ),
        ),
        errors=errors,
    )
    windows_overlay_pairs = re.findall(
        r'git show "\$TOOLING_REF:([A-Za-z0-9_./-]+)" \\\n'
        r"\s+> ([A-Za-z0-9_./-]+)",
        windows_job,
    )
    expected_windows_pairs = [(path, path) for path in EXPECTED_WINDOWS_TOOLING_PATHS]
    if windows_overlay_pairs != expected_windows_pairs:
        errors.append(
            "trusted Windows tooling overlay source/destination pairs must be exactly "
            f"{expected_windows_pairs!r}; got {windows_overlay_pairs!r}"
        )


def _validate_native_gates(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    native_gate = _validate_required_keys(
        contract.get("native_gate"),
        required={
            "ci_workflow",
            "ci_job",
            "runner",
            "ci_python_version",
            "release_matrix_workflow",
            "release_workflow",
            "release_requires_offline",
            "release_attestation_action",
            "release_attestation_version",
            "release_attestation_sha",
            "release_attestation_uses",
            "release_attestation_subject_path",
            "network_smoke_required",
            "native_tools",
            "cache_alias_test_node",
        },
        field="native_gate",
        errors=errors,
    )
    expected = {
        "ci_workflow": ".github/workflows/ci.yml",
        "ci_job": "macos-native",
        "runner": "macos-15",
        "ci_python_version": "3.14",
        "release_matrix_workflow": ".github/workflows/offline.yml",
        "release_workflow": ".github/workflows/release.yml",
        "release_requires_offline": True,
        "release_attestation_action": EXPECTED_RELEASE_ATTESTATION_ACTION,
        "release_attestation_version": EXPECTED_RELEASE_ATTESTATION_VERSION,
        "release_attestation_sha": EXPECTED_RELEASE_ATTESTATION_SHA,
        "release_attestation_uses": EXPECTED_RELEASE_ATTESTATION_USES,
        "release_attestation_subject_path": (EXPECTED_RELEASE_ATTESTATION_SUBJECT_PATH),
        "network_smoke_required": False,
        "native_tools": [
            "sw_vers",
            "file",
            "lipo",
            "otool",
            "install_name_tool",
            "codesign",
            "xattr",
        ],
        "cache_alias_test_node": (
            "tests/unit/test_cache_index_semantics.py::"
            "CacheIndexSemanticsTests::"
            "test_cache_scope_accepts_equivalent_filesystem_alias_for_root"
        ),
    }
    for key, value in expected.items():
        if native_gate.get(key) != value:
            errors.append(f"native_gate.{key} must be {value!r}")
    attestation_sha = native_gate.get("release_attestation_sha")
    if (
        not isinstance(attestation_sha, str)
        or FULL_REVISION_RE.fullmatch(attestation_sha) is None
    ):
        errors.append(
            "native_gate.release_attestation_sha must be a full 40-character git hash"
        )

    ci_workflow = _read_repo_file(
        ".github/workflows/ci.yml",
        repo_root=repo_root,
        errors=errors,
    )
    offline_workflow = _read_repo_file(
        ".github/workflows/offline.yml",
        repo_root=repo_root,
        errors=errors,
    )
    release_workflow = _read_repo_file(
        ".github/workflows/release.yml",
        repo_root=repo_root,
        errors=errors,
    )
    _require_fragments(
        ci_workflow,
        (
            ("  macos-native:", "regular CI native macOS job"),
            ("runs-on: macos-15", "regular CI native macOS runner"),
            ('python-version: "3.14"', "regular CI native Python ABI"),
            (
                "python scripts/validate_macos_adaptation.py",
                "regular CI contract validation",
            ),
            ('test "$(uname -m)" = "arm64"', "regular CI arm64 assertion"),
            (
                'MACOSX_DEPLOYMENT_TARGET: "15.0"',
                "regular CI deployment target",
            ),
            (
                "paper-fetch-skill-offline-macos-arm64-cp314.tar.gz",
                "regular CI cp314 artifact",
            ),
            (
                "scripts/verify-offline-package.sh",
                "regular CI native verifier",
            ),
            (
                'PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE: "1"',
                "regular CI deterministic verification",
            ),
            (
                "test_cache_scope_accepts_equivalent_filesystem_alias_for_root",
                "regular CI native cache alias test",
            ),
            ("if-no-files-found: error", "regular CI artifact failure policy"),
        ),
        errors=errors,
    )
    matrix_expectations: list[tuple[str, str]] = [
        ("os: macos-15", "offline matrix macOS runner"),
        (
            "python scripts/validate_macos_adaptation.py",
            "offline matrix contract validation",
        ),
        ("packages=(dist/*.tar.gz)", "offline matrix macOS package selection"),
        ("packages=(dist/*.sh)", "offline matrix Linux package selection"),
        (
            'scripts/verify-offline-package.sh "${packages[0]}"',
            "offline matrix POSIX verifier",
        ),
        (
            'if [ "${#packages[@]}" -ne 1 ]',
            "offline matrix exact package count",
        ),
        ("if-no-files-found: error", "offline matrix artifact failure policy"),
    ]
    for version, tag in zip(
        EXPECTED_PYTHON_VERSIONS,
        EXPECTED_PYTHON_TAGS,
        strict=True,
    ):
        matrix_expectations.extend(
            (
                (
                    f'python-version: "{version}"',
                    f"offline matrix Python {version}",
                ),
                (
                    f"target: macos-arm64-{tag}",
                    f"offline matrix macOS {tag}",
                ),
            )
        )
    _require_fragments(
        offline_workflow,
        tuple(matrix_expectations),
        errors=errors,
    )
    if offline_workflow.count("os: macos-15") < 4:
        errors.append("offline matrix must pin all four macOS ABI entries to macos-15")
    _require_fragments(
        release_workflow,
        (
            (
                "uses: ./.github/workflows/offline.yml",
                "release reusable offline workflow",
            ),
            ("needs: [verify-tag, offline]", "release offline publish gate"),
        ),
        errors=errors,
    )
    _validate_release_attestation_workflow(repo_root=repo_root, errors=errors)


def _validate_release_attestation_workflow(
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    relative_path = ".github/workflows/release.yml"
    workflow = _read_repo_file(
        relative_path,
        repo_root=repo_root,
        errors=errors,
    )
    lines = workflow.splitlines()
    attestation_steps: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = PINNED_ACTION_USE_RE.fullmatch(line)
        if match and match.group("action") == EXPECTED_RELEASE_ATTESTATION_ACTION:
            attestation_steps.append((index, match))

    if len(attestation_steps) != EXPECTED_RELEASE_ATTESTATION_USES:
        errors.append(
            f"{relative_path} must use {EXPECTED_RELEASE_ATTESTATION_ACTION} exactly "
            f"{EXPECTED_RELEASE_ATTESTATION_USES} times; got {len(attestation_steps)}"
        )

    for line_index, match in attestation_steps:
        if match.group("sha") != EXPECTED_RELEASE_ATTESTATION_SHA:
            errors.append(
                f"{relative_path} {EXPECTED_RELEASE_ATTESTATION_ACTION} SHA must be "
                f"{EXPECTED_RELEASE_ATTESTATION_SHA!r}"
            )
        if match.group("version") != EXPECTED_RELEASE_ATTESTATION_VERSION:
            errors.append(
                f"{relative_path} {EXPECTED_RELEASE_ATTESTATION_ACTION} version "
                f"comment must be {EXPECTED_RELEASE_ATTESTATION_VERSION!r}"
            )

        step_indent = len(match.group("indent"))
        step_lines: list[str] = []
        for following in lines[line_index + 1 :]:
            stripped = following.strip()
            following_indent = len(following) - len(following.lstrip())
            if stripped.startswith("- ") and following_indent <= step_indent:
                break
            step_lines.append(stripped)
        expected_subject = f"subject-path: {EXPECTED_RELEASE_ATTESTATION_SUBJECT_PATH}"
        if step_lines.count(expected_subject) != 1:
            errors.append(
                f"{relative_path} {EXPECTED_RELEASE_ATTESTATION_ACTION} must declare "
                f"exactly one {expected_subject!r}"
            )


def _validate_posix_line_endings(
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    attributes = _read_repo_file(
        ".gitattributes",
        repo_root=repo_root,
        errors=errors,
    )
    for required in (
        "*.sh text eol=lf",
        "*.py text eol=lf",
        "*.toml text eol=lf",
        "*.yml text eol=lf",
        "*.yaml text eol=lf",
        "*.md text eol=lf",
    ):
        if required not in attributes:
            errors.append(f".gitattributes is missing LF rule: {required}")

    entrypoints = sorted(repo_root.glob("*.sh"))
    entrypoints.extend(sorted((repo_root / "scripts").glob("*.sh")))
    if not entrypoints:
        errors.append("repository has no POSIX shell entrypoints to validate")
    for path in entrypoints:
        try:
            payload = path.read_bytes()
        except OSError as exc:
            errors.append(f"cannot read POSIX entrypoint {path}: {exc}")
            continue
        if b"\r\n" in payload:
            relative = path.relative_to(repo_root).as_posix()
            errors.append(f"POSIX entrypoint contains CRLF line endings: {relative}")


def _validate_windows_entrypoint(
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    entrypoint = _read_repo_file(
        "scripts/test-macos-contract.ps1",
        repo_root=repo_root,
        errors=errors,
    )
    _require_fragments(
        entrypoint,
        (
            (
                "scripts/validate_macos_adaptation.py",
                "Windows contract validator",
            ),
            ("--print-test-nodes windows", "Windows selected pytest nodes"),
            ("@testNodes", "Windows pytest node array"),
            ("-m pytest", "Windows pytest invocation"),
            ("PYTHONPATH", "Windows source import path"),
            ("ValidatorOnly", "Windows validator-only mode"),
        ),
        errors=errors,
    )
    lowered = entrypoint.casefold()
    for forbidden in (
        "test_offline_install.py",
        "tests/live",
        "bash ",
        "/bin/",
        "sw_vers",
        "xattr ",
        "codesign",
        "otool",
        "install_name_tool",
        "curl ",
        "wget ",
        "-n 0",
    ):
        if forbidden.casefold() in lowered:
            errors.append(
                "Windows contract entrypoint invokes a non-portable dependency: "
                f"{forbidden}"
            )


def _validate_wsl_entrypoint(
    *,
    repo_root: Path,
    errors: list[str],
) -> None:
    entrypoint = _read_repo_file(
        "scripts/test-macos-contract.sh",
        repo_root=repo_root,
        errors=errors,
    )
    _require_fragments(
        entrypoint,
        (
            (
                "scripts/validate_macos_adaptation.py",
                "WSL/Linux contract validator",
            ),
            (".venv-wsl/bin/python", "WSL-specific virtual environment"),
            ("PYTHONPATH=", "WSL/Linux source import path"),
            ("readlink -f --", "WSL/Linux script path resolution"),
            ("--print-test-nodes wsl", "WSL/Linux selected pytest nodes"),
            ("mapfile -t TEST_NODES", "WSL/Linux pytest node array"),
            ('"${TEST_NODES[@]}"', "WSL/Linux pytest node expansion"),
            ("--validator-only", "WSL/Linux validator-only mode"),
            ("/mnt/[a-zA-Z]/*", "WSL DrvFS detection"),
            ('sys.platform != "linux"', "native Linux Python check"),
            ('startswith("/mnt/")', "Windows Python environment rejection"),
            ("DEGRADED_CHECKOUT=1", "WSL degraded checkout marker"),
            ("VALIDATOR_ONLY=1", "WSL /mnt validator-only downgrade"),
            ("-m pytest", "WSL/Linux pytest invocation"),
        ),
        errors=errors,
    )
    lowered = entrypoint.casefold()
    for forbidden in (
        "tests/live",
        "paper_fetch_run_live",
        "verify-offline-package.sh",
        "paper-fetch --query",
        "pip install",
        "python.exe",
        "powershell.exe",
        "sw_vers",
        "xattr ",
        "codesign",
        "otool",
        "install_name_tool",
        "lipo",
        "vtool",
        "curl ",
        "wget ",
        "-n 0",
    ):
        if forbidden.casefold() in lowered:
            errors.append(
                "WSL/Linux contract entrypoint invokes a native/live dependency: "
                f"{forbidden}"
            )


def _validate_development_surfaces(
    contract: dict[str, Any],
    *,
    all_test_nodes: set[str],
    repo_root: Path,
    errors: list[str],
) -> None:
    surfaces = _validate_required_keys(
        contract.get("development_surfaces"),
        required={"windows", "wsl"},
        field="development_surfaces",
        errors=errors,
    )
    if not surfaces:
        return

    windows = _validate_required_keys(
        surfaces.get("windows"),
        required={
            "entrypoint",
            "coverage",
            "selection",
            "native_equivalent",
            "included_test_nodes",
        },
        field="development_surfaces.windows",
        errors=errors,
    )
    wsl = _validate_required_keys(
        surfaces.get("wsl"),
        required={
            "entrypoint",
            "coverage",
            "selection",
            "preferred_repo_filesystem",
            "shared_windows_checkout",
            "requires_native_linux_python",
            "native_equivalent",
            "excluded_test_nodes",
            "exclusion_reason",
        },
        field="development_surfaces.wsl",
        errors=errors,
    )
    for name, surface in (("windows", windows), ("wsl", wsl)):
        entrypoint = _repo_path(
            surface.get("entrypoint"),
            field=f"development_surfaces.{name}.entrypoint",
            repo_root=repo_root,
            errors=errors,
        )
        if entrypoint is not None and not entrypoint.is_file():
            errors.append(
                f"development_surfaces.{name}.entrypoint does not exist: "
                f"{surface.get('entrypoint')}"
            )
        if surface.get("native_equivalent") is not False:
            errors.append(
                f"development_surfaces.{name}.native_equivalent must be false"
            )

    if windows.get("coverage") != "contract_and_pure_python_static":
        errors.append(
            "development_surfaces.windows.coverage must be "
            "contract_and_pure_python_static"
        )
    if windows.get("selection") != "explicit":
        errors.append("development_surfaces.windows.selection must be explicit")
    included = _validate_unique_strings(
        windows.get("included_test_nodes"),
        field="development_surfaces.windows.included_test_nodes",
        allow_empty=False,
        errors=errors,
    )
    for node_id in included:
        if node_id not in all_test_nodes:
            errors.append(
                "development_surfaces.windows includes an unknown pytest node: "
                f"{node_id}"
            )
        if node_id.split("::", 1)[0] not in WINDOWS_STATIC_TEST_FILES:
            errors.append(
                "development_surfaces.windows includes a non-static pytest file: "
                f"{node_id}"
            )

    if wsl.get("coverage") != "contract_and_fake_darwin":
        errors.append(
            "development_surfaces.wsl.coverage must be contract_and_fake_darwin"
        )
    if wsl.get("selection") != "all_except":
        errors.append("development_surfaces.wsl.selection must be all_except")
    if wsl.get("preferred_repo_filesystem") != "wsl_linux_filesystem":
        errors.append(
            "development_surfaces.wsl.preferred_repo_filesystem must be "
            "wsl_linux_filesystem"
        )
    if wsl.get("shared_windows_checkout") != "validator_only":
        errors.append(
            "development_surfaces.wsl.shared_windows_checkout must be validator_only"
        )
    if wsl.get("requires_native_linux_python") is not True:
        errors.append(
            "development_surfaces.wsl.requires_native_linux_python must be true"
        )
    excluded = _validate_unique_strings(
        wsl.get("excluded_test_nodes"),
        field="development_surfaces.wsl.excluded_test_nodes",
        allow_empty=False,
        errors=errors,
    )
    for node_id in excluded:
        if node_id not in all_test_nodes:
            errors.append(
                f"development_surfaces.wsl excludes an unknown pytest node: {node_id}"
            )
    reason = wsl.get("exclusion_reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(
            "development_surfaces.wsl.exclusion_reason must be a non-empty string"
        )

    for name in ("windows", "wsl"):
        selected = test_nodes_for_surface(contract, name)
        if not selected:
            errors.append(f"development surface {name} selects no pytest nodes")
        if len(selected) != len(set(selected)):
            errors.append(f"development surface {name} selects duplicate pytest nodes")


def _validate_changes(
    contract: dict[str, Any],
    *,
    change_markdown: str,
    audit_markdown: str,
    repo_root: Path,
    errors: list[str],
) -> set[str]:
    changes = contract.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append("changes must be a non-empty array of tables")
        return set()

    documented_audit_ids = set(AUDIT_ID_RE.findall(audit_markdown))
    missing_audit_ids = sorted(EXPECTED_AUDIT_IDS - documented_audit_ids)
    if missing_audit_ids:
        errors.append(
            f"audit document is missing required cases: {', '.join(missing_audit_ids)}"
        )

    seen_change_ids: set[str] = set()
    all_test_nodes: set[str] = set()
    for index, value in enumerate(changes):
        field = f"changes[{index}]"
        if not isinstance(value, dict):
            errors.append(f"{field} must be a TOML table")
            continue
        change = value
        missing = sorted(REQUIRED_CHANGE_FIELDS - set(change))
        if missing:
            errors.append(f"{field} is missing required keys: {', '.join(missing)}")

        change_id = change.get("id")
        if not isinstance(change_id, str) or CHANGE_ID_RE.fullmatch(change_id) is None:
            errors.append(f"{field}.id must match MAC-V4-NNN")
            change_id = f"<invalid-{index}>"
        elif change_id in seen_change_ids:
            errors.append(f"duplicate change id: {change_id}")
        else:
            seen_change_ids.add(change_id)
            if change_id not in change_markdown:
                errors.append(f"change document does not mention `{change_id}`")

        if change.get("status") not in ALLOWED_STATUSES:
            errors.append(
                f"{change_id}.status must be one of {sorted(ALLOWED_STATUSES)}"
            )
        if change.get("risk") not in ALLOWED_RISKS:
            errors.append(f"{change_id}.risk must be one of {sorted(ALLOWED_RISKS)}")
        if change.get("portable_validation") not in ALLOWED_PORTABLE_VALIDATION:
            errors.append(
                f"{change_id}.portable_validation must be one of "
                f"{sorted(ALLOWED_PORTABLE_VALIDATION)}"
            )
        native_required = change.get("native_validation_required")
        if not isinstance(native_required, bool):
            errors.append(f"{change_id}.native_validation_required must be boolean")
        elif change.get("risk") == "P0" and not native_required:
            errors.append(f"{change_id} is P0 and must require native validation")
        for text_field in ("title", "area", "summary", "rationale"):
            text = change.get(text_field)
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{change_id}.{text_field} must be a non-empty string")

        implementation_paths = _validate_unique_strings(
            change.get("implementation_paths"),
            field=f"{change_id}.implementation_paths",
            allow_empty=False,
            errors=errors,
        )
        has_non_doc_implementation = False
        for path_index, relative_path in enumerate(implementation_paths):
            path = _repo_path(
                relative_path,
                field=f"{change_id}.implementation_paths[{path_index}]",
                repo_root=repo_root,
                errors=errors,
            )
            if path is None:
                continue
            if not path.is_file():
                errors.append(
                    f"{change_id} implementation path does not exist: {relative_path}"
                )
            if not relative_path.startswith("docs/"):
                has_non_doc_implementation = True
        if implementation_paths and not has_non_doc_implementation:
            errors.append(
                f"{change_id} must reference at least one non-doc implementation"
            )

        test_nodes = _validate_unique_strings(
            change.get("test_nodes"),
            field=f"{change_id}.test_nodes",
            allow_empty=False,
            errors=errors,
        )
        for node_id in test_nodes:
            all_test_nodes.add(node_id)
            parts = node_id.split("::")
            if len(parts) not in (2, 3):
                errors.append(f"{change_id} has an invalid pytest node id: {node_id}")
                continue
            relative_path, selectors = parts[0], parts[1:]
            if not relative_path.startswith("tests/"):
                errors.append(
                    f"{change_id} pytest node must live under tests/: {node_id}"
                )
                continue
            test_path = _repo_path(
                relative_path,
                field=f"{change_id}.test_nodes",
                repo_root=repo_root,
                errors=errors,
            )
            if test_path is None or not test_path.is_file():
                errors.append(
                    f"{change_id} pytest file does not exist: {relative_path}"
                )
            elif not _test_node_exists(test_path, selectors):
                errors.append(f"{change_id} pytest node does not exist: {node_id}")

        audit_cases = _validate_unique_strings(
            change.get("audit_cases"),
            field=f"{change_id}.audit_cases",
            allow_empty=False,
            errors=errors,
        )
        for audit_id in audit_cases:
            if AUDIT_ID_RE.fullmatch(audit_id) is None:
                errors.append(f"{change_id} has an invalid audit case id: {audit_id!r}")
            elif audit_id not in documented_audit_ids:
                errors.append(
                    f"{change_id} references undocumented audit case: {audit_id}"
                )

    if seen_change_ids != EXPECTED_CHANGE_IDS:
        missing = sorted(EXPECTED_CHANGE_IDS - seen_change_ids)
        unexpected = sorted(seen_change_ids - EXPECTED_CHANGE_IDS)
        errors.append(
            "changes must contain exactly MAC-V4-001 through MAC-V4-009; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return all_test_nodes


def validate_contract(
    contract: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    errors: list[str] = []
    missing_top_level = sorted(REQUIRED_TOP_LEVEL - set(contract))
    if missing_top_level:
        errors.append(
            "contract is missing required top-level keys: "
            f"{', '.join(missing_top_level)}"
        )

    if contract.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if contract.get("contract_id") != "paper-fetch/macos":
        errors.append("contract_id must be paper-fetch/macos")
    contract_version = contract.get("contract_version")
    if (
        not isinstance(contract_version, str)
        or VERSION_RE.fullmatch(contract_version) is None
    ):
        errors.append("contract_version must use semantic x.y.z form")
    elif contract_version != EXPECTED_CONTRACT_VERSION:
        errors.append(
            f"contract_version must track upstream v{EXPECTED_CONTRACT_VERSION}"
        )
    if contract.get("platform") != "macos":
        errors.append("platform must be macos")

    change_doc_path = _repo_path(
        contract.get("change_document"),
        field="change_document",
        repo_root=repo_root,
        errors=errors,
    )
    audit_doc_path = _repo_path(
        contract.get("audit_document"),
        field="audit_document",
        repo_root=repo_root,
        errors=errors,
    )
    change_markdown = ""
    audit_markdown = ""
    if change_doc_path is not None:
        if change_doc_path.is_file():
            change_markdown = change_doc_path.read_text(encoding="utf-8")
        else:
            errors.append(
                f"change document does not exist: {contract.get('change_document')}"
            )
    if audit_doc_path is not None:
        if audit_doc_path.is_file():
            audit_markdown = audit_doc_path.read_text(encoding="utf-8")
        else:
            errors.append(
                f"audit document does not exist: {contract.get('audit_document')}"
            )

    _validate_source_baseline(contract, errors=errors)
    _validate_support_values(contract, repo_root=repo_root, errors=errors)
    _validate_safety_values(contract, errors=errors)
    _validate_native_packaging(contract, repo_root=repo_root, errors=errors)
    _validate_browser_boundary(contract, repo_root=repo_root, errors=errors)
    _validate_portable_and_release_tooling(
        contract,
        repo_root=repo_root,
        errors=errors,
    )
    _validate_native_gates(contract, repo_root=repo_root, errors=errors)
    all_test_nodes = _validate_changes(
        contract,
        change_markdown=change_markdown,
        audit_markdown=audit_markdown,
        repo_root=repo_root,
        errors=errors,
    )
    _validate_development_surfaces(
        contract,
        all_test_nodes=all_test_nodes,
        repo_root=repo_root,
        errors=errors,
    )
    _validate_posix_line_endings(repo_root=repo_root, errors=errors)
    _validate_windows_entrypoint(repo_root=repo_root, errors=errors)
    _validate_wsl_entrypoint(repo_root=repo_root, errors=errors)
    return errors


def validate_repository(
    *,
    contract_path: Path = CONTRACT_PATH,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    try:
        contract = load_contract(contract_path)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot load macOS adaptation contract: {exc}"]
    return validate_contract(contract, repo_root=repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the machine-readable macOS adaptation contract.",
    )
    parser.add_argument(
        "--print-test-nodes",
        choices=("windows", "wsl"),
        help="Print deterministic pytest nodes for a development surface.",
    )
    args = parser.parse_args(argv)

    errors = validate_repository()
    if errors:
        print("macOS adaptation contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    contract = load_contract()
    if args.print_test_nodes:
        for node_id in test_nodes_for_surface(contract, args.print_test_nodes):
            print(node_id)
        return 0

    print(
        "macOS adaptation contract OK: "
        f"{contract['contract_id']} v{contract['contract_version']}, "
        f"{len(contract['changes'])} tracked changes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
