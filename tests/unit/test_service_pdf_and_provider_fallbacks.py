# ruff: noqa: F403,F405
from __future__ import annotations

from ._service_support import *


class ServicePdfAndProviderFallbackTests(unittest.TestCase):
    def test_fetch_paper_model_records_rate_limited_fulltext_trail(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1016/test",
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_error=paper_fetch.ProviderFailure(
                            "rate_limited",
                            "HTTP 429 for https://api.elsevier.com/content/article/doi/10.1016%2Ftest (Retry-After: 3s)",
                            retry_after_seconds=3,
                        ),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertIn("fulltext:elsevier_rate_limited", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertTrue(
            any("Retry-After: 3s" in warning for warning in article.quality.warnings)
        )

    def test_merge_metadata_preserves_explicit_blank_primary_scalar(self) -> None:
        merged = paper_fetch.merge_primary_secondary_metadata(
            {"abstract": "", "title": "Primary Title"},
            {"abstract": "Crossref abstract", "title": "Secondary Title"},
        )

        self.assertIsNone(merged["abstract"])
        self.assertEqual(merged["title"], "Primary Title")

    def test_merge_metadata_dedupes_semantic_author_names(self) -> None:
        merged = paper_fetch.merge_primary_secondary_metadata(
            {"authors": ["Zhang, San", "Alice Example"]},
            {"authors": ["San Zhang", "Alice Example"]},
        )

        self.assertEqual(merged["authors"], ["Zhang, San", "Alice Example"])

    def test_merge_metadata_prefers_public_landing_page_over_api_endpoint(self) -> None:
        merged = paper_fetch.merge_primary_secondary_metadata(
            {
                "landing_page_url": "https://api.elsevier.com/content/abstract/scopus_id/0012465826"
            },
            {
                "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
            },
        )

        self.assertEqual(
            merged["landing_page_url"],
            "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
        )

    def test_choose_public_landing_page_url_ignores_elsevier_link_flags_and_scopus_urls(
        self,
    ) -> None:
        selected = choose_public_landing_page_url(
            [
                {
                    "@_fa": "true",
                    "@rel": "self",
                    "@href": "https://api.elsevier.com/content/abstract/scopus_id/0012465826",
                },
                {
                    "@_fa": "true",
                    "@rel": "scopus",
                    "@href": "https://www.scopus.com/inward/record.uri?partnerID=HzOxMe3b&scp=0012465826&origin=inward",
                },
            ],
            "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
        )

        self.assertEqual(
            selected, "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
        )

    def test_wiley_pdf_fallback_is_downloaded_and_extracted_into_fulltext(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/test",
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure(
                                "not_supported", "No official metadata."
                            ),
                            raw_payload=_typed_payload(
                                provider="wiley",
                                source_url="https://example.test/wiley.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                route_kind="pdf_fallback",
                                reason="Downloaded full text from the Wiley TDM API PDF fallback.",
                                markdown_text=(
                                    "# Wiley PDF Article\n\n## Introduction\n\n"
                                    + ("Introduction text " * 60)
                                    + "\n\n## Methods\n\n"
                                    + ("Methods text " * 60)
                                    + "\n\n## Results\n\n"
                                    + ("Results text " * 60)
                                ),
                                warnings=[
                                    "Full text was extracted from the Wiley TDM API PDF fallback after the HTML path was not usable."
                                ],
                                source_trail=[
                                    "fulltext:wiley_html_fail",
                                    "fulltext:wiley_pdf_api_ok",
                                    "fulltext:wiley_pdf_fallback_ok",
                                ],
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(
                                HttpTransport(), {}
                            ).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley PDF Article",
                                "landing_page_url": "https://example.test/wiley",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                downloaded = Path(tmpdir) / "Example_unknown_Wiley_PDF_Article.pdf"
                self.assertTrue(downloaded.exists())
                self.assertTrue(downloaded.read_bytes().startswith(b"%PDF"))
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "wiley_browser")
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(
            any(
                "downloaded as PDF/binary" in warning
                for warning in article.quality.warnings
            )
        )
        self.assertTrue(
            any("PDF fallback" in warning for warning in article.quality.warnings)
        )
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        self.assertIn("download:wiley_saved", article.quality.source_trail)

    def test_pdf_only_provider_result_is_not_replaced_by_crossref_metadata_only(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/scanned",
            query_kind="doi",
            doi="10.1111/scanned",
            landing_url="https://example.test/wiley-scanned",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/scanned",
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure(
                                "not_supported", "No official metadata."
                            ),
                            raw_payload=_typed_payload(
                                provider="wiley",
                                source_url="https://example.test/wiley-scanned.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                route_kind="pdf_fallback",
                                reason="Downloaded full text from the Wiley PDF fallback.",
                                markdown_text="",
                                warnings=[
                                    "PDF was downloaded but Markdown extraction was not usable."
                                ],
                                source_trail=[
                                    "fulltext:wiley_html_fail",
                                    "fulltext:wiley_pdf_fallback_ok",
                                ],
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(
                                HttpTransport(), {}
                            ).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/scanned",
                                "title": "Scanned Wiley Article",
                                "landing_page_url": "https://example.test/wiley-scanned",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "wiley_browser")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)
        self.assertTrue(
            any(
                "Markdown extraction was not usable" in warning
                for warning in article.quality.warnings
            )
        )

    def test_wiley_pdf_fallback_markdown_creates_multiple_sections_with_heading_priority(
        self,
    ) -> None:
        article = WileyClient(HttpTransport(), {}).to_article_model(
            {
                "doi": "10.1111/test",
                "title": "Wiley PDF Article",
                "authors": ["Alice Example"],
            },
            _typed_payload(
                provider="wiley",
                source_url="https://example.test/wiley.pdf",
                content_type="application/pdf",
                body=fulltext_pdf_bytes(),
                route_kind="pdf_fallback",
                markdown_text=(
                    "# Wiley PDF Article\n\n## Introduction\n\n"
                    + ("Introduction text " * 60)
                    + "\n\n## Methods\n\n"
                    + ("Methods text " * 60)
                    + "\n\n## Results\n\n"
                    + ("Results text " * 60)
                    + "\n\n## Discussion\n\n"
                    + ("Discussion text " * 60)
                ),
                source_trail=[
                    "fulltext:wiley_pdf_api_ok",
                    "fulltext:wiley_pdf_fallback_ok",
                ],
            ),
        )

        headings = [section.heading for section in article.sections]
        self.assertIn("Introduction", headings)
        self.assertIn("Methods", headings)
        self.assertIn("Results", headings)

        truncated_markdown = article.to_ai_markdown(max_tokens=500)
        self.assertIn("## Introduction", truncated_markdown)
        self.assertIn("## Methods", truncated_markdown)
        self.assertNotIn("## Discussion", truncated_markdown)

    def test_binary_downloads_follow_payload_semantics_not_provider_name(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=_typed_payload(
                                provider="custompdf",
                                source_url="https://example.test/custom.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                route_kind="",
                                reason="Downloaded full text from a custom PDF endpoint.",
                                needs_local_copy=True,
                            ),
                            article=official_article,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                downloaded = Path(tmpdir) / "unknown_unknown_Example_Article.pdf"
                self.assertTrue(downloaded.exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:custompdf_saved", article.quality.source_trail)
        self.assertNotIn("download:elsevier_saved", article.quality.source_trail)

    def test_wiley_pdf_fallback_can_be_processed_without_download_side_effects(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/test",
                    allow_downloads=False,
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure(
                                "not_supported", "No official metadata."
                            ),
                            raw_payload=_typed_payload(
                                provider="wiley",
                                source_url="https://example.test/wiley.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                route_kind="pdf_fallback",
                                reason="Downloaded full text from the Wiley TDM API PDF fallback.",
                                markdown_text=(
                                    "# Wiley PDF Article\n\n## Introduction\n\n"
                                    + ("Introduction text " * 60)
                                    + "\n\n## Results\n\n"
                                    + ("Results text " * 60)
                                ),
                                source_trail=[
                                    "fulltext:wiley_html_fail",
                                    "fulltext:wiley_pdf_api_ok",
                                    "fulltext:wiley_pdf_fallback_ok",
                                ],
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(
                                HttpTransport(), {}
                            ).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley PDF Article",
                                "landing_page_url": "https://example.test/wiley",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                downloaded = Path(tmpdir) / "Example_unknown_Wiley_PDF_Article.pdf"
                self.assertFalse(downloaded.exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("download:wiley_skipped", article.quality.source_trail)
        self.assertTrue(
            any("--no-download" in warning for warning in article.quality.warnings)
        )

    def test_wiley_provider_skips_generic_html_fallback_after_provider_failure(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1111/test",
                allow_downloads=False,
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "not_supported", "No official metadata."
                        ),
                        raw_error=paper_fetch.ProviderFailure(
                            "no_result", "Browser workflow failed."
                        ),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Wiley PDF Article",
                            "landing_page_url": "https://example.test/wiley",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_fail", article.quality.source_trail)
        self.assertIn(
            "fallback:wiley_html_managed_by_provider", article.quality.source_trail
        )
        self.assertIn("fallback:metadata_only", article.quality.source_trail)

    def test_springer_provider_owned_html_downloads_figure_assets_when_enabled(
        self,
    ) -> None:
        landing_url = "https://www.nature.com/articles/example"
        figure_page_url = "https://www.nature.com/articles/example/figures/1"
        preview_image_url = "https://media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png"
        full_image_url = "https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png"
        preview_bytes = b"\x89PNG\r\n\x1a\npreview-image"
        full_bytes = b"\x89PNG\r\n\x1a\nfull-size-image"
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            landing_url=landing_url,
            provider_hint="springer",
            confidence=1.0,
        )
        transport = FixtureHtmlTransport(
            {
                landing_url: {
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="HTML Springer Article" />'
                        b'<meta name="citation_doi" content="10.1007/test" />'
                        b"</head><body><article><section><h2>Introduction</h2><p>"
                        + (b"Important body text for HTML fallback. " * 30)
                        + b"</p></section>"
                        b'<div class="c-article-section__figure-item">'
                        b'<picture class="c-article-section__figure-picture">'
                        b'<img aria-describedby="figure-1-desc" src="//media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" alt="Preview image" />'
                        b"</picture>"
                        b'<div class="c-article-section__figure-link"><a href="/articles/example/figures/1" aria-label="Full size image figure 1">Full size image</a></div>'
                        b"</div>"
                        b'<div class="c-article-section__figure-description" id="figure-1-desc"><p>Figure showing a woodland canopy.</p></div>'
                        b"</article></body></html>"
                    ),
                },
                figure_page_url: {
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="twitter:image" content="https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />'
                        b"</head><body>"
                        b'<img src="//media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />'
                        b"</body></html>"
                    ),
                },
                preview_image_url: {
                    "headers": {"content-type": "image/png"},
                    "body": preview_bytes,
                },
                full_image_url: {
                    "headers": {"content-type": "image/png"},
                    "body": full_bytes,
                },
            }
        )
        original_resolve = paper_fetch.resolve_paper
        original_extract = springer_html_helper.extract_article_markdown
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            springer_html_helper.extract_article_markdown = lambda html, url: "\n".join(
                [
                    "# HTML Springer Article",
                    "",
                    "## Introduction",
                    ("Important body text for HTML fallback. " * 30).strip(),
                    "",
                    "## Results",
                    ("More important body text for HTML fallback. " * 30).strip(),
                    "",
                    "**Figure 1.** Figure showing a woodland canopy.",
                ]
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1007/test",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "springer": paper_fetch.build_clients(transport, {})[
                            "springer"
                        ],
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1007/test",
                                "title": "HTML Springer Article",
                                "landing_page_url": landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    transport=transport,
                )
                markdown = article.to_ai_markdown(asset_profile="body")
                self.assertEqual(article.source, "springer_html")
                self.assertTrue(article.quality.has_fulltext)
                self.assertEqual(len(article.assets), 1)
                self.assertEqual(article.assets[0].section, "body")
                self.assertIsNotNone(article.assets[0].path)
                asset_path = Path(article.assets[0].path or "")
                self.assertTrue(asset_path.exists())
                self.assertEqual(asset_path.parent.name, "10.1007_test_assets")
                self.assertEqual(asset_path.read_bytes(), full_bytes)
                self.assertIn("![Figure 1](", markdown)
                self.assertIn(str(asset_path), markdown)
                self.assertNotIn("## Figures", markdown)
        finally:
            paper_fetch.resolve_paper = original_resolve
            springer_html_helper.extract_article_markdown = original_extract

        self.assertIn("fulltext:springer_html_ok", article.quality.source_trail)
        self.assertIn(
            "download:springer_assets_saved_profile_body", article.quality.source_trail
        )
