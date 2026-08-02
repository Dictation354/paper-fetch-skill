from __future__ import annotations

from dataclasses import dataclass

import paper_fetch.providers  # noqa: F401
from paper_fetch.provider_catalog import official_provider_names
from tests.golden_criteria import doi_to_fixture_slug


@dataclass(frozen=True)
class ProviderBenchmarkSample:
    provider: str
    doi: str
    year: int
    title: str
    landing_url: str
    accepted_sources: tuple[str, ...]
    accepted_live_source_trail_groups: tuple[tuple[str, ...], ...]
    required_env: tuple[str, ...] = ()
    recommended_env: tuple[str, ...] = ()
    fallback_dois: tuple[str, ...] = ()
    fixture_name: str | None = None
    fixture_kind: str | None = None
    resolve_url: str | None = None

    def accepted_live_outcomes(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Pair each accepted source with only its declared route trail(s)."""

        if len(self.accepted_sources) == 1:
            source = self.accepted_sources[0]
            return tuple(
                (source, group) for group in self.accepted_live_source_trail_groups
            )
        if len(self.accepted_sources) != len(self.accepted_live_source_trail_groups):
            raise ValueError(
                f"{self.provider}: accepted sources and source-trail groups "
                "must have equal lengths unless exactly one source is accepted"
            )
        return tuple(
            zip(
                self.accepted_sources,
                self.accepted_live_source_trail_groups,
                strict=True,
            )
        )

    def accepts_live_result(
        self,
        *,
        source: str,
        source_trail: list[str] | tuple[str, ...],
    ) -> bool:
        return any(
            source == accepted_source
            and all(marker in source_trail for marker in accepted_group)
            for accepted_source, accepted_group in self.accepted_live_outcomes()
        )


def golden_criteria_fixture(doi: str, filename: str) -> str:
    return f"golden_criteria/{doi_to_fixture_slug(doi)}/{filename}"


PROVIDER_BENCHMARK_SAMPLES: dict[str, ProviderBenchmarkSample] = {
    "elsevier": ProviderBenchmarkSample(
        provider="elsevier",
        doi="10.1016/j.rse.2025.114648",
        year=2025,
        title="Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations",
        landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
        accepted_sources=("elsevier_xml",),
        accepted_live_source_trail_groups=(("fulltext:elsevier_article_ok",),),
        required_env=("ELSEVIER_API_KEY",),
        recommended_env=("CROSSREF_MAILTO",),
        fallback_dois=("10.1016/j.rse.2026.115369",),
        fixture_name=golden_criteria_fixture(
            "10.1016/j.rse.2025.114648", "original.xml"
        ),
        fixture_kind="xml",
        resolve_url="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
    ),
    "springer": ProviderBenchmarkSample(
        provider="springer",
        doi="10.1038/s43247-024-01295-w",
        year=2024,
        title="Hydrological drought forecasts using precipitation data depend on catchment properties and human activities",
        landing_url="https://www.nature.com/articles/s43247-024-01295-w",
        accepted_sources=("springer_html",),
        accepted_live_source_trail_groups=(("fulltext:springer_html_ok",),),
        recommended_env=("CROSSREF_MAILTO",),
    ),
    "science": ProviderBenchmarkSample(
        provider="science",
        doi="10.1126/science.ady3136",
        year=2026,
        title="Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration",
        landing_url="https://www.science.org/doi/full/10.1126/science.ady3136",
        accepted_sources=("science",),
        accepted_live_source_trail_groups=(
            ("fulltext:science_html_ok",),
            ("fulltext:science_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1126/science.ady3136", "original.html"
        ),
        fixture_kind="html",
    ),
    "wiley": ProviderBenchmarkSample(
        provider="wiley",
        doi="10.1111/gcb.16414",
        year=2022,
        title="Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
        landing_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
        accepted_sources=("wiley_browser",),
        accepted_live_source_trail_groups=(
            ("fulltext:wiley_html_ok",),
            ("fulltext:wiley_pdf_browser_ok", "fulltext:wiley_pdf_fallback_ok"),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture("10.1111/gcb.16414", "original.html"),
        fixture_kind="html",
    ),
    "pnas": ProviderBenchmarkSample(
        provider="pnas",
        doi="10.1073/pnas.2406303121",
        year=2024,
        title="The kinetics of SARS-CoV-2 infection based on a human challenge study",
        landing_url="https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
        accepted_sources=("pnas",),
        accepted_live_source_trail_groups=(
            ("fulltext:pnas_html_ok",),
            ("fulltext:pnas_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1073/pnas.2406303121", "original.html"
        ),
        fixture_kind="html",
    ),
    "mdpi": ProviderBenchmarkSample(
        provider="mdpi",
        doi="10.3390/membranes15030093",
        year=2025,
        title="Simulation of Carbon Dioxide Absorption in a Hollow Fiber Membrane Contactor Under Non-Isothermal Conditions",
        landing_url="https://www.mdpi.com/2077-0375/15/3/93",
        accepted_sources=("mdpi_html",),
        accepted_live_source_trail_groups=(("fulltext:mdpi_html_ok",),),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.3390/membranes15030093", "original.html"
        ),
        fixture_kind="html",
    ),
    "ieee": ProviderBenchmarkSample(
        provider="ieee",
        doi="10.1109/TIM.2024.3509573",
        year=2025,
        title="Skeleton-Based Few-Shot Action Recognition via Fine-Grained Information Capture and Adaptive Metric Aggregation",
        landing_url="https://ieeexplore.ieee.org/document/10772041/",
        accepted_sources=("ieee_html",),
        accepted_live_source_trail_groups=(("fulltext:ieee_html_ok",),),
        fixture_name=golden_criteria_fixture(
            "10.1109/TIM.2024.3509573", "original.html"
        ),
        fixture_kind="html",
    ),
    "arxiv": ProviderBenchmarkSample(
        provider="arxiv",
        doi="10.48550/arxiv.2605.06663v1",
        year=2026,
        title="EMO: Pretraining Mixture of Experts for Emergent Modularity",
        landing_url="https://arxiv.org/abs/2605.06663v1",
        accepted_sources=("arxiv_html",),
        accepted_live_source_trail_groups=(("fulltext:arxiv_html_ok",),),
        fixture_name=golden_criteria_fixture(
            "10.48550/arxiv.2605.06663v1", "original.html"
        ),
        fixture_kind="html",
    ),
    "ams": ProviderBenchmarkSample(
        provider="ams",
        doi="10.1175/jcli-d-23-0738.1",
        year=2024,
        title="Human Influence Has Increased the Likelihood of Extreme Autumn Fire Weather in California",
        landing_url="https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml",
        accepted_sources=("ams_html", "ams_pdf"),
        accepted_live_source_trail_groups=(
            ("fulltext:ams_html_ok",),
            ("fulltext:ams_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1175/jcli-d-23-0738.1", "original.html"
        ),
        fixture_kind="html",
    ),
    "copernicus": ProviderBenchmarkSample(
        provider="copernicus",
        doi="10.5194/acp-24-1-2024",
        year=2024,
        title="Seasonal variations in photooxidant formation and light absorption in aqueous extracts of ambient particles",
        landing_url="https://acp.copernicus.org/articles/24/1/2024/",
        accepted_sources=("copernicus_xml",),
        accepted_live_source_trail_groups=(("fulltext:copernicus_xml_ok",),),
        fixture_name=golden_criteria_fixture("10.5194/acp-24-1-2024", "original.xml"),
        fixture_kind="xml",
    ),
    "royalsocietypublishing": ProviderBenchmarkSample(
        provider="royalsocietypublishing",
        doi="10.1098/rsta.2019.0558",
        year=2020,
        title="Creation and application of virtual patient cohorts of heart models",
        landing_url="https://royalsocietypublishing.org/doi/10.1098/rsta.2019.0558",
        accepted_sources=("royalsocietypublishing_html",),
        accepted_live_source_trail_groups=(
            ("fulltext:royalsocietypublishing_html_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture("10.1098/rsta.2019.0558", "original.html"),
        fixture_kind="html",
    ),
    "annualreviews": ProviderBenchmarkSample(
        provider="annualreviews",
        doi="10.1146/annurev-control-030123-013355",
        year=2025,
        title="Stretchable Shape Sensing and Computation for General Shape-Changing Robots",
        landing_url="https://www.annualreviews.org/content/journals/10.1146/annurev-control-030123-013355",
        accepted_sources=("annualreviews_html", "annualreviews_pdf"),
        accepted_live_source_trail_groups=(
            ("fulltext:annualreviews_html_ok",),
            ("fulltext:annualreviews_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1146/annurev-control-030123-013355", "original.html"
        ),
        fixture_kind="html",
    ),
    "oxfordacademic": ProviderBenchmarkSample(
        provider="oxfordacademic",
        doi="10.1093/bioinformatics/btaa161",
        year=2020,
        title="Unified methods for feature selection in large-scale genomic studies with censored survival outcomes",
        landing_url="https://academic.oup.com/bioinformatics/article/36/11/3409/5802463",
        accepted_sources=("oxfordacademic_html",),
        accepted_live_source_trail_groups=(("fulltext:oxfordacademic_html_ok",),),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1093/bioinformatics/btaa161", "original.html"
        ),
        fixture_kind="html",
    ),
    "plos": ProviderBenchmarkSample(
        provider="plos",
        doi="10.1371/journal.pone.0263725",
        year=2022,
        title="Social media usage to share information in communication journals",
        landing_url="https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0263725",
        accepted_sources=("plos_xml",),
        accepted_live_source_trail_groups=(("fulltext:plos_xml_ok",),),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1371/journal.pone.0263725", "original.xml"
        ),
        fixture_kind="xml",
    ),
    "frontiers": ProviderBenchmarkSample(
        provider="frontiers",
        doi="10.3389/fmars.2023.1101972",
        year=2023,
        title="Ocean acidification and warming modify stimulatory benthos effects on coastal ecosystem functioning",
        landing_url="https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1101972/full",
        accepted_sources=("frontiers_xml", "frontiers_pdf"),
        accepted_live_source_trail_groups=(
            ("fulltext:frontiers_xml_ok",),
            ("fulltext:frontiers_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_kind="xml",
    ),
    "acs": ProviderBenchmarkSample(
        provider="acs",
        doi="10.1021/acsomega.4c03987",
        year=2024,
        title="Functionalized Metal-Free Carbon Nanosphere Catalyst for the Selective C-N Bond Formation under Open-Air Conditions",
        landing_url="https://pubs.acs.org/doi/10.1021/acsomega.4c03987",
        accepted_sources=("acs",),
        accepted_live_source_trail_groups=(("fulltext:acs_html_ok",),),
        recommended_env=("CROSSREF_MAILTO",),
    ),
    "iop": ProviderBenchmarkSample(
        provider="iop",
        doi="10.1088/1748-9326/ab7d02",
        year=2020,
        title="Quantifying the role of internal variability in the temperature we expect to observe in the coming decades",
        landing_url="https://iopscience.iop.org/article/10.1088/1748-9326/ab7d02",
        accepted_sources=("iop_html", "iop_pdf"),
        accepted_live_source_trail_groups=(
            ("fulltext:iop_html_ok",),
            ("fulltext:iop_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1088/1748-9326/ab7d02",
            "original.html",
        ),
        fixture_kind="html",
    ),
    "aip": ProviderBenchmarkSample(
        provider="aip",
        doi="10.1063/5.0129134",
        year=2022,
        title="On-chip on-demand delivery of K+ for in vitro bioelectronics",
        landing_url="https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/On-chip-on-demand-delivery-of-K-for-in-vitro",
        accepted_sources=("aip_html", "aip_pdf"),
        accepted_live_source_trail_groups=(
            ("fulltext:aip_html_ok",),
            ("fulltext:aip_pdf_fallback_ok",),
        ),
        recommended_env=("CROSSREF_MAILTO",),
        fixture_name=golden_criteria_fixture(
            "10.1063/5.0129134",
            "original.html",
        ),
        fixture_kind="html",
    ),
}

SPRINGER_NEWS_ACCESS_GATE_SAMPLE = ProviderBenchmarkSample(
    provider="springer",
    doi="10.1038/d41586-023-01829-w",
    year=2023,
    title="How to make the workplace fairer for female researchers",
    landing_url="https://www.nature.com/articles/d41586-023-01829-w",
    accepted_sources=("crossref_meta",),
    accepted_live_source_trail_groups=(("fallback:metadata_only",),),
    recommended_env=("CROSSREF_MAILTO",),
    fixture_name=golden_criteria_fixture("10.1038/d41586-023-01829-w", "original.html"),
    fixture_kind="html",
)


WILEY_PDF_FALLBACK_SAMPLE = ProviderBenchmarkSample(
    provider="wiley",
    doi="10.1111/cas.16395",
    year=2024,
    title="Current status and future direction of cancer research using artificial intelligence for clinical application",
    landing_url="https://onlinelibrary.wiley.com/doi/full/10.1111/cas.16395",
    accepted_sources=("wiley_browser",),
    accepted_live_source_trail_groups=(
        ("fulltext:wiley_pdf_api_ok", "fulltext:wiley_pdf_fallback_ok"),
        ("fulltext:wiley_pdf_browser_ok", "fulltext:wiley_pdf_fallback_ok"),
    ),
    required_env=("WILEY_TDM_CLIENT_TOKEN",),
    recommended_env=("CROSSREF_MAILTO",),
    fixture_name=golden_criteria_fixture("10.1111/cas.16395", "extracted.md"),
    fixture_kind="markdown",
)


def provider_benchmark_sample(provider: str) -> ProviderBenchmarkSample:
    return PROVIDER_BENCHMARK_SAMPLES[provider]


def iter_provider_benchmark_samples() -> tuple[ProviderBenchmarkSample, ...]:
    return tuple(
        PROVIDER_BENCHMARK_SAMPLES[provider] for provider in official_provider_names()
    )


def source_trail_matches(
    source_trail: list[str] | tuple[str, ...],
    accepted_groups: tuple[tuple[str, ...], ...],
) -> bool:
    return any(
        all(marker in source_trail for marker in group) for group in accepted_groups
    )
