"""Opaque cache scopes derived from capabilities actually available to a request."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .provider_catalog import ordered_provider_specs, provider_has_browser_route
from .providers.browser_runtime import paths as browser_paths
from .publisher_identity import (
    extract_doi,
    infer_provider_from_doi,
    infer_provider_from_url,
)
from .utils import normalize_text

PUBLIC_CAPABILITY_SCOPE = "public"
UNCACHEABLE_CAPABILITY_SCOPE = "browser-state-unavailable"
_CREDENTIAL_ENV_TOKENS = ("API_KEY", "APIKEY", "TOKEN", "ACCESS_KEY", "SECRET")


def _file_sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def browser_profile_digest(path: Path, provider: str) -> str | None:
    from .providers.browser_runtime.profile import trusted_profile_digest

    return trusted_profile_digest(path, provider)


def _resolved_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


@dataclass(frozen=True, slots=True)
class BrowserStateCapabilityUse:
    """A provider profile that was actually opened, with its observed state digest."""

    provider: str
    backend: str
    storage_state_path: str
    content_sha256: str | None
    used: bool = True

    @classmethod
    def from_path(
        cls,
        *,
        provider: str,
        backend: str,
        storage_state_path: Path | str,
        used: bool = True,
    ) -> BrowserStateCapabilityUse:
        path = _resolved_path(storage_state_path)
        return cls(
            provider=normalize_text(provider).lower(),
            backend=normalize_text(backend).lower(),
            storage_state_path=str(path),
            content_sha256=(
                browser_profile_digest(path, provider)
                if path.is_dir()
                else _file_sha256(path)
            ),
            used=bool(used),
        )


class CapabilityScopeBuilder:
    """Build stable opaque scopes for API and browser-backed capabilities.

    Browser state is included after the native context has actually opened.
    Runtime callers refresh the context summary before building a scope; idle
    readers validate the on-disk summary against native state changes.
    """

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env or {})
        self._browser_uses: list[BrowserStateCapabilityUse] = []

    def add_browser_state_use(
        self, use: BrowserStateCapabilityUse | Mapping[str, Any]
    ) -> CapabilityScopeBuilder:
        if isinstance(use, BrowserStateCapabilityUse):
            normalized = use
        else:
            path = normalize_text(str(use.get("storage_state_path") or ""))
            if not path:
                return self
            normalized = BrowserStateCapabilityUse(
                provider=normalize_text(str(use.get("provider") or "")).lower(),
                backend=normalize_text(str(use.get("backend") or "")).lower(),
                storage_state_path=str(_resolved_path(path)),
                content_sha256=(
                    normalize_text(str(use.get("content_sha256") or "")) or None
                ),
                used=bool(use.get("used")),
            )
        if normalized.used:
            self._browser_uses.append(normalized)
        return self

    def add_browser_state_uses(
        self,
        uses: Iterable[BrowserStateCapabilityUse | Mapping[str, Any]],
    ) -> CapabilityScopeBuilder:
        for use in uses:
            self.add_browser_state_use(use)
        return self

    def _credential_values(self) -> list[tuple[str, str]]:
        """Return normalized credential facts for the current scope schema."""

        values: list[tuple[str, str]] = []
        for raw_name, raw_value in sorted(self._env.items()):
            name = str(raw_name).upper()
            value = normalize_text(raw_value)
            if not value or name == "CROSSREF_MAILTO":
                continue
            if any(token in name for token in _CREDENTIAL_ENV_TOKENS):
                values.append((name, value))
                continue
        return values

    def facts(self) -> dict[str, Any]:
        browser_states: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for use in reversed(self._browser_uses):
            if not use.used:
                continue
            path = _resolved_path(use.storage_state_path)
            digest = use.content_sha256 if path.is_dir() else _file_sha256(path)
            digest = digest or "unavailable"
            key = (use.provider, use.backend, str(path))
            if key in seen:
                continue
            seen.add(key)
            browser_states.append(
                {
                    "provider": use.provider,
                    "backend": use.backend,
                    "storage_state_path": str(path),
                    "content_sha256": digest,
                    "used": True,
                }
            )
        return {
            "version": 1,
            "credentials": self._credential_values(),
            "browser_states": sorted(
                browser_states,
                key=lambda item: (
                    item["provider"],
                    item["backend"],
                    item["storage_state_path"],
                ),
            ),
        }

    def build(self) -> str:
        facts = self.facts()
        if any(
            item["content_sha256"] == "unavailable" for item in facts["browser_states"]
        ):
            return UNCACHEABLE_CAPABILITY_SCOPE
        if not facts["credentials"] and not facts["browser_states"]:
            return PUBLIC_CAPABILITY_SCOPE
        digest = hashlib.sha256(
            json.dumps(
                facts,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return f"credential:{digest}"


def _provider_storage_state_use(
    env: Mapping[str, str], *, provider: str, backend: str
) -> BrowserStateCapabilityUse | None:
    from .providers.browser_runtime.selection import selected_state_mode

    if selected_state_mode(env, provider=provider) == "json":
        state = (
            browser_paths.default_provider_user_data_dir(
                env, provider=provider, backend=backend
            )
            / "storage-state.json"
        )
        if not state.is_file():
            return None
        return BrowserStateCapabilityUse(
            provider=provider,
            backend=backend,
            storage_state_path=str(state),
            content_sha256=_file_sha256(state),
        )
    from .providers.browser_runtime.profile import trusted_profile_digest

    profile = browser_paths.configured_profile_dir(
        env, provider=provider, backend=backend
    ) or browser_paths.configured_user_data_dir(env, backend=backend)
    if profile is None:
        profile = browser_paths.default_provider_user_data_dir(
            env, provider=provider, backend="camoufox"
        )
    resolved = _resolved_path(profile)
    digest = trusted_profile_digest(
        resolved,
        provider,
        explicit_state_path=browser_paths.configured_storage_state_path(
            env, provider=provider
        ),
    )
    if digest is None:
        return None
    return BrowserStateCapabilityUse(
        provider=provider,
        backend=backend,
        storage_state_path=str(resolved),
        content_sha256=digest,
    )


def capability_scopes_for_query(
    env: Mapping[str, str] | None,
    query: str | None,
) -> tuple[str, ...]:
    """Return active private scopes followed by the permitted public fallback."""

    runtime_env = dict(env or {})
    base_builder = CapabilityScopeBuilder(runtime_env)
    scopes: list[str] = []
    doi = extract_doi(query)
    inferred_provider = infer_provider_from_doi(doi) or infer_provider_from_url(query)
    browser_providers = frozenset(
        spec.name
        for spec in ordered_provider_specs()
        if provider_has_browser_route(spec.name)
    )
    from .providers.browser_runtime.selection import selected_backend
    from .providers.browser_runtime.platforms import supported_platform

    browser_supported = inferred_provider != "elsevier" or supported_platform()
    if inferred_provider in browser_providers and browser_supported:
        backend = selected_backend(runtime_env, provider=inferred_provider)
        use = _provider_storage_state_use(
            runtime_env,
            provider=inferred_provider,
            backend=backend,
        )
        scope = (
            CapabilityScopeBuilder(runtime_env).add_browser_state_use(use).build()
            if use is not None
            else PUBLIC_CAPABILITY_SCOPE
        )
        if scope != PUBLIC_CAPABILITY_SCOPE and scope not in scopes:
            scopes.append(scope)
    env_scope = base_builder.build()
    # Browser-backed scope already includes every environment credential. Adding
    # the env-only private scope would permit lateral private-scope fallback.
    if not scopes and env_scope != PUBLIC_CAPABILITY_SCOPE:
        scopes.append(env_scope)
    scopes.append(PUBLIC_CAPABILITY_SCOPE)
    return tuple(scopes)


def capability_scope_from_runtime_context(context: Any) -> str:
    env = getattr(context, "env", None)
    snapshot = getattr(context, "browser_state_capability_uses", None)
    uses: Sequence[Mapping[str, Any]] = ()
    if callable(snapshot):
        uses = snapshot()
    return CapabilityScopeBuilder(env).add_browser_state_uses(uses).build()


__all__ = [
    "PUBLIC_CAPABILITY_SCOPE",
    "UNCACHEABLE_CAPABILITY_SCOPE",
    "BrowserStateCapabilityUse",
    "CapabilityScopeBuilder",
    "capability_scope_from_runtime_context",
    "capability_scopes_for_query",
]
