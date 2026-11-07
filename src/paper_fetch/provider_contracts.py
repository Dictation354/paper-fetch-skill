"""Immutable provider contracts, independent of catalog assembly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Literal

from .acquisition import AcquisitionTransport
from .metadata.types import ProviderMetadata

AssetDefault = Literal["none", "body", "all"]
MetadataProbeShortCircuit = Callable[[str], ProviderMetadata | None]
ProviderRouteKind = Literal["metadata", "html", "xml", "pdf", "assets"]
ProviderRouteTransport = AcquisitionTransport


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


@dataclass(frozen=True, kw_only=True)
class ProviderRouteSpec:
    """Local requirements and policy for one provider acquisition route."""

    name: str
    kind: ProviderRouteKind
    source: str | None = None
    order: int | None = None
    browser_required: bool = False
    browser_optional: bool = False
    browser_preflight: bool = False
    auth_supported: bool = False
    requires_playwright: bool = False
    requires_pdf_conversion: bool = False
    timeout_seconds: int | None = None
    concurrency: int | None = None
    qps: float | None = None
    rate_limit_wait_budget_seconds: float | None = None
    transient_retry_categories: tuple[str, ...] = ()
    hosts: tuple[str, ...] = ()
    acceptance_policy: str | None = None
    asset_scope: AssetDefault | None = None
    notes: str | None = None
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
    persist_provider_html: bool = False
    xml_root_tags: tuple[str, ...] = ()
    xml_file_tokens: tuple[str, ...] = ()
    emits_html_managed_marker: bool = True
    html_capable: bool = True
    body_text_thresholds: BodyTextThresholds = DEFAULT_BODY_TEXT_THRESHOLDS
    env_requirements: tuple[str, ...] = ()
    batch_concurrency: int | None = None
    routes: tuple[ProviderRouteSpec, ...] = ()
    browser_backends: tuple[str, ...] = ("camoufox", "byparr")
    browser_default: str = "byparr"
    browser_default_x64: str | None = None
    browser_home_url: str = "about:blank"

    def __post_init__(self) -> None:
        if not self.routes:
            raise ValueError("Provider routes must be declared explicitly.")
        effective_batch_concurrency = self.batch_concurrency
        if effective_batch_concurrency is None:
            effective_batch_concurrency = (
                1 if any(route.browser_required for route in self.routes) else 2
            )
            object.__setattr__(self, "batch_concurrency", effective_batch_concurrency)
        if isinstance(effective_batch_concurrency, bool) or not (
            1 <= effective_batch_concurrency <= 8
        ):
            raise ValueError("batch_concurrency must be an integer from 1 to 8.")
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
        if self.asset_default != "none" and not any(
            route.kind == "assets" for route in self.routes
        ):
            raise ValueError(
                "Providers that download body resources must declare an explicit "
                "assets route."
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
    route: str
    kind: ProviderRouteKind
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


def _default_route_acceptance(kind: ProviderRouteKind) -> str:
    return {
        "metadata": "metadata_identity",
        "html": "provider_html_body",
        "xml": "structured_xml_body",
        "pdf": "validated_pdf",
        "assets": "validated_asset",
    }[kind]
