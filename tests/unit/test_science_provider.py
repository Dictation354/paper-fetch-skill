def test_loaded_biblioentry_keeps_reference_and_external_doi():
    from paper_fetch.providers._science_html import finalize_extraction

    html = '<section id="bibliography"><div class="biblioentry"><div class="label">1</div><div class="citation-content">A. Author. Title (2024).</div><div class="external-links"><a href="https://doi.org/10.1234/example">Crossref</a></div></div></section>'
    _, result = finalize_extraction(
        html, "https://www.science.org/doi/10.1126/example", "", {}
    )
    assert len(result["references"]) == 1
    assert result["references"][0]["doi"] == "10.1234/example"
    assert "A. Author. Title (2024)." in result["references"][0]["raw"]
