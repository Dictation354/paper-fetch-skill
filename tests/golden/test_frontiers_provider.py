from __future__ import annotations
from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
)
import re


DOI = "10.3389/fmars.2023.1101972"
LEGACY_FULL_URL = f"https://www.frontiersin.org/articles/{DOI}/full"
CANONICAL_FULL_URL = (
    f"https://www.frontiersin.org/journals/marine-science/articles/{DOI}/full"
)
XML_URL = f"https://www.frontiersin.org/journals/marine-science/articles/{DOI}/xml"
PDF_URL = f"https://www.frontiersin.org/journals/marine-science/articles/{DOI}/pdf"
IMAGE_URL = "https://www.frontiersin.org/files/Articles/1101972/xml-images/fmars-10-1101972-g001.webp"
SUPPLEMENT_URL = (
    "https://www.frontiersin.org/files/Articles/1101972/supplementary-material/"
    "Table_1.docx"
)
SUPPLEMENT_API_URL = (
    "https://www.frontiersin.org/api/v4/articles/1101972/supplemental-data"
)
TARGET_DOI = "10.3389/fpls.2020.01216"
TARGET_CANONICAL_FULL_URL = (
    f"https://www.frontiersin.org/journals/plant-science/articles/{TARGET_DOI}/full"
)
TARGET_XML_URL = (
    f"https://www.frontiersin.org/journals/plant-science/articles/{TARGET_DOI}/xml"
)
TARGET_IMAGE_STEMS = tuple(f"fpls-11-01216-g{index:03d}" for index in range(1, 6))
TARGET_IMAGE_URLS = tuple(
    f"https://www.frontiersin.org/files/Articles/569407/xml-images/{stem}.webp"
    for stem in TARGET_IMAGE_STEMS
)
TARGET_WRONG_IMAGE_URLS = tuple(
    f"https://www.frontiersin.org/files/Articles/01216/xml-images/{stem}.webp"
    for stem in TARGET_IMAGE_STEMS
)
WEBP_1X1 = bytes.fromhex(
    "52494646220000005745425056503820160000003001009d012a010001000140262500"
    "4e8021f000fefee0000000"
)


def test_real_fmars_figure_and_scoc_equation() -> None:
    # Read the registered original.xml, not the constructed _frontiers_xml().
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(DOI))
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    figure = next(
        a for a in article.assets if a.kind == "figure" and a.download_url == IMAGE_URL
    )
    assert "Effects of temperature and pH on the survival rate" in figure.caption
    assert "6-week incubation period" in figure.caption
    image = f"![Figure 1]({IMAGE_URL})"
    assert markdown.count(image) == 1
    assert markdown.index(image) < markdown.index(
        "Effects of temperature and pH on the survival rate"
    )
    # M1 consists of the product of two fractions, dC/dt and V/A.
    assert "(1)\n\n$$\n" + r"\text{SCOC =}\frac{dC}{dt}\frac{V}{A}" + "\n$$" in markdown
    assert "V is the volume of the overlying water" in markdown
    assert "A is the sediment surface area" in markdown


def test_real_fmars_treatment_table_preserves_species_and_cells() -> None:
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(DOI))
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    compact = re.sub(r"\s+", " ", markdown)
    assert (
        "| Treatment | Control | Acidification | Temperature | Climate Change |"
        in compact
    )
    lanice = (
        "| **Temperature (° C)** | 18.3 ± 0.8 | 19.4 ± 0.9 | 21.1 ± 0.9 | 21.9 ± 1.4 |"
    )
    abra = (
        "| **Temperature (° C)** | 19.3 ± 0.5 | 19.4 ± 0.4 | 22.1 ± 0.8 | 22.4 ± 0.7 |"
    )
    assert lanice in compact
    assert abra in compact
    assert (
        compact.index(lanice) < compact.index("| ***Abra alba***") < compact.index(abra)
    )
    assert (
        "| **pCO<sub>2</sub>(μatm)** | 496.3 ± 65.0 | 1515.7 ± 420.5 | 488.4 ± 67.8 | 1297.2 ± 195.2 |"
        in compact
    )
