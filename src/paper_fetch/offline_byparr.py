"""Prepare the managed Byparr component and validate a temporary shared page."""

from __future__ import annotations

import platform
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .config import resolve_user_data_dir
from .providers.browser_runtime import byparr_preparation as preparation
from .providers.browser_runtime.backends.byparr import DEFAULT_BYPARR_BACKEND
from .providers.browser_runtime.byparr_manager import ByparrManager
from .providers.browser_runtime.platforms import supported_platform
from .providers.browser_runtime.types import BrowserRuntimeFailure

if TYPE_CHECKING:
    from .offline_setup import Setup


def local_check(env, runtime: Path):
    with tempfile.TemporaryDirectory(prefix="paper-fetch-byparr-check-") as directory:
        config = DEFAULT_BYPARR_BACKEND.load_runtime_config(
            env, provider="pnas", doi="probe://byparr/install"
        )
        from dataclasses import replace

        config = replace(
            config,
            timeout_ms=120000,
            user_data_dir=Path(directory),
            storage_state_path=None,
            persist_storage_state=False,
        )
        manager = ByparrManager(config, local_check=True)
        try:
            context = manager.new_context(prepared=runtime)
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.goto("about:blank", timeout=int(manager.budget.remaining() * 1000))
            page.wait_for_function(
                "() => 1 + 1 === 2",
                timeout=max(1, int(manager.budget.remaining() * 1000)),
            )
            manager.budget.check()
        finally:
            manager.close()


def prepare(
    setup: Setup, *, interactive: bool, system_dependencies: bool = True
) -> None:
    del (
        interactive,
        system_dependencies,
    )  # Libraries are handled by shared browser preparation.
    if setup.env.get("PAPER_FETCH_CHROME_BINARY_PATH", "").strip() or any(
        key.startswith("PAPER_FETCH_")
        and key.endswith("_BROWSER_BACKEND")
        and value.strip().lower() == "flaresolverr"
        for key, value in setup.env.items()
    ):
        setup.report(
            "Byparr",
            "not ready",
            "FlareSolverr configuration was removed; select auto/byparr, remove PAPER_FETCH_CHROME_BINARY_PATH and use PAPER_FETCH_BROWSER_BINARY_PATH for Camoufox. See docs/browser-backends.md#migration.",
        )
        return
    if not supported_platform():
        setup.report("Byparr", "skipped", "Unsupported Camoufox/Byparr platform")
        return
    if platform.python_implementation() != "CPython" or not (3, 11) <= sys.version_info[
        :2
    ] <= (3, 14):
        setup.report("Python", "unsupported", "Requires CPython 3.11–3.14")
        setup.report("Byparr", "not ready", "Requires CPython 3.11–3.14")
        return
    try:
        config = DEFAULT_BYPARR_BACKEND.load_runtime_config(
            setup.env, provider="pnas", doi="probe://byparr/install"
        )
        DEFAULT_BYPARR_BACKEND.ensure_runtime_ready(config)
        cache = (
            config.component_cache_dir or resolve_user_data_dir(setup.env) / "byparr"
        )
        setup.report(
            "Byparr cache", "preparing", f"{cache}; download budget 10 minutes"
        )
        runtime = preparation.prepare_components(
            cache, preparation.PreparationBudget(600)
        )
        setup.report(
            "Byparr local launch",
            "checking",
            "Shared Camoufox/about:blank only; budget 2 minutes",
        )
        local_check(setup.env, runtime)
        setup.report("Byparr", "ready", "Byparr 3.1.1; shared page verified")
    except (KeyboardInterrupt, EOFError):
        setup.report("Byparr", "not ready", "Cancelled; core installation is preserved")
    except BrowserRuntimeFailure as exc:
        setup.report(
            "Byparr", "not ready", exc.kind + "; core installation is preserved"
        )
    except Exception as exc:
        setup.report(
            "Byparr",
            "not ready",
            type(exc).__name__ + "; core installation is preserved",
        )
