"""Network-free runtime, offline-install, and skill provenance diagnostics."""

from __future__ import annotations

import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

from .config import DEFAULT_USER_AGENT
from .skill_integrity import (
    SkillManifestError,
    build_skill_bundle_manifest,
    read_offline_manifest,
    verify_skill_bundle,
    verify_skill_directory,
)


DIST_NAME = "paper-fetch-skill"
SKILL_NAME = "paper-fetch-skill"
_USER_AGENT_PREFIX = f"{DIST_NAME}/"
_CLI_VERSION_RE = re.compile(r"\bpaper-fetch\s+([^\s]+)")


@dataclass(frozen=True)
class ProvenanceContext:
    """Resolved process facts used to make provenance tests deterministic."""

    module_file: Path
    executable: Path
    sys_prefix: Path
    argv0: str
    home: Path
    env: Mapping[str, str]
    source_root: Path | None
    current_distribution: Mapping[str, Any]
    active_cli: Mapping[str, Any]


def _normalized_name(value: object) -> str:
    return re.sub(r"[-_.]+", "-", str(value or "").strip().lower())


def _project_version(pyproject_path: Path) -> str | None:
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = payload.get("project")
    if not isinstance(project, Mapping):
        return None
    if _normalized_name(project.get("name")) != DIST_NAME:
        return None
    version = str(project.get("version") or "").strip()
    return version or None


def _find_source_root(module_file: Path) -> Path | None:
    resolved = module_file.expanduser().resolve()
    for parent in (resolved.parent, *resolved.parents):
        pyproject_path = parent / "pyproject.toml"
        if _project_version(pyproject_path):
            return parent
        if len(parent.parts) + 8 < len(resolved.parts):
            break
    return None


def _distribution_metadata_path(
    distribution: importlib.metadata.Distribution,
) -> Path | None:
    for relative in distribution.files or ():
        if relative.name == "METADATA" and relative.parent.name.endswith(".dist-info"):
            return Path(str(distribution.locate_file(relative))).resolve()
    root = Path(str(distribution.locate_file(""))).resolve()
    for pattern in (
        "paper_fetch_skill-*.dist-info/METADATA",
        "paper_fetch_skill*.egg-info/PKG-INFO",
    ):
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[-1].resolve()
    return None


