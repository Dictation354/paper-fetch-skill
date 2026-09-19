from __future__ import annotations
import urllib.parse
from paper_fetch.http import RequestFailure
from paper_fetch.providers import (
    browser_runtime,
    elsevier as elsevier_provider,
)
from paper_fetch.providers.base import (
    ProviderContent,
    RawFulltextPayload,
)
from tests.paths import FIXTURE_DIR
from tests.support._paper_fetch_support import RecordingTransport
import unittest
from pathlib import Path
from unittest import mock
from tests.provider_benchmark_samples import (
    WILEY_PDF_FALLBACK_SAMPLE,
    provider_benchmark_sample,
)


def _payload_route(raw_payload: RawFulltextPayload) -> str | None:
    return raw_payload.content.route_kind if raw_payload.content is not None else None


def _payload_availability_diagnostics(
    raw_payload: RawFulltextPayload,
) -> dict[str, object]:
    assert raw_payload.content is not None
    return dict(raw_payload.content.diagnostics.get("availability_diagnostics") or {})


def _payload_source_trail(raw_payload: RawFulltextPayload) -> list[str]:
    return [event.marker() for event in raw_payload.trace if event.marker()]


ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
WILEY_PDF_SAMPLE = WILEY_PDF_FALLBACK_SAMPLE


class PublisherWaterfallTests(unittest.TestCase):
    def _runtime_config(
        self, tmpdir: str, provider: str, doi: str
    ) -> browser_runtime.BrowserRuntimeConfig:
        tmp = Path(tmpdir)
        return browser_runtime.BrowserRuntimeConfig(
            provider=provider,
            doi=doi,
            artifact_dir=tmp / "artifacts",
            headless=True,
            user_agent="paper-fetch-test/1",
        )

    def test_elsevier_official_xml_success_keeps_elsevier_xml_source(self) -> None:
        doi = ELSEVIER_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": ELSEVIER_SAMPLE.title,
            "landing_page_url": ELSEVIER_SAMPLE.landing_url,
        }
        xml_body = (FIXTURE_DIR / ELSEVIER_SAMPLE.fixture_name).read_bytes()
        official_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2025.114648",
            content_type="text/xml",
            body=xml_body,
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2025.114648",
                content_type="text/xml",
                body=xml_body,
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(
            transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"}
        )

        with (
            mock.patch.object(
                client, "_fetch_official_xml_payload", return_value=official_payload
            ),
            mock.patch.object(client, "_official_payload_is_usable", return_value=True),
            mock.patch.object(client, "_fetch_official_pdf_payload") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.provider, "elsevier")
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)

    def test_elsevier_official_xml_usable_records_structured_diagnostics(self) -> None:
        doi = ELSEVIER_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": ELSEVIER_SAMPLE.title,
            "landing_page_url": ELSEVIER_SAMPLE.landing_url,
        }
        xml_body = (FIXTURE_DIR / ELSEVIER_SAMPLE.fixture_name).read_bytes()
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=xml_body,
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/example",
                content_type="text/xml",
                body=xml_body,
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(
            transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"}
        )

        usable = client._official_payload_is_usable(metadata, raw_payload)

        self.assertTrue(usable)
        diagnostics = _payload_availability_diagnostics(raw_payload)
        self.assertEqual(diagnostics["content_kind"], "fulltext")
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["reason"], "structured_body_sections")

    def test_elsevier_transient_doi_xml_failure_uses_pii_xml_fallback(self) -> None:
        doi = ELSEVIER_SAMPLE.doi
        pii = elsevier_provider.extract_elsevier_pii_from_url(
            ELSEVIER_SAMPLE.landing_url
        )
        assert pii
        metadata = {
            "doi": doi,
            "title": ELSEVIER_SAMPLE.title,
            "landing_page_url": ELSEVIER_SAMPLE.landing_url,
            "fulltext_links": [],
        }
        xml_body = (FIXTURE_DIR / ELSEVIER_SAMPLE.fixture_name).read_bytes()
        doi_url = "https://api.elsevier.com/content/article/doi/" + urllib.parse.quote(
            doi, safe=""
        )
        pii_url = f"https://api.elsevier.com/content/article/pii/{pii}"
        transport = RecordingTransport(
            {
                ("GET", doi_url): RequestFailure(
                    503, f"HTTP 503 for {doi_url}?view=FULL"
                ),
                ("GET", pii_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/xml"},
                    "body": xml_body,
                    "url": f"{pii_url}?view=FULL",
                },
            }
        )
        client = elsevier_provider.ElsevierClient(
            transport=transport, env={"ELSEVIER_API_KEY": "secret"}
        )

        with (
            mock.patch.object(client, "_official_payload_is_usable", return_value=True),
            mock.patch.object(client, "_fetch_official_pdf_payload") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)

        mocked_pdf.assert_not_called()
        self.assertEqual(_payload_route(raw_payload), "official")
        self.assertEqual(raw_payload.source_url, f"{pii_url}?view=FULL")
        self.assertIn("fulltext:elsevier_xml_fail", _payload_source_trail(raw_payload))
        self.assertIn(
            "fulltext:elsevier_xml_pii_ok", _payload_source_trail(raw_payload)
        )
        self.assertNotIn(
            "fulltext:elsevier_pdf_api_ok", _payload_source_trail(raw_payload)
        )
        self.assertEqual(
            [str(call["url"]) for call in transport.calls], [doi_url, pii_url]
        )


if __name__ == "__main__":
    unittest.main()
