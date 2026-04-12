from __future__ import annotations

import unittest

from paper_fetch import service as paper_fetch
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.providers import html_generic
from paper_fetch.providers.base import ProviderFailure, RawFulltextPayload
from tests.paths import FIXTURE_DIR


class FixtureTransport(html_generic.HttpTransport):
    def __init__(self, responses):
        self.responses = responses

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
        if url not in self.responses:
            raise html_generic.RequestFailure(404, f"Missing fixture response for {url}")
        body, response_url = self.responses[url]
        return {
            "status_code": 200,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": body,
            "url": response_url,
        }


class ProviderStub:
    def __init__(self, metadata=None, raw_payload=None, raw_error=None, article_factory=None):
        self._metadata = metadata
        self._raw_payload = raw_payload
        self._raw_error = raw_error
        self._article_factory = article_factory

    def fetch_metadata(self, query):
        if isinstance(self._metadata, Exception):
            raise self._metadata
        return self._metadata

    def fetch_raw_fulltext(self, doi, metadata):
        if self._raw_error:
            raise self._raw_error
        return self._raw_payload

    def to_article_model(self, metadata, raw_payload, *, downloaded_assets=None, asset_failures=None):
        if self._article_factory is None:
            raise AssertionError("article_factory must be provided for raw full-text tests.")
        return self._article_factory(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )


class FailingHtmlClient:
    def __init__(self, error):
        self.error = error

    def fetch_article_model(self, landing_url, *, metadata=None, expected_doi=None, download_dir=None, asset_profile="none"):
        raise self.error


def fetch_article(query: str, **kwargs):
    envelope = paper_fetch.fetch_paper(query, modes={"article"}, **kwargs)
    assert envelope.article is not None
    return envelope.article


NATURE_HTML_SAMPLES = [
    {
        "doi": "10.1038/d41586-022-01795-9",
        "fixture": "nature_d41586_022_01795_9.html",
        "url": "https://www.nature.com/articles/d41586-022-01795-9",
        "title": "After COVID, African countries vow to take the fight to malaria",
        "journal": "Nature",
        "authors": ["T. V. Padma"],
        "expected_headings": [
            "After COVID, African countries vow to take the fight to malaria",
            "Rising cases",
            "Lessons learnt",
        ],
        "figure_caption_contains": "Checking mosquito netting",
    },
    {
        "doi": "10.1038/d41586-023-01829-w",
        "fixture": "nature_d41586_023_01829_w.html",
        "url": "https://www.nature.com/articles/d41586-023-01829-w",
        "title": "How to make the workplace fairer for female researchers",
        "journal": "Nature",
        "authors": ["Katharine Sanderson"],
        "expected_headings": [
            "How to make the workplace fairer for female researchers",
            "Doing science equally",
        ],
        "figure_caption_contains": "Children study at an open-air school",
    },
    {
        "doi": "10.1038/s41561-022-00983-6",
        "fixture": "nature_s41561_022_00983_6.html",
        "url": "https://www.nature.com/articles/s41561-022-00983-6",
        "title": "Ozone depletion over the Arctic affects spring climate in the Northern Hemisphere",
        "journal": "Nature Geoscience",
        "authors": [],
        "expected_headings": [
            "The question",
            "The discovery",
            "The implications",
            "Expert opinion",
            "Behind the paper",
            "From the editor",
        ],
        "figure_caption_contains": "Modelled ozone effects",
    },
]


def read_fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


