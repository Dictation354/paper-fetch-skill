# ruff: noqa: F403,F405
from __future__ import annotations

from unittest import mock

from ._service_support import *


class ServiceBrowserWorkflowTests(unittest.TestCase):
    def test_wiley_provider_failure_returns_metadata_only_without_generic_html_fallback(
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
                    "wiley": FixtureProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "not_supported", "No official metadata."
                        ),
                        raw_error=paper_fetch.ProviderFailure(
                            "no_result", "Browser workflow failed."
                        ),
                    ),
                    "crossref": FixtureProvider(
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
        self.assertTrue(
            any(
                "Full text was not available" in warning
                for warning in article.quality.warnings
            )
        )

    def test_science_provider_skips_generic_html_fallback_after_provider_failure(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.ady3136",
            query_kind="doi",
            doi="10.1126/science.ady3136",
            landing_url="https://www.science.org/doi/full/10.1126/science.ady3136",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1126/science.ady3136",
                clients={
                    "science": FixtureProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "not_supported", "Science metadata probe is route-only."
                        ),
                        raw_error=paper_fetch.ProviderFailure(
                            "no_result", "Science provider failed."
                        ),
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1126/science.ady3136",
                            "title": "Science Example",
                            "publisher": "American Association for the Advancement of Science",
                            "landing_page_url": resolved.landing_url,
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
        self.assertIn(
            "fallback:science_html_managed_by_provider", article.quality.source_trail
        )
        self.assertIn("fallback:metadata_only", article.quality.source_trail)

    def test_science_provider_public_source_and_html_assets_are_exposed(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.aeg3511",
            query_kind="doi",
            doi="10.1126/science.aeg3511",
            landing_url="https://www.science.org/doi/full/10.1126/science.aeg3511",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                asset_path = Path(tmpdir) / "science-figure.png"
                asset_path.write_bytes(b"science-figure")
                envelope = _fetch_paper(
                    "10.1126/science.aeg3511",
                    modes={"article", "markdown"},
                    strategy=paper_fetch.FetchStrategy(asset_profile="body"),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": FixtureProvider(
                            metadata=paper_fetch.ProviderFailure(
                                "not_supported", "Science metadata probe is route-only."
                            ),
                            raw_payload=_typed_payload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html />",
                                route_kind="html",
                                markdown_text="# Science Example\n\n## Results\n\n"
                                + ("Body text " * 80),
                                source_trail=["fulltext:science_html_ok"],
                            ),
                            article_factory=science_provider.ScienceClient(
                                HttpTransport(), {}
                            ).to_article_model,
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Science figure",
                                        "path": str(asset_path),
                                        "source_url": "https://www.science.org/images/large/figure1.png",
                                        "section": "body",
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": FixtureProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1126/science.aeg3511",
                                "title": "Science Example",
                                "publisher": "American Association for the Advancement of Science",
                                "landing_page_url": resolved.landing_url,
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

        self.assertEqual(envelope.source, "science")
        self.assertIn(
            "download:science_assets_saved_profile_body", envelope.source_trail
        )
        self.assertFalse(
            any("text-only full text" in warning for warning in envelope.warnings)
        )
        assert envelope.article is not None
        self.assertEqual(len(envelope.article.assets), 1)
        self.assertEqual(envelope.article.assets[0].section, "body")
        self.assertEqual(envelope.article.assets[0].path, str(asset_path))

    def test_wiley_provider_public_source_and_html_body_assets_are_exposed(
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
                asset_path = Path(tmpdir) / "wiley-figure.png"
                asset_path.write_bytes(b"wiley-figure")
                article = fetch_paper_model(
                    "10.1111/test",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": FixtureProvider(
                            metadata=paper_fetch.ProviderFailure(
                                "not_supported", "No official metadata."
                            ),
                            raw_payload=_typed_payload(
                                provider="wiley",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text="# Wiley HTML Article\n\n## Results\n\n"
                                + ("Body text " * 80),
                                source_trail=["fulltext:wiley_html_ok"],
                            ),
                            article_factory=WileyClient(
                                HttpTransport(), {}
                            ).to_article_model,
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Wiley figure",
                                        "path": str(asset_path),
                                        "source_url": "https://example.test/wiley/figure1.png",
                                        "section": "body",
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": FixtureProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley HTML Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "wiley_browser")
        self.assertIn(
            "download:wiley_assets_saved_profile_body", article.quality.source_trail
        )
        self.assertEqual(len(article.assets), 1)
        self.assertEqual(article.assets[0].section, "body")
        self.assertFalse(
            any(
                "text-only full text" in warning for warning in article.quality.warnings
            )
        )

    def test_pnas_provider_public_source_and_html_all_assets_are_exposed(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1073/pnas.test",
            query_kind="doi",
            doi="10.1073/pnas.test",
            landing_url="https://www.pnas.org/doi/10.1073/pnas.test",
            provider_hint="pnas",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                figure_path = Path(tmpdir) / "pnas-figure.png"
                figure_path.write_bytes(b"pnas-figure")
                supplementary_path = Path(tmpdir) / "pnas-supp.pdf"
                supplementary_path.write_bytes(b"%PDF-pnas-supp")
                article = fetch_paper_model(
                    "10.1073/pnas.test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "pnas": FixtureProvider(
                            metadata=paper_fetch.ProviderFailure(
                                "not_supported", "PNAS metadata probe is route-only."
                            ),
                            raw_payload=_typed_payload(
                                provider="pnas",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text="# PNAS HTML Article\n\n## Results\n\n"
                                + ("Body text " * 80),
                                source_trail=["fulltext:pnas_html_ok"],
                            ),
                            article_factory=pnas_provider.PnasClient(
                                HttpTransport(), {}
                            ).to_article_model,
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "PNAS figure",
                                        "path": str(figure_path),
                                        "source_url": "https://www.pnas.org/images/figure1.png",
                                        "section": "body",
                                    },
                                    {
                                        "kind": "supplementary",
                                        "heading": "Supplementary Data",
                                        "caption": "PNAS supplementary",
                                        "path": str(supplementary_path),
                                        "source_url": "https://www.pnas.org/supp/s1.pdf",
                                        "section": "supplementary",
                                    },
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": FixtureProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1073/pnas.test",
                                "title": "PNAS HTML Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "pnas")
        self.assertIn(
            "download:pnas_assets_saved_profile_all", article.quality.source_trail
        )
        self.assertEqual(
            {asset.kind for asset in article.assets}, {"figure", "supplementary"}
        )
        self.assertFalse(
            any(
                "text-only full text" in warning for warning in article.quality.warnings
            )
        )

    def test_browser_workflow_html_final_markdown_prefers_downloaded_local_figure_links(
        self,
    ) -> None:
        cases = [
            {
                "provider_name": "science",
                "doi": "10.1126/science.aeg3511",
                "landing_url": "https://www.science.org/doi/full/10.1126/science.aeg3511",
                "expected_source": "science",
                "asset_profile": "body",
                "title": "Science Example",
                "remote_url": "https://www.science.org/images/large/figure1.png",
                "asset_name": "science-figure.png",
                "article_factory": science_provider.ScienceClient(
                    HttpTransport(), {}
                ).to_article_model,
            },
            {
                "provider_name": "wiley",
                "doi": "10.1111/test",
                "landing_url": "https://example.test/wiley",
                "expected_source": "wiley_browser",
                "asset_profile": "body",
                "title": "Wiley HTML Article",
                "remote_url": "https://example.test/wiley/figure1.png",
                "asset_name": "wiley-figure.png",
                "article_factory": WileyClient(HttpTransport(), {}).to_article_model,
            },
            {
                "provider_name": "pnas",
                "doi": "10.1073/pnas.test",
                "landing_url": "https://www.pnas.org/doi/10.1073/pnas.test",
                "expected_source": "pnas",
                "asset_profile": "all",
                "title": "PNAS HTML Article",
                "remote_url": "https://www.pnas.org/images/figure1.png",
                "asset_name": "pnas-figure.png",
                "article_factory": pnas_provider.PnasClient(
                    HttpTransport(), {}
                ).to_article_model,
            },
        ]
        original_resolve = paper_fetch.resolve_paper
        try:
            for case in cases:
                with self.subTest(provider=case["provider_name"]):
                    resolved = paper_fetch.ResolvedQuery(
                        query=case["doi"],
                        query_kind="doi",
                        doi=case["doi"],
                        landing_url=case["landing_url"],
                        provider_hint=case["provider_name"],
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = (
                        lambda *args, _resolved=resolved, **kwargs: _resolved
                    )
                    with tempfile.TemporaryDirectory() as tmpdir:
                        asset_path = Path(tmpdir) / case["asset_name"]
                        asset_path.write_bytes(
                            f"{case['provider_name']}-figure".encode()
                        )
                        envelope = _fetch_paper(
                            case["doi"],
                            modes={"article", "markdown"},
                            strategy=paper_fetch.FetchStrategy(
                                asset_profile=case["asset_profile"]
                            ),
                            download_dir=Path(tmpdir),
                            clients={
                                case["provider_name"]: FixtureProvider(
                                    metadata=paper_fetch.ProviderFailure(
                                        "not_supported",
                                        "Browser-workflow provider metadata is route-only.",
                                    ),
                                    raw_payload=_typed_payload(
                                        provider=case["provider_name"],
                                        source_url=case["landing_url"],
                                        content_type="text/html",
                                        body=b"<html></html>",
                                        route_kind="html",
                                        markdown_text="\n\n".join(
                                            [
                                                f"# {case['title']}",
                                                "## Results",
                                                ("Body text " * 80).strip(),
                                                f"![Figure 1]({case['remote_url']})",
                                                "**Figure 1.** Caption body for the browser HTML figure.",
                                            ]
                                        ),
                                        source_trail=[
                                            f"fulltext:{case['provider_name']}_html_ok"
                                        ],
                                    ),
                                    article_factory=case["article_factory"],
                                    related_assets={
                                        "assets": [
                                            {
                                                "kind": "figure",
                                                "heading": "Figure 1",
                                                "caption": "Caption body for the browser HTML figure.",
                                                "path": str(asset_path),
                                                "source_url": case["remote_url"],
                                                "section": "body",
                                            }
                                        ],
                                        "asset_failures": [],
                                    },
                                ),
                                "crossref": FixtureProvider(
                                    metadata={
                                        "provider": "crossref",
                                        "official_provider": False,
                                        "doi": case["doi"],
                                        "title": case["title"],
                                        "landing_page_url": case["landing_url"],
                                        "authors": ["Alice Example"],
                                        "fulltext_links": [],
                                        "references": [],
                                    }
                                ),
                            },
                        )

                    self.assertEqual(envelope.source, case["expected_source"])
                    assert envelope.article is not None
                    assert envelope.markdown is not None
                    self.assertEqual(envelope.article.assets[0].path, str(asset_path))
                    self.assertIn(f"![Figure 1]({asset_path})", envelope.markdown)
                    self.assertNotIn(
                        f"![Figure 1]({case['remote_url']})", envelope.markdown
                    )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_browser_workflow_pdf_fallback_routes_skip_asset_downloads(
        self,
    ) -> None:
        cases = [
            (
                "wiley",
                "10.1111/test",
                "https://example.test/wiley",
                WileyClient(HttpTransport(), {}),
                "wiley_browser",
            ),
            (
                "science",
                "10.1126/science.test",
                "https://www.science.org/doi/full/10.1126/science.test",
                science_provider.ScienceClient(HttpTransport(), {}),
                "science",
            ),
            (
                "pnas",
                "10.1073/pnas.test",
                "https://www.pnas.org/doi/10.1073/pnas.test",
                pnas_provider.PnasClient(HttpTransport(), {}),
                "pnas",
            ),
        ]
        original_resolve = paper_fetch.resolve_paper
        try:
            for (
                provider_name,
                doi,
                landing_url,
                provider_client,
                expected_source,
            ) in cases:
                with self.subTest(provider=provider_name):
                    resolved = paper_fetch.ResolvedQuery(
                        query=doi,
                        query_kind="doi",
                        doi=doi,
                        landing_url=landing_url,
                        provider_hint=provider_name,
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = (
                        lambda *args, resolved=resolved, **kwargs: resolved
                    )
                    raw_payload = _typed_payload(
                        provider=provider_name,
                        source_url=f"{landing_url}.pdf",
                        content_type="application/pdf",
                        body=fulltext_pdf_bytes(),
                        route_kind="pdf_fallback",
                        markdown_text=f"# {provider_name.title()} PDF Article\n\n## Results\n\n"
                        + ("Body text " * 80),
                        warnings=[
                            "Full text was extracted from PDF fallback after the HTML path was not usable."
                        ],
                        source_trail=[
                            f"fulltext:{provider_name}_html_fail",
                            f"fulltext:{provider_name}_pdf_fallback_ok",
                        ],
                        needs_local_copy=True,
                    )
                    asset_download = mock.Mock(
                        side_effect=AssertionError(
                            "PDF fallback routes should not attempt asset downloads."
                        )
                    )
                    with (
                        tempfile.TemporaryDirectory() as tmpdir,
                        mock.patch.object(
                            provider_client,
                            "fetch_metadata",
                            side_effect=paper_fetch.ProviderFailure(
                                "not_supported", "Route-only provider metadata."
                            ),
                        ),
                        mock.patch.object(
                            provider_client,
                            "fetch_raw_fulltext",
                            return_value=raw_payload,
                        ),
                        mock.patch.object(
                            provider_client,
                            "download_related_assets",
                            asset_download,
                        ),
                    ):
                        article = fetch_paper_model(
                            doi,
                            asset_profile="body",
                            output_dir=Path(tmpdir),
                            clients={
                                provider_name: provider_client,
                                "crossref": FixtureProvider(
                                    metadata={
                                        "provider": "crossref",
                                        "official_provider": False,
                                        "doi": doi,
                                        "title": f"{provider_name.title()} PDF Article",
                                        "landing_page_url": landing_url,
                                        "authors": ["Alice Example"],
                                        "fulltext_links": [],
                                        "references": [],
                                    }
                                ),
                            },
                        )

                    asset_download.assert_not_called()

                    self.assertEqual(article.source, expected_source)
                    self.assertIn(
                        f"download:{provider_name}_assets_skipped_text_only",
                        article.quality.source_trail,
                    )
        finally:
            paper_fetch.resolve_paper = original_resolve
