from __future__ import annotations

from dataclasses import dataclass


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
        fixture_name="elsevier_10.1016_j.rse.2025.114648.xml",
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
        fixture_name="nature_d41586_023_01829_w.html",
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
            "FLARESOLVERR_MIN_INTERVAL_SECONDS",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
        ),
        requires_flaresolverr=True,
        fixture_name="science_10.1126_science.ady3136.html",
        fixture_kind="html",
    ),
    "wiley": ProviderBenchmarkSample(
        provider="wiley",
        doi="10.1111/cas.16117",
        year=2024,
        title="Cell cycle heterogeneity and plasticity of colorectal cancer stem cells",
        landing_url="https://onlinelibrary.wiley.com/doi/10.1111/cas.16117",
        expected_source="wiley_browser",
        accepted_live_source_trail_groups=(("fulltext:wiley_pdf_api_ok", "fulltext:wiley_pdf_fallback_ok"),),
        required_env=("CROSSREF_MAILTO", "WILEY_TDM_CLIENT_TOKEN"),
        fallback_dois=("10.1111/cas.16395",),
        fixture_name="wiley_10.1111_cas.16117.md",
        fixture_kind="markdown",
    ),
    "pnas": ProviderBenchmarkSample(
        provider="pnas",
        doi="10.1073/pnas.2406303121",
        year=2024,
        title="The kinetics of SARS-CoV-2 infection based on a human challenge study",
        landing_url="https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
        expected_source="pnas",
        accepted_live_source_trail_groups=(
            ("fulltext:pnas_html_ok",),
            ("fulltext:pnas_pdf_fallback_ok",),
        ),
        required_env=(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
            "FLARESOLVERR_MIN_INTERVAL_SECONDS",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
        ),
        requires_flaresolverr=True,
        fallback_dois=("10.1073/pnas.2206192119",),
        fixture_name="pnas_10.1073_pnas.2406303121.md",
        fixture_kind="markdown",
    ),
}


def provider_benchmark_sample(provider: str) -> ProviderBenchmarkSample:
    return PROVIDER_BENCHMARK_SAMPLES[provider]


def iter_provider_benchmark_samples() -> tuple[ProviderBenchmarkSample, ...]:
    return tuple(PROVIDER_BENCHMARK_SAMPLES.values())


def source_trail_matches(
    source_trail: list[str] | tuple[str, ...],
    accepted_groups: tuple[tuple[str, ...], ...],
) -> bool:
    return any(all(marker in source_trail for marker in group) for group in accepted_groups)
