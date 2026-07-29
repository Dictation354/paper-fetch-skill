# ruff: noqa: F403,F405
from __future__ import annotations

from ._service_support import *


class ServiceProbeAndAssetTests(unittest.TestCase):
    def test_fetch_paper_omitted_asset_profile_defaults_to_body_for_scoped_html_providers(
        self,
    ) -> None:
        cases = [
            ("springer", "10.1007/test", "https://www.nature.com/articles/example"),
            ("wiley", "10.1111/test", "https://example.test/wiley"),
            (
                "science",
                "10.1126/science.test",
                "https://www.science.org/doi/full/10.1126/science.test",
            ),
            ("pnas", "10.1073/pnas.test", "https://www.pnas.org/doi/10.1073/pnas.test"),
        ]
        original_resolve = paper_fetch.resolve_paper
        try:
            for provider_name, doi, landing_url in cases:
                with self.subTest(provider=provider_name):
                    related_asset_calls: list[str] = []
                    resolved = paper_fetch.ResolvedQuery(
                        query=doi,
                        query_kind="doi",
                        doi=doi,
                        landing_url=landing_url,
                        provider_hint=provider_name,
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = (
                        lambda *args, _resolved=resolved, **kwargs: _resolved
                    )
                    with tempfile.TemporaryDirectory() as tmpdir:
                        envelope = _fetch_paper(
                            doi,
                            modes={"article"},
                            strategy=paper_fetch.FetchStrategy(),
                            download_dir=Path(tmpdir),
                            clients={
                                provider_name: StubProvider(
                                    raw_payload=_typed_payload(
                                        provider=provider_name,
                                        source_url=landing_url,
                                        content_type="text/html",
                                        body=b"<html></html>",
                                        route_kind="html",
                                        markdown_text="# Example Article\n\n## Results\n\n"
                                        + ("Body text " * 80),
                                        source_trail=[
                                            f"fulltext:{provider_name}_html_ok"
                                        ],
                                    ),
                                    article=sample_article(doi),
                                    related_asset_factory=lambda *args, related_asset_calls=related_asset_calls, **kwargs: (
                                        related_asset_calls.append(
                                            kwargs["asset_profile"]
                                        )
                                        or {"assets": [], "asset_failures": []}
                                    ),
                                ),
                                "crossref": StubProvider(
                                    metadata={
                                        "provider": "crossref",
                                        "official_provider": False,
                                        "doi": doi,
                                        "title": "Example Article",
                                        "landing_page_url": landing_url,
                                        "authors": ["Alice Example"],
                                        "fulltext_links": [],
                                        "references": [],
                                    }
                                ),
                            },
                        )

                    self.assertIsNotNone(envelope.article)
                    self.assertEqual(related_asset_calls, ["body"])
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fetch_paper_explicit_asset_profile_none_disables_scoped_provider_asset_downloads(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.test",
            query_kind="doi",
            doi="10.1126/science.test",
            landing_url="https://www.science.org/doi/full/10.1126/science.test",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                envelope = _fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(asset_profile="none"),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            raw_payload=_typed_payload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text="# Example Article\n\n## Results\n\n"
                                + ("Body text " * 80),
                                source_trail=["fulltext:science_html_ok"],
                            ),
                            article=sample_article(resolved.doi),
                            related_asset_factory=lambda *args, **kwargs: (
                                _ for _ in ()
                            ).throw(
                                AssertionError(
                                    "asset downloads should stay disabled when asset_profile='none'"
                                )
                            ),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Example Article",
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

        self.assertIn(
            "download:science_assets_skipped_profile_none", envelope.source_trail
        )

    def test_fetch_paper_warns_when_scoped_provider_falls_back_to_preview_images(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.preview",
            query_kind="doi",
            doi="10.1126/science.preview",
            landing_url="https://www.science.org/doi/full/10.1126/science.preview",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                preview_path = Path(tmpdir) / "figure-preview.png"
                preview_path.write_bytes(b"preview")
                envelope = _fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            raw_payload=_typed_payload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text="# Example Article\n\n## Results\n\n"
                                + ("Body text " * 80),
                                source_trail=["fulltext:science_html_ok"],
                            ),
                            article=sample_article(resolved.doi),
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Preview figure",
                                        "path": str(preview_path),
                                        "section": "body",
                                        "download_tier": "preview",
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Example Article",
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

        self.assertTrue(
            any(
                "fell back to preview images" in warning
                for warning in envelope.warnings
            )
        )

    def test_fetch_paper_accepts_preview_images_with_sufficient_dimensions(
        self,
    ) -> None:
        """rule: rule-image-download-validates-real-images"""
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.preview.accepted",
            query_kind="doi",
            doi="10.1126/science.preview.accepted",
            landing_url="https://www.science.org/doi/full/10.1126/science.preview.accepted",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                preview_path = Path(tmpdir) / "figure-preview.png"
                preview_path.write_bytes(b"preview")
                envelope = _fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            raw_payload=_typed_payload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text="# Example Article\n\n## Results\n\n"
                                + ("Body text " * 80),
                                source_trail=["fulltext:science_html_ok"],
                            ),
                            article=sample_article(resolved.doi),
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Accepted preview figure",
                                        "path": str(preview_path),
                                        "section": "body",
                                        "download_tier": "preview",
                                        "width": 640,
                                        "height": 480,
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Example Article",
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

        self.assertIn("download:science_assets_preview_accepted", envelope.source_trail)
        self.assertNotIn(
            "download:science_assets_preview_fallback", envelope.source_trail
        )
        self.assertFalse(
            any("used preview images" in warning for warning in envelope.warnings)
        )

    def test_probe_has_fulltext_uses_crossref_license_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1000/license",
            query_kind="doi",
            doi="10.1000/license",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = _probe_has_fulltext(
                "10.1000/license",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1000/license",
                            "title": "Licensed Article",
                            "license_urls": ["https://license.example/test"],
                            "fulltext_links": [],
                            "references": [],
                        }
                    )
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.doi, "10.1000/license")
        self.assertEqual(result.title, "Licensed Article")
        self.assertEqual(result.evidence, ["crossref_license"])
        self.assertEqual(result.warnings, [])

    def test_probe_has_fulltext_uses_crossref_fulltext_link_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1000/fulltext",
            query_kind="doi",
            doi="10.1000/fulltext",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = _probe_has_fulltext(
                "10.1000/fulltext",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1000/fulltext",
                            "title": "Linked Article",
                            "license_urls": [],
                            "fulltext_links": [
                                {"url": "https://fulltext.example/test.pdf"}
                            ],
                            "references": [],
                        }
                    )
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.evidence, ["crossref_fulltext_link"])

    def test_probe_has_fulltext_uses_provider_metadata_probe_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = _probe_has_fulltext(
                "10.1016/test",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1016/test",
                            "title": "Crossref Article",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://example.test/article",
                            "license_urls": [],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "doi": "10.1016/test",
                            "title": "Official Elsevier Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.title, "Official Elsevier Article")
        self.assertEqual(result.evidence, ["provider_probe:elsevier"])

    def test_probe_has_fulltext_uses_catalog_metadata_probe_capability(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.48550/arxiv.2605.06663",
            query_kind="doi",
            doi="10.48550/arxiv.2605.06663",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = _probe_has_fulltext(
                "10.48550/arxiv.2605.06663",
                clients={
                    "arxiv": StubProvider(
                        metadata={
                            "provider": "arxiv",
                            "doi": "10.48550/arxiv.2605.06663",
                            "title": "Official arXiv Article",
                            "landing_page_url": "https://arxiv.org/abs/2605.06663",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.title, "Official arXiv Article")
        self.assertEqual(result.evidence, ["provider_probe:arxiv"])

    def test_probe_has_fulltext_uses_landing_page_citation_pdf_url_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="https://example.test/article",
            query_kind="url",
            doi=None,
            landing_url="https://example.test/article",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = _probe_has_fulltext(
                "https://example.test/article",
                transport=FixtureHtmlTransport(
                    {
                        "https://example.test/article": {
                            "body": (
                                b"<html><head>"
                                b"<meta name='citation_title' content='Landing Page Article' />"
                                b"<meta name='citation_pdf_url' content='https://example.test/article.pdf' />"
                                b"</head><body></body></html>"
                            )
                        }
                    }
                ),
                clients={},
                env={"PAPER_FETCH_SKILL_USER_AGENT": "unit-test"},
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.title, "Landing Page Article")
        self.assertEqual(result.evidence, ["landing_page_citation_pdf_url"])

    def test_probe_has_fulltext_uses_crossref_only_for_springer_signals(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = _probe_has_fulltext(
                "10.1007/test",
                transport=FixtureHtmlTransport(
                    {
                        "https://example.test/article": {
                            "headers": {"content-type": "text/html; charset=utf-8"},
                            "body": b"<html><head><title>Example</title></head><body>Example</body></html>",
                        }
                    }
                ),
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1007/test",
                            "title": "Crossref Article",
                            "publisher": "Springer Science and Business Media LLC",
                            "landing_page_url": "https://example.test/article",
                            "license_urls": [],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                    "springer": StubProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "not_supported",
                            "Springer metadata probe should not be used.",
                        )
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.warnings, [])
