"""IEEE route declarations shared by provider catalog tooling."""

from __future__ import annotations

from ..provider_catalog import ProviderRouteSpec


IEEE_ROUTES = (
    ProviderRouteSpec(name="metadata", kind="metadata"),
    ProviderRouteSpec(name="rest_html", kind="html", transport="api"),
    ProviderRouteSpec(
        name="browser_html",
        kind="html",
        browser_optional=True,
        browser_preflight=True,
        concurrency=1,
        timeout_seconds=120,
    ),
    ProviderRouteSpec(
        name="direct_pdf",
        kind="pdf",
        requires_pdf_conversion=True,
    ),
    ProviderRouteSpec(
        name="browser_pdf",
        kind="pdf",
        browser_optional=True,
        browser_preflight=True,
        requires_pdf_conversion=True,
        concurrency=1,
        timeout_seconds=120,
    ),
    ProviderRouteSpec(name="direct_landing", kind="html", transport="http"),
    ProviderRouteSpec(
        name="browser_landing",
        kind="html",
        browser_optional=True,
        browser_preflight=True,
        concurrency=1,
        timeout_seconds=120,
    ),
)


def landing_route_name(acquisition_source: str) -> str:
    return (
        "browser_landing"
        if acquisition_source.endswith("_browser")
        else "direct_landing"
    )


__all__ = ["IEEE_ROUTES", "landing_route_name"]
