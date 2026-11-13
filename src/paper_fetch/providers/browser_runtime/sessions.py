"""Thread-affine browser sessions owned by a single request."""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...runtime import RuntimeContext


@dataclass
class BrowserSessions:
    lock: threading.RLock = field(default_factory=threading.RLock)
    managers: dict[tuple[int, bool, str], Any] = field(default_factory=dict)

    def new_browser_context_for_runtime_config(
        self,
        config: Any,
        *,
        runtime_context: RuntimeContext,
        **context_kwargs: Any,
    ) -> Any:
        """Borrow the publisher's thread-affine persistent context."""

        from .profile import (
            profile_path,
        )

        from dataclasses import replace

        config = replace(config, backend="byparr")
        path = profile_path(config)
        key = (threading.get_ident(), bool(config.headless), str(path))
        with self.lock:
            manager = self.managers.get(key)
            if manager is not None and manager.config.provider != config.provider:
                from .types import BrowserRuntimeFailure

                raise BrowserRuntimeFailure(
                    "browser_profile_provider_conflict",
                    f"Publisher profile {path} belongs to {manager.config.provider}; cannot use it for {config.provider}.",
                )
            if manager is not None and (
                manager.config.backend != config.backend
                or manager.config.binary_path != config.binary_path
            ):
                raise RuntimeError(
                    f"Conflicting browser executable for native profile: {path}"
                )
            if manager is None:
                # Release the prior publisher before waiting for another directory.
                # This prevents two requests from holding opposite profile leases.
                self.close_camoufox_for_current_thread(runtime_context)
                from .api import _backend

                manager = _backend(config.backend).create_manager(
                    config, runtime_context=runtime_context
                )
                self.managers[key] = manager
        try:
            return manager.new_context()
        except BaseException:
            with self.lock:
                self.managers.pop(key, None)
            manager.close()
            raise

    def refresh_browser_profiles(self) -> None:
        for key, manager in list(self.managers.items()):
            if key[0] == threading.get_ident():
                manager.refresh()

    def browser_profile_diagnostics(self, context: Any) -> dict[str, Any]:
        for manager in self.managers.values():
            if manager.context is context:
                return dict(manager.diagnostics)
        return {}

    def close_browser(self, runtime_context: RuntimeContext) -> None:
        """Close Camoufox managers owned by this runtime context."""

        self.close_camoufox_for_current_thread(runtime_context)

    def close_camoufox_for_current_thread(
        self, runtime_context: RuntimeContext
    ) -> None:
        """Close Camoufox managers while still on their owning worker thread."""

        owner_thread_id = threading.get_ident()
        with self.lock:
            owned_items = [
                (key, manager)
                for key, manager in self.managers.items()
                if key[0] == owner_thread_id
            ]
        seen: set[int] = set()
        try:
            for _key, manager in owned_items:
                if id(manager) in seen:
                    continue
                seen.add(id(manager))
                # Keep the manager handle visible until its owner has closed all
                # pages. A concurrent outer close must fence, never close them.
                with runtime_context._session_cache_lock:
                    cached = list(runtime_context.session_cache.items())
                for cache_key, value in cached:
                    if (
                        manager.context is not None
                        and getattr(value, "context", None) is manager.context
                    ):
                        close = getattr(value, "close", None)
                        if callable(close):
                            with contextlib.suppress(Exception):
                                close()
                        with runtime_context._session_cache_lock:
                            runtime_context.session_cache.pop(cache_key, None)
                manager.close()
        finally:
            with self.lock:
                for key, manager in owned_items:
                    if self.managers.get(key) is manager:
                        self.managers.pop(key, None)
