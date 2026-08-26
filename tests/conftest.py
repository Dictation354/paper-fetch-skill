"""Global pytest safety policy.

The test process must never inherit paper-fetch's real user data directories.
Unit tests additionally fail closed when they attempt external networking,
browser/runtime launch, or an unapproved subprocess.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any
from collections.abc import Iterator

from platformdirs import user_data_path
import pytest

from tests._environment import (
    PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR,
    PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR,
    PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR,
    TEST_ENVIRONMENT_REPAIR,
    locked_test_dependency_issues,
)


_REAL_USER_DATA_DIR = Path(user_data_path("paper-fetch", appauthor=False))
_ISOLATED_ENV_VARS = (
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_RUNTIME_DIR",
    "PAPER_FETCH_DOWNLOAD_DIR",
    "PAPER_FETCH_BROWSER_PROFILE_DIR",
    "PAPER_FETCH_BROWSER_USER_DATA_DIR",
    "PAPER_FETCH_FORMULA_TOOLS_DIR",
    "PAPER_FETCH_IMAGE_TOOLS_DIR",
)
_SAFE_SUBPROCESS_NAMES = frozenset(
    {
        Path(sys.executable).name,
        "bash",
        "git",
        "python",
        "python3",
        "sh",
        "zsh",
    }
)


def _worker_id(config: pytest.Config) -> str:
    worker_input = getattr(config, "workerinput", None)
    if isinstance(worker_input, dict):
        return str(worker_input.get("workerid") or "worker")
    return "controller"


def _snapshot_tree(root: Path) -> dict[str, tuple[int, int, int]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[int, int, int]] = {}
    for path in sorted(root.rglob("*")):
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot[str(path.relative_to(root))] = (
            stat.st_mode,
            stat.st_size,
            stat.st_mtime_ns,
        )
    return snapshot


def _preserve_installed_camoufox_executable() -> None:
    """Retain the prepared runtime while pytest isolates writable cache roots."""

    preserved_executable = os.environ.get(
        PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR, ""
    ).strip()
    preserved_cache_home = os.environ.get(
        PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR, ""
    ).strip()
    if preserved_executable and preserved_cache_home:
        return
    try:
        from camoufox import pkgman

        if preserved_executable:
            executable = Path(preserved_executable)
        else:
            runtime_path = pkgman.camoufox_path(download_if_missing=False)
            executable = Path(pkgman.launch_path(runtime_path))
    except Exception:
        return
    if executable.is_file() and (os.name == "nt" or os.access(executable, os.X_OK)):
        os.environ[PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR] = str(executable)
        os.environ[PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR] = str(
            Path(pkgman.INSTALL_DIR).parent
        )


def _preserve_explicit_formula_tools_dir() -> None:
    """Retain an explicitly prepared read-only formula backend for live tests."""

    if os.environ.get(PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR, "").strip():
        return
    configured = os.environ.get("PAPER_FETCH_FORMULA_TOOLS_DIR", "").strip()
    if not configured:
        return
    candidate = Path(configured).expanduser().resolve()
    if candidate.is_dir():
        os.environ[PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR] = str(candidate)


def pytest_configure(config: pytest.Config) -> None:
    dependency_issues = locked_test_dependency_issues()
    if dependency_issues:
        raise pytest.UsageError(
            "Incompatible ambient test environment: "
            + "; ".join(dependency_issues)
            + f". Repair with: {TEST_ENVIRONMENT_REPAIR}"
        )
    config.addinivalue_line(
        "markers",
        "browser: test intentionally exercises a real browser/runtime boundary",
    )
    config.addinivalue_line(
        "markers",
        "live: test intentionally depends on live network/provider state",
    )
    config.addinivalue_line(
        "markers",
        "allow_subprocess: test intentionally launches non-allowlisted executables",
    )
    config.addinivalue_line(
        "markers",
        "socket_adapter: test intentionally exercises a socket adapter boundary",
    )

    worker = _worker_id(config)
    _preserve_installed_camoufox_executable()
    _preserve_explicit_formula_tools_dir()
    isolated_root = Path(tempfile.mkdtemp(prefix=f"paper-fetch-tests-{worker}-"))
    config._paper_fetch_isolated_root = isolated_root
    for name in _ISOLATED_ENV_VARS:
        value = isolated_root / name.lower().replace("_", "-")
        value.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(value)
    os.environ["TEXMATH_BIN"] = str(isolated_root / "unavailable-texmath")
    os.environ["MATHML_TO_LATEX_NODE_BIN"] = str(isolated_root / "unavailable-node")
    os.environ["PAPER_FETCH_GHOSTSCRIPT_BIN"] = str(
        isolated_root / "unavailable-ghostscript"
    )
    os.environ["PAPER_FETCH_VIPS_BIN"] = str(isolated_root / "unavailable-vips")

    if worker == "controller":
        config._paper_fetch_real_user_data_snapshot = _snapshot_tree(
            _REAL_USER_DATA_DIR
        )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path))
        if "live" in path.parts:
            item.add_marker(pytest.mark.live)
        if item.get_closest_marker("live") or item.get_closest_marker("browser"):
            item.add_marker(pytest.mark.enable_socket)


@pytest.fixture(autouse=True)
def _paper_fetch_test_safety(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Block unsafe process launches for ordinary unit tests."""

    if request.node.get_closest_marker("live") or request.node.get_closest_marker(
        "browser"
    ):
        return

    if "unit" not in Path(str(request.node.path)).parts:
        return

    if request.node.get_closest_marker("allow_subprocess"):
        return

    from paper_fetch.providers import _playwright_browser

    def blocked_browser_context(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError(
            f"{request.node.nodeid} attempted a real browser runtime. "
            "Mock open_browser_context or mark the test browser."
        )

    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        blocked_browser_context,
    )

    real_popen = subprocess.Popen

    def guarded_popen(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        command = kwargs.get("args", args[0] if args else None)
        executable: object | None
        if isinstance(command, (list, tuple)) and command:
            executable = command[0]
        else:
            executable = command
        name = Path(os.fspath(executable)).name if executable is not None else ""
        if name not in _SAFE_SUBPROCESS_NAMES:
            raise AssertionError(
                f"{request.node.nodeid} attempted non-allowlisted subprocess: {name!r}. "
                "Mock the process boundary or mark the test allow_subprocess."
            )
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", guarded_popen)


@pytest.fixture(autouse=True)
def _unit_socket_attempt_guard(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Fail unit tests that swallow pytest-socket connection failures."""

    if (
        request.node.get_closest_marker("live")
        or request.node.get_closest_marker("browser")
        or request.node.get_closest_marker("socket_adapter")
        or "unit" not in Path(str(request.node.path)).parts
    ):
        yield
        return

    attempts: list[tuple[str, object]] = []
    current_connect = socket.socket.connect

    def tracked_connect(instance: socket.socket, address: object) -> None:
        attempts.append(("connect", address))
        return current_connect(instance, address)

    def tracked_connect_ex(instance: socket.socket, address: object) -> int:
        attempts.append(("connect_ex", address))
        try:
            current_connect(instance, address)
        except OSError as error:
            return int(error.errno or 1)
        return 0

    monkeypatch.setattr(socket.socket, "connect", tracked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", tracked_connect_ex)
    yield
    if attempts:
        attempted_methods = ", ".join(method for method, _address in attempts)
        pytest.fail(
            f"{request.node.nodeid} attempted socket connection(s): "
            f"{attempted_methods}. Mock the boundary or mark a socket-adapter test."
        )


def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int
) -> None:  # pragma: no cover - pytest lifecycle hook
    del exitstatus
    config = session.config
    before = getattr(config, "_paper_fetch_real_user_data_snapshot", None)
    if before is None:
        return
    after = _snapshot_tree(_REAL_USER_DATA_DIR)
    if after != before:
        changed = sorted(
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        )
        pytest.exit(
            "Tests modified the real paper-fetch user data directory: "
            f"{_REAL_USER_DATA_DIR}. Changed entries: " + ", ".join(changed[:20]),
            returncode=1,
        )


def pytest_unconfigure(config: pytest.Config) -> None:
    isolated_root = getattr(config, "_paper_fetch_isolated_root", None)
    if isinstance(isolated_root, Path):
        shutil.rmtree(isolated_root, ignore_errors=True)
