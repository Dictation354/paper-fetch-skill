"""Small publisher object-link scenarios; captured articles belong in golden."""

import pytest

from paper_fetch.models import article_from_markdown
from paper_fetch.providers._mdpi_markdown import _resolve_mdpi_retained_links
from paper_fetch.providers._science_html import finalize_extraction


@pytest.mark.parametrize("include_refs", ["all", "top1", "none"])
@pytest.mark.parametrize("provider", ["mdpi", "science"])
def test_retained_reference_keeps_source_identity_when_references_filtered(
    provider, include_refs
):
    if provider == "mdpi":
        source = "https://www.mdpi.com/2227-7390/11/3/657"
        html = '<ol id="html-references_list"><li id="B2" data-content="2.">Dataset Beta.</li></ol>'
        markdown = _resolve_mdpi_retained_links(
            "## Results\n\nNote: [[2](#B2)].", html, source
        )
        target = "B2"
    else:
        source = "https://www.science.org/doi/10.1126/science.example"
        html = '<div class="citations" id="R2"><div class="citation-content">Dataset Beta.</div></div>'
        markdown, _ = finalize_extraction(
            html, source, "## Results\n\nData: ([*2*](#R2)).", {}
        )
        target = "R2"
    article = article_from_markdown(
        source=provider,
        doi="10.1234/example",
        metadata={
            "title": "Example",
            "references": [{"raw": "1. Alpha."}, {"raw": "2. Dataset Beta."}],
        },
        markdown_text=markdown,
    )
    rendered = article.to_ai_markdown(include_refs=include_refs)
    assert f"]({source}#{target})" in rendered
    assert f"](#{target})" not in rendered
    assert ("2. Dataset Beta." in rendered) == (include_refs == "all")


def test_mdpi_table_note_targets_visible_owner_and_no_source_becomes_text():
    html = """<div class="html-table-wrap" id="table-A4">
<a href="#popup-A4"></a></div><div id="popup-A4" class="html-table_show">
<table><tr><td>Definition</td></tr></table></div>"""
    markdown = "Note: [Table A4](#popup-A4). [unknown](#missing)."
    source = "https://www.mdpi.com/article?view=full#old"
    assert _resolve_mdpi_retained_links(markdown, html, source) == (
        "Note: [Table A4](https://www.mdpi.com/article?view=full#table-A4). "
        "[unknown](#missing)."
    )
    assert _resolve_mdpi_retained_links(markdown, html, "") == (
        "Note: Table A4. [unknown](#missing)."
    )


def test_unrelated_ids_and_external_links_are_not_rewritten():
    html = '<div id="R2">Not a bibliography entry</div>'
    markdown = "[2](#R2) [other](https://elsewhere.example/#R2) ![2](#R2)"
    actual, _ = finalize_extraction(
        html, "https://www.science.org/article", markdown, {}
    )
    assert actual == markdown
