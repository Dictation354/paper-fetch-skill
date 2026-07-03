"""Provider-owned bundle registration."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from ..provider_catalog import ProviderSpec

if TYPE_CHECKING:
    from ..extraction.html.provider_rules import ProviderHtmlRules
    from ..metadata.types import MetadataMergeRule
    from ._asset_retry import AssetRetryPolicy


@dataclass(frozen=True)
class ProviderRenderPolicy:
    mark_inline_assets: Callable[[str, list[Any], str], None] | None = None

    def __post_init__(self) -> None:
        if self.mark_inline_assets is not None and not callable(
            self.mark_inline_assets
        ):
            raise TypeError(
                "Provider render policy mark_inline_assets must be callable."
            )


@dataclass(frozen=True)
class ProviderBundle:
    catalog: ProviderSpec
    html_rules: ProviderHtmlRules | None = None
    asset_retry: AssetRetryPolicy | None = None
    metadata_merge: tuple[MetadataMergeRule, ...] = ()
    sources: tuple[str, ...] = ()
    render_policy: ProviderRenderPolicy | None = None

    def __post_init__(self) -> None:
        if not self.catalog.name:
            raise ValueError("Provider bundle catalog name is required.")
        if not isinstance(self.metadata_merge, tuple):
            raise TypeError("Provider bundle metadata_merge must be a tuple.")
        if not isinstance(self.sources, tuple):
            raise TypeError("Provider bundle sources must be a tuple.")
        if self.render_policy is not None and not isinstance(
            self.render_policy,
            ProviderRenderPolicy,
        ):
            raise TypeError(
                "Provider bundle render_policy must be a ProviderRenderPolicy."
            )
        if self.html_rules is not None and self.html_rules.name != self.catalog.name:
            if self.catalog.name not in (
                self.html_rules.name,
                *self.html_rules.aliases,
            ):
                raise ValueError(
                    "Provider bundle HTML rules must match the catalog provider name."
                )


_REGISTERED_PROVIDERS: dict[str, ProviderBundle] = {}
_ENSURING_PROVIDER_IMPORTS = False


def _ensure_provider_entry_modules_imported() -> None:
    global _ENSURING_PROVIDER_IMPORTS
    if _ENSURING_PROVIDER_IMPORTS:
        return
    _ENSURING_PROVIDER_IMPORTS = True
    try:
        import paper_fetch.providers as provider_entries

        provider_entries.import_provider_entry_modules()
    finally:
        _ENSURING_PROVIDER_IMPORTS = False


def register_provider_bundle(bundle: ProviderBundle) -> None:
    name = bundle.catalog.name.strip().lower()
    if not name:
        raise ValueError("Provider bundle catalog name is required.")
    existing = _REGISTERED_PROVIDERS.get(name)
    if existing is not None:
        if existing == bundle:
            return
        raise ValueError(f"Provider bundle already registered: {name}")
    _REGISTERED_PROVIDERS[name] = bundle


def iter_provider_bundles() -> Iterator[ProviderBundle]:
    _ensure_provider_entry_modules_imported()
    yield from sorted(
        MappingProxyType(_REGISTERED_PROVIDERS).values(),
        key=lambda bundle: bundle.catalog.status_order,
    )


def provider_bundle(name: str) -> ProviderBundle:
    _ensure_provider_entry_modules_imported()
    normalized = str(name or "").strip().lower()
    try:
        return _REGISTERED_PROVIDERS[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown provider bundle: {name!r}") from exc
