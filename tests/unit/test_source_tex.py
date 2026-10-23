"""Source TeX selection and verbatim transport through Markdown containers."""

import html
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import pytest

from paper_fetch.formula import convert
from paper_fetch.extraction.markdown_render.formulas import (
    render_html_formula_container,
)
from paper_fetch.models import article_from_markdown, normalize_markdown_text
from paper_fetch.providers._article_markdown_common import render_inline_text
from paper_fetch.providers._article_markdown_math import (
    render_display_formula_result,
    render_inline_formula_result,
)
from paper_fetch.providers._html_section_markdown import render_container_markdown
from paper_fetch.providers.atypon_browser_workflow.formulas import (
    _structured_latex_from_math_node,
)

SOURCE = (
    r"\begin{equation}\updelta  + \mspace{6mu} + \unicode{x2A7D}"
    " % comment with trailing spaces  \n"
    r"\text{two  spaces and $x$} + \mathop\sum_{i j} x\textbackslash\_y"
    "\u200b\n"
    r"\end{equation}"
)


def unexpected_backend(*args, **kwargs):
    pytest.fail("Nonempty source TeX must bypass the conversion backend")


def test_provider_mathml_entries_keep_valid_source_spaces_and_newlines(monkeypatch):
    from paper_fetch.providers._ams_dom import _render_ams_mathml_inline
    from paper_fetch.providers._mdpi_dom import _render_mdpi_mathml_latex
    from paper_fetch.providers._royalsocietypublishing_html import (
        _normalize_silverchair_dom,
    )

    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    node = BeautifulSoup(
        '<span class="inline-formula"><math><mi>wrong</mi><annotation encoding="application/x-tex">'
        + html.escape(SOURCE)
        + "</annotation></math></span>",
        "html.parser",
    ).span
    assert SOURCE in _render_ams_mathml_inline(node)
    assert _render_mdpi_mathml_latex(node, display_mode=False) == SOURCE
    _normalize_silverchair_dom(node.parent)
    assert SOURCE in node.get_text("", strip=False)


@pytest.mark.parametrize("annotation", [False, True])
def test_html_and_atypon_choose_source_tex_before_mathml(annotation, monkeypatch):
    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    tex = html.escape(SOURCE)
    payload = (
        f'<math><semantics><mi>wrong</mi><annotation encoding="application/x-tex">{tex}</annotation></semantics></math>'
        if annotation
        else f"<math><mi>wrong</mi></math><tex-math>{tex}</tex-math>"
    )
    node = BeautifulSoup(f'<span class="inline-formula">{payload}</span>', "lxml").span
    assert SOURCE in render_html_formula_container(node)
    assert _structured_latex_from_math_node(node, display_mode=False) == SOURCE


@pytest.mark.parametrize("annotation", [False, True])
@pytest.mark.parametrize("display", [False, True])
def test_xml_source_tex_is_success_and_bypasses_backend(
    annotation, display, monkeypatch
):
    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    tex = html.escape(SOURCE)
    payload = (
        f'<math><semantics><mi>wrong</mi><annotation encoding="application/x-tex">{tex}</annotation></semantics></math>'
        if annotation
        else f"<math><mi>wrong</mi></math><tex-math>{tex}</tex-math>"
    )
    node = ET.fromstring(f"<inline-formula>{payload}</inline-formula>")
    result = (
        render_display_formula_result if display else render_inline_formula_result
    )(node)
    assert result.expression == SOURCE
    assert (
        result.status == "ok" and result.fallback_kind is None and result.note is None
    )
    assert result.method == ("annotation" if annotation else "tex-math")
    assert SOURCE in render_inline_text(
        ET.fromstring(f"<p>Before {ET.tostring(node, encoding='unicode')} after.</p>")
    )


@pytest.mark.parametrize("tex", ["", " \n \t ", "$$ $$"])
def test_empty_tex_still_converts_mathml(tex, monkeypatch):
    calls = []

    def backend(raw, *, display_mode, **kwargs):
        calls.append(raw)
        return convert.FormulaConversionResult(
            "texmath", "ok", "converted", raw, None, 0, display_mode
        )

    monkeypatch.setattr(convert, "convert_mathml_string", backend)
    payload = f"<math><mi>x</mi></math><tex-math>{tex}</tex-math>"
    xml = ET.fromstring(f"<inline-formula>{payload}</inline-formula>")
    assert render_inline_formula_result(xml).expression == "converted"
    node = BeautifulSoup(f'<span class="inline-formula">{payload}</span>', "lxml").span
    assert "converted" in render_html_formula_container(node)
    assert len(calls) == 2


