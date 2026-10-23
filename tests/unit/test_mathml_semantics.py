"""Minimal dimensions and source-error structure at the MathML boundary."""

import xml.etree.ElementTree as ET

import pytest

from paper_fetch.formula.semantics import (
    mathml_space_latex,
    prepare_mathml_semantics,
    restore_mathml_spacing,
)
from paper_fetch.providers._article_markdown_math import render_mathml_expression


@pytest.mark.parametrize(
    "body, expected",
    [
        ("<mo>∫</mo><mi>SMB</mi><mi>d</mi><mi>t</mi>", r"\int\mathrm{SMB}dt"),
        ("<mo>∫</mo><mi>D</mi><mi>d</mi><mi>t</mi>", r"\int Ddt"),
        ("<mo>∑</mo><mi>x</mi>", r"\sum x"),
        ("<mo>∬</mo><mi>x</mi>", r"\iint x"),
        ("<mo>∞</mo><mi>x</mi>", r"\infty x"),
        ("<mi>α</mi><mi>x</mi>", r"\alpha x"),
        ("<mrow><mo>∫</mo></mrow><mrow><mrow/><mi>x</mi></mrow>", r"\int x"),
        ("<mo>∫</mo><mrow/><mi>x</mi>", r"\int x"),
        ("<msqrt><mo>∑</mo><mi>x</mi></msqrt>", r"\sqrt{\sum x}"),
        (
            "<mfrac><mrow><mo>∫</mo><mi>x</mi></mrow><mi>y</mi></mfrac>",
            r"\frac{\int x}{y}",
        ),
        ("<msub><mo>∑</mo><mi>i</mi></msub><mi>x</mi>", r"\sum_{i}x"),
        ("<mo>∫</mo><mi>α</mi><mi>x</mi>", r"\int\alpha x"),
        ("<mi>\\alphax</mi>", r"\alphax"),
        ("<mi>\\inftyx</mi>", r"\inftyx"),
        ("<mtext>89%</mtext>", r"\text{89\%}"),
        ("<mi>%</mi><mo>%</mo>", r"\%\%"),
    ],
)
def test_mathml_node_boundaries_terminate_control_words_without_splitting_source(
    body, expected
):
    assert render_mathml_expression(ET.fromstring(f"<math>{body}</math>")) == expected


@pytest.mark.parametrize(
    "symbol, good, bad",
    [
        ("∫", r"\int\mathrm{SMB}dt", r"\intSMBdt"),
        ("∫", r"\int Ddt", r"\intDdt"),
        ("∑", r"\sum x", r"\sumx"),
        ("∬", r"\iint x", r"\iintx"),
        ("∞", r"\infty x", r"\inftyx"),
    ],
)
def test_source_operator_check_rejects_command_glue(symbol, good, bad):
    from bs4 import BeautifulSoup
    from tests.support.scientific_content import mathml_control_words_preserved

    source = BeautifulSoup(f"<math><mo>{symbol}</mo><mi>x</mi></math>", "xml").math
    assert mathml_control_words_preserved(source, good)
    assert not mathml_control_words_preserved(source, bad)


@pytest.mark.parametrize(
    "width, expected",
    [
        ("40pt", r"\hspace{40pt}"),
        ("1in", r"\hspace{1in}"),
        ("2.54cm", r"\hspace{2.54cm}"),
        ("25.4mm", r"\hspace{25.4mm}"),
        ("1pc", r"\hspace{1pc}"),
        ("16px", r"\hspace{12bp}"),
        ("0.5em", r"\hspace{0.5em}"),
        ("-0.5ex", r"\hspace{-0.5ex}"),
        ("0pt", r"\hspace{0pt}"),
        ("2", r"\hspace{2em}"),
        ("thinmathspace", r"\mkern3mu "),
        ("negativethinmathspace", r"\mkern-3mu "),
        ("50%", None),
    ],
)
def test_mspace_preserves_known_dimensions_without_font_size_assumptions(
    width, expected
):
    assert mathml_space_latex(width) == expected
    if expected is not None:
        assert (
            render_mathml_expression(
                ET.fromstring(f'<math><mspace width="{width}"/></math>')
            )
            == expected.strip()
        )


def test_merror_children_keep_fraction_structure_and_closing_parenthesis():
    raw = "<math><merror><mfrac><mrow><mi>k</mi><mo>-</mo><mn>1</mn></mrow><mi>K</mi></mfrac><mo>)</mo></merror></math>"
    prepared, markers = prepare_mathml_semantics(raw)
    assert "merror" in raw and "merror" not in prepared
    assert "mfrac" in prepared and markers == {}
    assert render_mathml_expression(ET.fromstring(raw)) == r"\frac{k - 1}{K})"


def test_spacing_marker_is_unique_and_must_survive_once():
    raw = '<math><mtext>PAPERFETCHMATHSPACE0TOKEN</mtext><mspace width="40pt"/></math>'
    _, markers = prepare_mathml_semantics(raw)
    marker = next(iter(markers))
    assert marker not in raw
    assert (
        restore_mathml_spacing(r"x\text{" + marker + "}y", markers)
        == r"x\hspace{40pt}y"
    )
    assert restore_mathml_spacing("x y", markers) is None
    assert restore_mathml_spacing((r"\text{" + marker + "}") * 2, markers) is None


@pytest.mark.parametrize(
    "raw",
    [
        '<!DOCTYPE math [<!ENTITY x "expanded">]><math><merror>&x;</merror></math>',
        "<math>"
        + "<mrow>" * 65
        + '<mspace width="40pt"/>'
        + "</mrow>" * 65
        + "</math>",
    ],
)
def test_semantics_preprocessing_reuses_bounded_xml_rejection(raw, monkeypatch):
    from paper_fetch.formula import convert

    def unexpected_backend(*args, **kwargs):
        pytest.fail("Rejected XML must not reach a backend")

    monkeypatch.setattr(convert, "backend_strategy", unexpected_backend)
    result = convert.convert_mathml_string(raw, display_mode=False, backend="texmath")
    assert result.status == "failed"
    assert result.raw_mathml == raw
    assert result.latex == ""


def test_oup_source_error_diagnostic_reaches_article_warning():
    from paper_fetch.http import HttpTransport
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.providers.oxfordacademic import OxfordAcademicClient

    source_url = "https://academic.oup.com/example"
    metadata = {"doi": "10.1093/bioinformatics/btaa153", "title": "Example"}
    payload = RawFulltextPayload(
        provider="oxfordacademic",
        source_url=source_url,
        content_type="text/html",
        body=b"<article/>",
        warnings=["existing warning"],
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=b"<article/>",
            markdown_text="# Example\n\nReadable formula content.",
            merged_metadata=metadata,
            diagnostics={"extraction": {"source_mathml_error_count": 1}},
        ),
    )
    article = OxfordAcademicClient(HttpTransport(), {}).to_article_model(
        metadata, payload
    )
    assert "existing warning" in article.quality.warnings
    assert any(
        "1 merror" in warning and "not corrected" in warning
        for warning in article.quality.warnings
    )
