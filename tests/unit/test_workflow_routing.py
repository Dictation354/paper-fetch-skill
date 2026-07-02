from __future__ import annotations

import unittest

from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow import routing
from paper_fetch.workflow.session_cache import LANDING_PDF_PROBE_KEY
from tests.unit._paper_fetch_support import RecordingTransport


class WorkflowRoutingTests(unittest.TestCase):
    def test_cached_landing_pdf_probe_uses_typed_session_cache_key(self) -> None:
        context = RuntimeContext(env={})
        probe = routing.LandingPageCitationPdfProbeResult(
            has_citation_pdf_url=True,
            title="Cached Landing",
            citation_pdf_urls=["https://example.test/article.pdf"],
        )
        context.set_session_cache(
            LANDING_PDF_PROBE_KEY.materialize("https://example.test/article"), probe
        )

        self.assertEqual(
            routing.get_cached_landing_page_citation_pdf_probe(
                "https://example.test/article", context=context
            ),
            probe,
        )

    def test_landing_pdf_probe_uses_browser_user_agent_for_publisher_page(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/article"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head><title>Article</title>"
                        b'<meta name="citation_pdf_url" content="/article.pdf">'
                        b"</head></html>"
                    ),
                    "url": "https://example.test/article",
                }
            }
        )

        probe = routing._landing_page_citation_pdf_probe(
            "https://example.test/article",
            transport=transport,
            env={"PAPER_FETCH_SKILL_USER_AGENT": "paper-fetch-skill/999"},
        )

        self.assertTrue(probe.has_citation_pdf_url)
        self.assertEqual(probe.citation_pdf_urls, ["https://example.test/article.pdf"])
        self.assertIn("Chrome/", transport.calls[0]["headers"]["User-Agent"])
        self.assertNotIn("paper-fetch", transport.calls[0]["headers"]["User-Agent"])
        self.assertEqual(
            transport.calls[0]["headers"]["Accept-Language"], "en-US,en;q=0.9"
        )


if __name__ == "__main__":
    unittest.main()
