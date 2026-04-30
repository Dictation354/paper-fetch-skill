from __future__ import annotations

import unittest

from paper_fetch import service as paper_fetch
from paper_fetch.extraction.html.assets import extract_html_assets
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.extraction.html._runtime import (
    clean_markdown,
    extract_article_markdown,
    extract_html_abstract_blocks,
    extract_html_section_hints,
)
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.models import article_from_markdown
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.providers import pnas as pnas_provider
from paper_fetch.providers import science as science_provider
from paper_fetch.providers import springer as springer_provider
from paper_fetch.providers import wiley as wiley_provider
from paper_fetch.providers.science_pnas import extract_science_pnas_markdown
from paper_fetch.providers.base import ProviderContent, ProviderFailure, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from tests.provider_benchmark_samples import (
    WILEY_PDF_FALLBACK_SAMPLE,
    iter_provider_benchmark_samples,
    provider_benchmark_sample,
)
from tests.paths import FIXTURE_DIR


class FixtureTransport(HttpTransport):
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
            raise RequestFailure(404, f"Missing fixture response for {url}")
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

    def fetch_raw_fulltext(self, doi, metadata, *, context=None):
        del context
        if self._raw_error:
            raise self._raw_error
        return self._raw_payload

    def to_article_model(self, metadata, raw_payload, *, downloaded_assets=None, asset_failures=None, context=None):
        del context
        if self._article_factory is None:
            raise AssertionError("article_factory must be provided for raw full-text tests.")
        return self._article_factory(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )


def fetch_article(query: str, **kwargs):
    runtime_keys = {key: kwargs.pop(key) for key in ("clients", "transport", "env", "download_dir") if key in kwargs}
    if runtime_keys:
        kwargs["context"] = paper_fetch.RuntimeContext(**runtime_keys)
    envelope = paper_fetch.fetch_paper(query, modes={"article"}, **kwargs)
    assert envelope.article is not None
    return envelope.article


