from __future__ import annotations

import unittest

from paper_fetch.providers import html_generic


class FakeTransport(html_generic.HttpTransport):
    def __init__(self, response):
        self.response = response

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        return self.response


class RecordingTransport(FakeTransport):
    def __init__(self, response):
        super().__init__(response)
        self.calls = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_transient": retry_on_transient,
            }
        )
        return super().request(
            method,
            url,
            headers=headers,
            query=query,
            timeout=timeout,
            retry_on_rate_limit=retry_on_rate_limit,
            rate_limit_retries=rate_limit_retries,
            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
            retry_on_transient=retry_on_transient,
            transient_retries=transient_retries,
            transient_backoff_base_seconds=transient_backoff_base_seconds,
        )


class MappingTransport(html_generic.HttpTransport):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        self.calls.append(url)
        if url not in self.responses:
            raise html_generic.RequestFailure(404, f"Missing fixture response for {url}")
        response = dict(self.responses[url])
        response.setdefault("status_code", 200)
        response.setdefault("headers", {})
        response.setdefault("url", url)
        return response


class HtmlGenericTests(unittest.TestCase):
    def test_parse_html_metadata_reads_citation_fields(self) -> None:
        html = """
<html>
  <head>
    <meta name="citation_title" content="Example HTML Article" />
    <meta name="citation_author" content="Alice Example" />
    <meta name="citation_author" content="Bob Example" />
    <meta name="citation_doi" content="10.1234/example" />
    <meta name="citation_journal_title" content="Journal of HTML" />
    <meta name="citation_publication_date" content="2026-01-15" />
  </head>
</html>
"""

        metadata = html_generic.parse_html_metadata(html, "https://example.test/article")

        self.assertEqual(metadata["title"], "Example HTML Article")
        self.assertEqual(metadata["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(metadata["journal_title"], "Journal of HTML")
        self.assertEqual(metadata["published"], "2026-01-15")

    def test_parse_html_metadata_cleans_nature_abstract_citations(self) -> None:
        html = """
<html>
  <head>
    <meta name="citation_abstract" content="Rainfall totals1-3. Growth3-17. Stable ending." />
  </head>
</html>
"""

        metadata = html_generic.parse_html_metadata(html, "https://www.nature.com/articles/example")

        self.assertEqual(metadata["abstract"], "Rainfall totals. Growth. Stable ending.")

    def test_parse_html_metadata_uses_redirect_stub_lookup_title(self) -> None:
        html = """
<html>
  <head>
    <title>Redirecting</title>
    <meta http-equiv="refresh" content="2; url='/retrieve/articleSelectSinglePerm'" />
  </head>
  <body>
    <input type="hidden" name="redirectURL" value="https%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2FS0034425725000525" />
    <script>
      siteCatalyst.pageDataLoad({ articleName : 'Stub Article Title', identifierValue : 'S0034425725000525' });
    </script>
  </body>
</html>
"""

        metadata = html_generic.parse_html_metadata(html, "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525")

        self.assertEqual(metadata["title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_redirect_url"], "https://www.sciencedirect.com/science/article/pii/S0034425725000525")
        self.assertEqual(metadata["identifier_value"], "S0034425725000525")

    def test_fetch_article_model_cleans_noise_and_keeps_sections(self) -> None:
        client = html_generic.HtmlGenericClient(
            FakeTransport(
                {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Example HTML Article" />'
                        b'<meta name="citation_author" content="Alice Example" />'
                        b'<meta name="citation_doi" content="10.1234/example" />'
                        b'<meta name="citation_journal_title" content="Journal of HTML" />'
                        b"</head><body>"
                        b'<figure><img src="/fig1.png" /><figcaption>Overview figure.</figcaption></figure>'
                        b"</body></html>"
                    ),
                    "url": "https://example.test/article",
                }
            ),
            {},
        )

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "\n".join(
                [
                    "# Example HTML Article",
                    "",
                    "## Sign in",
                    "Please sign in to access more options.",
                    "",
                    "**Abstract.** " + ("A" * 120),
                    "",
                    "## Introduction",
                    "Important body text " * 70,
                    "",
                    "## Data availability",
                    "Data are available in the repository.",
                    "",
                    "## Results",
                    "More important body text " * 70,
                ]
            )
            article = client.fetch_article_model("https://example.test/article")
        finally:
            html_generic.extract_article_markdown = original_extract

        self.assertEqual(article.source, "html_generic")
        self.assertEqual(article.metadata.title, "Example HTML Article")
        self.assertEqual(article.metadata.authors, ["Alice Example"])
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(any(section.heading == "Introduction" for section in article.sections))
        self.assertFalse(any("sign in" in section.text.lower() for section in article.sections))
        self.assertTrue(any(section.heading == "Data availability" for section in article.sections))
        self.assertEqual(article.assets[0].caption, "Overview figure.")

    def test_fetch_article_model_follows_elsevier_redirect_stub_when_initial_body_is_too_short(self) -> None:
        transport = MappingTransport(
            {
                "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525": {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b"<title>Redirecting</title>"
                        b'<meta http-equiv="refresh" content="2; url=\'/retrieve/articleSelectSinglePerm\'" />'
                        b"</head><body>"
                        b'<input type="hidden" name="redirectURL" value="https%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2FS0034425725000525" />'
                        b"<script>"
                        b"siteCatalyst.pageDataLoad({ articleName : 'Stub Article Title', identifierValue : 'S0034425725000525' });"
                        b"</script>"
                        b"</body></html>"
                    ),
                    "url": "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
                },
                "https://www.sciencedirect.com/science/article/pii/S0034425725000525": {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="ScienceDirect Article" />'
                        b'<meta name="citation_author" content="Alice Example" />'
                        b"</head><body>ScienceDirect body</body></html>"
                    ),
                    "url": "https://www.sciencedirect.com/science/article/pii/S0034425725000525",
                },
            }
        )
        client = html_generic.HtmlGenericClient(transport, {})

        original_extract = html_generic.extract_article_markdown
        try:
            def fake_extract(html: str, url: str) -> str:
                if "linkinghub.elsevier.com" in url:
                    return "# Redirecting\n\nPlease wait."
                return "\n".join(
                    [
                        "# ScienceDirect Article",
                        "",
                        "## Introduction",
                        "Important body text " * 70,
                        "",
                        "## Results",
                        "More important body text " * 70,
                    ]
                )

            html_generic.extract_article_markdown = fake_extract
            article = client.fetch_article_model(
                "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
                expected_doi="10.1016/j.rse.2025.114648",
            )
        finally:
            html_generic.extract_article_markdown = original_extract

        self.assertEqual(
            transport.calls,
            [
                "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
                "https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            ],
        )
        self.assertEqual(article.metadata.title, "Stub Article Title")
        self.assertEqual(article.metadata.authors, ["Alice Example"])
        self.assertEqual(article.doi, "10.1016/j.rse.2025.114648")
        self.assertTrue(article.quality.has_fulltext)

    def test_extract_figure_assets_reads_nature_full_size_links(self) -> None:
        html = """
<html>
  <body>
    <div class="c-article-section__figure-item">
      <picture class="c-article-section__figure-picture">
        <img
          aria-describedby="figure-1-desc"
          src="//media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png"
          alt="Fig. 1: Sensitivity of vegetation function."
        />
      </picture>
      <div class="c-article-section__figure-link">
        <a href="/articles/test/figures/1" aria-label="Full size image figure 1">Full size image</a>
      </div>
    </div>
    <div class="c-article-section__figure-description" id="figure-1-desc">
      <p>Figure caption from Nature HTML structure.</p>
    </div>
  </body>
</html>
"""

        assets = html_generic.extract_figure_assets(html, "https://www.nature.com/articles/test")

        self.assertEqual(len(assets), 1)
        self.assertEqual(
            assets[0]["url"],
            "https://media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png",
        )
        self.assertEqual(assets[0]["figure_page_url"], "https://www.nature.com/articles/test/figures/1")
        self.assertEqual(assets[0]["caption"], "Figure caption from Nature HTML structure.")

    def test_extract_full_size_figure_image_url_prefers_full_and_springer_candidates(self) -> None:
        html = """
<html>
  <head>
    <meta name="citation_title" content="Example Figure Article" />
  </head>
  <body>
    <img src="/preview/generic.png" />
    <img src="https://media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />
    <img src="https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />
  </body>
</html>
"""

        full_size_url = html_generic.extract_full_size_figure_image_url(
            html,
            "https://www.nature.com/articles/test",
        )

        self.assertEqual(
            full_size_url,
            "https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png",
        )

    def test_extract_figure_assets_dedupes_duplicate_nature_figure_wrappers(self) -> None:
        html = """
<html>
  <body>
    <figure>
      <img src="//media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png" alt="Fig. 1: Short title." />
      <figcaption>Fig. 1: Short title.</figcaption>
    </figure>
    <div class="c-article-section__figure-item">
      <picture class="c-article-section__figure-picture">
        <img
          aria-describedby="figure-1-desc"
          src="//media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png"
          alt="Fig. 1: Short title."
        />
      </picture>
      <div class="c-article-section__figure-link">
        <a href="/articles/test/figures/1" aria-label="Full size image figure 1">Full size image</a>
      </div>
    </div>
    <div class="c-article-section__figure-description" id="figure-1-desc">
      <p>Figure caption from Nature HTML structure with more detail.</p>
    </div>
  </body>
</html>
"""

        assets = html_generic.extract_figure_assets(html, "https://www.nature.com/articles/test")

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["figure_page_url"], "https://www.nature.com/articles/test/figures/1")
        self.assertEqual(assets[0]["caption"], "Figure caption from Nature HTML structure with more detail.")

    def test_extract_supplementary_assets_reads_nature_supplementary_links(self) -> None:
        html = """
<html>
  <body>
    <div class="c-article-supplementary__item">
      <h3>
        <a
          data-test="supp-info-link"
          href="/articles/test/figures/5"
          data-supp-info-image="//media.springernature.com/lw685/springer-static/esm/art%3A10.1038%2Ftest/MediaObjects/Fig5_ESM.jpg"
        >
          Extended Data Fig. 1 Across historical simulations.
        </a>
      </h3>
      <div class="c-article-supplementary__description">Extended-data description text.</div>
    </div>
    <div class="c-article-supplementary__item">
      <a
        data-test="supp-info-link"
        href="https://static-content.springer.com/esm/art%3A10.1038%2Ftest/MediaObjects/Supp1.pdf"
      >
        Supplementary Information (download PDF)
      </a>
    </div>
  </body>
</html>
"""

        assets = html_generic.extract_supplementary_assets(html, "https://www.nature.com/articles/test")

        self.assertEqual(len(assets), 2)
        self.assertEqual(assets[0]["kind"], "supplementary")
        self.assertEqual(assets[0]["section"], "supplementary")
        self.assertEqual(assets[0]["figure_page_url"], "https://www.nature.com/articles/test/figures/5")
        self.assertEqual(
            assets[0]["url"],
            "https://media.springernature.com/lw685/springer-static/esm/art%3A10.1038%2Ftest/MediaObjects/Fig5_ESM.jpg",
        )
        self.assertEqual(assets[0]["caption"], "Extended-data description text.")
        self.assertEqual(
            assets[1]["url"],
            "https://static-content.springer.com/esm/art%3A10.1038%2Ftest/MediaObjects/Supp1.pdf",
        )

    def test_fetch_article_model_downloads_full_size_nature_figure_when_available(self) -> None:
        article_url = "https://www.nature.com/articles/test"
        figure_page_url = "https://www.nature.com/articles/test/figures/1"
        preview_bytes = b"preview-image"
        full_bytes = b"full-size-image"
        client = html_generic.HtmlGenericClient(
            MappingTransport(
                {
                    article_url: {
                        "headers": {"content-type": "text/html"},
                        "body": (
                            b"<html><head>"
                            b'<meta name="citation_title" content="Nature HTML Article" />'
                            b'<meta name="citation_doi" content="10.1038/test" />'
                            b"</head><body>"
                            b'<div class="c-article-section__figure-item">'
                            b'<picture class="c-article-section__figure-picture">'
                            b'<img aria-describedby="figure-1-desc" src="//media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png" alt="Preview image" />'
                            b"</picture>"
                            b'<div class="c-article-section__figure-link"><a href="/articles/test/figures/1" aria-label="Full size image figure 1">Full size image</a></div>'
                            b"</div>"
                            b'<div class="c-article-section__figure-description" id="figure-1-desc"><p>Nature figure caption.</p></div>'
                            b"</body></html>"
                        ),
                    },
                    figure_page_url: {
                        "headers": {"content-type": "text/html"},
                        "body": (
                            b"<html><head>"
                            b'<meta name="twitter:image" content="https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png" />'
                            b"</head><body>"
                            b'<img src="//media.springernature.com/full/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png" />'
                            b"</body></html>"
                        ),
                    },
                    "https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png": {
                        "headers": {"content-type": "image/png"},
                        "body": full_bytes,
                    },
                    "https://media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png": {
                        "headers": {"content-type": "image/png"},
                        "body": preview_bytes,
                    },
                }
            ),
            {},
        )

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "# Nature HTML Article\n\n" + ("Body text " * 120)
            with self.subTest("download full size"):
                import tempfile
                from pathlib import Path

                with tempfile.TemporaryDirectory() as tmpdir:
                    article = client.fetch_article_model(
                        article_url,
                        download_dir=Path(tmpdir),
                        asset_profile="body",
                    )
                    asset_path = Path(article.assets[0].path or "")
                    self.assertTrue(asset_path.exists())
                    self.assertEqual(asset_path.read_bytes(), full_bytes)
                    self.assertIn("download:html_assets_saved_profile_body", article.quality.source_trail)
        finally:
            html_generic.extract_article_markdown = original_extract

    def test_fetch_article_model_downloads_supplementary_assets_when_profile_all(self) -> None:
        article_url = "https://www.nature.com/articles/test"
        client = html_generic.HtmlGenericClient(
            MappingTransport(
                {
                    article_url: {
                        "headers": {"content-type": "text/html"},
                        "body": (
                            b"<html><head>"
                            b'<meta name="citation_title" content="Nature HTML Article" />'
                            b'<meta name="citation_doi" content="10.1038/test" />'
                            b"</head><body>"
                            b'<figure><img src="/fig1.png" /><figcaption>Overview figure.</figcaption></figure>'
                            b'<div class="c-article-supplementary__item">'
                            b'<a data-test="supp-info-link" href="https://static-content.springer.com/esm/art%3A10.1038%2Ftest/MediaObjects/Supp1.pdf">Supplementary Information (download PDF)</a>'
                            b"</div>"
                            b"</body></html>"
                        ),
                    },
                    "https://www.nature.com/fig1.png": {
                        "headers": {"content-type": "image/png"},
                        "body": b"figure-image",
                    },
                    "https://static-content.springer.com/esm/art%3A10.1038%2Ftest/MediaObjects/Supp1.pdf": {
                        "headers": {"content-type": "application/pdf"},
                        "body": b"%PDF-1.7 supplementary",
                    },
                }
            ),
            {},
        )

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "# Nature HTML Article\n\n" + ("Body text " * 120)
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                article = client.fetch_article_model(
                    article_url,
                    download_dir=Path(tmpdir),
                    asset_profile="all",
                )
                markdown = article.to_ai_markdown(asset_profile="all")
                self.assertEqual(len(article.assets), 2)
                self.assertTrue(any(asset.kind == "supplementary" for asset in article.assets))
                supplement = next(asset for asset in article.assets if asset.kind == "supplementary")
                self.assertTrue(Path(supplement.path or "").exists())
                self.assertIn("## Supplementary Materials", markdown)
                self.assertIn("[Supplementary Information]", markdown)
                self.assertIn("download:html_assets_saved_profile_all", article.quality.source_trail)
        finally:
            html_generic.extract_article_markdown = original_extract

    def test_resolve_figure_download_url_prefers_promoted_full_size_when_figure_page_is_cookie_stub(self) -> None:
        transport = MappingTransport(
            {
                "https://www.nature.com/articles/test/figures/1": {
                    "headers": {"content-type": "text/html"},
                    "url": "https://www.nature.com/articles/test/figures/1?error=cookies_not_supported",
                    "body": (
                        b"<html><body>"
                        b'<img src="https://media.springernature.com/full/nature-cms/uploads/product/nature/header.svg" />'
                        b"</body></html>"
                    ),
                }
            }
        )

        resolved = html_generic.resolve_figure_download_url(
            transport,
            asset={
                "url": "https://media.springernature.com/lw685/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png",
                "figure_page_url": "https://www.nature.com/articles/test/figures/1",
            },
            user_agent="paper-fetch-skill/0.2",
        )

        self.assertEqual(
            resolved,
            "https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Ftest/MediaObjects/Fig1.png",
        )

    def test_clean_html_for_extraction_removes_noise_but_keeps_sections(self) -> None:
        html = """
<html>
  <body>
    <article>
      <div class="cookie-banner">Cookie settings</div>
      <div class="share-tools">Get shareable link</div>
      <section>
        <h2>Introduction</h2>
        <p>Important intro text.</p>
      </section>
      <section>
        <h2>Data availability</h2>
        <p>Data are available at example.test/data.</p>
      </section>
      <section>
        <h2>Code availability</h2>
        <p>Code is available at example.test/code.</p>
      </section>
    </article>
  </body>
</html>
"""

        cleaned = html_generic.clean_html_for_extraction(html)

        self.assertNotIn("Cookie settings", cleaned)
        self.assertNotIn("Get shareable link", cleaned)
        self.assertIn("Data availability", cleaned)
        self.assertIn("Code availability", cleaned)

    def test_extract_article_markdown_preserves_data_availability_section(self) -> None:
        html = """
<html>
  <body>
    <article>
      <div class="cookie-banner">Cookie settings</div>
      <section>
        <h1>Example HTML Article</h1>
      </section>
      <section>
        <h2>Introduction</h2>
        <p>Important intro text repeated many times. Important intro text repeated many times.</p>
      </section>
      <section>
        <h2>Data availability</h2>
        <p>Data are available in the repository.</p>
      </section>
      <section>
        <h2>Code availability</h2>
        <p>Code is available on GitHub.</p>
      </section>
    </article>
  </body>
</html>
"""
        original_trafilatura = html_generic.trafilatura
        try:
            html_generic.trafilatura = None
            markdown = html_generic.extract_article_markdown(html, "https://example.test/article")
        finally:
            html_generic.trafilatura = original_trafilatura

        self.assertIn("# Example HTML Article", markdown)
        self.assertIn("## Data availability", markdown)
        self.assertIn("Data are available in the repository.", markdown)
        self.assertIn("## Code availability", markdown)
        self.assertNotIn("Cookie settings", markdown)

    def test_short_extracted_body_raises_no_result(self) -> None:
        client = html_generic.HtmlGenericClient(
            FakeTransport(
                {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Tiny Article" />'
                        b"</head><body>Tiny</body></html>"
                    ),
                    "url": "https://example.test/tiny",
                }
            ),
            {},
        )

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "# Tiny Article\n\nShort body."
            with self.assertRaises(html_generic.ProviderFailure) as ctx:
                client.fetch_article_model("https://example.test/tiny")
        finally:
            html_generic.extract_article_markdown = original_extract

        self.assertEqual(ctx.exception.code, "no_result")

    def test_short_doi_page_passes_adaptive_body_threshold(self) -> None:
        client = html_generic.HtmlGenericClient(
            FakeTransport(
                {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Short DOI Article" />'
                        b'<meta name="citation_doi" content="10.1038/sj.bdj.2017.900" />'
                        b"</head><body></body></html>"
                    ),
                    "url": "https://example.test/short-doi",
                }
            ),
            {},
        )

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "# Short DOI Article\n\n" + (
                "This short editorial still contains enough article prose to count as a usable DOI page. " * 8
            )
            article = client.fetch_article_model("https://example.test/short-doi")
        finally:
            html_generic.extract_article_markdown = original_extract

        self.assertEqual(article.source, "html_generic")
        self.assertTrue(article.quality.has_fulltext)
        self.assertEqual(article.doi, "10.1038/sj.bdj.2017.900")

    def test_cjk_heavy_body_passes_adaptive_body_threshold(self) -> None:
        client = html_generic.HtmlGenericClient(
            FakeTransport(
                {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": '<html><head><meta name="citation_title" content="中文示例" /></head><body></body></html>'.encode(
                        "utf-8"
                    ),
                    "url": "https://example.test/cjk",
                }
            ),
            {},
        )

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "# 中文示例\n\n## 正文\n\n" + (
                "遥感分析结果显示植被指数持续升高，且样地之间存在稳定差异。" * 12
            )
            article = client.fetch_article_model("https://example.test/cjk")
        finally:
            html_generic.extract_article_markdown = original_extract

        self.assertEqual(article.source, "html_generic")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)

    def test_fetch_article_model_uses_default_timeout(self) -> None:
        transport = RecordingTransport(
            {
                "status_code": 200,
                "headers": {"content-type": "text/html"},
                "body": (
                    b"<html><head>"
                    b'<meta name="citation_title" content="Timeout Article" />'
                    b"</head><body></body></html>"
                ),
                "url": "https://example.test/timeout",
            }
        )
        client = html_generic.HtmlGenericClient(transport, {})

        original_extract = html_generic.extract_article_markdown
        try:
            html_generic.extract_article_markdown = lambda html, url: "# Timeout Article\n\n" + ("Body text " * 120)
            article = client.fetch_article_model("https://example.test/timeout")
        finally:
            html_generic.extract_article_markdown = original_extract

        self.assertTrue(article.quality.has_fulltext)
        self.assertEqual(transport.calls[0]["timeout"], 20)

    def test_extract_article_markdown_cleans_nature_references_and_figures(self) -> None:
        html = """
<html>
  <body>
    <article>
      <h1>Nature Example</h1>
      <div class="c-article-body">
        <section aria-labelledby="Abs1" data-title="Abstract" lang="en">
          <div class="c-article-section" id="Abs1-section">
            <h2 id="Abs1">Abstract</h2>
            <div class="c-article-section__content" id="Abs1-content">
              <p>Rainfall totals<sup><a href="#ref-CR1">1</a>, <a href="/articles/example#ref-CR2">2</a></sup>. Stable ending.</p>
            </div>
          </div>
        </section>
        <div class="main-content">
          <section data-title="Main">
            <div class="c-article-section" id="Sec1-section">
              <h2 id="Sec1">Main</h2>
              <div class="c-article-section__content" id="Sec1-content">
                <p>CO<sub>2</sub> and climate (ref.<sup><a href="#ref-CR3">3</a></sup>) matter.</p>
                <figure>
                  <figcaption>Fig. 1: Caption noise that should stay out of the main body.</figcaption>
                </figure>
              </div>
            </div>
          </section>
          <section data-title="Data availability">
            <div class="c-article-section" id="Sec2-section">
              <h2 id="Sec2">Data availability</h2>
              <div class="c-article-section__content" id="Sec2-content">
                <p>Data are available in the repository.</p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </article>
  </body>
</html>
"""

        markdown = html_generic.extract_article_markdown(html, "https://www.nature.com/articles/example")

        self.assertIn("## Abstract", markdown)
        self.assertNotIn("### Abstract", markdown)
        self.assertIn("Rainfall totals. Stable ending.", markdown)
        self.assertIn("CO2 and climate matter.", markdown)
        self.assertNotIn("(ref.)", markdown)
        self.assertNotIn("Fig. 1:", markdown)
        self.assertIn("## Data availability", markdown)


if __name__ == "__main__":
    unittest.main()
