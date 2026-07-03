"""CloakBrowser backend for the browser runtime facade."""

from __future__ import annotations

from dataclasses import replace
import time
from typing import Any
from collections.abc import Mapping

from ....reason_codes import ERROR, OK, READY
from ....runtime_browser import browser_context_options
from ....utils import normalize_text
from ... import _cloakbrowser
from ...base import ProviderStatusResult, build_provider_status_check
from .. import paths as runtime_paths
from ..types import BrowserFetchedHtml, BrowserRuntimeConfig


class CloakBrowserBackend:
    name = "cloakbrowser"

    def load_runtime_config(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str,
        require_storage_state: bool = False,
    ) -> BrowserRuntimeConfig:
        return _cloakbrowser.load_runtime_config(
            env,
            provider=provider,
            doi=doi,
            require_storage_state=require_storage_state,
        )

    def ensure_runtime_ready(self, config: BrowserRuntimeConfig) -> None:
        _cloakbrowser.ensure_runtime_ready(config)

    def probe_runtime_status(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str = _cloakbrowser.CLOAKBROWSER_STATUS_PROBE_ID,
        deep: bool = False,
    ) -> ProviderStatusResult:
        result = _cloakbrowser.probe_runtime_status(env, provider=provider, doi=doi)
        if not deep:
            return result
        return self._with_deep_probe(result, env, provider=provider, doi=doi)

    def _with_deep_probe(
        self,
        result: ProviderStatusResult,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str,
    ) -> ProviderStatusResult:
        manager = None
        context = None
        started = time.monotonic()
        try:
            config = self.load_runtime_config(env, provider=provider, doi=doi)
            self.ensure_runtime_ready(config)
            from ....runtime_browser import BrowserContextManager

            manager = BrowserContextManager(
                binary_path=config.binary_path,
                cdp_endpoint=config.cdp_endpoint,
                profile_dir=config.profile_dir,
                user_data_dir=config.user_data_dir,
            )
            context = manager.new_context(
                headless=config.headless,
                **browser_context_options(
                    user_agent=normalize_text(config.user_agent),
                    **self.storage_context_options(config),
                ),
            )
            check = build_provider_status_check(
                "cdp_connection",
                OK,
                "CDP browser context can be created.",
                details={
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "external_cdp": bool(config.cdp_endpoint),
                    "storage_state_path": str(self.storage_state_path(config) or ""),
                },
            )
        except Exception as exc:
            check = build_provider_status_check(
                "cdp_connection",
                ERROR,
                normalize_text(str(exc)) or exc.__class__.__name__,
                details={"duration_seconds": round(time.monotonic() - started, 3)},
            )
        finally:
            for value in (context, manager):
                try:
                    if value is not None:
                        value.close()
                except Exception:
                    pass

        checks = [*result.checks, check]
        status = ERROR if check.status == ERROR else result.status
        return replace(
            result,
            checks=checks,
            status=status,
            available=status == READY,
        )

    def fetch_html(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        **kwargs: Any,
    ) -> BrowserFetchedHtml:
        return _cloakbrowser.fetch_html_with_cloakbrowser(
            candidate_urls,
            publisher=publisher,
            config=config,
            **kwargs,
        )

    def warm_context(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        browser_context_seed: Mapping[str, Any] | None = None,
        runtime_context: Any | None = None,
        lightweight: bool = False,
    ) -> dict[str, Any]:
        return _cloakbrowser.warm_browser_context_with_cloakbrowser(
            candidate_urls,
            publisher=publisher,
            config=config,
            browser_context_seed=browser_context_seed,
            runtime_context=runtime_context,
            lightweight=lightweight,
        )

    def storage_state_path(self, config: BrowserRuntimeConfig):
        return runtime_paths.storage_state_path(config)

    def storage_context_options(self, config: BrowserRuntimeConfig) -> dict[str, Any]:
        return runtime_paths.storage_context_options(config)

    def save_storage_state(
        self,
        context: Any,
        config: BrowserRuntimeConfig,
        *,
        filter_url: str | None = None,
    ) -> Mapping[str, Any]:
        return runtime_paths.save_storage_state(
            context,
            config,
            filter_url=filter_url,
        )


DEFAULT_CLOAKBROWSER_BACKEND = CloakBrowserBackend()
