from __future__ import annotations
import re
from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
)
import unittest


DOI = "10.5194/acp-24-1-2024"
LANDING_URL = "https://acp.copernicus.org/articles/24/1/2024/"
XML_URL = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024.xml"
PDF_URL = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024.pdf"
MARKDOWN_REVIEWED_FIXTURES = {
    "structure": "10.5194_acp-24-1-2024",
    "figure": "10.5194_acp-24-1-2024",
    "references": "10.5194_acp-24-1-2024",
    "pdf_fallback": "10.5194_acp-1-1-2001",
}


if __name__ == "__main__":
    unittest.main()


def test_real_acp_figure_and_numbered_equations() -> None:
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(DOI))
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    # original.xml Ch1.F1, Ch1.E6 and Ch1.E8; MathML mfrac/msub/msubsup.
    url = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024-f01.png"
    figure = next(
        a for a in article.assets if a.kind == "figure" and a.download_url == url
    )
    assert "DOC-normalized mass absorption coefficients" in figure.caption
    image = f"![Figure 1]({url})"
    assert markdown.count(image) == 1
    assert markdown.index(image) < markdown.index(
        "DOC-normalized mass absorption coefficients"
    )
    assert "\n6\n\n$$\n" + r"\Phi_{Ox} = \frac{P_{Ox}}{R_{abs}}," + "\n$$" in markdown
    assert "\n8\n\n$$\n" + r"[Ox] = \frac{P_{Ox}}{k_{Ox}^{′}}," + "\n$$" in markdown


def test_real_bg_table_preserves_cals_column_associations() -> None:
    article = build_article_from_fixture(
        golden_corpus_fixture_for_doi("10.5194/bg-21-1-2024")
    )
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    # original.xml Ch1.T1: col2-col6 saline soils; col7 cottonseed meal.
    assert "Soil samples and cottonseed meal properties." in markdown
    compact = re.sub(r"\s+", " ", markdown)
    assert (
        "| | Salinity 1 | Salinity 2 | Salinity 3 | Salinity 4 | Salinity 5 | Cottonseed / meal |"
        in compact
    )
    assert "| Total C (%) | 3.38b | 3.18c | 3.16c | 3.57a | 3.35b | 42.98 |" in compact
    assert "| Total N (%) | 0.18d | 0.19d | 0.20c | 0.22b | 0.26a | 5.84 |" in compact
    assert "| Salinity (%) | 0.25e | 0.58d | 0.75c | 1.00b | 2.64a | ND |" in compact
