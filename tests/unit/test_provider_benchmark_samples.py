from __future__ import annotations

import paper_fetch.providers  # noqa: F401
from paper_fetch.provider_catalog import official_provider_names
from tests.provider_benchmark_samples import (
    PROVIDER_BENCHMARK_SAMPLES,
    ProviderBenchmarkSample,
)


def test_provider_benchmark_samples_cover_official_live_smoke_providers() -> None:
    assert set(PROVIDER_BENCHMARK_SAMPLES) == set(official_provider_names())


def test_crossref_mailto_is_recommended_but_never_required() -> None:
    for sample in PROVIDER_BENCHMARK_SAMPLES.values():
        assert "CROSSREF_MAILTO" not in sample.required_env
        if sample.provider not in {"arxiv", "copernicus", "ieee"}:
            assert "CROSSREF_MAILTO" in sample.recommended_env


def test_live_source_and_trail_are_validated_as_one_outcome() -> None:
    sample = PROVIDER_BENCHMARK_SAMPLES["ams"]

    assert sample.accepts_live_result(
        source="ams_html",
        source_trail=["fulltext:ams_html_ok"],
    )
    assert sample.accepts_live_result(
        source="ams_pdf",
        source_trail=["fulltext:ams_pdf_fallback_ok"],
    )
    assert not sample.accepts_live_result(
        source="ams_html",
        source_trail=["fulltext:ams_pdf_fallback_ok"],
    )
    assert not sample.accepts_live_result(
        source="ams_pdf",
        source_trail=["fulltext:ams_html_ok"],
    )


def test_single_public_source_can_have_multiple_accepted_route_trails() -> None:
    sample = PROVIDER_BENCHMARK_SAMPLES["wiley"]

    assert sample.accepts_live_result(
        source="wiley_browser",
        source_trail=[
            "fulltext:wiley_pdf_browser_ok",
            "fulltext:wiley_pdf_fallback_ok",
        ],
    )


def test_tandf_live_html_and_pdf_outcomes_are_paired_with_their_sources() -> None:
    sample = PROVIDER_BENCHMARK_SAMPLES["tandf"]

    assert sample.accepts_live_result(
        source="tandf_html",
        source_trail=["fulltext:tandf_html_ok"],
    )
    assert sample.accepts_live_result(
        source="tandf_pdf",
        source_trail=["fulltext:tandf_pdf_fallback_ok"],
    )
    assert not sample.accepts_live_result(
        source="tandf_html",
        source_trail=["fulltext:tandf_pdf_fallback_ok"],
    )


def test_ambiguous_live_source_trail_configuration_is_rejected() -> None:
    sample = ProviderBenchmarkSample(
        provider="example",
        doi="10.1000/example",
        year=2026,
        title="Example",
        landing_url="https://example.test/article",
        accepted_sources=("example_html", "example_pdf"),
        accepted_live_source_trail_groups=(
            ("fulltext:example_html_ok",),
            ("fulltext:example_pdf_ok",),
            ("fulltext:example_other_ok",),
        ),
    )

    try:
        sample.accepted_live_outcomes()
    except ValueError as exc:
        assert "must have equal lengths" in str(exc)
    else:
        raise AssertionError("ambiguous live outcome configuration was accepted")
