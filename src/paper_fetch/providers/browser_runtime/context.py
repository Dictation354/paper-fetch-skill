"""Open backend-specific Playwright contexts behind one small facade."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from .types import BrowserRuntimeConfig, BrowserRuntimeSession

if TYPE_CHECKING:
    from ...runtime import RuntimeContext


def open_browser_context(
    config: BrowserRuntimeConfig,
    *,
    runtime_context: RuntimeContext | Any | None = None,
) -> tuple[Any | None, Any]:
    """Return an owned persistent context, or borrow the runtime-owned context."""

    if runtime_context is not None:
        factory = getattr(
            runtime_context, "new_browser_context_for_runtime_config", None
        )
        if not callable(factory):
            raise RuntimeError(
                "Runtime context does not support publisher browser contexts."
            )
        return None, factory(config)
    from .api import create_runtime_manager

    manager = create_runtime_manager(config)
    try:
        return manager, manager.new_context()
    except BaseException:
        manager.close()
        raise


@contextlib.contextmanager
def browser_context(
    config: BrowserRuntimeConfig,
    *,
    runtime_context: RuntimeContext | Any | None = None,
):
    """Yield the persistent context; close only a locally owned manager."""

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
        if manager is not None:
            with contextlib.suppress(Exception):
                manager.close()
