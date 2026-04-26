from __future__ import annotations

from dataclasses import dataclass

from tests.golden_criteria import doi_to_fixture_slug


@dataclass(frozen=True)
class ProviderBenchmarkSample:
    provider: str
    doi: str
    year: int
    title: str
    landing_url: str
    expected_source: str
    accepted_live_source_trail_groups: tuple[tuple[str, ...], ...]
    required_env: tuple[str, ...] = ()
    requires_flaresolverr: bool = False
    fallback_dois: tuple[str, ...] = ()
    fixture_name: str | None = None
    fixture_kind: str | None = None
    resolve_url: str | None = None


def golden_criteria_fixture(doi: str, filename: str) -> str:
    return f"golden_criteria/{doi_to_fixture_slug(doi)}/{filename}"


PROVIDER_BENCHMARK_SAMPLES: dict[str, ProviderBenchmarkSample] = {
    "elsevier": ProviderBenchmarkSample(
        provider="elsevier",
        doi="10.1016/j.rse.2025.114648",
        year=2025,
        title="Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations",
        landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
        expected_source="elsevier_xml",
        accepted_live_source_trail_groups=(("fulltext:elsevier_article_ok",),),
        required_env=("ELSEVIER_API_KEY", "CROSSREF_MAILTO"),
        fallback_dois=("10.1016/j.rse.2026.115369",),
        fixture_name=golden_criteria_fixture("10.1016/j.rse.2025.114648", "original.xml"),
        fixture_kind="xml",
        resolve_url="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
    ),
    "springer": ProviderBenchmarkSample(
        provider="springer",
        doi="10.1038/d41586-023-01829-w",
        year=2023,
        title="How to make the workplace fairer for female researchers",
        landing_url="https://www.nature.com/articles/d41586-023-01829-w",
        expected_source="springer_html",
        accepted_live_source_trail_groups=(("fulltext:springer_html_ok",),),
        required_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture("10.1038/d41586-023-01829-w", "original.html"),
        fixture_kind="html",
    ),
    "science": ProviderBenchmarkSample(
        provider="science",
        doi="10.1126/science.ady3136",
        year=2026,
        title="Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration",
        landing_url="https://www.science.org/doi/full/10.1126/science.ady3136",
        expected_source="science",
        accepted_live_source_trail_groups=(("fulltext:science_html_ok",),),
        required_env=(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
        ),
        requires_flaresolverr=True,
        fixture_name=golden_criteria_fixture("10.1126/science.ady3136", "original.html"),
        fixture_kind="html",
    ),
    "wiley": ProviderBenchmarkSample(
        provider="wiley",
        doi="10.1111/gcb.16414",
        year=2022,
        title="Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
        landing_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
        expected_source="wiley_browser",
        accepted_live_source_trail_groups=(("fulltext:wiley_html_ok",),),
        required_env=(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
        ),
        requires_flaresolverr=True,
        fixture_name=golden_criteria_fixture("10.1111/gcb.16414", "original.html"),
        fixture_kind="html",
    ),
    "pnas": ProviderBenchmarkSample(
        provider="pnas",
        doi="10.1073/pnas.2406303121",
        year=2024,
        title="The kinetics of SARS-CoV-2 infection based on a human challenge study",
        landing_url="https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
        expected_source="pnas",
        accepted_live_source_trail_groups=(("fulltext:pnas_html_ok",),),
        required_env=(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
        ),
        requires_flaresolverr=True,
        fixture_name=golden_criteria_fixture("10.1073/pnas.2406303121", "original.html"),
        fixture_kind="html",
    ),
}


WILEY_PDF_FALLBACK_SAMPLE = ProviderBenchmarkSample(
    provider="wiley",
    doi="10.1111/cas.16395",
    year=2024,
    title="Current status and future direction of cancer research using artificial intelligence for clinical application",
    landing_url="https://onlinelibrary.wiley.com/doi/full/10.1111/cas.16395",
    expected_source="wiley_browser",
    accepted_live_source_trail_groups=(
        ("fulltext:wiley_pdf_api_ok", "fulltext:wiley_pdf_fallback_ok"),
        ("fulltext:wiley_pdf_browser_ok", "fulltext:wiley_pdf_fallback_ok"),
    ),
    required_env=("CROSSREF_MAILTO", "WILEY_TDM_CLIENT_TOKEN"),
    fixture_name=golden_criteria_fixture("10.1111/cas.16395", "extracted.md"),
    fixture_kind="markdown",
)


def provider_benchmark_sample(provider: str) -> ProviderBenchmarkSample:
    return PROVIDER_BENCHMARK_SAMPLES[provider]


def iter_provider_benchmark_samples() -> tuple[ProviderBenchmarkSample, ...]:
    return tuple(PROVIDER_BENCHMARK_SAMPLES.values())


def source_trail_matches(
    source_trail: list[str] | tuple[str, ...],
    accepted_groups: tuple[tuple[str, ...], ...],
) -> bool:
    return any(all(marker in source_trail for marker in group) for group in accepted_groups)
