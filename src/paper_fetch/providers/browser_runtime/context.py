"""Open backend-specific Playwright contexts behind one small facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import contextlib

from . import paths
from .camoufox_manager import CamoufoxBrowserManager
from .types import BrowserRuntimeConfig, BrowserRuntimeSession

if TYPE_CHECKING:
    from ...runtime import RuntimeContext


def context_options_for_config(config: BrowserRuntimeConfig) -> dict[str, Any]:
    """Build context options without overriding Camoufox fingerprint values."""

    if config.backend != "camoufox":
        raise RuntimeError(f"Unsupported browser backend {config.backend!r}.")
    storage_options = paths.storage_context_options(config)
    return {"accept_downloads": True, **storage_options}


def open_browser_context(
    config: BrowserRuntimeConfig,
    *,
    runtime_context: RuntimeContext | Any | None = None,
) -> tuple[Any | None, Any]:
    """Return ``(owned manager, fresh context)`` for the selected backend."""

    if config.backend != "camoufox":
        raise RuntimeError(f"Unsupported browser backend {config.backend!r}.")
    context_kwargs = context_options_for_config(config)
    manager: Any
    if runtime_context is not None:
        from ...runtime import RuntimeContext

        if isinstance(runtime_context, RuntimeContext):
            return None, runtime_context.new_browser_context_for_runtime_config(
                config, **context_kwargs
            )
        generic_factory = getattr(
            runtime_context, "new_browser_context_for_runtime_config", None
        )
        if callable(generic_factory):
            return None, generic_factory(config, **context_kwargs)
        raise RuntimeError(
            f"Runtime context does not support browser backend {config.backend!r}."
        )

    manager = CamoufoxBrowserManager(
        binary_path=config.binary_path,
        headless=config.headless,
    )
    return manager, manager.new_context(**context_kwargs)


@contextlib.contextmanager
def browser_context(
    config: BrowserRuntimeConfig,
    *,
    runtime_context: RuntimeContext | Any | None = None,
):
    """Yield a fresh context for the explicitly selected backend and close it safely."""

    manager = None
    context = None
    try:
        manager, context = open_browser_context(
            config,
            runtime_context=runtime_context,
        )
        yield BrowserRuntimeSession(
            backend=config.backend,
            context=context,
            manager=manager,
        )
    finally:
        for value in (context, manager):
            if value is not None:
                with contextlib.suppress(Exception):
                    value.close()