class RegressionSampleTests(unittest.TestCase):
    def test_nature_html_generic_regression_samples(self) -> None:
        for sample in NATURE_HTML_SAMPLES:
            with self.subTest(doi=sample["doi"]):
                client = html_generic.HtmlGenericClient(
                    FixtureTransport({sample["url"]: (read_fixture_bytes(sample["fixture"]), sample["url"])}),
                    {},
                )

                article = client.fetch_article_model(sample["url"])
                headings = [section.heading for section in article.sections]
                markdown = article.to_ai_markdown(max_tokens=16000)

                self.assertEqual(article.source, "html_generic")
                self.assertEqual(article.doi, sample["doi"])
                self.assertEqual(article.metadata.title, sample["title"])
                self.assertEqual(article.metadata.journal, sample["journal"])
                self.assertEqual(article.metadata.authors, sample["authors"])
                self.assertTrue(article.quality.has_fulltext)
                self.assertEqual(article.quality.warnings, [])
                self.assertGreaterEqual(len(article.sections), len(sample["expected_headings"]))
                for heading in sample["expected_headings"]:
                    self.assertIn(heading, headings)
                self.assertTrue(
                    any(sample["figure_caption_contains"] in (asset.caption or "") for asset in article.assets),
                    f"Expected figure caption containing {sample['figure_caption_contains']!r}.",
                )
                self.assertNotIn("Similar content being viewed by others", markdown)
                self.assertNotIn("Get shareable link", markdown)
                self.assertNotIn("Cookie settings", markdown)
                self.assertNotIn("(refs.)", markdown)
                self.assertNotIn("(ref.)", markdown)

    def test_paper_fetch_uses_html_fallback_for_nature_samples(self) -> None:
        original_resolve = paper_fetch.resolve_paper
        try:
            for sample in NATURE_HTML_SAMPLES:
                with self.subTest(doi=sample["doi"]):
                    resolved = paper_fetch.ResolvedQuery(
                        query=sample["doi"],
                        query_kind="doi",
                        doi=sample["doi"],
                        landing_url=sample["url"],
                        provider_hint="springer",
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = lambda *args, _resolved=resolved, **kwargs: _resolved

                    html_client = html_generic.HtmlGenericClient(
                        FixtureTransport({sample["url"]: (read_fixture_bytes(sample["fixture"]), sample["url"])}),
                        {},
                    )
                    metadata = {
                        "provider": "crossref",
                        "official_provider": False,
                        "doi": sample["doi"],
                        "title": sample["title"],
                        "journal_title": sample["journal"],
                        "landing_page_url": sample["url"],
                        "authors": sample["authors"],
                        "fulltext_links": [],
                        "references": [],
                    }

                    article = fetch_article(
                        sample["doi"],
                        strategy=paper_fetch.FetchStrategy(),
                        clients={
                            "springer": ProviderStub(
                                metadata=ProviderFailure("not_supported", "Regression fixture omits official XML."),
                                raw_error=ProviderFailure("not_supported", "Regression fixture omits official XML."),
                            ),
                            "crossref": ProviderStub(metadata=metadata),
                        },
                        html_client=html_client,
                    )

                    self.assertEqual(article.source, "html_generic")
                    self.assertEqual(article.metadata.title, sample["title"])
                    self.assertTrue(article.quality.has_fulltext)
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_paper_fetch_uses_elsevier_xml_fixture_for_positive_sample(self) -> None:
        doi = "10.1016/j.rse.2026.115369"
        metadata = {
            "provider": "elsevier",
            "official_provider": True,
            "doi": doi,
            "title": "Sentinel-1 for offshore wind energy application",
            "journal_title": "Remote Sensing of Environment",
            "published": "2026-6",
            "landing_page_url": "https://www.sciencedirect.com/science/article/pii/S0034425726001030",
            "authors": ["C.B. Hasager", "K. Dimitriadou"],
            "abstract": "This review summarizes Sentinel-1 SAR products used in offshore wind-energy applications.",
            "fulltext_links": [],
            "references": [],
        }
        xml_body = read_fixture_bytes("elsevier_10.1016_j.rse.2026.115369.xml")
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2026.115369?view=FULL",
            content_type="text/xml",
            body=xml_body,
            metadata={"reason": "Replay fixture for Elsevier XML regression test."},
        )
        real_elsevier_client = elsevier_provider.ElsevierClient(FixtureTransport({}), {})
        replay_provider = ProviderStub(
            metadata=metadata,
            raw_payload=raw_payload,
            article_factory=real_elsevier_client.to_article_model,
        )

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: paper_fetch.ResolvedQuery(
                query=doi,
                query_kind="doi",
                doi=doi,
                landing_url=metadata["landing_page_url"],
                provider_hint="elsevier",
                confidence=1.0,
            )

            article = fetch_article(
                doi,
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": replay_provider,
                    "crossref": ProviderStub(metadata=metadata),
                },
                html_client=FailingHtmlClient(
                    paper_fetch.ProviderFailure("no_result", "HTML fallback should not be used for XML regression.")
                ),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertEqual(article.metadata.title, metadata["title"])
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(len(article.sections) >= 4)
        headings = [section.heading for section in article.sections]
        self.assertIn("Introduction", headings)
        self.assertIn("Operational systems", headings)
        self.assertIn("Wind direction sources", headings)
        self.assertIn("Trend analysis", headings)

    def test_paper_fetch_elsevier_negative_sample_falls_back_to_crossref_metadata(self) -> None:
        doi = "10.1016/j.solener.2024.01.001"
        landing_url = "https://www.sciencedirect.com/science/article/pii/S0038092X24000010"
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": doi,
            "title": "Regression fixture for unavailable Elsevier full text",
            "journal_title": "Solar Energy",
            "published": "2024-01-01",
            "landing_page_url": landing_url,
            "authors": [],
            "abstract": "Metadata-only fallback for a DOI whose official Elsevier full text returned 404.",
            "fulltext_links": [],
            "references": [],
        }
        not_found_error = paper_fetch.ProviderFailure(
            "error",
            "HTTP 404 for https://api.elsevier.com/content/article/doi/10.1016%2Fj.solener.2024.01.001?view=FULL",
        )

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: paper_fetch.ResolvedQuery(
                query=doi,
                query_kind="doi",
                doi=doi,
                landing_url=landing_url,
                provider_hint="elsevier",
                confidence=1.0,
            )

            article = fetch_article(
                doi,
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": ProviderStub(
                        metadata=ProviderFailure("not_supported", "Regression fixture omits official metadata."),
                        raw_error=not_found_error,
                    ),
                    "crossref": ProviderStub(metadata=metadata),
                },
                html_client=FailingHtmlClient(
                    paper_fetch.ProviderFailure("no_result", "HTML extraction failed for the regression fixture.")
                ),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertEqual(article.doi, doi)
        self.assertTrue(any("HTTP 404" in warning for warning in article.quality.warnings))
        self.assertTrue(any("Full text was not available" in warning for warning in article.quality.warnings))


if __name__ == "__main__":
    unittest.main()
