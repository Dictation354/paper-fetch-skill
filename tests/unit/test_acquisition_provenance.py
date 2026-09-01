from __future__ import annotations

from dataclasses import asdict

import pytest

from paper_fetch.acquisition import (
    AcquisitionProvenance,
    coerce_acquisition_provenance,
)
from paper_fetch.mcp.markdown_frontmatter import parse_markdown_front_matter
from paper_fetch.models import ArticleModel, FetchEnvelope, Metadata, Quality, Section
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    ProviderRouteSpec,
    acquisition_for_provider_route,
    acquisition_matches_provider_route,
)
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers._waterfall import WaterfallStep, run_provider_waterfall


def _wiley_article() -> ArticleModel:
    return ArticleModel(
        doi="10.1029/98wr02522",
        source="wiley_browser",
        metadata=Metadata(title="Acquisition provenance", abstract="Abstract."),
        sections=[
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="Accepted full-text body. " * 80,
            )
        ],
        quality=Quality(),
        acquisition=AcquisitionProvenance(
            provider="wiley",
            route="tdm_pdf",
            representation="pdf",
            transport="api",
            fallback_used=True,
        ),
    )


def test_envelope_rejects_conflicting_article_acquisition() -> None:
    article = _wiley_article()
    conflicting = AcquisitionProvenance(
        provider="wiley",
        route="browser_pdf",
        representation="pdf",
        transport="browser",
        fallback_used=True,
    )

    with pytest.raises(ValueError, match="must match"):
        FetchEnvelope(
            doi=article.doi,
            source=article.source,
            has_fulltext=True,
            article=article,
            acquisition=conflicting,
        )


def test_acquisition_coercion_is_strict_and_never_invents_missing_facts() -> None:
    valid = {
        "provider": " Wiley ",
        "route": " TDM_PDF ",
        "representation": "pdf",
        "transport": "api",
        "fallback_used": True,
    }
    assert asdict(coerce_acquisition_provenance(valid)) == {
        "provider": "wiley",
        "route": "tdm_pdf",
        "representation": "pdf",
        "transport": "api",
        "fallback_used": True,
    }
    assert coerce_acquisition_provenance(None) is None
    assert coerce_acquisition_provenance({**valid, "fallback_used": "true"}) is None
    assert (
        coerce_acquisition_provenance(
            {key: value for key, value in valid.items() if key != "route"}
        )
        is None
    )


def test_catalog_maps_every_content_route_to_exact_acquisition() -> None:
    for provider, spec in PROVIDER_CATALOG.items():
        for route in spec.routes:
            assert route.transport in {"api", "browser", "http"}
            acquisition = acquisition_for_provider_route(provider, route.name)
            if route.kind == "assets":
                assert acquisition is None
                continue
            assert acquisition is not None
            assert acquisition.representation == route.kind
            assert acquisition.transport == route.transport
            assert acquisition_matches_provider_route(acquisition)

    assert acquisition_for_provider_route(
        "wiley", "tdm_pdf", fallback_used=True
    ) == AcquisitionProvenance(
        provider="wiley",
        route="tdm_pdf",
        representation="pdf",
        transport="api",
        fallback_used=True,
    )
    assert acquisition_for_provider_route("wiley", "unknown") is None


def test_provider_route_transport_defaults_are_explicit_and_validated() -> None:
    assert ProviderRouteSpec(name="metadata", kind="metadata").transport == "api"
    assert ProviderRouteSpec(name="direct_html", kind="html").transport == "http"
    assert (
        ProviderRouteSpec(
            name="browser_html", kind="html", browser_required=True
        ).transport
        == "browser"
    )
    with pytest.raises(ValueError, match="Browser-backed"):
        ProviderRouteSpec(
            name="browser_html",
            kind="html",
            browser_required=True,
            transport="http",
        )


def test_waterfall_stamps_exact_route_in_structured_trace() -> None:
    class _Client:
        name = "wiley"

    def _tdm_payload(_state):
        return build_provider_payload(
            provider="wiley",
            route_kind="pdf_fallback",
            source_url="https://api.wiley.test/article.pdf",
            content_type="application/pdf",
            body=b"%PDF-test",
        )

    payload = run_provider_waterfall(
        [
            WaterfallStep(
                label="pdf_api",
                run=_tdm_payload,
                route_name="tdm_pdf",
            )
        ],
        client=_Client(),
    )

    assert payload.content is not None
    assert payload.content.route_name == "tdm_pdf"
    assert any(
        event.stage == "fulltext" and event.outcome == "ok" and event.route == "tdm_pdf"
        for event in payload.trace
    )


def test_waterfall_success_trace_prefers_payload_route_over_step_default() -> None:
    class _Client:
        name = "ieee"

    def _browser_pdf_payload(_state):
        return build_provider_payload(
            provider="ieee",
            route_kind="pdf_fallback",
            route_name="browser_pdf",
            source_url="https://ieee.test/article.pdf",
            content_type="application/pdf",
            body=b"%PDF-test",
        )

    payload = run_provider_waterfall(
        [
            WaterfallStep(
                label="pdf",
                run=_browser_pdf_payload,
                route_name="direct_pdf",
            )
        ],
        client=_Client(),
    )

    assert any(
        event.stage == "fulltext"
        and event.outcome == "ok"
        and event.route == "browser_pdf"
        for event in payload.trace
    )


def test_markdown_front_matter_requires_current_acquisition() -> None:
    article = _wiley_article()
    front_matter = parse_markdown_front_matter(article.to_ai_markdown())

    assert front_matter is not None
    assert front_matter.source == "wiley_browser"
    assert front_matter.acquisition == article.acquisition

    missing_acquisition = parse_markdown_front_matter(
        """---
doi: "10.1029/98wr02522"
source: "wiley_browser"
has_fulltext: true
content_kind: "fulltext"
---

# Incomplete cache
"""
    )
    assert missing_acquisition is None

    invalid = parse_markdown_front_matter(
        """---
doi: "10.1029/98wr02522"
source: "wiley_browser"
acquisition:
  provider: "wiley"
  route: "tdm_pdf"
  representation: "pdf"
  transport: "api"
  fallback_used: "true"
has_fulltext: true
content_kind: "fulltext"
---
"""
    )
    assert invalid is None
