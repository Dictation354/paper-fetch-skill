"""Static provider identity, routing, and capability catalog."""

from __future__ import annotations

import importlib
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator, Mapping as MappingABC
from dataclasses import asdict, dataclass, replace
from types import MappingProxyType
from typing import Any, Literal

from .acquisition import AcquisitionProvenance, AcquisitionTransport
from .metadata.types import ProviderMetadata

AssetDefault = Literal["none", "body", "all"]
MetadataProbeShortCircuit = Callable[[str], ProviderMetadata | None]
ProviderRouteKind = Literal["metadata", "html", "xml", "pdf", "assets"]
ProviderRouteTransport = AcquisitionTransport
ProviderRouteImplementationStatus = Literal[
    "available",
    "not_configured",
    "unsupported",
]


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
class ProviderRouteSpec:
    """Local requirements and policy for one provider acquisition route."""

    name: str
    kind: ProviderRouteKind
    source: str | None = None
    order: int | None = None
    implementation_status: ProviderRouteImplementationStatus = "available"
    browser_required: bool = False
    browser_optional: bool = False
    browser_preflight: bool = False
    auth_supported: bool = False
    requires_playwright: bool = False
    requires_pdf_conversion: bool = False
    requires_formula_tools: bool = False
    timeout_seconds: int | None = None
    concurrency: int | None = None
    qps: float | None = None
    rate_limit_wait_budget_seconds: float | None = None
    transient_retry_categories: tuple[str, ...] = ()
    rate_policy: str | None = None
    required_packages: tuple[str, ...] = ()
    hosts: tuple[str, ...] = ()
    acceptance_policy: str | None = None
    asset_scope: AssetDefault | None = None
    notes: str | None = None
    # Additive field kept last so existing positional route declarations retain
    # their pre-acquisition argument order.
    transport: ProviderRouteTransport | None = None
    transient_retries: int | None = None
    rate_limit_retries: int | None = None

    def __post_init__(self) -> None:
        if self.browser_required and self.browser_optional:
            raise ValueError(
                "A provider route cannot be both browser-required and browser-optional."
            )
        effective_transport = self.transport
        if effective_transport is None:
            if self.browser_required or self.browser_optional:
                effective_transport = "browser"
            elif self.kind == "metadata" or self.name.endswith("_api"):
                effective_transport = "api"
            else:
                effective_transport = "http"
            object.__setattr__(self, "transport", effective_transport)
        if effective_transport not in {"api", "browser", "http"}:
            raise ValueError(
                f"Unsupported provider route transport: {effective_transport!r}"
            )
        if (self.browser_required or self.browser_optional) and (
            effective_transport != "browser"
        ):
            raise ValueError("Browser-backed routes must use browser transport.")
        if (self.browser_required or self.browser_optional) and not (
            self.requires_playwright
        ):
            object.__setattr__(self, "requires_playwright", True)
        if self.auth_supported and not self.browser_preflight:
            object.__setattr__(self, "browser_preflight", True)
        if self.browser_preflight and not (
            self.browser_required or self.browser_optional
        ):
            raise ValueError("Browser preflight requires a browser-backed route.")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("Route timeout_seconds must be positive.")
        if self.concurrency is not None and not (1 <= self.concurrency <= 8):
            raise ValueError("Route concurrency must be from 1 to 8.")
        if self.order is not None and self.order < 0:
            raise ValueError("Route order must be non-negative.")
        if self.qps is not None and self.qps <= 0:
            raise ValueError("Route qps must be positive.")
        if self.transient_retries is not None and self.transient_retries < 0:
            raise ValueError("Route transient_retries must be non-negative.")
        if self.rate_limit_retries is not None and self.rate_limit_retries < 0:
            raise ValueError("Route rate_limit_retries must be non-negative.")
        if (
            self.rate_limit_wait_budget_seconds is not None
            and self.rate_limit_wait_budget_seconds < 0
        ):
            raise ValueError(
                "Route rate_limit_wait_budget_seconds must be non-negative."
            )


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
    batch_concurrency: int | None = None
    routes: tuple[ProviderRouteSpec, ...] = ()
    cdn_hosts: tuple[str, ...] = ()
    identity_priority: int | None = None
    identity_conflict_reason: str | None = None

    def __post_init__(self) -> None:
        has_identity_priority = self.identity_priority is not None
        has_identity_reason = bool(str(self.identity_conflict_reason or "").strip())
        if has_identity_priority != has_identity_reason:
            raise ValueError(
                "identity_priority and identity_conflict_reason must be declared together"
            )
        if isinstance(self.identity_priority, bool):
            raise ValueError("identity_priority must be an integer")
        if self.requires_playwright and not self.requires_browser_runtime:
            object.__setattr__(self, "requires_browser_runtime", True)
        effective_batch_concurrency = self.batch_concurrency
        if effective_batch_concurrency is None:
            effective_batch_concurrency = 1 if self.requires_browser_runtime else 2
            object.__setattr__(self, "batch_concurrency", effective_batch_concurrency)
        if isinstance(effective_batch_concurrency, bool) or not (
            1 <= effective_batch_concurrency <= 8
        ):
            raise ValueError("batch_concurrency must be an integer from 1 to 8.")
        if not self.routes:
            routes: list[ProviderRouteSpec] = [
                ProviderRouteSpec(name="metadata", kind="metadata")
            ]
            if self.html_capable:
                routes.append(
                    ProviderRouteSpec(
                        name=(
                            "browser_html"
                            if self.requires_browser_runtime
                            else "direct_html"
                        ),
                        kind="html",
                        browser_required=self.requires_browser_runtime,
                        browser_preflight=self.requires_browser_runtime,
                        auth_supported=self.requires_browser_runtime,
                        requires_playwright=self.requires_playwright,
                        concurrency=1 if self.requires_browser_runtime else 2,
                    )
                )
            if self.xml_path_templates:
                routes.append(ProviderRouteSpec(name="xml", kind="xml"))
            if self.pdf_path_templates or self.pdf_source_path_templates:
                browser_backed_pdf = self.requires_browser_runtime
                routes.append(
                    ProviderRouteSpec(
                        name="browser_pdf" if browser_backed_pdf else "direct_pdf",
                        kind="pdf",
                        browser_required=browser_backed_pdf,
                        browser_preflight=browser_backed_pdf,
                        auth_supported=browser_backed_pdf,
                        requires_playwright=browser_backed_pdf,
                        requires_pdf_conversion=True,
                        concurrency=1 if browser_backed_pdf else 2,
                    )
                )
            object.__setattr__(self, "routes", tuple(routes))
        if self.requires_browser_runtime and not any(
            route.browser_required or route.browser_optional for route in self.routes
        ):
            object.__setattr__(
                self,
                "routes",
                (
                    *self.routes,
                    ProviderRouteSpec(
                        name="browser_html",
                        kind="html",
                        browser_required=True,
                        browser_preflight=True,
                        auth_supported=True,
                        requires_playwright=True,
                        concurrency=1,
                    ),
                ),
            )
        route_names = [route.name for route in self.routes]
        if len(route_names) != len(set(route_names)):
            raise ValueError("Provider route names must be unique.")
        object.__setattr__(
            self,
            "routes",
            tuple(
                replace(
                    route,
                    order=index if route.order is None else route.order,
                    hosts=route.hosts or self.domains,
                    asset_scope=route.asset_scope or self.asset_default,
                    timeout_seconds=route.timeout_seconds
                    or _default_route_timeout(route),
                    concurrency=route.concurrency
                    or (1 if route.browser_required or route.browser_optional else 2),
                    rate_limit_wait_budget_seconds=(
                        route.rate_limit_wait_budget_seconds
                        if route.rate_limit_wait_budget_seconds is not None
                        else 5.0
                    ),
                    transient_retry_categories=(
                        route.transient_retry_categories
                        or (
                            "timeout",
                            "connection_reset",
                            "connection_closed",
                            "dns_error",
                        )
                    ),
                    transient_retries=(
                        route.transient_retries
                        if route.transient_retries is not None
                        else 2
                    ),
                    rate_limit_retries=(
                        route.rate_limit_retries
                        if route.rate_limit_retries is not None
                        else 2
                    ),
                    rate_policy=route.rate_policy or "shared_host_cooldown",
                    required_packages=route.required_packages
                    or _default_route_packages(route),
                    acceptance_policy=route.acceptance_policy
                    or _default_route_acceptance(route.kind),
                )
                for index, route in enumerate(self.routes)
            ),
        )
        route_orders = [route.order for route in self.routes]
        if route_orders != list(range(len(self.routes))):
            raise ValueError(
                "Provider route order must be unique and contiguous from zero."
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RouteExecutionPolicy:
    """One compiled provider-route policy consumed by runtime transports.

    Provider declarations remain intentionally descriptive.  Runtime code must
    consume this compiled form so host boundaries, pacing, retries, acceptance,
    and asset limits cannot drift into separate provider-specific defaults.
    """

    provider: str
    route: str | None
    kind: ProviderRouteKind | None
    hosts: tuple[str, ...]
    sensitive_headers: tuple[str, ...]
    timeout_seconds: int
    concurrency: int
    qps: float | None
    minimum_interval_seconds: float
    rate_limit_wait_budget_seconds: float
    transient_retry_categories: tuple[str, ...]
    transient_retries: int
    rate_limit_retries: int
    rate_policy: str
    acceptance_policy: str | None
    asset_scope: AssetDefault

    @property
    def retry_on_transient(self) -> bool:
        return bool(self.transient_retry_categories and self.transient_retries)

    @property
    def retry_on_rate_limit(self) -> bool:
        return bool(self.rate_limit_wait_budget_seconds and self.rate_limit_retries)

    @property
    def asset_concurrency_cap(self) -> int:
        return self.concurrency


def _default_route_timeout(route: ProviderRouteSpec) -> int:
    if route.browser_required or route.browser_optional:
        return 120
    return 120 if route.kind == "pdf" else 20


def _default_route_packages(route: ProviderRouteSpec) -> tuple[str, ...]:
    packages: list[str] = []
    if route.requires_playwright:
        packages.append("camoufox")
    if route.requires_pdf_conversion:
        packages.append("pymupdf4llm")
    return tuple(packages)


def _default_route_acceptance(kind: ProviderRouteKind) -> str:
    return {
        "metadata": "metadata_identity",
        "html": "provider_html_body",
        "xml": "structured_xml_body",
        "pdf": "validated_pdf",
        "assets": "validated_asset",
    }[kind]


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


def provider_batch_concurrency(provider_name: str | None) -> int:
    """Return the production batch limit for one resolved provider lane."""

    spec = _provider_spec(provider_name)
    if spec is None or spec.batch_concurrency is None:
        return 1
    return spec.batch_concurrency


def provider_routes(provider_name: str | None) -> tuple[ProviderRouteSpec, ...]:
    spec = _provider_spec(provider_name)
    return spec.routes if spec is not None else ()


def provider_route(
    provider_name: str | None, route_name: str | None
) -> ProviderRouteSpec | None:
    normalized_route = _normalize_catalog_token(route_name)
    return next(
        (
            route
            for route in provider_routes(provider_name)
            if route.name == normalized_route
        ),
        None,
    )


def _template_hostname(template: str | None) -> str:
    value = str(template or "").strip()
    if "://" not in value:
        return ""
    return _normalize_hostname(urllib.parse.urlsplit(value).hostname)


def _compiled_provider_hosts(
    spec: ProviderSpec,
    route: ProviderRouteSpec | None,
) -> tuple[str, ...]:
    """Return every catalog-declared network identity for a route.

    Domain suffixes are deliberately retained as allowlist entries: the shared
    URL policy interprets them with label-boundary matching.  Absolute URL
    templates and PDF source declarations are included so API/CDN endpoints do
    not need ad-hoc runtime exceptions.
    """

    candidates = [
        *(route.hosts if route is not None else ()),
        *spec.domains,
        *spec.domain_suffixes,
        *spec.base_domains,
        *spec.api_hosts,
        *spec.cdn_hosts,
        *(source.domain for source in spec.pdf_source_path_templates),
        *(_template_hostname(template) for _name, template in spec.api_url_templates),
        *(
            _template_hostname(template)
            for template in (
                *spec.html_path_templates,
                *spec.xml_path_templates,
                *spec.landing_path_templates,
                *spec.pdf_path_templates,
            )
        ),
    ]
    return tuple(
        dict.fromkeys(
            host for value in candidates if (host := _normalize_hostname(value))
        )
    )


def compile_route_execution_policy(
    provider_name: str,
    route_name: str | None = None,
) -> RouteExecutionPolicy:
    """Compile the sole catalog-to-runtime policy for a provider route.

    ``route_name=None`` is an additive compatibility mode used by legacy asset
    and browser helpers that can traverse more than one declared route.  It
    unions declared hosts and chooses conservative runtime limits; new request
    call sites should pass the exact route name.
    """

    normalized_provider = _normalize_catalog_token(provider_name)
    spec = _provider_spec(normalized_provider)
    if spec is None:
        raise ValueError(f"Unknown provider route policy: {provider_name!r}")
    route = provider_route(normalized_provider, route_name) if route_name else None
    if route_name and route is None:
        raise ValueError(
            f"Unknown provider route policy: {normalized_provider}:{route_name}"
        )
    routes = (route,) if route is not None else spec.routes
    timeout_seconds = (
        int(route.timeout_seconds or _default_route_timeout(route))
        if route is not None
        else max(int(item.timeout_seconds or 20) for item in routes)
    )
    concurrency = (
        int(route.concurrency or 1)
        if route is not None
        else min(int(item.concurrency or 1) for item in routes)
    )
    qps_values = tuple(float(item.qps) for item in routes if item.qps is not None)
    qps = min(qps_values) if qps_values else None
    transient_categories = tuple(
        dict.fromkeys(
            category
            for item in routes
            for raw_category in item.transient_retry_categories
            if (category := _normalize_catalog_token(raw_category))
        )
    )
    wait_budget = min(
        float(item.rate_limit_wait_budget_seconds or 0.0) for item in routes
    )
    transient_retries = min(int(item.transient_retries or 0) for item in routes)
    rate_limit_retries = min(int(item.rate_limit_retries or 0) for item in routes)
    sensitive_headers = tuple(
        dict.fromkeys(
            header
            for raw_header in spec.sensitive_headers
            if (header := _normalize_catalog_token(raw_header))
        )
    )
    return RouteExecutionPolicy(
        provider=normalized_provider,
        route=route.name if route is not None else None,
        kind=route.kind if route is not None else None,
        hosts=_compiled_provider_hosts(spec, route),
        sensitive_headers=sensitive_headers,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
        qps=qps,
        minimum_interval_seconds=(1.0 / qps if qps is not None else 0.0),
        rate_limit_wait_budget_seconds=wait_budget,
        transient_retry_categories=transient_categories,
        transient_retries=transient_retries,
        rate_limit_retries=rate_limit_retries,
        rate_policy=(
            route.rate_policy
            if route is not None and route.rate_policy
            else "shared_host_cooldown"
        ),
        acceptance_policy=(route.acceptance_policy if route is not None else None),
        asset_scope=(route.asset_scope or spec.asset_default)
        if route is not None
        else spec.asset_default,
    )


def compile_route_execution_policy_for_kind(
    provider_name: str,
    kind: ProviderRouteKind,
    *,
    prefer_transport: ProviderRouteTransport | None = None,
) -> RouteExecutionPolicy:
    """Compile the first catalog route for a runtime representation kind."""

    candidates = [
        route
        for route in provider_routes(provider_name)
        if route.kind == kind
        and (prefer_transport is None or route.transport == prefer_transport)
    ]
    if not candidates and prefer_transport is not None:
        candidates = [
            route for route in provider_routes(provider_name) if route.kind == kind
        ]
    if not candidates:
        return compile_route_execution_policy(provider_name)
    selected = min(candidates, key=lambda route: int(route.order or 0))
    return compile_route_execution_policy(provider_name, selected.name)


def effective_route_asset_scope(
    requested: AssetDefault | None,
    *,
    provider_name: str | None,
    route_name: str | None = None,
) -> AssetDefault:
    """Merge the public asset profile with the compiled route default.

    An explicit ``none|body|all`` remains a user override for compatibility.
    When the caller leaves the profile unset, the exact route's compiled
    ``asset_scope`` selects execution; unknown providers fail closed.
    """

    if requested is not None:
        return requested
    normalized_provider = _normalize_catalog_token(provider_name)
    if not normalized_provider:
        return "none"
    try:
        compiled = (
            compile_route_execution_policy(normalized_provider, route_name)
            if route_name
            else compile_route_execution_policy_for_kind(normalized_provider, "assets")
        )
    except ValueError:
        return "none"
    return compiled.asset_scope


def acquisition_for_provider_route(
    provider_name: str | None,
    route_name: str | None,
    *,
    fallback_used: bool = False,
) -> AcquisitionProvenance | None:
    """Build exact public acquisition provenance from the route catalog."""

    normalized_provider = _normalize_catalog_token(provider_name)
    route = provider_route(normalized_provider, route_name)
    if (
        not normalized_provider
        or route is None
        or route.kind == "assets"
        or route.transport is None
    ):
        return None
    return AcquisitionProvenance(
        provider=normalized_provider,
        route=route.name,
        representation=route.kind,
        transport=route.transport,
        fallback_used=fallback_used,
    )


def acquisition_matches_provider_route(
    acquisition: AcquisitionProvenance | None,
) -> bool:
    """Validate an acquisition object against the authoritative route catalog."""

    if acquisition is None:
        return False
    route = provider_route(acquisition.provider, acquisition.route)
    return bool(
        route is not None
        and route.kind != "assets"
        and route.kind == acquisition.representation
        and route.transport == acquisition.transport
    )


def provider_has_browser_route(provider_name: str | None) -> bool:
    return any(
        route.browser_required or route.browser_optional
        for route in provider_routes(provider_name)
    )


def provider_requires_browser(provider_name: str | None) -> bool:
    return any(route.browser_required for route in provider_routes(provider_name))


def provider_supports_browser_preflight(provider_name: str | None) -> bool:
    return any(route.browser_preflight for route in provider_routes(provider_name))


def provider_supports_auth(provider_name: str | None) -> bool:
    return any(route.auth_supported for route in provider_routes(provider_name))


def provider_requires_pdf_conversion(provider_name: str | None) -> bool:
    return any(
        route.requires_pdf_conversion for route in provider_routes(provider_name)
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


def _xml_identity_hints(
    xml_root: ET.Element | None,
) -> tuple[str, list[str]]:
    if xml_root is None:
        return "", []
    doi = ""
    publisher_values: list[str] = []
    for node in xml_root.iter():
        if not isinstance(node.tag, str):
            continue
        local_name = node.tag.rsplit("}", 1)[-1].lower()
        text = " ".join("".join(node.itertext()).split())
        if (
            not doi
            and local_name == "article-id"
            and _normalize_catalog_token(node.get("pub-id-type")) == "doi"
        ):
            doi = _normalize_catalog_token(text)
        elif local_name in {"publisher-name", "journal-title"} and text:
            publisher_values.append(_normalize_catalog_token(text))
    return doi, publisher_values


def _provider_candidates_for_publisher_values(
    values: list[str],
) -> set[str]:
    candidates: set[str] = set()
    for spec in ordered_provider_specs():
        aliases = {
            _normalize_catalog_token(spec.display_name),
            *(_normalize_catalog_token(alias) for alias in spec.publisher_aliases),
        }
        if any(
            value
            and any(
                value == alias or alias in value or value in alias
                for alias in aliases
                if alias
            )
            for value in values
        ):
            candidates.add(spec.name)
    return candidates


def provider_for_xml_source(
    root_tag: str | None,
    xml_path: str | None,
    *,
    xml_root: ET.Element | None = None,
    doi: str | None = None,
    publisher: str | None = None,
    journal: str | None = None,
) -> str:
    root_name = _normalize_catalog_token(root_tag)
    lower_path = str(xml_path or "").lower()
    specs = ordered_provider_specs()
    path_candidates = {
        spec.name
        for spec in specs
        if any(token and token.lower() in lower_path for token in spec.xml_file_tokens)
    }
    root_candidates = {
        spec.name
        for spec in specs
        if root_name
        and root_name in {_normalize_catalog_token(tag) for tag in spec.xml_root_tags}
    }
    extracted_doi, publisher_values = _xml_identity_hints(xml_root)
    normalized_doi = _normalize_catalog_token(doi) or extracted_doi
    doi_candidates = {
        spec.name
        for spec in specs
        if normalized_doi
        and any(
            normalized_doi.startswith(_normalize_catalog_token(prefix))
            for prefix in spec.doi_prefixes
        )
    }
    publisher_values.extend(
        value
        for value in (
            _normalize_catalog_token(publisher),
            _normalize_catalog_token(journal),
        )
        if value
    )
    publisher_candidates = _provider_candidates_for_publisher_values(publisher_values)

    strong_sets = [
        candidates
        for candidates in (doi_candidates, publisher_candidates)
        if candidates
    ]
    if strong_sets:
        compatible = set.intersection(*strong_sets)
        if len(compatible) != 1:
            return "unknown"
        selected = next(iter(compatible))
        if len(path_candidates) == 1 and selected not in path_candidates:
            return "unknown"
        if root_candidates and selected not in root_candidates:
            return "unknown"
        return selected
    if len(path_candidates) == 1:
        return next(iter(path_candidates))
    if len(root_candidates) == 1:
        return next(iter(root_candidates))
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


def identity_ordered_provider_specs() -> tuple[ProviderSpec, ...]:
    """Return deterministic identity precedence without changing status order."""

    return tuple(
        sorted(
            PROVIDER_CATALOG.values(),
            key=lambda spec: (
                -(spec.identity_priority or 0),
                spec.status_order,
                spec.name,
            ),
        )
    )


def provider_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in ordered_provider_specs())


def official_provider_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in ordered_provider_specs() if spec.official)


def browser_preflight_provider_names() -> tuple[str, ...]:
    return tuple(
        spec.name
        for spec in ordered_provider_specs()
        if provider_supports_browser_preflight(spec.name)
    )


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
    result: dict[str, str] = {}
    for spec in identity_ordered_provider_specs():
        for raw_prefix in spec.doi_prefixes:
            prefix = _normalize_catalog_token(raw_prefix)
            if prefix:
                result.setdefault(prefix, spec.name)
    return result
