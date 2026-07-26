"""Static provider identity, routing, and capability catalog."""

from __future__ import annotations
from collections.abc import Iterator, Mapping as MappingABC
from dataclasses import asdict, dataclass
import importlib
from types import MappingProxyType
from typing import Any, Literal
from collections.abc import Callable

from .metadata.types import ProviderMetadata

AssetDefault = Literal["none", "body", "all"]
MetadataProbeShortCircuit = Callable[[str], ProviderMetadata | None]


@dataclass(frozen=True)
class BodyTextThresholds:
    min_chars: int = 800
    short_body_min_chars: int = 300
    short_body_min_words: int = 60
    single_block_min_words: int = 90
    cjk_min_chars: int = 120
    single_block_min_cjk_chars: int = 180
    cjk_min_ratio: float = 0.20


DEFAULT_BODY_TEXT_THRESHOLDS = BodyTextThresholds()
ATYPON_DEFAULT_PDF_PATH_TEMPLATES = (
    "/doi/epdf/{doi}",
    "/doi/pdf/{doi}",
)


@dataclass(frozen=True)
class PdfSourcePathTemplate:
    domain: str
    path_prefix: str
    path_template: str


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    official: bool
    domains: tuple[str, ...]
    doi_prefixes: tuple[str, ...]
    publisher_aliases: tuple[str, ...]
    asset_default: AssetDefault
    probe_capability: str
    provider_managed_abstract_only: bool
    client_factory_path: str
    status_order: int
    domain_suffixes: tuple[str, ...] = ()
    base_domains: tuple[str, ...] = ()
    html_path_templates: tuple[str, ...] = ()
    xml_path_templates: tuple[str, ...] = ()
    landing_path_templates: tuple[str, ...] = ()
    pdf_path_templates: tuple[str, ...] = ()
    pdf_source_path_templates: tuple[PdfSourcePathTemplate, ...] = ()
    crossref_pdf_position: int = 0
    api_hosts: tuple[str, ...] = ()
    api_url_templates: tuple[tuple[str, str], ...] = ()
    sensitive_headers: tuple[str, ...] = ()
    metadata_probe_short_circuit: MetadataProbeShortCircuit | str | None = None
    persist_provider_html: bool = False
    xml_root_tags: tuple[str, ...] = ()
    xml_file_tokens: tuple[str, ...] = ()
    emits_html_managed_marker: bool = True
    html_capable: bool = True
    body_text_thresholds: BodyTextThresholds = DEFAULT_BODY_TEXT_THRESHOLDS
    env_requirements: tuple[str, ...] = ()
    requires_playwright: bool = False
    requires_browser_runtime: bool = False

    def __post_init__(self) -> None:
        if self.requires_playwright and not self.requires_browser_runtime:
            object.__setattr__(self, "requires_browser_runtime", True)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_METADATA_PROBE_SHORT_CIRCUITS: dict[str, MetadataProbeShortCircuit] = {}
_PROVIDER_CATALOG_CACHE: MappingABC[str, ProviderSpec] | None = None
_SOURCE_PROVIDER_MAP_CACHE: MappingABC[str, str] | None = None


def _registered_provider_bundles():
    import paper_fetch.providers as providers

    providers.import_provider_entry_modules()
    from .providers._registry import iter_provider_bundles

    return tuple(iter_provider_bundles())


def _build_provider_catalog() -> MappingABC[str, ProviderSpec]:
    return MappingProxyType(
        {
            bundle.catalog.name: bundle.catalog
            for bundle in _registered_provider_bundles()
        }
    )


def _provider_catalog_map() -> MappingABC[str, ProviderSpec]:
    global _PROVIDER_CATALOG_CACHE
    catalog = _PROVIDER_CATALOG_CACHE
    if catalog is None:
        catalog = _build_provider_catalog()
        import paper_fetch.providers as providers

        if getattr(providers, "_PROVIDER_ENTRY_IMPORTS_COMPLETE", False):
            _PROVIDER_CATALOG_CACHE = catalog
    return catalog


class _ProviderCatalogMapping(MappingABC[str, ProviderSpec]):
    def __getitem__(self, key: str) -> ProviderSpec:
        return _provider_catalog_map()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(_provider_catalog_map())

    def __len__(self) -> int:
        return len(_provider_catalog_map())


PROVIDER_CATALOG: MappingABC[str, ProviderSpec] = _ProviderCatalogMapping()


def _build_source_provider_map() -> MappingABC[str, str]:
    return MappingProxyType(
        {
            source: bundle.catalog.name
            for bundle in _registered_provider_bundles()
            for source in bundle.sources
        }
    )


