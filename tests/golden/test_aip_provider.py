from __future__ import annotations
import re
from urllib.parse import urlsplit
from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
)
from pathlib import Path
from bs4 import BeautifulSoup
from tests.golden_criteria import golden_criteria_asset
from tests.support.reviewed_publisher_content import _words


AIP_STRUCTURE_DOI = "10.1063/5.0129134"
AIP_STRUCTURE_LANDING = (
    "https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/"
    "On-chip-on-demand-delivery-of-K-for-in-vitro"
)
AIP_TABLE_FORMULA_DOI = "10.1063/5.0188905"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_real_aip_ion_pump_figure_identity_and_caption() -> None:
    article = build_article_from_fixture(
        golden_corpus_fixture_for_doi(AIP_STRUCTURE_DOI)
    )
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    # original.html .fig[data-id=f1]. Compare the complete stable CDN identity;
    # the archived query contains an expiring publisher signature.
    image = re.search(r"!\[Figure 1\]\(([^)]+)\)", markdown)
    assert image
    figure = next(
        a for a in article.assets if a.kind == "figure" and a.path == image.group(1)
    )
    parsed = urlsplit(figure.download_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "aipp.silverchair-cdn.com"
    assert (
        parsed.path
        == "/aipp/content_public/journal/adv/12/12/10.1063_5.0129134/2/m_125205_1_f1.jpeg"
    )
    assert "Image of the ion pump with the adapter" in figure.caption
    assert "Reactions taking place at the working electrode" in figure.caption
    assert markdown.index(image.group(0)) < markdown.index(
        "Image of the ion pump with the adapter"
    )


def test_real_aip_energy_equations_and_lattice_parameter_table() -> None:
    article = build_article_from_fixture(
        golden_corpus_fixture_for_doi(AIP_TABLE_FORMULA_DOI)
    )
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    # original.html jumplink-d1/d2: E=sum_i epsilon_i; epsilon_i=F(phi_i^(1),...,phi_i^(p)).
    assert (
        "**Equation 1.**\n\n$$\n"
        + r"\begin{matrix} E = \sum\limits_{i}⁡\varepsilon_{i}, \end{matrix}"
        + "\n$$"
        in markdown
    )
    assert (
        "**Equation 2.**\n\n$$\n"
        + r"\begin{matrix} \varepsilon_{i} = F(\varphi_{i}^{(1)},…,\varphi_{i}^{(p)}), \end{matrix}"
        + "\n$$"
        in markdown
    )
    compact = re.sub(r"\s+", " ", markdown)
    assert (
        r"| Method | Lattice parameter / $a / b(\text{Å})$ | Lattice parameter / $c(\text{Å})$ | Lattice parameter / *γ* (deg) | Max relative error against Expt. (%) |"
        in compact
    )
    assert "| ACE potential relaxation | 3.115 58 | 4.981 53 | 120 | 0.116 |" in compact
    assert "| DFT relaxation (PBEsol) | 3.112 88 | 4.982 47 | 120 | 0.032 |" in compact
    assert "| Experiment<sup>64</sup> | 3.111 97 | 4.980 89 | 120 | 0 |" in compact


def test_original_aip_alt_and_modal_caption_variants_render_once():
    doi = AIP_TABLE_FORMULA_DOI
    soup = BeautifulSoup(
        golden_criteria_asset(doi, "original.html").read_text(), "lxml"
    )
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    rendered = _words(markdown)
    for figure_id, anchor in [
        (
            "f1",
            "Room temperature thermal conductivities of different materials vs their electronic bandgaps",
        ),
        ("f5", "The effects of biaxial strains on thermal conductivities of"),
    ]:
        figure = soup.select_one(f'.fig-section[data-id="{figure_id}"]')
        modal = soup.select_one(f'.fig-modal[content-id="{figure_id}"]')
        assert anchor in figure.img["alt"]
        assert anchor in modal.select_one(".fig-caption").get_text()
        caption = figure.select_one(".fig-caption")
        for formula in caption.select(".inline-formula"):
            formula.replace_with("FORMULA")
        for run in caption.get_text(" ", strip=True).split("FORMULA"):
            if len(_words(run)) > 20:
                assert _words(run) in rendered
        assert rendered.count(_words(anchor)) == 1
    assert "Refer to the image caption for details" not in markdown
