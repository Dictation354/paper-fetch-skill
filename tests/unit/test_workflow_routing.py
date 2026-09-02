from __future__ import annotations

from dataclasses import dataclass
import unittest

from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow import routing
from paper_fetch.workflow.batch_routing import (
    GENERIC_BATCH_LANE,
    deduplicate_batch_items,
    expected_doi_from_query,
    fanout_batch_items,
    resolve_batch_item_routing,
)
from paper_fetch.workflow.session_cache import LANDING_PDF_PROBE_KEY
from tests.unit._paper_fetch_support import RecordingTransport


@dataclass(frozen=True)
class _BatchItem:
    index: int
    query: str
    lane_key: str
    canonical_doi: str | None = None


class WorkflowRoutingTests(unittest.TestCase):
    def test_route_signal_markers_preserve_signal_order_and_deduplicate(self) -> None:
        markers = routing.route_signal_markers(
            landing_urls=[
                "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                "https://www.sciencedirect.com/science/article/pii/S0021863496900852",
            ],
            publishers=["Elsevier BV", "Springer Nature"],
            doi="10.1111/example",
        )

        self.assertEqual(
            markers,
            [
                "route:signal_domain_elsevier",
                "route:signal_publisher_elsevier",
                "route:signal_publisher_springer",
                "route:signal_doi_wiley",
            ],
        )

    def test_batch_identity_resolution_deduplication_and_fanout_are_shared(
        self,
    ) -> None:
        item = _BatchItem(1, "A paper title", GENERIC_BATCH_LANE)
        context = RuntimeContext(env={})

        routed = resolve_batch_item_routing(
            item,
            context=context,
            resolver=lambda _query, **_kwargs: {
                "provider_hint": "provider-a",
                "doi": "10.1000/Example",
            },
        )
        duplicate = _BatchItem(
            2,
            "https://doi.org/10.1000/example",
            "provider-a",
            expected_doi_from_query("https://doi.org/10.1000/example"),
        )
        without_doi = _BatchItem(3, "Another title", GENERIC_BATCH_LANE)

        representatives, duplicates = deduplicate_batch_items(
            [routed, duplicate, without_doi]
        )

        self.assertEqual(routed.lane_key, "provider-a")
        self.assertEqual(routed.canonical_doi, "10.1000/example")
        self.assertEqual([value.index for value in representatives], [1, 3])
        self.assertEqual(
            [value.index for value in fanout_batch_items(routed, duplicates)],
            [1, 2],
        )

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
