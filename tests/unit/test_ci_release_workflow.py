from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SETUP_ACTION = REPO_ROOT / ".github" / "actions" / "setup-python-deps" / "action.yml"


def _load(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _workflow(name: str) -> dict:
    return _load(WORKFLOWS / name)


def _steps(job: Mapping[str, object]) -> Iterable[Mapping[str, object]]:
    steps = job.get("steps", [])
    assert isinstance(steps, list)
    return (step for step in steps if isinstance(step, Mapping))


def test_all_workflow_yaml_loads() -> None:
    paths = list(WORKFLOWS.glob("*.yml"))
    assert paths
    for path in paths:
        _load(path)


def test_external_actions_are_pinned_to_full_commit_shas() -> None:
    paths = [*WORKFLOWS.glob("*.yml"), SETUP_ACTION]
    for path in paths:
        payload = path.read_text(encoding="utf-8")
        for line in payload.splitlines():
            stripped = line.strip()
            if not stripped.startswith("uses: ") or stripped.startswith("uses: ./"):
                continue
            reference = stripped.split("#", 1)[0].strip().rsplit("@", 1)[-1]
            assert len(reference) == 40, (path, stripped)
            assert all(character in "0123456789abcdef" for character in reference)


def test_workflow_checkouts_do_not_persist_credentials() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        workflow = _load(path)
        for job in workflow.get("jobs", {}).values():
            if not isinstance(job, Mapping):
                continue
            for step in _steps(job):
                if not str(step.get("uses") or "").startswith("actions/checkout@"):
                    continue
                assert (step.get("with") or {}).get("persist-credentials") is False


def test_reusable_builds_require_immutable_source_and_drop_checkout_credentials() -> (
    None
):
    for name in ("verify.yml", "package.yml"):
        workflow = _workflow(name)
        inputs = workflow[True]["workflow_call"]["inputs"]
        assert inputs["ref"]["required"] is True
        for job in workflow["jobs"].values():
            if "uses" in job:
                continue
            checkouts = [
                step
                for step in _steps(job)
                if str(step.get("uses") or "").startswith("actions/checkout@")
            ]
            assert checkouts
            for checkout in checkouts:
                options = checkout.get("with", {})
                assert options.get("ref") == "${{ inputs.ref }}"
                assert options.get("persist-credentials") is False

    package_text = (WORKFLOWS / "package.yml").read_text(encoding="utf-8")
    assert '[[ ! "$SOURCE_REF" =~ ^[0-9a-f]{40}$ ]]' in package_text
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_REF"' in package_text


def test_stable_release_grants_write_permissions_only_to_publish_job() -> None:
    workflow = _workflow("release.yml")
    assert workflow["permissions"] == {"contents": "read"}
    elevated: dict[str, object] = {}
    for name, job in workflow["jobs"].items():
        permissions = job.get("permissions", {})
        if any(value == "write" for value in permissions.values()):
            elevated[name] = permissions

    assert elevated == {
        "publish": {
            "contents": "write",
            "id-token": "write",
            "attestations": "write",
        }
    }


def test_stable_publish_requires_integrity_scan_and_provenance() -> None:
    publish = _workflow("release.yml")["jobs"]["publish"]
    steps = list(_steps(publish))
    commands = "\n".join(str(step.get("run") or "") for step in steps)
    action_uses = [str(step.get("uses") or "") for step in steps]

    assert "scripts/prepare_release_assets.py prepare-stable" in commands
    assert "release-assets/SHA256SUMS" in commands
    assert "scripts/scan_artifacts_for_secrets.py" in commands
    assert any(
        use.startswith("actions/attest-build-provenance@") for use in action_uses
    )
    publish_steps = [
        index
        for index, step in enumerate(steps)
        if "gh release" in str(step.get("run") or "")
    ]
    assert publish_steps
    publish_index = publish_steps[-1]
    assert all(
        next(
            index
            for index, step in enumerate(steps)
            if marker in str(step.get("run") or "")
            or marker in str(step.get("uses") or "")
        )
        < publish_index
        for marker in (
            "scripts/prepare_release_assets.py",
            "scripts/scan_artifacts_for_secrets.py",
            "actions/attest-build-provenance@",
        )
    )


def test_supported_python_and_native_macos_matrix_remains_explicit() -> None:
    offline = _workflow("offline.yml")
    includes = offline["jobs"]["posix"]["strategy"]["matrix"]["include"]
    macos_versions = {
        str(item["python-version"]) for item in includes if item.get("os") == "macos-15"
    }
    assert macos_versions == {"3.11", "3.12", "3.13", "3.14"}

    verify = _workflow("verify.yml")
    python_versions = verify["jobs"]["python-boundaries"]["strategy"]["matrix"][
        "python-version"
    ]
    assert {str(version) for version in python_versions} == {"3.11", "3.14"}
    native_macos = verify["jobs"]["macos-native"]
    assert native_macos["runs-on"] == "macos-15"
    setup = next(
        step
        for step in _steps(native_macos)
        if str(step.get("uses") or "").startswith("./.github/actions/setup-python-deps")
    )
    assert str(setup["with"]["python-version"]) == "3.14"


def test_locked_dependency_audit_covers_all_extras_and_fails_directly() -> None:
    for name, job_name in (
        ("verify.yml", "quality"),
        ("dependency-refresh.yml", "latest-compatible"),
    ):
        job = _workflow(name)["jobs"][job_name]
        commands = "\n".join(str(step.get("run") or "") for step in _steps(job))
        assert "uv export --locked --all-extras" in commands
        assert "python -m pip_audit" in commands
        assert all(step.get("continue-on-error") is not True for step in _steps(job))


def test_python_boundaries_build_once_then_smoke_core_and_full() -> None:
    job = _workflow("verify.yml")["jobs"]["python-boundaries"]
    matrix = job["strategy"]["matrix"]
    assert set(matrix) == {"python-version"}

    commands = [str(step.get("run") or "") for step in _steps(job)]
    assert sum("uv build --wheel" in command for command in commands) == 1
    smoke = next(command for command in commands if "wheel[full]" in command)
    assert "for install_kind in core full" in smoke
    assert "python -m venv" in smoke
