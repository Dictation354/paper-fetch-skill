from __future__ import annotations

import unittest

from paper_fetch import service as paper_fetch
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.providers import html_generic
from paper_fetch.providers import pnas as pnas_provider
from paper_fetch.providers import science as science_provider
from paper_fetch.providers import springer as springer_provider
from paper_fetch.providers import wiley as wiley_provider
from paper_fetch.providers._science_pnas_html import extract_science_pnas_markdown
from paper_fetch.providers.base import ProviderFailure, RawFulltextPayload
from tests.provider_benchmark_samples import (
    iter_provider_benchmark_samples,
    provider_benchmark_sample,
)
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
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SCIENCE_SAMPLE = provider_benchmark_sample("science")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


def read_fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def read_fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class RegressionSampleTests(unittest.TestCase):
    def _fetch_replayed_provider_article(
        self,
        *,
        sample,
        metadata: dict[str, object],
        provider_name: str,
        raw_payload: RawFulltextPayload,
        provider_client,
    ):
        replay_provider = ProviderStub(
            metadata=metadata,
            raw_payload=raw_payload,
            article_factory=provider_client.to_article_model,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: paper_fetch.ResolvedQuery(
                query=sample.doi,
                query_kind="doi",
                doi=sample.doi,
                landing_url=sample.landing_url,
                provider_hint=provider_name,
                confidence=1.0,
            )
            return fetch_article(
                sample.doi,
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    provider_name: replay_provider,
                    "crossref": ProviderStub(metadata=metadata),
                },
                html_client=FailingHtmlClient(
                    paper_fetch.ProviderFailure("no_result", "HTML fallback should not be used for regression replay.")
                ),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_provider_benchmark_samples_are_post_2020(self) -> None:
        for sample in iter_provider_benchmark_samples():
            with self.subTest(provider=sample.provider):
                self.assertGreaterEqual(sample.year, 2020)

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

    def test_paper_fetch_uses_springer_html_provider_for_nature_samples(self) -> None:
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

                    transport = FixtureTransport({sample["url"]: (read_fixture_bytes(sample["fixture"]), sample["url"])})
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
                            "springer": springer_provider.SpringerClient(transport, {}),
                            "crossref": ProviderStub(metadata=metadata),
                        },
                        transport=transport,
                    )

                    self.assertEqual(article.source, "springer_html")
                    self.assertEqual(article.metadata.title, sample["title"])
                    self.assertTrue(article.quality.has_fulltext)
                    self.assertIn("fulltext:springer_html_ok", article.quality.source_trail)
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_paper_fetch_uses_elsevier_xml_fixture_for_positive_sample(self) -> None:
        sample = ELSEVIER_SAMPLE
        metadata = {
            "provider": "elsevier",
            "official_provider": True,
            "doi": sample.doi,
            "title": sample.title,
            "journal_title": "Remote Sensing of Environment",
            "published": "2025-01-01",
            "landing_page_url": sample.landing_url,
            "authors": [],
            "abstract": "Paraphrased offline fixture for the 2025 geostationary satellite vegetation study.",
            "fulltext_links": [],
            "references": [],
        }
        xml_body = read_fixture_bytes(sample.fixture_name)
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2025.114648?view=FULL",
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
                query=sample.doi,
                query_kind="doi",
                doi=sample.doi,
                landing_url=sample.landing_url,
                provider_hint="elsevier",
                confidence=1.0,
            )

            article = fetch_article(
                sample.doi,
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
        self.assertIn("Data sources", headings)
        self.assertIn("Seasonal transitions", headings)
        self.assertIn("Regional implications", headings)

    def test_paper_fetch_uses_science_replay_fixture_for_positive_sample(self) -> None:
        science_html = read_fixture_text(SCIENCE_SAMPLE.fixture_name)
        markdown_text, _ = extract_science_pnas_markdown(
            science_html,
            SCIENCE_SAMPLE.landing_url,
            "science",
            metadata={"doi": SCIENCE_SAMPLE.doi},
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": SCIENCE_SAMPLE.doi,
            "title": SCIENCE_SAMPLE.title,
            "journal_title": "Science",
            "published": "2026-01-01",
            "landing_page_url": SCIENCE_SAMPLE.landing_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="science",
            source_url=SCIENCE_SAMPLE.landing_url,
            content_type="text/html",
            body=science_html.encode("utf-8"),
            metadata={
                "route": "html",
                "markdown_text": markdown_text,
                "source_trail": ["fulltext:science_html_ok"],
            },
        )

        article = self._fetch_replayed_provider_article(
            sample=SCIENCE_SAMPLE,
            metadata=metadata,
            provider_name="science",
            raw_payload=raw_payload,
            provider_client=science_provider.ScienceClient(FixtureTransport({}), {}),
        )

        self.assertEqual(article.source, SCIENCE_SAMPLE.expected_source)
        self.assertEqual(article.metadata.title, SCIENCE_SAMPLE.title)
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:science_html_ok", article.quality.source_trail)

    def test_paper_fetch_uses_wiley_replay_fixture_for_positive_sample(self) -> None:
        markdown_text = read_fixture_text(WILEY_SAMPLE.fixture_name)
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": WILEY_SAMPLE.doi,
            "title": WILEY_SAMPLE.title,
            "journal_title": "Cancer Science",
            "published": "2024-01-01",
            "landing_page_url": WILEY_SAMPLE.landing_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="wiley",
            source_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{WILEY_SAMPLE.doi}",
            content_type="application/pdf",
            body=b"%PDF-1.4\n",
            metadata={
                "route": "pdf_fallback",
                "markdown_text": markdown_text,
                "source_trail": [
                    "fulltext:wiley_html_fail",
                    "fulltext:wiley_pdf_api_ok",
                    "fulltext:wiley_pdf_fallback_ok",
                ],
            },
            needs_local_copy=True,
        )

        article = self._fetch_replayed_provider_article(
            sample=WILEY_SAMPLE,
            metadata=metadata,
            provider_name="wiley",
            raw_payload=raw_payload,
            provider_client=wiley_provider.WileyClient(FixtureTransport({}), {}),
        )

        self.assertEqual(article.source, WILEY_SAMPLE.expected_source)
        self.assertEqual(article.metadata.title, WILEY_SAMPLE.title)
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)

    def test_paper_fetch_uses_pnas_replay_fixture_for_positive_sample(self) -> None:
        markdown_text = read_fixture_text(PNAS_SAMPLE.fixture_name)
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": PNAS_SAMPLE.doi,
            "title": PNAS_SAMPLE.title,
            "journal_title": "Proceedings of the National Academy of Sciences",
            "published": "2024-01-01",
            "landing_page_url": PNAS_SAMPLE.landing_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="pnas",
            source_url=PNAS_SAMPLE.landing_url,
            content_type="text/html",
            body=markdown_text.encode("utf-8"),
            metadata={
                "route": "html",
                "markdown_text": markdown_text,
                "source_trail": ["fulltext:pnas_html_ok"],
            },
        )

        article = self._fetch_replayed_provider_article(
            sample=PNAS_SAMPLE,
            metadata=metadata,
            provider_name="pnas",
            raw_payload=raw_payload,
            provider_client=pnas_provider.PnasClient(FixtureTransport({}), {}),
        )

        self.assertEqual(article.source, PNAS_SAMPLE.expected_source)
        self.assertEqual(article.metadata.title, PNAS_SAMPLE.title)
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:pnas_html_ok", article.quality.source_trail)

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
