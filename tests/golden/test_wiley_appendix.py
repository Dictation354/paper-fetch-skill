"""Reviewed Appendix A content, independent of the extractor's summary baseline."""

import re

import pytest
from bs4 import BeautifulSoup

from paper_fetch.providers.wiley import WileyClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from tests.golden_criteria import golden_criteria_asset

DOI = "10.1029/2004gb002273"
# Entire visible source paragraph, including its original paragraph number.
APPENDIX_PARAGRAPH = (
    "[43] The terrestrial carbon model VEgetation-Global-Atmosphere-Soil (VEGAS [ Zeng , 2003 "
    "; Zeng et al. , 2004 ]) simulates the dynamics of vegetation growth and competition "
    "among different plant functional types (PFTs). It includes four PFTs: broadleaf tree, "
    "needleleaf tree, cold grass, and warm grass. The different photosynthetic pathways are "
    "distinguished for C3 (the first three PFTs above) and C4 (warm grass) plants. Phenology "
    "is simulated dynamically as the balance between growth and respiration/turnover. "
    "Competition is determined by climatic constraints and resource allocation strategy such "
    "as temperature tolerance and height-dependent shading. The relative competitive "
    "advantage then determines fractional coverage of each PFT with possibility of "
    "coexistence. Accompanying the vegetation dynamics is the full terrestrial carbon cycle, "
    "starting from photosynthetic carbon assimilation in the leaves and the allocation of "
    "this carbon into three vegetation carbon pools: leaf, root, and wood. After accounting "
    "for respiration, the biomass turnover from these three vegetation carbon pools cascades "
    "into a fast soil carbon pool, an intermediate, and finally a slow soil pool. "
    "Temperature- and moisture-dependent decomposition of these carbon pools returns carbon "
    "back into atmosphere, thus closing the terrestrial carbon cycle. Wetland is "
    "parameterized as a function of soil moisture and topography. A flat place becomes "
    "wetland when soil moisture is above a value close to saturation, and the corresponding "
    "decomposition rate R h decreases as soil moisture further increases. A fire module "
    "includes the effects of moisture availability, fuel loading, and PFT dependent "
    "resistance. The vegetation component is coupled to land and atmosphere through a soil "
    "moisture dependence of photosynthesis and evapotranspiration, as well as dependence on "
    "temperature, radiation, and atmospheric CO 2 . The isotope carbon 13 is modeled by "
    "assuming a different carbon discrimination for C3 and C4 plants, thus providing a "
    "diagnostic quantity useful for distinguishing ocean and land sources and sinks of "
    "atmospheric CO 2 . Competition between C3 and C4 grass is a function of temperature and "
    "CO 2 following Collatz et al. [1998] . Unique features of VEGAS include a vegetation "
    "height dependent maximum canopy which introduces a decadal timescale that can be "
    "important for feedback into climate variability and a decreasing temperature dependence "
    "of respiration from fast to slow soil pools [ Liski et al. , 1999 ; Barrett , 2002 ]. "
    "Specifically, our two lower soil pools have weaker temperature dependence of "
    "decomposition due to physical protection underground (Q 10 value of 2.2 for the fast "
    "pool, 1.35 for the intermediate pool, and 1.1 for the slow pool). In addition, the "
    "turnover times in the two lower pools are decadal and longer so that the interannual "
    "variability in R h almost completely comes from the fast soil (about 250 PgC)."
)
CITATIONS = {
    "gbc1137-bib-0070",
    "gbc1137-bib-0074",
    "gbc1137-bib-0009",
    "gbc1137-bib-0041",
    "gbc1137-bib-0004",
}


@pytest.mark.parametrize(
    "asset",
    [
        "original.html",
        "acquisition/browser-retry-2026-09-16/landing-dom.html",
        "acquisition/known-gaps-2026-09-16/000-browser_rendered_dom.html",
    ],
)
def test_reviewed_wiley_appendix_complete_paragraph_and_citations(asset):
    html = golden_criteria_asset(DOI, asset).read_text()
    source = BeautifulSoup(html, "html.parser").select_one("#gbc1137-app-0001")
    assert source.find("h2").get_text(strip=True) == "Appendix A"
    assert source.find("p").get_text(" ", strip=True) == APPENDIX_PARAGRAPH
    assert {
        a["href"].removeprefix("#") for a in source.select("a.bibLink")
    } == CITATIONS
    markdown, extraction = WileyClient(None, {}).extract_markdown(
        html,
        "https://agupubs.onlinelibrary.wiley.com/doi/full/" + DOI,
        metadata={"doi": DOI},
    )
    assert markdown.count("## Appendix A") == 1
    appendix = markdown.split("## Appendix A", 1)[1].split("## References", 1)[0]
    # Ignore only Markdown emphasis/link syntax and whitespace for comparison.
    visible = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", appendix)
    visible = re.sub(r"</?sub>", "", visible.replace("*", ""))

    def compact(text):
        return re.sub(r"\s+", "", text)

    assert compact(APPENDIX_PARAGRAPH) == compact(visible)
    assert len(extraction["references"]) == 75
    # The provider renders author-year citations as text. Check each source
    # target remains the same complete reference in the extracted reference list.
    soup = BeautifulSoup(html, "html.parser")
    for target in CITATIONS:
        ref = extraction["references"][int(target.rsplit("-", 1)[1]) - 1]
        assert compact(ref["raw"]) in compact(
            soup.find(attrs={"data-bib-id": target}).get_text(" ", strip=True)
        )
    url = "https://agupubs.onlinelibrary.wiley.com/doi/full/" + DOI
    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=url,
            content_type="text/html",
            body=html.encode(),
            markdown_text=markdown,
            merged_metadata={"doi": DOI},
            diagnostics={"extraction": extraction},
        ),
    )
    article = WileyClient(None, {}).to_article_model({"doi": DOI}, payload)
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert (
        rendered.index("Conclusions")
        < rendered.index("## Appendix A")
        < rendered.index("## References")
    )
    assert "We have benefited from stimulating discussions" not in markdown
