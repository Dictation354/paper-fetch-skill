# ruff: noqa: F403,F405
from __future__ import annotations

from ._service_support import *


class ServiceMetadataRoutingTests(unittest.TestCase):
    def test_fetch_metadata_uses_crossref_signal_without_public_crossref_source(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )

        metadata, provider_name, source_trail = (
            paper_fetch.fetch_metadata_for_resolved_query(
                resolved,
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://api.elsevier.com/content/abstract/scopus_id/0012465826",
                            "authors": ["Alice Example"],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "authors": ["Alice Example"],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                strategy=paper_fetch.FetchStrategy(preferred_providers=["elsevier"]),
            )
        )

        self.assertEqual(provider_name, "elsevier")
        self.assertEqual(metadata["title"], "Official Elsevier Title")
        self.assertEqual(
            metadata["landing_page_url"],
            "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
        )
        self.assertIn("route:crossref_signal_ok", source_trail)
        self.assertIn("route:signal_domain_elsevier", source_trail)
        self.assertIn("route:signal_publisher_elsevier", source_trail)
        self.assertIn("route:probe_elsevier_positive", source_trail)
        self.assertIn("route:provider_selected_elsevier", source_trail)
        self.assertIn("metadata:elsevier_ok", source_trail)
        self.assertNotIn("metadata:crossref_ok", source_trail)

    def test_fetch_metadata_records_unknown_probe_and_uses_crossref_public_metadata(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            provider_hint="springer",
            confidence=1.0,
        )

        metadata, provider_name, source_trail = (
            paper_fetch.fetch_metadata_for_resolved_query(
                resolved,
                clients={
                    "springer": FixtureProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "not_supported", "Springer metadata probe is not supported."
                        )
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1007/test",
                            "title": "Crossref Fallback",
                            "landing_page_url": "https://example.test/article",
                            "authors": [],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                strategy=paper_fetch.FetchStrategy(),
            )
        )

        self.assertEqual(provider_name, "springer")
        self.assertEqual(metadata["title"], "Crossref Fallback")
        self.assertIn("route:probe_springer_unknown", source_trail)
        self.assertIn("route:provider_selected_springer", source_trail)
        self.assertIn("metadata:crossref_ok", source_trail)

    def test_fetch_paper_model_routes_10_1006_doi_to_elsevier_via_crossref_signal(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )
        official_article = sample_article()
        official_article.doi = resolved.doi
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = _fetch_paper(
                "10.1006/jaer.1996.0085",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    preferred_providers=["elsevier"],
                ),
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1006%2Fjaer.1996.0085",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            ).article
        finally:
            paper_fetch.resolve_paper = original_resolve

        assert article is not None
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("route:crossref_signal_ok", article.quality.source_trail)
        self.assertIn("route:provider_selected_elsevier", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertNotIn("metadata:crossref_ok", article.quality.source_trail)

    def test_fetch_paper_model_weak_negative_metadata_probe_still_attempts_official_fulltext(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )
        official_article = sample_article()
        official_article.doi = resolved.doi
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1006/jaer.1996.0085",
                clients={
                    "elsevier": FixtureProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "no_result", "Elsevier metadata probe missed."
                        ),
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1006%2Fjaer.1996.0085",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("route:probe_elsevier_negative", article.quality.source_trail)
        self.assertIn("route:provider_selected_elsevier", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_attempt", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)

    def test_fetch_paper_crossref_only_strategy_skips_official_probes(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = _fetch_paper(
                "10.1016/test",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    preferred_providers=["crossref"],
                ),
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=sample_article(),
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Crossref Title",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        assert envelope.article is not None
        self.assertEqual(envelope.article.source, "crossref_meta")
        self.assertIn("metadata:crossref_ok", envelope.article.quality.source_trail)
        self.assertNotIn(
            "route:probe_elsevier_positive", envelope.article.quality.source_trail
        )
        self.assertNotIn(
            "fulltext:elsevier_attempt", envelope.article.quality.source_trail
        )

    def test_fetch_paper_returns_fixed_envelope_shape_with_public_source_mapping(
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
        official_article = sample_article()
        official_article.doi = resolved.doi
        official_article.source = "wiley_browser"
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = _fetch_paper(
                "10.1111/test",
                modes={"markdown"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "wiley": FixtureProvider(
                        metadata=paper_fetch.ProviderFailure(
                            "not_supported", "No official metadata."
                        ),
                        raw_payload=RawFulltextPayload(
                            provider="wiley",
                            source_url="https://example.test/wiley.pdf",
                            content_type="application/pdf",
                            body=b"%PDF-1.4",
                        ),
                        article=official_article,
                    ),
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/wiley",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(
            set(envelope.to_dict().keys()),
            {
                "doi",
                "source",
                "acquisition",
                "has_fulltext",
                "content_kind",
                "has_abstract",
                "warnings",
                "source_trail",
                "trace",
                "diagnostic_artifacts",
                "token_estimate",
                "token_estimate_breakdown",
                "quality",
                "article",
                "markdown",
                "metadata",
            },
        )
        self.assertEqual(envelope.source, "wiley_browser")
        self.assertIsNone(envelope.article)
        self.assertIsNone(envelope.metadata)
        self.assertTrue(envelope.markdown)
        self.assertTrue(envelope.has_fulltext)

    def test_fetch_paper_only_populates_envelope_metadata_when_requested(self) -> None:
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
            without_metadata = _fetch_paper(
                "10.1016/test",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": FixtureProvider(
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
            with_metadata = _fetch_paper(
                "10.1016/test",
                modes={"article", "metadata"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": FixtureProvider(
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
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIsNone(without_metadata.metadata)
        self.assertIsNotNone(with_metadata.metadata)
        self.assertEqual(
            with_metadata.metadata.title, with_metadata.article.metadata.title
        )

    def test_fetch_paper_non_provider_landing_page_returns_metadata_only_without_generic_html_attempt(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1000/test",
            query_kind="doi",
            doi="10.1000/test",
            landing_url="https://example.test/article-abstract",
            provider_hint=None,
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1000/test",
                clients={
                    "crossref": FixtureProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1000/test",
                            "title": "Abstract Only Article",
                            "abstract": "Crossref abstract",
                            "landing_page_url": "https://example.test/article-abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    )
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertNotIn("fallback:html_attempt", article.quality.source_trail)
        self.assertNotIn("fallback:html_abstract_only", article.quality.source_trail)

    def test_fetch_paper_raises_when_metadata_only_fallback_is_disabled(self) -> None:
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
            with self.assertRaises(paper_fetch.PaperFetchFailure):
                _fetch_paper(
                    "10.1016/test",
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(
                        allow_metadata_only_fallback=False,
                    ),
                    clients={
                        "elsevier": FixtureProvider(
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
                                "no_result", "No full text."
                            ),
                        ),
                        "crossref": FixtureProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fulltext_tries_second_ranked_official_provider_after_no_result(
        self,
    ) -> None:
        doi = "10.1007/ranked-fallback"
        resolved = paper_fetch.ResolvedQuery(
            query=doi,
            query_kind="doi",
            doi=doi,
            landing_url="https://linkinghub.elsevier.com/retrieve/pii/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        springer_article = sample_article()
        springer_article.doi = doi
        springer_article.source = "springer_html"
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                doi,
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": doi,
                            "title": "Ranked Provider Article",
                        },
                        raw_error=paper_fetch.ProviderFailure(
                            "no_result",
                            "Elsevier did not expose this migrated article.",
                        ),
                    ),
                    "springer": FixtureProvider(
                        metadata={
                            "provider": "springer",
                            "official_provider": True,
                            "doi": doi,
                            "title": "Ranked Provider Article",
                        },
                        raw_payload=RawFulltextPayload(
                            provider="springer",
                            source_url="https://link.springer.com/article/test",
                            content_type="text/html",
                            body=b"<article>full text</article>",
                        ),
                        article=springer_article,
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "springer_html")
        self.assertIn(
            "route:provider_candidate_elsevier_rejected",
            article.quality.source_trail,
        )
        self.assertIn(
            "route:provider_candidate_springer_accepted",
            article.quality.source_trail,
        )

    def test_weak_conflicting_access_boundary_continues_to_strong_doi_provider(
        self,
    ) -> None:
        class CountingProvider(FixtureProvider):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.raw_calls = 0

            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                self.raw_calls += 1
                return super().fetch_raw_fulltext(
                    doi,
                    metadata,
                    context=context,
                )

        doi = "10.1007/access-boundary"
        resolved = paper_fetch.ResolvedQuery(
            query=doi,
            query_kind="doi",
            doi=doi,
            landing_url="https://linkinghub.elsevier.com/retrieve/pii/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        springer_article = sample_article()
        springer_article.doi = doi
        springer_article.source = "springer_html"
        second = CountingProvider(
            metadata={
                "provider": "springer",
                "official_provider": True,
                "doi": doi,
                "title": "Protected Article",
            },
            raw_payload=RawFulltextPayload(
                provider="springer",
                source_url="https://link.springer.com/article/test",
                content_type="text/html",
                body=b"<article>full text</article>",
            ),
            article=springer_article,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                doi,
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": doi,
                            "title": "Protected Article",
                        },
                        raw_error=paper_fetch.ProviderFailure(
                            "no_access",
                            "Authentication is required.",
                        ),
                    ),
                    "springer": second,
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "springer_html")
        self.assertEqual(second.raw_calls, 1)
        self.assertIn(
            "route:provider_candidate_elsevier_access_boundary_weak_continue",
            article.quality.source_trail,
        )
        self.assertIn(
            "route:provider_candidate_springer_identity_strong",
            article.quality.source_trail,
        )

    def test_strong_doi_provider_access_boundary_stops_weaker_candidate(self) -> None:
        class CountingProvider(FixtureProvider):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.raw_calls = 0

            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                self.raw_calls += 1
                return super().fetch_raw_fulltext(doi, metadata, context=context)

        doi = "10.1016/j.example.2026.1"
        resolved = paper_fetch.ResolvedQuery(
            query=doi,
            query_kind="doi",
            doi=doi,
            landing_url="https://linkinghub.elsevier.com/retrieve/pii/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        second = CountingProvider(
            metadata={"provider": "springer", "doi": doi},
            raw_error=AssertionError("weak second provider must not be attempted"),
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                doi,
                clients={
                    "elsevier": FixtureProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": doi,
                            "title": "Protected Article",
                            "publisher": "Springer Nature",
                        },
                        raw_error=paper_fetch.ProviderFailure(
                            "no_access", "Authentication is required."
                        ),
                    ),
                    "springer": second,
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertEqual(second.raw_calls, 0)
        self.assertIn(
            "route:provider_candidate_elsevier_access_boundary_stop",
            article.quality.source_trail,
        )