def _source_provider_map() -> MappingABC[str, str]:
    global _SOURCE_PROVIDER_MAP_CACHE
    source_map = _SOURCE_PROVIDER_MAP_CACHE
    if source_map is None:
        source_map = _build_source_provider_map()
        import paper_fetch.providers as providers

        if getattr(providers, "_PROVIDER_ENTRY_IMPORTS_COMPLETE", False):
            _SOURCE_PROVIDER_MAP_CACHE = source_map
    return source_map


class _SourceProviderMapping(MappingABC[str, str]):
    def __getitem__(self, key: str) -> str:
        return _source_provider_map()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(_source_provider_map())

    def __len__(self) -> int:
        return len(_source_provider_map())


SOURCE_PROVIDER_MAP: MappingABC[str, str] = _SourceProviderMapping()


def _normalize_catalog_token(value: str | None) -> str:
    return str(value or "").strip().lower().rstrip(".")


def _normalize_hostname(value: str | None) -> str:
    normalized = _normalize_catalog_token(value)
    if not normalized:
        return ""
    if "://" in normalized:
        from urllib.parse import urlparse

        return _normalize_catalog_token(urlparse(normalized).hostname)
    if "/" in normalized:
        normalized = normalized.split("/", 1)[0]
    if "@" in normalized:
        normalized = normalized.rsplit("@", 1)[-1]
    if normalized.startswith("["):
        return normalized.strip("[]")
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0]
    return normalized


def host_matches_domain(hostname: str | None, domain: str | None) -> bool:
    host = _normalize_hostname(hostname)
    normalized_domain = _normalize_catalog_token(domain)
    return bool(
        host
        and normalized_domain
        and (host == normalized_domain or host.endswith(f".{normalized_domain}"))
    )


def _provider_spec(provider_name: str | None) -> ProviderSpec | None:
    return PROVIDER_CATALOG.get(_normalize_catalog_token(provider_name))


