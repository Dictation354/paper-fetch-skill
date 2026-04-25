"""Static provider identity, routing, and capability catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssetDefault = Literal["none", "body", "all"]


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
    abstract_only_policy: str
    client_factory_path: str
    status_order: int


PROVIDER_CATALOG: dict[str, ProviderSpec] = {
    "crossref": ProviderSpec(
        name="crossref",
        display_name="Crossref",
        official=False,
        domains=(),
        doi_prefixes=(),
        publisher_aliases=(),
        asset_default="none",
        probe_capability="metadata_api",
        abstract_only_policy="metadata_fallback",
        client_factory_path="paper_fetch.providers.crossref:CrossrefClient",
        status_order=0,
    ),
    "elsevier": ProviderSpec(
        name="elsevier",
        display_name="Elsevier",
        official=True,
        domains=("sciencedirect.com", "elsevier.com"),
        doi_prefixes=("10.1016/",),
        publisher_aliases=("elsevier", "elsevier bv", "elsevier ltd", "elsevier masson sas"),
        asset_default="none",
        probe_capability="metadata_api",
        abstract_only_policy="metadata_fallback",
        client_factory_path="paper_fetch.providers.elsevier:ElsevierClient",
        status_order=1,
    ),
    "springer": ProviderSpec(
        name="springer",
        display_name="Springer",
        official=True,
        domains=("springer.com", "springernature.com", "nature.com", "biomedcentral.com"),
        doi_prefixes=("10.1038/", "10.1007/", "10.1186/"),
        publisher_aliases=(
            "springer",
            "springer nature",
            "springer science and business media llc",
        ),
        asset_default="body",
        probe_capability="routing_signal",
        abstract_only_policy="provider_managed",
        client_factory_path="paper_fetch.providers.springer:SpringerClient",
        status_order=2,
    ),
    "wiley": ProviderSpec(
        name="wiley",
        display_name="Wiley",
        official=True,
        domains=("wiley.com", "onlinelibrary.wiley.com"),
        doi_prefixes=("10.1002/", "10.1111/"),
        publisher_aliases=("wiley", "wiley blackwell", "john wiley and sons", "john wiley sons"),
        asset_default="body",
        probe_capability="routing_signal",
        abstract_only_policy="provider_managed",
        client_factory_path="paper_fetch.providers.wiley:WileyClient",
        status_order=3,
    ),
    "science": ProviderSpec(
        name="science",
        display_name="Science",
        official=True,
        domains=("science.org",),
        doi_prefixes=("10.1126/",),
        publisher_aliases=("american association for the advancement of science", "aaas"),
        asset_default="body",
        probe_capability="routing_signal",
        abstract_only_policy="provider_managed",
        client_factory_path="paper_fetch.providers.science:ScienceClient",
        status_order=4,
    ),
    "pnas": ProviderSpec(
        name="pnas",
        display_name="PNAS",
        official=True,
        domains=("pnas.org",),
        doi_prefixes=("10.1073/",),
        publisher_aliases=(
            "proceedings of the national academy of sciences",
            "proceedings of the national academy of sciences of the united states of america",
        ),
        asset_default="body",
        probe_capability="routing_signal",
        abstract_only_policy="provider_managed",
        client_factory_path="paper_fetch.providers.pnas:PnasClient",
        status_order=5,
    ),
}

SOURCE_PROVIDER_MAP: dict[str, str] = {
    "crossref_meta": "crossref",
    "elsevier_xml": "elsevier",
    "elsevier_pdf": "elsevier",
    "springer_html": "springer",
    "wiley_browser": "wiley",
    "science": "science",
    "pnas": "pnas",
}


def ordered_provider_specs() -> tuple[ProviderSpec, ...]:
    return tuple(sorted(PROVIDER_CATALOG.values(), key=lambda spec: spec.status_order))


def provider_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in ordered_provider_specs())


def official_provider_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in ordered_provider_specs() if spec.official)


def provider_status_order() -> tuple[str, ...]:
    return provider_names()


def is_official_provider(provider_name: str | None) -> bool:
    normalized = str(provider_name or "").strip().lower()
    spec = PROVIDER_CATALOG.get(normalized)
    return bool(spec and spec.official)


def provider_managed_abstract_only_names() -> frozenset[str]:
    return frozenset(
        spec.name
        for spec in PROVIDER_CATALOG.values()
        if spec.abstract_only_policy == "provider_managed"
    )


def provider_display_names() -> dict[str, str]:
    return {spec.name: spec.display_name for spec in PROVIDER_CATALOG.values()}


def default_asset_profile_for_provider(provider_name: str | None) -> AssetDefault:
    normalized = str(provider_name or "").strip().lower()
    spec = PROVIDER_CATALOG.get(normalized)
    return spec.asset_default if spec is not None else "none"


def provider_for_source(source_name: str | None) -> str | None:
    normalized = str(source_name or "").strip().lower()
    return SOURCE_PROVIDER_MAP.get(normalized)


def known_article_source_names() -> frozenset[str]:
    return frozenset(SOURCE_PROVIDER_MAP)


def default_asset_profile_for_source(source_name: str | None) -> AssetDefault:
    provider_name = provider_for_source(source_name)
    return default_asset_profile_for_provider(provider_name)


def doi_prefix_provider_map() -> dict[str, str]:
    return {
        prefix: spec.name
        for spec in ordered_provider_specs()
        for prefix in spec.doi_prefixes
    }


def url_provider_tokens() -> dict[str, tuple[str, ...]]:
    return {spec.name: spec.domains for spec in ordered_provider_specs() if spec.domains}
