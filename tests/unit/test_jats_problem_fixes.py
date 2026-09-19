"""Minimal provider-specific JATS formula/citation boundaries."""

import pytest

from paper_fetch.providers.plos import parse_plos_xml

DOI = "10.1371/journal.pcbi.1003118"


def _plos(formula):
    return parse_plos_xml(
        f"""<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="doi">{DOI}</article-id></article-meta></front><body><sec><title>Results</title><p>Before <inline-formula>{formula}</inline-formula> after.</p></sec></body></article>""".encode(),
        source_url="https://journals.plos.org/ploscompbiol/article/file",
    )


def test_plos_inline_graphic_uses_existing_official_formula_route():
    result = _plos(f'<inline-graphic xlink:href="info:doi/{DOI}.e001"/>')
    url = f"https://journals.plos.org/ploscompbiol/article/file?id={DOI}.e001&type=thumbnail"
    assert f"Before ![Formula]({url}) after." in result.markdown_text
    assert result.assets[0]["kind"] == "formula"
    assert result.assets[0]["link"] == url
    assert result.semantic_losses.formula_fallback_count == 1
    assert result.semantic_losses.formula_missing_count == 0
    from paper_fetch.providers.plos import _plos_figure_candidates

    assert _plos_figure_candidates(None, asset=result.assets[0], user_agent="test") == [
        url
    ]


@pytest.mark.parametrize(
    "content", ["<math><mi>x</mi></math>", "<tex-math>x^2</tex-math>"]
)
def test_plos_inline_graphic_does_not_override_source_math(content):
    result = _plos(content + f'<inline-graphic xlink:href="info:doi/{DOI}.e001"/>')
    assert "$x" in result.markdown_text
    assert "![Formula]" not in result.markdown_text
    assert result.assets == []


@pytest.mark.parametrize(
    "href", ["", "info:doi/malformed", "info:doi/10.1371/journal.pone.999.e001"]
)
def test_plos_missing_or_unrelated_inline_formula_stays_missing(href):
    result = _plos(f'<inline-graphic xlink:href="{href}"/>')
    assert "Before [Formula unavailable] after." in result.markdown_text
    assert result.semantic_losses.formula_missing_count == 1
    assert result.semantic_losses.formula_fallback_count == 0


def test_shared_inline_graphic_is_only_interpreted_inside_formula_context():
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml

    body = b"""<article><body><sec><title>Results</title><p>Outside <inline-graphic href="ordinary.png"/> inside <inline-formula><inline-graphic href="equation.png"/></inline-formula> priority <inline-formula><graphic href="preferred.png"/><inline-graphic href="alternative.png"/></inline-formula>.</p></sec></body></article>"""
    result = parse_jats_xml(body, source_url="https://publisher.example/article.xml")
    assert "![Formula](https://publisher.example/equation.png)" in result.markdown_text
    assert "![Formula](https://publisher.example/preferred.png)" in result.markdown_text
    assert "ordinary.png" not in result.markdown_text
    assert "alternative.png" not in result.markdown_text
    assert result.semantic_losses.formula_fallback_count == 2


def test_copernicus_empty_citations_resolve_targets_without_overwriting_labels():
    from paper_fetch.providers._article_markdown_copernicus import parse_copernicus_xml
    from paper_fetch.xml_security import parse_xml

    source = "https://hess.copernicus.org/articles/28/1/2024/article.xml"
    xml = b"""<article><body><sec><title>Results</title><p>Before <xref ref-type="bibr" rid="r1 r2 bad"/> after. Existing <xref ref-type="bibr" rid="r1"><italic>Already supplied</italic></xref>. Other <xref ref-type="fig" rid="f1"/>.</p><p>Unknown <xref ref-type="bibr"/> and unlabelled <xref ref-type="bibr" rid="r3"/>.</p></sec></body><back><ref-list><ref id="r1"><label>Smith et al.(2020)Smith, Doe</label><mixed-citation>First work</mixed-citation></ref><ref id="r2"><label>9</label><mixed-citation>Second work</mixed-citation></ref><ref id="r3"><mixed-citation>Third work</mixed-citation></ref></ref-list></back></article>"""
    root = parse_xml(xml)
    result = parse_copernicus_xml(xml, source_url=source, xml_root=root)
    assert (
        f"Before [Smith et al. (2020)]({source}#r1); [9]({source}#r2); [Reference unavailable: bad] after."
        in result.markdown_text
    )
    assert "Existing *Already supplied*." in result.markdown_text
    assert "Other ." in result.markdown_text
    assert (
        f"Unknown [Reference unavailable] and unlabelled [Reference r3]({source}#r3)."
        in result.markdown_text
    )
    assert root.find(".//xref").text is None  # caller-owned source is not changed
    without_url = parse_copernicus_xml(xml, source_url="")
    assert (
        "Before Smith et al. (2020); 9; [Reference unavailable: bad] after."
        in without_url.markdown_text
    )


@pytest.mark.parametrize("wrapper", ["italic", "bold", "named-content"])
def test_plos_scientific_stars_survive_rendered_markdown(wrapper):
    from bs4 import BeautifulSoup
    from markdown_it import MarkdownIt

    identifier = f"(<italic>HLA</italic>)<{wrapper}>-DRB1*01:01</{wrapper}>"
    result = parse_plos_xml(
        f"""<article><front><article-meta><title-group><article-title>Study ({identifier})</article-title></title-group></article-meta></front><body><sec><title>{identifier}</title><p>Allele ({identifier}), plain DRB1*01:01 and DRB1*02:01. <italic>ordinary</italic></p><table-wrap><label>Table 1</label><caption><p>{identifier}</p></caption><table><tr><td>{identifier}</td></tr></table></table-wrap><p>Math <inline-formula><tex-math>x*y</tex-math></inline-formula>.</p></sec></body></article>""".encode(),
        source_url="https://journals.plos.org/plosone/article/file",
    )
    rendered = BeautifulSoup(
        MarkdownIt("commonmark").enable("table").render(result.markdown_text),
        "html.parser",
    )
    text = rendered.get_text()
    assert "(HLA)-DRB1*01:01" in text
    assert "plain DRB1*01:01 and DRB1*02:01" in text
    assert rendered.find("em", string="ordinary") is not None
    assert "DRB1*01:01" in rendered.find("td").get_text()
    assert "$x*y$" in result.markdown_text
    assert r"x\*y" not in result.markdown_text
