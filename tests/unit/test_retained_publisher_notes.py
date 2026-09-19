"""Minimal mechanism scenarios; publisher originals live in golden regressions."""

from bs4 import BeautifulSoup
import pytest
from paper_fetch.providers import _science_html, _oxfordacademic_html
from paper_fetch.extraction.html.semantics import collect_html_section_hints


@pytest.mark.parametrize(
    "heading,kind",
    [
        ("Data and materials availability", "data_availability"),
        ("Data and code availability", "data_availability"),
        ("Code availability", "code_availability"),
    ],
)
def test_science_label_promotion_is_idempotent_and_semantic(heading, kind):
    soup = BeautifulSoup(
        f"""<article><section id="acknowledgments"><h2>Acknowledgments</h2>
    <div role="paragraph"><b>Funding:</b> Grant.</div>
    <div role="paragraph"><strong>{heading}:</strong> See <a href="https://example.org/data">repository</a>.</div>
    <p>Thanks.</p></section><h2>Next</h2></article>""",
        "html.parser",
    )
    _science_html.science_before_block_normalization(soup.article)
    once = str(soup)
    _science_html.science_before_block_normalization(soup.article)
    assert str(soup) == once
    promoted = soup.select_one("." + kind.replace("_", "-"))
    assert promoted is not None and promoted.parent == soup.article
    assert "[repository](https://example.org/data)" in promoted.get_text()
    assert (
        soup.select_one("#acknowledgments").get_text(" ", strip=True)
        == "Acknowledgments Funding: Grant. Thanks."
    )
    assert [
        h["kind"] for h in collect_html_section_hints(soup) if h["heading"] == heading
    ] == [kind]
    assert _science_html.science_classify_heading(heading) == kind


@pytest.mark.parametrize(
    "paragraph",
    [
        "<p hidden><b>Code availability:</b> Hidden.</p>",
        '<p aria-hidden="true"><b>Code availability:</b> Hidden.</p>',
        '<p style="display: none"><b>Code availability:</b> Hidden.</p>',
        "<p>Prefix <b>Code availability:</b> Mixed.</p>",
        "<p><b hidden>Code availability:</b> Hidden label.</p>",
        "<p><b>Funding:</b> Grant.</p>",
        "<p><b>Important finding:</b> Body.</p>",
    ],
)
def test_science_does_not_promote_other_or_hidden_paragraphs(paragraph):
    soup = BeautifulSoup(
        f'<section id="acknowledgments">{paragraph}</section>', "html.parser"
    )
    _science_html.science_before_block_normalization(soup)
    assert soup.select_one(".data-availability, .code-availability") is None


@pytest.mark.parametrize(
    "notes",
    [
        "",
        """<div class="table-wrap-foot"><p><sup>a</sup> First <em>note</em>.
<a href="/data">data</a><a href="/download">Download slide</a></p></div>
<div class="table-wrap-foot"><p><sup>b</sup> Second <strong>note</strong>.</p></div>""",
    ],
)
def test_oup_table_notes_follow_table_before_next_paragraph(notes):
    result = _oxfordacademic_html.extract_markdown(
        f"""<article><div class="table-wrap">
<div class="label">Table 1</div><table><tr><th>Value</th></tr><tr><td>3<sup>a</sup></td></tr></table>
{notes}</div><p>Next paragraph.</p></article>""",
        "https://academic.oup.com/article",
        metadata={},
    )
    md = result.markdown_text
    assert md.count("Table 1") == 1
    if notes:
        assert (
            md.index("| Value")
            < md.index("First *note*")
            < md.index("Second **note**")
            < md.index("Next paragraph")
        )
        assert "[data](https://academic.oup.com/data)" in md
        assert md.count("First *note*") == 1
        assert "Download slide" not in md


def test_science_retained_statement_does_not_supply_primary_body():
    from paper_fetch.extraction.html._runtime import body_metrics

    soup = BeautifulSoup(
        '<article><section id="acknowledgments"><h2>Acknowledgments</h2>'
        "<p><b>Data and materials availability:</b> "
        + ("Available from the repository. " * 100)
        + "</p></section></article>",
        "html.parser",
    )
    from paper_fetch.extraction.html.renderer import render_html_markdown

    before = body_metrics("## Acknowledgments\n\n" + soup.p.get_text(), {})
    _science_html.science_before_block_normalization(soup.article)
    markdown = render_html_markdown(
        str(soup),
        "https://science.org/article",
        trafilatura_backend=None,
        cleaned_html=True,
    )
    after = body_metrics(markdown, {}, section_hints=collect_html_section_hints(soup))
    assert before["word_count"] == after["word_count"] == 0