def provider_domains(provider_name: str | None) -> tuple[str, ...]:
    return (
        spec.domains + spec.domain_suffixes
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_base_domains(provider_name: str | None) -> tuple[str, ...]:
    return (
        spec.base_domains or spec.domains
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_html_path_templates(provider_name: str | None) -> tuple[str, ...]:
    return (
        spec.html_path_templates
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_xml_path_templates(provider_name: str | None) -> tuple[str, ...]:
    return (
        spec.xml_path_templates
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_landing_path_templates(provider_name: str | None) -> tuple[str, ...]:
    return (
        spec.landing_path_templates
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_pdf_path_templates(provider_name: str | None) -> tuple[str, ...]:
    return (
        spec.pdf_path_templates
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_pdf_source_path_templates(
    provider_name: str | None,
) -> tuple[PdfSourcePathTemplate, ...]:
    return (
        spec.pdf_source_path_templates
        if (spec := _provider_spec(provider_name)) is not None
        else ()
    )


def provider_crossref_pdf_position(provider_name: str | None) -> int:
    return (
        int(spec.crossref_pdf_position)
        if (spec := _provider_spec(provider_name)) is not None
        else 0
    )


def matching_provider_domain(
    provider_name: str | None, hostname: str | None
) -> str | None:
    for domain in provider_domains(provider_name):
        if host_matches_domain(hostname, domain):
            return domain
    return None


def provider_domain_matches(provider_name: str | None, hostname: str | None) -> bool:
    return matching_provider_domain(provider_name, hostname) is not None


def api_like_hosts() -> frozenset[str]:
    return frozenset(
        _normalize_hostname(host)
        for spec in PROVIDER_CATALOG.values()
        for host in spec.api_hosts
        if _normalize_hostname(host)
    )


def is_declared_api_host(hostname: str | None) -> bool:
    return _normalize_hostname(hostname) in api_like_hosts()


def provider_api_url_template(
    provider_name: str | None, template_name: str
) -> str | None:
    spec = _provider_spec(provider_name)
    if spec is None:
        return None
    for name, template in spec.api_url_templates:
        if name == template_name:
            return template
    return None


def provider_sensitive_header_names() -> frozenset[str]:
    return frozenset(
        _normalize_catalog_token(header)
        for spec in PROVIDER_CATALOG.values()
        for header in spec.sensitive_headers
        if _normalize_catalog_token(header)
    )


def _load_callable(callback_path: str) -> MetadataProbeShortCircuit:
    module_path, _, attribute = callback_path.partition(":")
    if not module_path or not attribute:
        raise ValueError(f"Invalid provider callback path: {callback_path!r}")
    module = importlib.import_module(module_path)
    callback = getattr(module, attribute)
    if not callable(callback):
        raise TypeError(f"Provider callback path is not callable: {callback_path!r}")
    return callback


def register_metadata_probe_short_circuit(
    provider_name: str,
    callback: MetadataProbeShortCircuit,
) -> None:
    normalized = _normalize_catalog_token(provider_name)
    if not normalized:
        raise ValueError(
            "Provider name is required for metadata probe short-circuit registration."
        )
    if not callable(callback):
        raise TypeError("Metadata probe short-circuit must be callable.")
    _METADATA_PROBE_SHORT_CIRCUITS[normalized] = callback


def provider_metadata_probe_short_circuit(
    provider_name: str | None,
) -> MetadataProbeShortCircuit | None:
    normalized = _normalize_catalog_token(provider_name)
    if not normalized:
        return None
    callback = _METADATA_PROBE_SHORT_CIRCUITS.get(normalized)
    if callback is not None:
        return callback
    spec = _provider_spec(normalized)
    declared = spec.metadata_probe_short_circuit if spec is not None else None
    if declared is None:
        return None
    callback = _load_callable(declared) if isinstance(declared, str) else declared
    _METADATA_PROBE_SHORT_CIRCUITS[normalized] = callback
    return callback


def provider_persists_provider_html(provider_name: str | None) -> bool:
    spec = _provider_spec(provider_name)
    return bool(spec and spec.persist_provider_html)


def provider_for_xml_source(root_tag: str | None, xml_path: str | None) -> str:
    root_name = _normalize_catalog_token(root_tag)
    lower_path = str(xml_path or "").lower()
    for spec in ordered_provider_specs():
        if any(token and token.lower() in lower_path for token in spec.xml_file_tokens):
            return spec.name
    for spec in ordered_provider_specs():
        if root_name and root_name in {
            _normalize_catalog_token(tag) for tag in spec.xml_root_tags
        }:
            return spec.name
    return "unknown"


def provider_emits_html_managed_marker(provider_name: str | None) -> bool:
    spec = _provider_spec(provider_name)
    return bool(spec and spec.official and spec.emits_html_managed_marker)


def provider_body_text_thresholds(provider_name: str | None) -> BodyTextThresholds:
    spec = _provider_spec(provider_name)
    return (
        spec.body_text_thresholds if spec is not None else DEFAULT_BODY_TEXT_THRESHOLDS
    )


def sources_by_provider() -> dict[str, frozenset[str]]:
    grouped: dict[str, set[str]] = {}
    for source, provider in SOURCE_PROVIDER_MAP.items():
        grouped.setdefault(provider, set()).add(source)
    return {provider: frozenset(sources) for provider, sources in grouped.items()}


def ordered_provider_specs() -> tuple[ProviderSpec, ...]:
    return tuple(sorted(PROVIDER_CATALOG.values(), key=lambda spec: spec.status_order))


def provider_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in ordered_provider_specs())


def official_provider_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in ordered_provider_specs() if spec.official)


def provider_status_order() -> tuple[str, ...]:
    return provider_names()


def is_official_provider(provider_name: str | None) -> bool:
    spec = _provider_spec(provider_name)
    return bool(spec and spec.official)


def provider_managed_abstract_only_names() -> frozenset[str]:
    return frozenset(
        spec.name
        for spec in PROVIDER_CATALOG.values()
        if spec.provider_managed_abstract_only
    )


def provider_display_names() -> dict[str, str]:
    return {spec.name: spec.display_name for spec in PROVIDER_CATALOG.values()}


def default_asset_profile_for_provider(provider_name: str | None) -> AssetDefault:
    spec = _provider_spec(provider_name)
    return spec.asset_default if spec is not None else "none"


def provider_for_source(source_name: str | None) -> str | None:
    normalized = str(source_name or "").strip().lower()
    return SOURCE_PROVIDER_MAP.get(normalized)


def provider_render_policy_for_source(source_name: str | None) -> Any | None:
    provider_name = provider_for_source(source_name)
    if not provider_name:
        return None
    from .providers._registry import provider_bundle

    try:
        return provider_bundle(provider_name).render_policy
    except KeyError:
        return None


def known_article_source_names() -> frozenset[str]:
    return frozenset(SOURCE_PROVIDER_MAP)


def default_asset_profile_for_source(source_name: str | None) -> AssetDefault:
    provider_name = provider_for_source(source_name)
    return default_asset_profile_for_provider(provider_name)


def provider_probe_capability(provider_name: str | None) -> str:
    spec = _provider_spec(provider_name)
    return spec.probe_capability if spec is not None else ""


def provider_supports_metadata_api_probe(provider_name: str | None) -> bool:
    return provider_probe_capability(provider_name) == "metadata_api"


def doi_prefix_provider_map() -> dict[str, str]:
    return {
        prefix: spec.name
        for spec in ordered_provider_specs()
        for prefix in spec.doi_prefixes
    }
