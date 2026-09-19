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
from paper_fetch.http import HttpTransport
from paper_fetch.models import article_from_markdown
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.providers import tandf as tandf_provider
from paper_fetch.providers import wiley as wiley_provider
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
)
from paper_fetch.providers.base import (
    ProviderContent,
    RawFulltextPayload,
)
from paper_fetch.tracing import trace_from_markers
from tests.provider_benchmark_samples import (
    iter_provider_benchmark_samples,
    provider_benchmark_sample,
)
from tests.paths import FIXTURE_DIR


class ProviderStub:
    def __init__(
        self, metadata=None, raw_payload=None, raw_error=None, article_factory=None
    ):
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

    def to_article_model(
        self,
        metadata,
        raw_payload,
        *,
        downloaded_assets=None,
        asset_failures=None,
        context=None,
    ):
        del context
        if self._article_factory is None:
            raise AssertionError(
                "article_factory must be provided for raw full-text tests."
            )
        return self._article_factory(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )


def fetch_article(query: str, **kwargs):
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
        abstracts = [
            section for section in article.sections if section.kind == "abstract"
        ]
        self.assertEqual([section.heading for section in abstracts], abstract_headings)
        self.assertTrue(all(section.kind == "abstract" for section in abstracts))
        self.assertEqual(article.metadata.abstract, abstracts[0].text)
        self.assertTrue(article.quality.has_fulltext)
        first_body_section = next(
            section for section in article.sections if section.kind != "abstract"
        )
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
            "tandf": {
                "builder": self._build_tandf_bilingual_fixture_article,
                "abstract_headings": [
                    "Abstract",
                    "Resumen",
                    "الملخص",
                    "Resumo",
                    "摘要",
                ],
                "first_body_heading": "Introduction",
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
        markdown, info = extract_atypon_browser_workflow_markdown(
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
        return wiley_provider.WileyClient(HttpTransport(), {}).to_article_model(
            metadata, raw_payload
        )

    def _build_tandf_bilingual_fixture_article(self):
        fixture_name = "golden_criteria/10.1080_19455224.2025.2547671/original.html"
        doi = "10.1080/19455224.2025.2547671"
        landing_url = f"https://www.tandfonline.com/doi/full/{doi}"
        metadata = {
            "doi": doi,
            "title": "The affective turn and the management of conservation",
            "landing_page_url": landing_url,
        }
        html = read_fixture_text(fixture_name)
        client = tandf_provider.TandfClient(HttpTransport(), {})
        markdown, info = client.extract_markdown(
            html,
            landing_url,
            metadata=metadata,
        )
        raw_payload = RawFulltextPayload(
            provider="tandf",
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
            trace=trace_from_markers(["fulltext:tandf_html_ok"]),
            merged_metadata=metadata,
        )
        return client.to_article_model(metadata, raw_payload)

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
        landing_url = (
            "https://www.sciencedirect.com/science/article/pii/S1575181318302614"
        )
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
        return elsevier_provider.ElsevierClient(HttpTransport(), {}).to_article_model(
            metadata, raw_payload
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
            paper_fetch.resolve_paper = lambda *args, **kwargs: (
                paper_fetch.ResolvedQuery(
                    query=sample.doi,
                    query_kind="doi",
                    doi=sample.doi,
                    landing_url=sample.landing_url,
                    provider_hint=provider_name,
                    confidence=1.0,
                )
            )
            return fetch_article(
                sample.doi,
                strategy=paper_fetch.FetchStrategy(),
                context=paper_fetch.RuntimeContext(
                    clients={
                        provider_name: replay_provider,
                        "crossref": ProviderStub(metadata=metadata),
                    }
                ),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_provider_benchmark_samples_are_post_2020(self) -> None:
        for sample in iter_provider_benchmark_samples():
            with self.subTest(provider=sample.provider):
                self.assertGreaterEqual(sample.year, 2020)


if __name__ == "__main__":
    unittest.main()


def test_capture_url_matching_preserves_non_signature_identity():
    from tests.support.acquired_publisher_inputs import capture_url_identity

    base = "https://cdn.example/image?id=one&size=large&empty=&Signature=old"
    renewed = base.replace("Signature=old", "Signature=new")
    assert capture_url_identity(base) != capture_url_identity(renewed)
    assert capture_url_identity(base, provider="plos") != capture_url_identity(
        renewed, provider="plos"
    )
    for provider, cdn in (
        ("acs", "acs"),
        ("aip", "aipp"),
        ("oxfordacademic", "oup"),
        ("royalsocietypublishing", "trs"),
    ):
        assert capture_url_identity(base, provider=provider) == base
        signed = base.replace("cdn.example", cdn + ".silverchair-cdn.com")
        renewed = signed.replace("Signature=old", "Signature=new")
        expected = capture_url_identity(signed, provider=provider)
        assert expected == capture_url_identity(renewed, provider=provider)
        for changed in (
            signed.replace("id=one", "id=two"),
            signed.replace("large", "small"),
            signed.replace("&empty=", ""),
        ):
            assert expected != capture_url_identity(changed, provider=provider)
