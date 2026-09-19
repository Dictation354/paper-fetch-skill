"""Small figure-caption ownership and article-heading scenarios."""

from collections import Counter

from bs4 import BeautifulSoup

from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers import _annualreviews_html as annual


def test_caption_formulas_are_inline_and_legitimate_reuse_is_preserved():
    source = "https://www.annualreviews.org/article"
    formula = "https://www.annualreviews.org/eq-shared.gif"
    html = "<article><h2>Results</h2>"
    for index in (1, 2):
        html += f'''<div class="figure" id="f{index}">
<div class="caption">Figure {index} Before <img class="inline-equation" src="{formula}">
between <img class="inline-equation" src="{formula}"> after.</div>
<div class="image"><a class="media-link" href="/shared.gif"><img src="/preview.gif"></a></div>
</div>'''
    html += f'<p>Body reuse <img class="inline-equation" src="{formula}"> ends.</p></article>'
    soup = BeautifulSoup(html, "lxml")
    annual._normalize_figures(soup.article, source)
    original = str(soup)
    markdown = annual._render_annualreviews_article_markdown(original, source)
    markdown = annual.inject_inline_figure_links(
        markdown,
        figure_assets=[
            {
                "kind": "figure",
                "heading": "Figure 1",
                "url": "https://www.annualreviews.org/shared.gif",
            }
        ],
        clean_markdown_fn=annual.annualreviews_normalize_markdown,
    )
    counts = Counter(i.url for i in iter_markdown_images(markdown))
    assert counts[formula] == 5  # two in each caption, one in prose
    assert counts["https://www.annualreviews.org/shared.gif"] == 2
    for index in (1, 2):
        caption = next(
            line
            for line in markdown.splitlines()
            if line.startswith(f"**Figure {index}.**")
        )
        assert caption.count(f"![Formula]({formula})") == 2
        assert (
            caption.index("Before") < caption.index(formula) < caption.index("between")
        )
    assert str(soup) == original  # discovery DOM still has every formula img


def test_table_label_is_bold_and_only_article_backmatter_modals_are_promoted():
    soup = BeautifulSoup(
        """<article><h2>Results</h2><h3>Comparison</h3>
<div class="table-caption-container" id="t1"><h5 class="table-label">Table 1</h5><p>Measurements.</p></div>
<div class="table-container"><table class="html-fulltext-inline-table"><tr><th>Value</th></tr><tr><td>7</td></tr></table></div>
<div id="viewGlossaryPopup"><div class="modal-header"><h4 class="modal-title">TERMS AND DEFINITIONS</h4></div><p>Term definition.</p></div>
<div id="viewFootnotePopup"><div class="modal-header"><h4 class="modal-title">FOOTNOTES</h4></div><p>Note text.</p></div>
<section><h4>Scientific detail</h4><p>Nested content.</p></section></article>""",
        "lxml",
    )
    annual._normalize_section_headings(soup.article)
    annual._normalize_tables(soup.article)
    markdown = annual._render_annualreviews_article_markdown(str(soup), "")
    assert "**Table 1**" in markdown and "# Table 1" not in markdown
    assert (
        markdown.index("**Table 1**")
        < markdown.index("Measurements.")
        < markdown.index("| Value")
    )
    assert "## Terms And Definitions\n" in markdown
    assert "## Footnotes\n" in markdown
    assert soup.select_one("section h4").get_text() == "Scientific detail"
    assert "Scientific detail" in markdown
    assert "Term definition." in markdown and "Note text." in markdown