def _current_distribution_record() -> dict[str, Any]:
    try:
        distribution = importlib.metadata.distribution(DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return {
            "status": "not_installed",
            "reason_code": "distribution_metadata_not_found",
            "name": DIST_NAME,
            "version": None,
            "root": None,
            "metadata_path": None,
        }
    metadata_path = _distribution_metadata_path(distribution)
    return {
        "status": "ready",
        "reason_code": "distribution_metadata_found",
        "name": DIST_NAME,
        "version": distribution.version,
        "root": str(Path(str(distribution.locate_file(""))).resolve()),
        "metadata_path": str(metadata_path) if metadata_path else None,
    }


def _active_cli_record() -> dict[str, Any]:
    located = shutil.which("paper-fetch")
    if not located:
        return {
            "status": "not_found",
            "reason_code": "path_cli_not_found",
            "path": None,
            "version": None,
        }
    path = Path(located).expanduser().resolve()
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {
            "status": "error",
            "reason_code": "path_cli_version_probe_failed",
            "path": str(path),
            "version": None,
            "error_type": error.__class__.__name__,
        }
    match = _CLI_VERSION_RE.search(
        f"{completed.stdout.strip()} {completed.stderr.strip()}"
    )
    if completed.returncode != 0 or match is None:
        return {
            "status": "error",
            "reason_code": "path_cli_version_unreadable",
            "path": str(path),
            "version": None,
            "exit_code": completed.returncode,
        }
    return {
        "status": "ready",
        "reason_code": "path_cli_version_found",
        "path": str(path),
        "version": match.group(1),
    }


def default_provenance_context() -> ProvenanceContext:
    """Collect local-only process and PATH facts."""

    module_file = Path(__file__).resolve()
    return ProvenanceContext(
        module_file=module_file,
        executable=Path(sys.executable).resolve(),
        sys_prefix=Path(sys.prefix).resolve(),
        argv0=sys.argv[0],
        home=Path.home().resolve(),
        env=dict(os.environ),
        source_root=_find_source_root(module_file),
        current_distribution=_current_distribution_record(),
        active_cli=_active_cli_record(),
    )


def _find_manifest_root(path: Path) -> Path | None:
    resolved = path.expanduser().resolve()
    start = resolved if resolved.is_dir() else resolved.parent
    for parent in (start, *start.parents):
        if (parent / "offline-manifest.json").is_file():
            return parent
        if len(parent.parts) + 8 < len(start.parts):
            break
    return None


def _resolve_install_root(
    install_root: Path | None,
    *,
    context: ProvenanceContext,
) -> tuple[Path | None, str]:
    if install_root is not None:
        return install_root.expanduser().resolve(), "explicit"
    candidates = [context.module_file, context.executable]
    if context.argv0:
        candidates.append(Path(context.argv0))
    cli_path = context.active_cli.get("path")
    if cli_path:
        candidates.append(Path(str(cli_path)))
    env_file = str(context.env.get("PAPER_FETCH_ENV_FILE") or "").strip()
    if env_file:
        candidates.append(Path(env_file))
    for candidate in candidates:
        root = _find_manifest_root(candidate)
        if root is not None:
            return root, "inferred"
    return None, "not_applicable"


def _source_record(context: ProvenanceContext) -> dict[str, Any]:
    if context.source_root is None:
        return {
            "status": "not_applicable",
            "reason_code": "source_checkout_not_detected",
            "version": None,
            "root": None,
            "pyproject_path": None,
        }
    pyproject_path = context.source_root / "pyproject.toml"
    version = _project_version(pyproject_path)
    return {
        "status": "ready" if version else "error",
        "reason_code": (
            "source_version_found" if version else "source_version_unreadable"
        ),
        "version": version,
        "root": str(context.source_root),
        "pyproject_path": str(pyproject_path),
    }


def _project_requirement(
    pyproject_path: Path,
    dependency_name: str,
) -> Requirement | None:
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = payload.get("project")
    if not isinstance(project, Mapping):
        return None
    dependencies = project.get("dependencies")
    if not isinstance(dependencies, list):
        return None
    normalized_dependency = _normalized_name(dependency_name)
    for raw_requirement in dependencies:
        if not isinstance(raw_requirement, str):
            continue
        try:
            requirement = Requirement(raw_requirement)
        except InvalidRequirement:
            continue
        if _normalized_name(requirement.name) == normalized_dependency:
            return requirement
    return None


def _source_project_environment_record(
    context: ProvenanceContext,
) -> dict[str, Any]:
    source_root = context.source_root
    if source_root is None:
        return {
            "status": "not_applicable",
            "reason_code": "source_checkout_not_detected",
            "python_prefix": str(context.sys_prefix),
            "project_venv": None,
            "activation_command": None,
            "mcp": {
                "status": "not_applicable",
                "reason_code": "source_checkout_not_detected",
                "requirement": None,
                "installed_version": None,
            },
            "issues": [],
        }

    project_venv = (source_root / ".venv").resolve()
    active_prefix = context.sys_prefix.expanduser().resolve()
    activation_command = f"source {project_venv / 'bin' / 'activate'}"
    issues: list[dict[str, Any]] = []
    venv_exists = project_venv.is_dir()
    venv_active = not venv_exists or active_prefix == project_venv
    if not venv_active:
        issues.append(
            {
                "severity": "drift",
                "reason_code": "source_checkout_project_venv_not_active",
                "component": "source_project_environment",
                "path": str(active_prefix),
                "expected_prefix": str(project_venv),
                "suggested_action": activation_command,
            }
        )

    pyproject_path = source_root / "pyproject.toml"
    requirement = _project_requirement(pyproject_path, "mcp")
    if requirement is None:
        mcp_record: dict[str, Any] = {
            "status": "not_applicable",
            "reason_code": "project_dependency_not_declared",
            "requirement": None,
            "installed_version": None,
            "pyproject_path": str(pyproject_path),
        }
    else:
        try:
            installed_version = importlib.metadata.version(requirement.name)
        except importlib.metadata.PackageNotFoundError:
            installed_version = None
            mcp_record = {
                "status": "missing",
                "reason_code": "project_dependency_missing",
                "requirement": str(requirement),
                "installed_version": None,
                "pyproject_path": str(pyproject_path),
            }
            issues.append(
                {
                    "severity": "drift",
                    "reason_code": "project_dependency_missing",
                    "component": "project_dependency.mcp",
                    "path": str(active_prefix),
                    "requirement": str(requirement),
                    "suggested_action": activation_command,
                }
            )
        else:
            try:
                compatible = requirement.specifier.contains(
                    Version(installed_version),
                    prereleases=True,
                )
            except InvalidVersion:
                compatible = False
            mcp_record = {
                "status": "ready" if compatible else "incompatible",
                "reason_code": (
                    "project_dependency_compatible"
                    if compatible
                    else "project_dependency_incompatible"
                ),
                "requirement": str(requirement),
                "installed_version": installed_version,
                "pyproject_path": str(pyproject_path),
            }
            if not compatible:
                issues.append(
                    {
                        "severity": "drift",
                        "reason_code": "project_dependency_incompatible",
                        "component": "project_dependency.mcp",
                        "path": str(active_prefix),
                        "requirement": str(requirement),
                        "actual": installed_version,
                        "suggested_action": activation_command,
                    }
                )

    if issues:
        reason_code = str(issues[0]["reason_code"])
        status = "degraded"
    else:
        reason_code = "source_project_environment_verified"
        status = "ready"
    return {
        "status": status,
        "reason_code": reason_code,
        "python_prefix": str(active_prefix),
        "project_venv": str(project_venv) if venv_exists else None,
        "project_venv_exists": venv_exists,
        "project_venv_active": venv_active,
        "activation_command": activation_command,
        "mcp": mcp_record,
        "issues": issues,
    }


def _user_agent_record() -> dict[str, Any]:
    version = (
        DEFAULT_USER_AGENT.removeprefix(_USER_AGENT_PREFIX)
        if DEFAULT_USER_AGENT.startswith(_USER_AGENT_PREFIX)
        else None
    )
    return {
        "status": "ready" if version else "error",
        "reason_code": (
            "default_user_agent_version_found"
            if version
            else "default_user_agent_version_unreadable"
        ),
        "value": DEFAULT_USER_AGENT,
        "version": version,
        "path": str(Path(__file__).with_name("config.py").resolve()),
    }


def _installed_runtime_record(install_root: Path | None) -> dict[str, Any]:
    if install_root is None:
        return {
            "status": "not_applicable",
            "reason_code": "offline_install_root_not_applicable",
            "version": None,
            "root": None,
            "metadata_path": None,
            "package_path": None,
        }
    site_package_candidates = (
        install_root / "runtime" / "site-packages",
        install_root / "runtime" / "Lib" / "site-packages",
    )
    metadata_candidates: list[Path] = []
    for site_packages in site_package_candidates:
        metadata_candidates.extend(
            sorted(site_packages.glob("paper_fetch_skill-*.dist-info/METADATA"))
        )
    if not metadata_candidates:
        return {
            "status": "missing",
            "reason_code": "installed_runtime_metadata_missing",
            "version": None,
            "root": str(install_root),
            "metadata_path": None,
            "package_path": None,
        }
    metadata_path = metadata_candidates[-1].resolve()
    try:
        metadata = Parser().parsestr(metadata_path.read_text(encoding="utf-8"))
    except OSError as error:
        return {
            "status": "error",
            "reason_code": "installed_runtime_metadata_unreadable",
            "version": None,
            "root": str(install_root),
            "metadata_path": str(metadata_path),
            "package_path": None,
            "error_type": error.__class__.__name__,
        }
    version = str(metadata.get("Version") or "").strip() or None
    site_packages = metadata_path.parent.parent
    package_path = site_packages / "paper_fetch" / "__init__.py"
    return {
        "status": "ready" if version and package_path.is_file() else "missing",
        "reason_code": (
            "installed_runtime_metadata_found"
            if version and package_path.is_file()
            else "installed_runtime_package_missing"
        ),
        "version": version,
        "root": str(install_root),
        "metadata_path": str(metadata_path),
        "package_path": str(package_path),
    }


def _manifest_record(
    install_root: Path | None,
    *,
    source_root: Path | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if install_root is None:
        return (
            {
                "status": "not_applicable",
                "reason_code": "source_development_without_offline_manifest",
                "path": None,
                "schema_version": None,
                "version": None,
                "git_revision": None,
                "built_at_utc": None,
                "target": None,
                "entrypoint": None,
                "skill_file_count": None,
            },
            None,
        )
    path = install_root / "offline-manifest.json"
    if not path.is_file():
        source_matches = (
            source_root is not None and install_root == source_root.resolve()
        )
        return (
            {
                "status": "not_applicable" if source_matches else "missing",
                "reason_code": (
                    "source_development_without_offline_manifest"
                    if source_matches
                    else "offline_manifest_missing"
                ),
                "path": str(path),
                "schema_version": None,
                "version": None,
                "git_revision": None,
                "built_at_utc": None,
                "target": None,
                "entrypoint": None,
                "skill_file_count": None,
            },
            None,
        )
    try:
        payload = read_offline_manifest(path)
    except SkillManifestError as error:
        return (
            {
                "status": "error",
                "reason_code": "offline_manifest_invalid",
                "path": str(path),
                "schema_version": None,
                "version": None,
                "git_revision": None,
                "built_at_utc": None,
                "target": None,
                "entrypoint": None,
                "skill_file_count": None,
                "error_type": error.__class__.__name__,
            },
            None,
        )
    skill_bundle = payload.get("skill_bundle")
    files = skill_bundle.get("files") if isinstance(skill_bundle, Mapping) else None
    return (
        {
            "status": "ready",
            "reason_code": "offline_manifest_found",
            "path": str(path.resolve()),
            "schema_version": payload.get("schema_version"),
            "version": str(payload.get("version") or "").strip() or None,
            "git_revision": payload.get("git_revision"),
            "built_at_utc": payload.get("built_at_utc"),
            "target": payload.get("target"),
            "entrypoint": payload.get("entrypoint"),
            "skill_file_count": len(files) if isinstance(files, list) else None,
        },
        payload,
    )


def _entrypoint_record(
    install_root: Path | None,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if install_root is None or manifest is None:
        return {
            "status": "not_applicable",
            "reason_code": "offline_entrypoint_not_applicable",
            "declared": None,
            "declared_path": None,
            "runtime_cli_path": None,
        }
    target = manifest.get("target")
    platform = str(target.get("platform") or "") if isinstance(target, Mapping) else ""
    declared = str(manifest.get("entrypoint") or "").strip() or None
    declared_path = install_root / declared if declared else None
    runtime_cli = (
        install_root
        / "bin"
        / ("paper-fetch.cmd" if platform == "windows" else "paper-fetch")
    )
    runtime_exists = runtime_cli.is_file()
    declared_required = platform != "windows"
    declared_exists = bool(declared_path and declared_path.is_file())
    ready = (
        bool(declared) and runtime_exists and (declared_exists or not declared_required)
    )
    return {
        "status": "ready" if ready else "missing",
        "reason_code": (
            "offline_entrypoints_found" if ready else "offline_entrypoint_missing"
        ),
        "declared": declared,
        "declared_path": str(declared_path) if declared_path else None,
        "declared_expected_in_install_root": declared_required,
        "declared_exists": declared_exists,
        "runtime_cli_path": str(runtime_cli),
        "runtime_cli_exists": runtime_exists,
    }


def _host_skill_paths(
    *,
    context: ProvenanceContext,
    skill_name: str,
) -> tuple[tuple[str, Path], ...]:
    codex_home = Path(context.env.get("CODEX_HOME") or context.home / ".codex")
    antigravity_home = Path(
        context.env.get("ANTIGRAVITY_HOME")
        or context.home / ".gemini" / "antigravity-cli"
    )
    return (
        ("codex", codex_home / "skills" / skill_name),
        ("claude", context.home / ".claude" / "skills" / skill_name),
        ("antigravity", antigravity_home / "skills" / skill_name),
    )


def _source_skill_records(
    *,
    context: ProvenanceContext,
    manifest_record: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if context.source_root is None:
        return (
            {
                "status": "not_applicable",
                "reason_code": "skill_manifest_not_applicable",
                "manifest_path": manifest_record.get("path"),
            },
            [],
        )
    source_skill = context.source_root / "skills" / SKILL_NAME
    if not source_skill.is_dir():
        return (
            {
                "status": "not_applicable",
                "reason_code": "source_skill_not_found",
                "manifest_path": None,
                "skill_root": str(source_skill),
            },
            [],
        )
    try:
        bundle = build_skill_bundle_manifest(
            source_skill,
            name=SKILL_NAME,
            root=f"skills/{SKILL_NAME}",
        )
        bundled = verify_skill_directory(bundle, skill_dir=source_skill)
    except SkillManifestError as error:
        return (
            {
                "status": "missing",
                "reason_code": "source_skill_missing_or_invalid",
                "manifest_path": None,
                "skill_root": str(source_skill),
                "error_type": error.__class__.__name__,
            },
            [],
        )

    project_skill = context.source_root / ".codex" / "skills" / SKILL_NAME
    codex_home = Path(context.env.get("CODEX_HOME") or context.home / ".codex")
    user_skill = codex_home / "skills" / SKILL_NAME
    if project_skill.exists() or project_skill.is_symlink():
        active_skill = project_skill
        scope = "project"
    else:
        active_skill = user_skill
        scope = "user"
    active = verify_skill_directory(bundle, skill_dir=active_skill)
    return bundled, [{"host": "codex", "scope": scope, **active}]


def _skill_records(
    install_root: Path | None,
    manifest_record: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    *,
    context: ProvenanceContext,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if install_root is None or manifest is None:
        return _source_skill_records(
            context=context,
            manifest_record=manifest_record,
        )
    manifest_path = Path(str(manifest_record["path"]))
    try:
        bundled = verify_skill_bundle(manifest_path)
    except SkillManifestError as error:
        return (
            {
                "status": "missing",
                "reason_code": "skill_manifest_missing_or_invalid",
                "manifest_path": str(manifest_path),
                "error_type": error.__class__.__name__,
            },
            [],
        )
    skill_name = str(bundled.get("skill_name") or SKILL_NAME)
    hosts: list[dict[str, Any]] = []
    for host, path in _host_skill_paths(context=context, skill_name=skill_name):
        result = verify_skill_bundle(manifest_path, skill_dir=path)
        hosts.append({"host": host, **result})
    return bundled, hosts


def _component_path(record: Mapping[str, Any]) -> str | None:
    for key in (
        "pyproject_path",
        "metadata_path",
        "path",
        "root",
        "skill_root",
    ):
        value = record.get(key)
        if value:
            return str(value)
    return None


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(root.expanduser().resolve())
    except ValueError:
        return False
    return True


def install_provenance_payload(
    *,
    install_root: Path | None = None,
    context: ProvenanceContext | None = None,
) -> dict[str, Any]:
    """Aggregate source, runtime, PATH, manifest, and host-skill provenance."""

    active_context = context or default_provenance_context()
    resolved_root, root_source = _resolve_install_root(
        install_root,
        context=active_context,
    )
    source = _source_record(active_context)
    source_project_environment = _source_project_environment_record(active_context)
    current_distribution = dict(active_context.current_distribution)
    active_cli = dict(active_context.active_cli)
    user_agent = _user_agent_record()
    manifest_record, manifest = _manifest_record(
        resolved_root,
        source_root=active_context.source_root,
    )
    installed_runtime = _installed_runtime_record(
        resolved_root if manifest is not None else None
    )
    entrypoints = _entrypoint_record(resolved_root, manifest)
    bundled_skill, host_skills = _skill_records(
        resolved_root,
        manifest_record,
        manifest,
        context=active_context,
    )

    version_components: list[tuple[str, Mapping[str, Any]]] = [
        ("source", source),
        ("current_distribution", current_distribution),
        ("offline_manifest", manifest_record),
        ("installed_runtime", installed_runtime),
        ("default_user_agent", user_agent),
        ("active_cli", active_cli),
    ]
    expected_version = next(
        (
            str(record["version"])
            for _name, record in version_components
            if record.get("status") == "ready" and record.get("version")
        ),
        None,
    )
    version_drift: list[dict[str, Any]] = []
    if expected_version:
        for name, record in version_components:
            actual = record.get("version")
            if (
                record.get("status") == "ready"
                and actual
                and actual != expected_version
            ):
                version_drift.append(
                    {
                        "component": name,
                        "expected": expected_version,
                        "actual": str(actual),
                        "path": _component_path(record),
                    }
                )

    issues: list[dict[str, Any]] = [
        {
            "severity": "drift",
            "reason_code": "version_mismatch",
            **item,
        }
        for item in version_drift
    ]
    issues.extend(source_project_environment["issues"])
    if resolved_root is not None and manifest_record["status"] == "missing":
        issues.append(
            {
                "severity": "error",
                "reason_code": "offline_manifest_missing",
                "component": "offline_manifest",
                "path": manifest_record.get("path"),
            }
        )
    elif manifest_record["status"] == "error":
        issues.append(
            {
                "severity": "error",
                "reason_code": "offline_manifest_invalid",
                "component": "offline_manifest",
                "path": manifest_record.get("path"),
            }
        )

    if bundled_skill.get("status") not in {"ready", "not_applicable"}:
        issues.append(
            {
                "severity": "drift",
                "reason_code": str(
                    bundled_skill.get("reason_code") or "skill_bundle_drift"
                ),
                "component": "bundled_skill",
                "path": _component_path(bundled_skill),
            }
        )
    for host_record in host_skills:
        if host_record.get("status") != "ready":
            issues.append(
                {
                    "severity": "drift",
                    "reason_code": str(
                        host_record.get("reason_code") or "host_skill_drift"
                    ),
                    "component": f"host_skill.{host_record.get('host')}",
                    "path": host_record.get("skill_root"),
                    "scope": host_record.get("scope"),
                }
            )

    if manifest is not None:
        assert resolved_root is not None
        for component, record in (
            ("installed_runtime", installed_runtime),
            ("entrypoints", entrypoints),
        ):
            if record.get("status") != "ready":
                issues.append(
                    {
                        "severity": "drift",
                        "reason_code": str(
                            record.get("reason_code") or "component_drift"
                        ),
                        "component": component,
                        "path": _component_path(record),
                    }
                )
        cli_path = active_cli.get("path")
        if active_cli.get("status") != "ready":
            issues.append(
                {
                    "severity": "drift",
                    "reason_code": str(
                        active_cli.get("reason_code") or "path_cli_not_ready"
                    ),
                    "component": "active_cli",
                    "path": cli_path,
                }
            )
        elif cli_path and not _path_is_within(Path(str(cli_path)), resolved_root):
            issues.append(
                {
                    "severity": "drift",
                    "reason_code": "active_cli_outside_install_root",
                    "component": "active_cli",
                    "path": str(cli_path),
                    "expected_root": str(resolved_root),
                }
            )

    if any(item["severity"] == "error" for item in issues):
        status = "error"
        reason_code = "install_provenance_error"
    elif issues:
        status = "drift"
        reason_code = "install_provenance_drift"
    elif manifest is None:
        if bundled_skill.get("status") == "ready":
            status = "ready"
            reason_code = "source_skill_verified_without_offline_manifest"
        else:
            status = "not_applicable"
            reason_code = "source_development_without_offline_manifest"
    else:
        status = "ready"
        reason_code = "install_provenance_verified"

    return {
        "schema_version": 1,
        "status": status,
        "reason_code": reason_code,
        "requested_install_root": str(install_root) if install_root else None,
        "resolved_install_root": str(resolved_root) if resolved_root else None,
        "install_root_source": root_source,
        "invocation": {
            "python_executable": str(active_context.executable),
            "python_prefix": str(active_context.sys_prefix),
            "argv0": active_context.argv0,
            "module_path": str(active_context.module_file),
        },
        "source": source,
        "source_project_environment": source_project_environment,
        "current_distribution": current_distribution,
        "default_user_agent": user_agent,
        "active_cli": active_cli,
        "offline_manifest": manifest_record,
        "installed_runtime": installed_runtime,
        "entrypoints": entrypoints,
        "bundled_skill": bundled_skill,
        "host_skills": host_skills,
        "consistency": {
            "expected_version": expected_version,
            "version_status": "drift" if version_drift else "ready",
            "version_drift": version_drift,
            "issue_count": len(issues),
        },
        "issues": issues,
    }


__all__ = [
    "DIST_NAME",
    "ProvenanceContext",
    "default_provenance_context",
    "install_provenance_payload",
]