def test_source_tex_survives_body_list_table_and_final_article(monkeypatch):
    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    tex_node = f'<span class="mathjax-tex">{html.escape(SOURCE)}</span>'
    body = BeautifulSoup(
        f"<section><h2>Methods</h2><p>Before {tex_node} after.</p>"
        f"<ol><li>Item {tex_node} after.</li></ol>"
        f"<table><tr><th>Value</th></tr><tr><td>{tex_node}</td></tr></table></section>",
        "lxml",
    )
    lines = []
    render_container_markdown(body.section, lines, level=2)
    markdown = normalize_markdown_text("\n".join(lines))
    assert SOURCE in markdown
    assert SOURCE.replace("\n", "\n   ") in markdown  # Markdown list indentation
    assert SOURCE.replace("\n", "<br>") in markdown  # pipe table encoding
    article = article_from_markdown(
        source="springer_html",
        metadata={"title": "Source formulas"},
        doi="10.1000/test",
        markdown_text=markdown,
    )
    final = article.to_ai_markdown(
        max_tokens="full_text", include_refs="none", asset_profile="all"
    )
    assert SOURCE in final
    assert SOURCE.replace("\n", "\n   ") in final
    assert SOURCE.replace("\n", "<br>") in final
    assert "PAPERFETCH" not in final


def test_arxiv_annotation_and_alttext_keep_nonempty_source(monkeypatch):
    from paper_fetch.providers._arxiv_authors import _arxiv_math_markdown

    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    node = BeautifulSoup(
        '<math class="ltx_Math"><annotation encoding="application/x-tex"></annotation></math>',
        "lxml",
    ).math
    node["alttext"] = SOURCE
    assert SOURCE in _arxiv_math_markdown(node)
    node.annotation.string = SOURCE
    node["alttext"] = "wrong"
    assert SOURCE in _arxiv_math_markdown(node)


def test_display_tex_with_internal_dollar_runs_survives_final_assembly():
    from paper_fetch.extraction.markdown_render import MarkdownFormula, render_formula

    source = r"\text{two  $$ signs and $x$}" + " % comment  \n" + r"\mathop\sum_{i j} x"
    markdown = "\n".join(
        render_formula(MarkdownFormula(label="", latex=source, display_mode=True))
    )
    article = article_from_markdown(
        source="springer_html",
        metadata={"title": "Formulas"},
        doi="10.1000/test",
        markdown_text=markdown,
    )
    assert source in article.to_ai_markdown(max_tokens="full_text")


def test_atypon_inline_normalization_chooses_sibling_tex_once(monkeypatch):
    from paper_fetch.models import SemanticLosses
    from paper_fetch.providers.atypon_browser_workflow.formulas import (
        _normalize_inline_math_nodes,
    )

    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    node = BeautifulSoup(
        '<article><p>Before <span class="inline-formula"><math><mi>wrong</mi></math>'
        f"<tex-math>{html.escape(SOURCE)}</tex-math></span> after.</p></article>",
        "lxml",
    )
    losses = SemanticLosses()
    _normalize_inline_math_nodes(node.article, losses)
    assert node.article.get_text().count(SOURCE) == 1
    assert "wrong" not in node.article.get_text()
    assert losses.formula_fallback_count == losses.formula_missing_count == 0


def test_formula_in_section_heading_is_restored_after_section_scan():
    article = article_from_markdown(
        source="arxiv_html",
        metadata={"title": "Formulas"},
        doi="10.1000/test",
        markdown_text="## A heading with $L_{i j}$\n\nA body formula $x  +  y$.",
    )
    final = article.to_ai_markdown(max_tokens="full_text")
    assert "## A heading with $L_{i j}$" in final
    assert "$x  +  y$" in final
    assert "PAPERFETCH" not in final


def test_oxford_table_selects_tex_before_any_mathml_conversion(monkeypatch):
    from paper_fetch.providers._oxfordacademic_html import extract_markdown

    monkeypatch.setattr(convert, "convert_mathml_string", unexpected_backend)
    result = extract_markdown(
        '<article><h2>Results</h2><div class="table-wrap"><table>'
        '<tr><th>Value</th></tr><tr><td><span class="inline-formula">'
        f"<math><mi>wrong</mi></math><tex-math>{html.escape(SOURCE)}</tex-math>"
        "</span></td></tr></table></div></article>",
        "https://academic.oup.com/example",
        metadata={},
        asset_profile="none",
    )
    assert SOURCE.replace("\n", "<br>") in result.markdown_text
    assert "[Formula unavailable]" not in result.markdown_text
