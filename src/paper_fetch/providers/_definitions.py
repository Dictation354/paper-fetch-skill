"""Static built-in provider definitions; importing these never loads clients."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from collections.abc import Iterable

from ..provider_contracts import (
    ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
    BodyTextThresholds,
    PdfSourcePathTemplate,
    ProviderRouteSpec,
    ProviderSpec,
)
from ._registry import (
    _default_bundle_route_source,
    validate_provider_identity_conflicts,
)
from ._ieee_routes import IEEE_ROUTES
from ..timeouts import DEFAULT_FULLTEXT_TIMEOUT_SECONDS


def normalize_rule_key(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", "_").split())


@dataclass(frozen=True)
class ProviderDefinition:
    catalog: ProviderSpec
    implementation: str
    sources: tuple[str, ...] = ()
    rules_name: str = ""
    rules_aliases: tuple[str, ...] = ()
    noise_profile: str = "generic"

    def __post_init__(self) -> None:
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
                            self.catalog.name, route, self.sources
                        ),
                    )
                    for route in self.catalog.routes
                ),
            ),
        )


def validate_provider_definitions(definitions: Iterable[ProviderDefinition]) -> None:
    seen: list[ProviderDefinition] = []
    rule_keys: dict[str, str] = {"generic": "generic"}
    noise_keys: dict[str, str] = {"generic": "generic"}
    for definition in definitions:
        spec = definition.catalog
        if not spec.name or spec.name != spec.name.strip().lower():
            raise ValueError("Provider definition requires a normalized name.")
        module, separator, attribute = definition.implementation.partition(":")
        if (
            not separator
            or not module
            or not attribute
            or not all(
                token.isidentifier() for token in (*module.split("."), attribute)
            )
        ):
            raise ValueError(
                f"Invalid provider implementation reference: {definition.implementation!r}"
            )
        if len(definition.sources) != len(set(definition.sources)):
            raise ValueError(f"Provider source declared more than once: {spec.name}")
        for existing in seen:
            if spec.name == existing.catalog.name:
                raise ValueError(
                    f"Provider definition declared more than once: {spec.name}"
                )
            if spec.status_order == existing.catalog.status_order:
                raise ValueError(f"Provider status_order conflict: {spec.name}")
            if definition.implementation == existing.implementation:
                raise ValueError(f"Provider implementation conflict: {spec.name}")
            if set(definition.sources) & set(existing.sources):
                raise ValueError(f"Provider source conflict: {spec.name}")
            validate_provider_identity_conflicts(spec, existing.catalog)
        for lookup, keys in (
            (rule_keys, (definition.rules_name, *definition.rules_aliases)),
            (
                noise_keys,
                (definition.noise_profile,)
                if definition.noise_profile != "generic"
                else (),
            ),
        ):
            for key in keys:
                normalized = normalize_rule_key(key)
                if not normalized:
                    continue
                if normalized in lookup and lookup[normalized] != spec.name:
                    raise ValueError(
                        f"Provider HTML rules alias/profile conflict: {key}"
                    )
                lookup[normalized] = spec.name
        seen.append(definition)


BUILTIN_PROVIDER_DEFINITIONS = (
    ProviderDefinition(
        catalog=ProviderSpec(
            name="crossref",
            display_name="Crossref",
            official=False,
            domains=(),
            doi_prefixes=(),
            publisher_aliases=(),
            asset_default="none",
            probe_capability="metadata_api",
            provider_managed_abstract_only=False,
            status_order=0,
            html_capable=False,
            api_hosts=("api.crossref.org",),
            sensitive_headers=("cr-clickthrough-client-token",),
            routes=(ProviderRouteSpec(name="metadata", kind="metadata"),),
        ),
        implementation="paper_fetch.providers.crossref:PROVIDER_BUNDLE",
        sources=("crossref_meta",),
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="elsevier",
            browser_backends=("camoufox", "byparr"),
            browser_default="byparr",
            browser_home_url="https://www.sciencedirect.com/",
            display_name="Elsevier",
            official=True,
            domains=("sciencedirect.com", "elsevier.com"),
            base_domains=("www.sciencedirect.com",),
            doi_prefixes=("10.1016/",),
            publisher_aliases=(
                "elsevier",
                "elsevier bv",
                "elsevier ltd",
                "elsevier masson sas",
            ),
            asset_default="none",
            probe_capability="metadata_api",
            provider_managed_abstract_only=False,
            status_order=1,
            api_hosts=("scopus.com", "www.scopus.com"),
            sensitive_headers=("x-els-apikey",),
            xml_root_tags=("full-text-retrieval-response",),
            xml_file_tokens=("elsevier", "10.1016"),
            routes=(
                ProviderRouteSpec(name="metadata_api", kind="metadata"),
                ProviderRouteSpec(
                    name="xml_api",
                    source="elsevier_xml",
                    kind="xml",
                    timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                ),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    source="elsevier_html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="pdf_api",
                    source="elsevier_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                    timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    source="elsevier_pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(name="object_assets", kind="assets", transport="api"),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
            ),
        ),
        implementation="paper_fetch.providers.elsevier:PROVIDER_BUNDLE",
        sources=("elsevier_xml", "elsevier_html", "elsevier_pdf"),
        rules_name="elsevier",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="springer",
            display_name="Springer",
            official=True,
            domains=(
                "springer.com",
                "springernature.com",
                "nature.com",
                "biomedcentral.com",
            ),
            doi_prefixes=("10.1038/", "10.1007/", "10.1186/"),
            publisher_aliases=(
                "springer",
                "springer nature",
                "springer science and business media llc",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=2,
            base_domains=("link.springer.com",),
            pdf_path_templates=("/content/pdf/{doi_quoted}.pdf",),
            pdf_source_path_templates=(
                PdfSourcePathTemplate(
                    domain="nature.com",
                    path_prefix="/articles/",
                    path_template="{source_path}.pdf",
                ),
            ),
            persist_provider_html=True,
            xml_root_tags=("article",),
            xml_file_tokens=("springer", "nature", "10.1038", "10.1007", "10.1186"),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="direct_html",
                    kind="html",
                    concurrency=2,
                ),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                    concurrency=2,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    concurrency=2,
                    asset_scope="body",
                ),
            ),
        ),
        implementation="paper_fetch.providers.springer:PROVIDER_BUNDLE",
        sources=("springer_html", "springer_pdf"),
        rules_name="springer_nature",
        rules_aliases=("springer", "nature"),
        noise_profile="springer_nature",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="wiley",
            display_name="Wiley",
            official=True,
            domains=("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com"),
            doi_prefixes=("10.1002/", "10.1111/"),
            publisher_aliases=(
                "wiley",
                "wiley blackwell",
                "john wiley and sons",
                "john wiley sons",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=3,
            base_domains=("onlinelibrary.wiley.com",),
            html_path_templates=("/doi/{doi}", "/doi/full/{doi}"),
            pdf_path_templates=(
                *ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
                "/doi/pdfdirect/{doi}",
                "/wol1/doi/{doi}/fullpdf",
            ),
            crossref_pdf_position=1,
            api_url_templates=(
                (
                    "tdm_pdf",
                    "https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                ),
            ),
            sensitive_headers=("wiley-tdm-client-token",),
            env_requirements=(),
            batch_concurrency=1,
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_optional=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                    timeout_seconds=120,
                ),
                ProviderRouteSpec(
                    name="tdm_pdf",
                    kind="pdf",
                    transport="api",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_optional=True,
                    browser_preflight=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                    timeout_seconds=120,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.wiley:PROVIDER_BUNDLE",
        sources=("wiley_browser",),
        rules_name="wiley",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="science",
            display_name="Science",
            official=True,
            domains=("www.science.org", "science.org"),
            doi_prefixes=("10.1126/",),
            publisher_aliases=(
                "american association for the advancement of science",
                "aaas",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=4,
            base_domains=("www.science.org", "science.org"),
            html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
            pdf_path_templates=(
                *ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
                "/doi/pdf/{doi}?download=true",
            ),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.science:PROVIDER_BUNDLE",
        sources=("science",),
        rules_name="science",
        rules_aliases=("aaas",),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="pnas",
            browser_backends=("camoufox", "byparr"),
            browser_default_x64="byparr",
            browser_home_url="https://www.pnas.org/",
            display_name="PNAS",
            official=True,
            domains=("www.pnas.org", "pnas.org"),
            doi_prefixes=("10.1073/",),
            publisher_aliases=(
                "proceedings of the national academy of sciences",
                "proceedings of the national academy of sciences of the united states of america",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=5,
            base_domains=("www.pnas.org", "pnas.org"),
            html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
            pdf_path_templates=(
                "/doi/epdf/{doi}",
                "/doi/pdf/{doi}?download=true",
                "/doi/pdf/{doi}",
            ),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.pnas:PROVIDER_BUNDLE",
        sources=("pnas",),
        rules_name="pnas",
        rules_aliases=(),
        noise_profile="pnas",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="ieee",
            display_name="IEEE",
            official=True,
            domains=("ieeexplore.ieee.org",),
            doi_prefixes=("10.1109/",),
            publisher_aliases=(
                "ieee",
                "institute of electrical and electronics engineers",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=6,
            routes=IEEE_ROUTES,
        ),
        implementation="paper_fetch.providers.ieee:PROVIDER_BUNDLE",
        sources=("ieee_html", "ieee_pdf"),
        rules_name="ieee",
        rules_aliases=(),
        noise_profile="ieee",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="arxiv",
            display_name="arXiv",
            official=True,
            domains=("arxiv.org",),
            doi_prefixes=("10.48550/",),
            publisher_aliases=("arxiv",),
            asset_default="body",
            probe_capability="metadata_api",
            provider_managed_abstract_only=False,
            status_order=7,
            persist_provider_html=True,
            routes=(
                ProviderRouteSpec(
                    name="atom_metadata",
                    kind="metadata",
                    transport="api",
                    timeout_seconds=60,
                    qps=1,
                ),
                ProviderRouteSpec(name="official_html", kind="html"),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="source_assets",
                    kind="assets",
                    hosts=("arxiv.org",),
                    qps=1,
                    asset_scope="all",
                ),
            ),
        ),
        implementation="paper_fetch.providers.arxiv:PROVIDER_BUNDLE",
        sources=("arxiv_html", "arxiv_pdf"),
        rules_name="arxiv",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="copernicus",
            display_name="Copernicus",
            official=True,
            domains=(),
            doi_prefixes=("10.5194/",),
            publisher_aliases=(
                "copernicus",
                "copernicus publications",
                "copernicus gmbh",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            status_order=8,
            domain_suffixes=("copernicus.org",),
            xml_path_templates=("/articles/{volume}/{page}/{year}/{suffix}.xml",),
            landing_path_templates=("/articles/{volume}/{page}/{year}/",),
            pdf_path_templates=("/articles/{volume}/{page}/{year}/{suffix}.pdf",),
            emits_html_managed_marker=False,
            html_capable=False,
            xml_root_tags=("article",),
            xml_file_tokens=("copernicus", "10.5194"),
            body_text_thresholds=BodyTextThresholds(min_chars=500),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(name="xml", kind="xml"),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=2,
                ),
            ),
        ),
        implementation="paper_fetch.providers.copernicus:PROVIDER_BUNDLE",
        sources=("copernicus_xml", "copernicus_pdf"),
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="ams",
            display_name="AMS",
            official=True,
            domains=("journals.ametsoc.org", "ametsoc.org"),
            doi_prefixes=("10.1175/",),
            publisher_aliases=(
                "american meteorological society",
                "ams",
                "american meteorological society (ams)",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=9,
            base_domains=("journals.ametsoc.org",),
            crossref_pdf_position=0,
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    concurrency=2,
                    asset_scope="body",
                ),
            ),
        ),
        implementation="paper_fetch.providers.ams:PROVIDER_BUNDLE",
        sources=("ams_html", "ams_pdf"),
        rules_name="ams",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="mdpi",
            display_name="MDPI",
            official=True,
            domains=("www.mdpi.com", "mdpi.com"),
            doi_prefixes=("10.3390/",),
            publisher_aliases=("mdpi", "mdpi ag"),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            status_order=10,
            base_domains=("www.mdpi.com",),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.mdpi:PROVIDER_BUNDLE",
        sources=("mdpi_html", "mdpi_pdf"),
        rules_name="mdpi",
        rules_aliases=(),
        noise_profile="mdpi",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="royalsocietypublishing",
            display_name="Royal Society Publishing",
            official=True,
            domains=("royalsocietypublishing.org",),
            doi_prefixes=("10.1098/",),
            publisher_aliases=("the royal society", "royal society publishing"),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            status_order=11,
            base_domains=("royalsocietypublishing.org",),
            html_path_templates=("/doi/{doi}",),
            pdf_path_templates=("/doi/pdf/{doi}",),
            body_text_thresholds=BodyTextThresholds(min_chars=800),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.royalsocietypublishing:PROVIDER_BUNDLE",
        sources=("royalsocietypublishing_html", "royalsocietypublishing_pdf"),
        rules_name="royalsocietypublishing",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="annualreviews",
            display_name="Annual Reviews",
            official=True,
            domains=("annualreviews.org", "www.annualreviews.org"),
            doi_prefixes=("10.1146/",),
            publisher_aliases=(
                "annual reviews",
                "annual reviews inc",
                "annual reviews inc.",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=12,
            base_domains=("www.annualreviews.org",),
            html_path_templates=(
                "/content/journals/{doi}",
                "/doi/{doi}",
            ),
            pdf_path_templates=("/doi/pdf/{doi}",),
            crossref_pdf_position=0,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    concurrency=2,
                    asset_scope="body",
                ),
            ),
        ),
        implementation="paper_fetch.providers.annualreviews:PROVIDER_BUNDLE",
        sources=("annualreviews_html", "annualreviews_pdf"),
        rules_name="annualreviews",
        rules_aliases=(),
        noise_profile="annualreviews",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="plos",
            display_name="PLOS",
            official=True,
            domains=("journals.plos.org",),
            doi_prefixes=("10.1371/",),
            publisher_aliases=(
                "plos",
                "public library of science",
                "public library of science (plos)",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            status_order=13,
            domain_suffixes=("plos.org",),
            xml_path_templates=(
                "/{journal_path}/article/file?id={doi}&type=manuscript",
            ),
            pdf_path_templates=(
                "/{journal_path}/article/file?id={doi}&type=printable",
            ),
            emits_html_managed_marker=False,
            html_capable=False,
            xml_root_tags=("article",),
            xml_file_tokens=("10.1371", "plos"),
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="xml",
                    kind="xml",
                    hosts=("plos.org", "doi.org", "storage.googleapis.com"),
                ),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    hosts=("plos.org", "storage.googleapis.com"),
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    hosts=("plos.org", "storage.googleapis.com"),
                    asset_scope="body",
                ),
            ),
        ),
        implementation="paper_fetch.providers.plos:PROVIDER_BUNDLE",
        sources=("plos_xml", "plos_pdf"),
        rules_name="plos",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="oxfordacademic",
            display_name="Oxford Academic",
            official=True,
            domains=("academic.oup.com",),
            doi_prefixes=("10.1093/",),
            publisher_aliases=(
                "oxford academic",
                "oxford university press",
                "oxford university press (oup)",
                "oup",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            status_order=14,
            base_domains=("academic.oup.com",),
            pdf_path_templates=(
                "/doi/pdf/{doi}",
                "/doi/epdf/{doi}",
            ),
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="direct_html",
                    kind="html",
                    timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                ),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=2,
                ),
            ),
        ),
        implementation="paper_fetch.providers.oxfordacademic:PROVIDER_BUNDLE",
        sources=("oxfordacademic_html", "oxfordacademic_pdf"),
        rules_name="oxfordacademic",
        rules_aliases=(),
        noise_profile="oxfordacademic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="acs",
            display_name="ACS",
            official=True,
            domains=("www.acs.org", "pubs.acs.org", "acs.org"),
            doi_prefixes=("10.1021/",),
            publisher_aliases=(
                "american chemical society",
                "american chemical society (acs)",
                "acs publications",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=15,
            base_domains=("pubs.acs.org",),
            html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
            pdf_path_templates=(
                *ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
                "/doi/pdf/{doi}?download=true",
            ),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.acs:PROVIDER_BUNDLE",
        sources=("acs",),
        rules_name="acs",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="iop",
            display_name="IOP Publishing",
            official=True,
            domains=("iopscience.iop.org",),
            doi_prefixes=("10.1088/",),
            publisher_aliases=(
                "iop publishing",
                "institute of physics publishing",
                "iopscience",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=16,
            base_domains=("iopscience.iop.org",),
            html_path_templates=("/article/{doi}",),
            pdf_path_templates=("/article/{doi}/pdf",),
            crossref_pdf_position=0,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(
                    name="metadata",
                    kind="metadata",
                    source="crossref_metadata",
                    concurrency=2,
                ),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    source="iop_html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    timeout_seconds=120,
                    concurrency=1,
                    acceptance_policy="provider_html_body",
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    source="iop_pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    timeout_seconds=120,
                    concurrency=1,
                    acceptance_policy="validated_pdf",
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.iop:PROVIDER_BUNDLE",
        sources=("iop_html", "iop_pdf"),
        rules_name="iop",
        rules_aliases=(),
        noise_profile="iop",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="aip",
            display_name="AIP Publishing",
            official=True,
            domains=("pubs.aip.org",),
            doi_prefixes=("10.1063/",),
            publisher_aliases=(
                "aip publishing",
                "aip publishing llc",
                "american institute of physics",
                "aip",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=17,
            base_domains=("pubs.aip.org",),
            html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
            pdf_path_templates=ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
            crossref_pdf_position=0,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.aip:PROVIDER_BUNDLE",
        sources=("aip_html", "aip_pdf"),
        rules_name="aip",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="frontiers",
            display_name="Frontiers",
            official=True,
            domains=("www.frontiersin.org", "frontiersin.org"),
            doi_prefixes=("10.3389/",),
            publisher_aliases=(
                "frontiers",
                "frontiers media",
                "frontiers media s.a.",
                "frontiers media sa",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            status_order=18,
            base_domains=("www.frontiersin.org",),
            landing_path_templates=("/articles/{doi}/full",),
            xml_path_templates=("/journals/{journal_slug}/articles/{doi}/xml",),
            pdf_path_templates=(
                "/journals/{journal_slug}/articles/{doi}/pdf",
                "/articles/{doi}/pdf",
            ),
            emits_html_managed_marker=False,
            html_capable=False,
            xml_root_tags=("article",),
            xml_file_tokens=("10.3389", "frontiers"),
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(name="xml", kind="xml"),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=2,
                ),
            ),
        ),
        implementation="paper_fetch.providers.frontiers:PROVIDER_BUNDLE",
        sources=("frontiers_xml", "frontiers_pdf"),
        rules_name="frontiers",
        rules_aliases=(),
        noise_profile="generic",
    ),
    ProviderDefinition(
        catalog=ProviderSpec(
            name="tandf",
            display_name="Taylor & Francis Online",
            official=True,
            domains=("tandfonline.com", "www.tandfonline.com"),
            domain_suffixes=("tandfonline.com",),
            doi_prefixes=("10.1080/",),
            publisher_aliases=(
                "taylor & francis",
                "taylor & francis group",
                "informa uk limited",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            status_order=19,
            base_domains=("www.tandfonline.com",),
            html_path_templates=("/doi/full/{doi}", "/doi/abs/{doi}", "/doi/{doi}"),
            pdf_path_templates=ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
            crossref_pdf_position=0,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    browser_optional=True,
                    requires_playwright=True,
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=0,
                ),
            ),
        ),
        implementation="paper_fetch.providers.tandf:PROVIDER_BUNDLE",
        sources=("tandf_html", "tandf_pdf"),
        rules_name="tandf",
        rules_aliases=(),
        noise_profile="generic",
    ),
)

validate_provider_definitions(BUILTIN_PROVIDER_DEFINITIONS)
PROVIDER_DEFINITIONS = MappingProxyType(
    {definition.catalog.name: definition for definition in BUILTIN_PROVIDER_DEFINITIONS}
)
RULE_PROVIDER_INDEX = MappingProxyType(
    {
        normalize_rule_key(key): definition.catalog.name
        for definition in BUILTIN_PROVIDER_DEFINITIONS
        for key in (definition.rules_name, *definition.rules_aliases)
        if key
    }
)
NOISE_PROVIDER_INDEX = MappingProxyType(
    {
        normalize_rule_key(definition.noise_profile): definition.catalog.name
        for definition in BUILTIN_PROVIDER_DEFINITIONS
        if definition.noise_profile != "generic"
    }
)
