"""Provider-owned bundle registration."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from dataclasses import replace
import threading
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from ..provider_catalog import ProviderRouteSpec, ProviderSpec

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
        object.__setattr__(
            self,
            "catalog",
            replace(
                self.catalog,
                routes=tuple(
                    replace(
                        route,
                        source=route.source
                        or _default_bundle_route_source(
                            self.catalog.name,
                            route,
                            self.sources,
                        ),
                    )
                    for route in self.catalog.routes
                ),
            ),
        )


def _default_bundle_route_source(
    provider: str,
    route: ProviderRouteSpec,
    sources: tuple[str, ...],
) -> str:
    if route.kind == "metadata":
        return sources[0] if provider == "crossref" and sources else route.name
    suffix = {
        "html": "_html",
        "xml": "_xml",
        "pdf": "_pdf",
    }.get(route.kind)
    if suffix is not None:
        matching = next((source for source in sources if source.endswith(suffix)), None)
        if matching is not None:
            return matching
    if route.kind == "assets":
        xml_source = next(
            (source for source in sources if source.endswith("_xml")),
            None,
        )
        if xml_source is not None:
            return xml_source
    if sources:
        return sources[0]
    return route.name


_REGISTERED_PROVIDERS: dict[str, ProviderBundle] = {}
_REGISTRY_LOCK = threading.RLock()
_ENSURING_PROVIDER_IMPORTS_THREAD: int | None = None
_PROVIDER_IMPORT_EVENT: threading.Event | None = None


def _ensure_provider_entry_modules_imported() -> None:
    global _ENSURING_PROVIDER_IMPORTS_THREAD, _PROVIDER_IMPORT_EVENT
    current_thread = threading.get_ident()
    wait_event: threading.Event | None = None
    with _REGISTRY_LOCK:
        if _ENSURING_PROVIDER_IMPORTS_THREAD == current_thread:
            return
        if _ENSURING_PROVIDER_IMPORTS_THREAD is not None:
            wait_event = _PROVIDER_IMPORT_EVENT
        else:
            _ENSURING_PROVIDER_IMPORTS_THREAD = current_thread
            _PROVIDER_IMPORT_EVENT = threading.Event()
    if wait_event is not None:
        wait_event.wait()
        return
    try:
        import paper_fetch.providers as provider_entries

        provider_entries.import_provider_entry_modules()
    finally:
        with _REGISTRY_LOCK:
            _ENSURING_PROVIDER_IMPORTS_THREAD = None
            completed_event = _PROVIDER_IMPORT_EVENT
            _PROVIDER_IMPORT_EVENT = None
            if completed_event is not None:
                completed_event.set()


def _validate_registration_conflicts(
    bundle: ProviderBundle,
    *,
    name: str,
) -> None:
    for existing_name, existing in _REGISTERED_PROVIDERS.items():
        if existing.catalog.status_order == bundle.catalog.status_order:
            raise ValueError(
                "Provider status_order conflict: "
                f"{name} and {existing_name} both use {bundle.catalog.status_order}."
            )
        if (
            bundle.catalog.client_factory_path
            and existing.catalog.client_factory_path
            == bundle.catalog.client_factory_path
        ):
            raise ValueError(
                "Provider client factory conflict: "
                f"{name} and {existing_name} both use "
                f"{bundle.catalog.client_factory_path!r}."
            )
        duplicate_sources = set(bundle.sources) & set(existing.sources)
        if duplicate_sources:
            raise ValueError(
                "Provider source conflict: "
                f"{name} and {existing_name} both declare "
                f"{', '.join(sorted(duplicate_sources))}."
            )
        duplicate_domains = {domain.lower() for domain in bundle.catalog.domains} & {
            domain.lower() for domain in existing.catalog.domains
        }
        if duplicate_domains:
            raise ValueError(
                "Provider domain conflict: "
                f"{name} and {existing_name} both declare "
                f"{', '.join(sorted(duplicate_domains))}."
            )


def register_provider_bundle(bundle: ProviderBundle) -> None:
    name = bundle.catalog.name.strip().lower()
    if not name:
        raise ValueError("Provider bundle catalog name is required.")
    with _REGISTRY_LOCK:
        existing = _REGISTERED_PROVIDERS.get(name)
        if existing is not None:
            if existing == bundle:
                return
            raise ValueError(f"Provider bundle already registered: {name}")
        _validate_registration_conflicts(bundle, name=name)
        _REGISTERED_PROVIDERS[name] = bundle


def iter_provider_bundles() -> Iterator[ProviderBundle]:
    _ensure_provider_entry_modules_imported()
    with _REGISTRY_LOCK:
        snapshot = tuple(
            sorted(
                MappingProxyType(dict(_REGISTERED_PROVIDERS)).values(),
                key=lambda bundle: bundle.catalog.status_order,
            )
        )
    yield from snapshot


def provider_bundle(name: str) -> ProviderBundle:
    _ensure_provider_entry_modules_imported()
    normalized = str(name or "").strip().lower()
    with _REGISTRY_LOCK:
        try:
            return _REGISTERED_PROVIDERS[normalized]
        except KeyError as exc:
            raise KeyError(f"Unknown provider bundle: {name!r}") from exc
