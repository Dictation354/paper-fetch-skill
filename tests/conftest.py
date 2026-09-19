"""Global pytest safety policy.

The test process must never inherit paper-fetch's real user data directories.
Unit tests additionally fail closed when they attempt external networking,
browser/runtime launch, or an unapproved subprocess.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from platformdirs import user_data_path
import pytest

from tests._environment import (
    PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR,
    PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR,
    PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR,
)


pytest_plugins = ["tests.support.test_evidence"]


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
    from tests.support import layer_policy

    layer_policy.install()
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
        if "unit" in path.parts:
            for marker in ("browser", "live", "allow_subprocess"):
                if item.get_closest_marker(marker):
                    raise pytest.UsageError(
                        f"unit boundary: {item.nodeid}: forbidden marker {marker}"
                    )
        if "live" in path.parts:
            item.add_marker(pytest.mark.live)
        if item.get_closest_marker("live") or item.get_closest_marker("browser"):
            item.add_marker(pytest.mark.enable_socket)


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector):
    from tests.support import layer_policy

    previous = layer_policy.UNIT_NODE
    if "unit" in Path(str(collector.path)).parts:
        layer_policy.UNIT_NODE = str(collector.nodeid)
    try:
        return (yield)
    finally:
        layer_policy.UNIT_NODE = previous


@pytest.fixture(autouse=True)
def _paper_fetch_test_safety(request, monkeypatch):
    """Unit tests cannot opt out of process, replay, or conversion boundaries."""
    from tests.support import layer_policy

    if "unit" not in Path(str(request.node.path)).parts:
        yield
        return
    layer_policy.UNIT_NODE = request.node.nodeid
    from paper_fetch.providers import _playwright_browser, _pdf_common

    def blocked(*args: Any, **kwargs: Any) -> None:
        layer_policy.reject("real browser runtime")

    monkeypatch.setattr(_playwright_browser, "open_browser_context", blocked)
    original = _pdf_common._call_pdf_renderer_with_tessdata_retry

    def guarded_renderer(renderer, *args, **kwargs):
        if str(getattr(renderer, "__module__", "")).startswith("pymupdf"):
            layer_policy.reject("real PDF conversion")
        return original(renderer, *args, **kwargs)

    monkeypatch.setattr(
        _pdf_common, "_call_pdf_renderer_with_tessdata_retry", guarded_renderer
    )
    for name, module in tuple(sys.modules.items()):
        if name.startswith("pymupdf4llm") and hasattr(module, "to_markdown"):

            def blocked_converter(*args, **kwargs):
                layer_policy.reject("real PDF conversion")

            monkeypatch.setattr(module, "to_markdown", blocked_converter)
    try:
        yield
    finally:
        layer_policy.UNIT_NODE = None


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
