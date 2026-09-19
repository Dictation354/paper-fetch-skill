"""Original identity must come from the article, not a cited DOI or another version."""

from tests.support.verified_source_inputs import inspect_original


def test_pdf_metadata_doi_takes_priority_over_cited_text(monkeypatch):
    from unittest.mock import MagicMock

    import pymupdf

    document = MagicMock()
    document.__enter__.return_value = document
    document.__len__.return_value = 1
    document.metadata = {"subject": "Journal;10.1234/article", "title": "Article"}
    document.__getitem__.return_value.get_text.return_value = "See 10.1234/cited"
    document.load_page.return_value.rect.width = 100
    monkeypatch.setattr(pymupdf, "open", lambda **kwargs: document)
    url = "https://example.org/article.pdf"
    identity = inspect_original(b"%PDF-stub", "ieee", "10.1234/article", url)
    assert identity["identity"] == "matched"
    assert identity["doi_evidence"] == "pdf_metadata"
    assert (
        inspect_original(b"%PDF-stub", "ieee", "10.1234/cited", url)["identity"]
        == "mismatch"
    )


def test_cited_doi_does_not_establish_article_identity():
    body = b"""<html><head><meta name="citation_doi" content="10.1234/other"></head>
    <body><div id="references">10.1234/requested</div></body></html>"""
    assert (
        inspect_original(
            body,
            "pnas",
            "10.1234/requested",
            "https://www.pnas.org/doi/10.1234/requested",
        )
        is None
    )


def test_arxiv_header_and_requested_version_must_agree():
    body = b"""<html><head><title>Paper</title></head><body>
    <a aria-label="Back to abstract page" href="/abs/2605.06598v1">Abstract</a>
    <h1 class="ltx_title_document">Paper</h1></body></html>"""
    assert (
        inspect_original(
            body,
            "arxiv",
            "10.48550/arxiv.2605.06598v2",
            "https://arxiv.org/html/2605.06598v2",
        )
        is None
    )
    result = inspect_original(
        body,
        "arxiv",
        "10.48550/arxiv.2605.06598v1",
        "https://arxiv.org/html/2605.06598v1",
    )
    assert result and result["identity"] == "matched"