NATURE_HTML_SAMPLES = [
    {
        "doi": "10.1038/d41586-022-01795-9",
        "fixture": "golden_criteria/10.1038_d41586-022-01795-9/original.html",
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
        "fixture": "golden_criteria/10.1038_d41586-023-01829-w/original.html",
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
        "fixture": "golden_criteria/10.1038_s41561-022-00983-6/original.html",
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


def build_shared_html_fixture_article(
    *,
    fixture_name: str,
    landing_url: str,
    source: str = "springer_html",
    metadata: dict[str, object] | None = None,
    noise_profile: str | None = None,
):
    html = read_fixture_text(fixture_name)
    merged_metadata = dict(parse_html_metadata(html, landing_url))
    merged_metadata.update(metadata or {})
    merged_metadata["landing_page_url"] = landing_url

    markdown_text = clean_markdown(
        extract_article_markdown(html, landing_url),
        noise_profile=noise_profile,
    )
    abstract_sections = extract_html_abstract_blocks(html, noise_profile=noise_profile)
    section_hints = extract_html_section_hints(html)
    assets = extract_html_assets(html, landing_url, asset_profile="all")

    return article_from_markdown(
        source=source,
        metadata=merged_metadata,
        doi=str(merged_metadata.get("doi") or "") or None,
        markdown_text=markdown_text,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        assets=assets,
    )


class RegressionSampleTests(unittest.TestCase):
    def _assert_bilingual_abstract_sections(
        self,
        article,
        *,
        abstract_headings: list[str],
        first_body_heading: str,
    ) -> None:
        abstracts = [section for section in article.sections if section.kind == "abstract"]
        self.assertEqual([section.heading for section in abstracts], abstract_headings)
        self.assertTrue(all(section.kind == "abstract" for section in abstracts))
        self.assertEqual(article.metadata.abstract, abstracts[0].text)
        self.assertTrue(article.quality.has_fulltext)
        first_body_section = next(section for section in article.sections if section.kind != "abstract")
        self.assertEqual(first_body_section.kind, "body")
        self.assertEqual(first_body_section.heading, first_body_heading)
        for abstract in abstracts:
            self.assertNotIn(abstract.text, first_body_section.text)

    def _bilingual_case_specs(self):
        return {
            "wiley": {
                "builder": self._build_wiley_bilingual_fixture_article,
                "abstract_headings": ["Abstract", "Resumo"],
                "first_body_heading": "Main Text",
            },
            "springer": {
                "builder": self._build_springer_bilingual_fixture_article,
                "abstract_headings": ["Abstract", "Resume", "Resumen"],
                "first_body_heading": "Results",
            },
            "elsevier": {
                "builder": self._build_elsevier_bilingual_fixture_article,
                "abstract_headings": ["Abstract", "Resumen"],
                "first_body_heading": "Results",
            },
            "sage": {
                "builder": lambda: self._build_shared_bilingual_fixture_article(
                    fixture_name="golden_criteria/10.1345_aph.1M379/bilingual.html",
                    landing_url="https://journals.sagepub.com/doi/full/10.1345/aph.1M379",
                ),
                "abstract_headings": ["Abstract", "Resumen"],
                "first_body_heading": "",
            },
            "tandf": {
                "builder": lambda: self._build_shared_bilingual_fixture_article(
                    fixture_name="golden_criteria/10.1080_19455224.2025.2547671/bilingual.html",
                    landing_url="https://www.tandfonline.com/doi/full/10.1080/19455224.2025.2547671",
                ),
                "abstract_headings": ["Abstract", "Resumen"],
                "first_body_heading": "",
            },
        }

    def _assert_bilingual_fixture_case(self, case_name: str) -> None:
        case = self._bilingual_case_specs()[case_name]
        article = case["builder"]()
        self._assert_bilingual_abstract_sections(
            article,
            abstract_headings=case["abstract_headings"],
            first_body_heading=case["first_body_heading"],
        )

    def _build_wiley_bilingual_fixture_article(self):
        fixture_name = "golden_criteria/10.1111_gcb.16386/bilingual.html"
        landing_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16386"
        metadata = {
            "doi": "10.1111/gcb.16386",
            "title": "Brazilian Cerrado disturbance and recovery pathways",
            "journal_title": "Global Change Biology",
            "landing_page_url": landing_url,
        }
        html = read_fixture_text(fixture_name)
        markdown, info = extract_science_pnas_markdown(
            html,
            landing_url,
            "wiley",
            metadata=metadata,
        )
        raw_payload = RawFulltextPayload(
            provider="wiley",
            source_url=landing_url,
            content_type="text/html",
            body=html.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                markdown_text=markdown,
                merged_metadata=dict(metadata),
                diagnostics={"extraction": info},
            ),
            trace=trace_from_markers(["fulltext:wiley_html_ok"]),
            merged_metadata=metadata,
        )
        return wiley_provider.WileyClient(HttpTransport(), {}).to_article_model(metadata, raw_payload)

    def _build_springer_bilingual_fixture_article(self):
        return build_shared_html_fixture_article(
            fixture_name="golden_criteria/10.1007_s13158-025-00473-x/bilingual.html",
            landing_url="https://link.springer.com/article/10.1007/s13158-025-00473-x",
            metadata={
                "doi": "10.1007/s13158-025-00473-x",
                "title": "Multilingual summaries in restoration field studies",
                "journal_title": "Restoration Ecology",
            },
            noise_profile="springer_nature",
        )

    def _build_elsevier_bilingual_fixture_article(self):
        fixture_name = "golden_criteria/10.1016_S1575-1813(18)30261-4/bilingual.xml"
        landing_url = "https://www.sciencedirect.com/science/article/pii/S1575181318302614"
        metadata = {
            "doi": "10.1016/S1575-1813(18)30261-4",
            "title": "Community pharmacy counseling in multilingual care",
            "landing_page_url": landing_url,
        }
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url=landing_url,
            content_type="application/xml",
            body=read_fixture_bytes(fixture_name),
            trace=trace_from_markers(["fulltext:elsevier_xml_ok"]),
            merged_metadata=metadata,
        )
        return elsevier_provider.ElsevierClient(HttpTransport(), {}).to_article_model(metadata, raw_payload)

    def _build_shared_bilingual_fixture_article(
        self,
        *,
        fixture_name: str,
        landing_url: str,
    ):
        return build_shared_html_fixture_article(
            fixture_name=fixture_name,
            landing_url=landing_url,
        )

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
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_provider_benchmark_samples_are_post_2020(self) -> None:
        for sample in iter_provider_benchmark_samples():
            with self.subTest(provider=sample.provider):
                self.assertGreaterEqual(sample.year, 2020)

    def test_nature_shared_html_regression_samples(self) -> None:
        for sample in NATURE_HTML_SAMPLES:
            with self.subTest(doi=sample["doi"]):
                article = build_shared_html_fixture_article(
                    fixture_name=sample["fixture"],
                    landing_url=sample["url"],
                    metadata={
                        "doi": sample["doi"],
                        "title": sample["title"],
                        "journal_title": sample["journal"],
                        "authors": sample["authors"],
                    },
                    noise_profile="springer_nature",
                )
                headings = [section.heading for section in article.sections]
                markdown = article.to_ai_markdown(max_tokens=16000)

                self.assertEqual(article.source, "springer_html")
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
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertEqual(article.metadata.title, metadata["title"])
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(len(article.sections) >= 4)
        headings = [section.heading for section in article.sections]
        self.assertIn("Introduction", headings)
        self.assertIn("Discussion", headings)
        self.assertIn("Conclusions", headings)
        self.assertTrue(any("data" in heading.lower() for heading in headings))
        self.assertTrue(any("season" in heading.lower() or "climate" in heading.lower() for heading in headings))

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
            content=ProviderContent(
                route_kind="html",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=science_html.encode("utf-8"),
                markdown_text=markdown_text,
            ),
            trace=trace_from_markers(["fulltext:science_html_ok"]),
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
        markdown = article.to_ai_markdown(max_tokens=16000)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)

    def test_paper_fetch_uses_wiley_html_replay_fixture_for_positive_sample(self) -> None:
        wiley_html = read_fixture_text(WILEY_SAMPLE.fixture_name)
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": WILEY_SAMPLE.doi,
            "title": WILEY_SAMPLE.title,
            "journal_title": "Global Change Biology",
            "published": "2022-12-01",
            "landing_page_url": WILEY_SAMPLE.landing_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        markdown_text, extraction_info = extract_science_pnas_markdown(
            wiley_html,
            WILEY_SAMPLE.landing_url,
            "wiley",
            metadata={"doi": WILEY_SAMPLE.doi, "title": WILEY_SAMPLE.title},
        )
        raw_payload = RawFulltextPayload(
            provider="wiley",
            source_url=WILEY_SAMPLE.landing_url,
            content_type="text/html",
            body=wiley_html.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=WILEY_SAMPLE.landing_url,
                content_type="text/html",
                body=wiley_html.encode("utf-8"),
                markdown_text=markdown_text,
                merged_metadata=dict(metadata),
                diagnostics={"extraction": extraction_info},
            ),
            trace=trace_from_markers(["fulltext:wiley_html_ok"]),
            merged_metadata=metadata,
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
        self.assertTrue(article.metadata.abstract)
        self.assertIn("fulltext:wiley_html_ok", article.quality.source_trail)
        markdown = article.to_ai_markdown(max_tokens=16000)
        self.assertIn("## Abstract", markdown)
        self.assertIn("Global vegetation greening has been widely confirmed in previous studies", article.metadata.abstract)
        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertIn("### 2.1 Study area", markdown)
        self.assertIn("### 3.1 Spatiotemporal changes in the velocity of vegetation green-up", markdown)
        self.assertIn("## 4 DISCUSSION", markdown)
        self.assertNotIn("## Abbreviations", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)

    def test_paper_fetch_uses_wiley_pdf_fallback_replay_fixture_for_secondary_sample(self) -> None:
        markdown_text = read_fixture_text(WILEY_PDF_FALLBACK_SAMPLE.fixture_name)
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": WILEY_PDF_FALLBACK_SAMPLE.doi,
            "title": WILEY_PDF_FALLBACK_SAMPLE.title,
            "journal_title": "Cancer Science",
            "published": "2024-01-01",
            "landing_page_url": WILEY_PDF_FALLBACK_SAMPLE.landing_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="wiley",
            source_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{WILEY_PDF_FALLBACK_SAMPLE.doi}",
            content_type="application/pdf",
            body=b"%PDF-1.4\n",
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{WILEY_PDF_FALLBACK_SAMPLE.doi}",
                content_type="application/pdf",
                body=b"%PDF-1.4\n",
                markdown_text=markdown_text,
            ),
            trace=trace_from_markers(
                [
                    "fulltext:wiley_html_fail",
                    "fulltext:wiley_pdf_api_ok",
                    "fulltext:wiley_pdf_fallback_ok",
                ]
            ),
            needs_local_copy=True,
        )

        article = self._fetch_replayed_provider_article(
            sample=WILEY_PDF_FALLBACK_SAMPLE,
            metadata=metadata,
            provider_name="wiley",
            raw_payload=raw_payload,
            provider_client=wiley_provider.WileyClient(FixtureTransport({}), {}),
        )

        self.assertEqual(article.source, WILEY_PDF_FALLBACK_SAMPLE.expected_source)
        self.assertEqual(article.metadata.title, WILEY_PDF_FALLBACK_SAMPLE.title)
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)

    def test_paper_fetch_uses_pnas_replay_fixture_for_positive_sample(self) -> None:
        pnas_html = read_fixture_text(PNAS_SAMPLE.fixture_name)
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": PNAS_SAMPLE.doi,
            "title": PNAS_SAMPLE.title,
            "journal_title": "Proceedings of the National Academy of Sciences",
            "published": "2024-11-12",
            "landing_page_url": PNAS_SAMPLE.landing_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        markdown_text, extraction_info = extract_science_pnas_markdown(
            pnas_html,
            PNAS_SAMPLE.landing_url,
            "pnas",
            metadata={"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
        )
        raw_payload = RawFulltextPayload(
            provider="pnas",
            source_url=PNAS_SAMPLE.landing_url,
            content_type="text/html",
            body=pnas_html.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=pnas_html.encode("utf-8"),
                markdown_text=markdown_text,
                merged_metadata=dict(metadata),
                diagnostics={"extraction": extraction_info},
            ),
            trace=trace_from_markers(["fulltext:pnas_html_ok"]),
            merged_metadata=metadata,
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
        markdown = article.to_ai_markdown(max_tokens=16000)
        self.assertTrue(article.metadata.abstract)
        self.assertIn("## Significance", markdown)
        self.assertEqual(article.sections[0].kind, "abstract")
        self.assertEqual(article.sections[0].heading, "Significance")
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("### Data", markdown)
        self.assertNotIn("### Data.", markdown)
        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("**Figure 1.**", markdown)

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
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertEqual(article.doi, doi)
        self.assertTrue(any("HTTP 404" in warning for warning in article.quality.warnings))
        self.assertTrue(any("Full text was not available" in warning for warning in article.quality.warnings))

    def test_wiley_bilingual_fixture_preserves_parallel_abstract_sections(self) -> None:
        self._assert_bilingual_fixture_case("wiley")

    def test_springer_bilingual_fixture_preserves_parallel_abstract_sections(self) -> None:
        self._assert_bilingual_fixture_case("springer")

    def test_elsevier_bilingual_fixture_preserves_parallel_abstract_sections(self) -> None:
        self._assert_bilingual_fixture_case("elsevier")

    def test_sage_bilingual_fixture_preserves_parallel_abstract_sections(self) -> None:
        self._assert_bilingual_fixture_case("sage")

    def test_tandf_bilingual_fixture_preserves_parallel_abstract_sections(self) -> None:
        self._assert_bilingual_fixture_case("tandf")


if __name__ == "__main__":
    unittest.main()
