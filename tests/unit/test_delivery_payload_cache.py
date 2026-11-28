from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paper_fetch.delivery._scoped_fs import LOCK_DIRNAME, cache_lock_dir
from paper_fetch.delivery.fetch_cache import (
    PUBLIC_CREDENTIAL_SCOPE,
    FetchCache,
    article_from_payload,
    cache_request_fingerprint,
    envelope_from_payload,
    payload_from_envelope,
    request_cache_payload,
)
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.models import Asset
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import TraceContext, trace_event
from tests.golden_criteria import golden_criteria_scenario_asset
from tests.support.fetch_fixtures import sample_envelope, sample_resolved_query


class DeliveryPayloadCacheTests(unittest.TestCase):
    def test_strict_asset_strategy_is_normalized_and_changes_cache_fingerprint(
        self,
    ) -> None:
        default_request = FetchPaperRequest.model_validate(
            {
                "query": "10.1000/strict-cache",
                "strategy": {"asset_profile": "body"},
            }
        )
        strict_request = FetchPaperRequest.model_validate(
            {
                "query": "10.1000/strict-cache",
                "strategy": {
                    "asset_profile": "body",
                    "require_full_size_body_assets": True,
                },
            }
        )

        strict_payload = request_cache_payload(strict_request)
        self.assertTrue(strict_request.strategy.require_local_body_assets)
        self.assertTrue(strict_payload["strategy"]["require_local_body_assets"])
        self.assertTrue(strict_payload["strategy"]["require_full_size_body_assets"])
        self.assertNotEqual(
            cache_request_fingerprint(
                default_request.query,
                request_cache_payload(default_request),
            ),
            cache_request_fingerprint(
                strict_request.query,
                strict_payload,
            ),
        )

    def test_writer_has_one_top_level_trace_owner_and_preserves_retries(
        self,
    ) -> None:
        request = FetchPaperRequest(
            query="10.1000/trace-v8",
            modes=["article", "markdown"],
        )
        envelope = sample_envelope(
            modes={"article", "markdown"},
            doi=request.query,
        )
        envelope.trace = [
            trace_event(
                "fulltext",
                "springer_html",
                "fail",
                code="publisher_paywall",
                context=TraceContext(attempt=1, attempt_id="html-1"),
            ),
            trace_event(
                "fulltext",
                "springer_html",
                "fail",
                code="publisher_paywall",
                context=TraceContext(attempt=2, attempt_id="html-2"),
            ),
        ]

        payload = payload_from_envelope(envelope, request)
        round_trip = envelope_from_payload(payload)

        self.assertNotIn("schema_version", payload)
        self.assertEqual(len(payload["trace"]), 2)
        self.assertNotIn("trace", payload["quality"])
        self.assertNotIn("quality", payload["article"])
        self.assertEqual(
            [event.attempt_id for event in round_trip.trace],
            ["html-1", "html-2"],
        )

    def test_article_payload_preserves_asset_download_diagnostics(self) -> None:
        payload = json.loads(
            golden_criteria_scenario_asset(
                "asset_download_diagnostics", "article_payload.json"
            ).read_text(encoding="utf-8")
        )
        payload["assets"][0]["provenance"] = [
            "conversion_degraded",
            "conversion_degraded",
        ]
        payload["assets"][0]["preview_accepted"] = False
        payload["assets"][0]["browser_backend"] = "scrapling"
        payload["assets"][0]["final_fetcher"] = "scrapling"
        payload["assets"][0]["recovery_attempts"] = [
            {"stage": "direct", "status": 403},
            {
                "stage": "browser",
                "browser_backend": "scrapling",
                "reason": "recovered",
            },
        ]
        article = article_from_payload(payload)

        self.assertIsNotNone(article)
        assert article is not None
        asset = article.assets[0]
        self.assertEqual(asset.render_state, "appendix")
        self.assertEqual(asset.anchor_key, "F1")
        self.assertEqual(asset.download_tier, "preview")
        self.assertEqual(asset.download_url, "https://example.test/figure-preview.png")
        self.assertEqual(asset.width, 640)
        self.assertEqual(asset.height, 480)
        self.assertEqual(asset.browser_backend, "scrapling")
        self.assertEqual(asset.final_fetcher, "scrapling")
        self.assertEqual(asset.recovery_attempts[0]["status"], 403)
        self.assertEqual(asset.provenance, ["conversion_degraded"])

    def test_fetch_envelope_payload_preserves_quality_asset_failures(self) -> None:
        request = FetchPaperRequest(query="10.1000/example", modes=["article"])
        envelope = sample_envelope(modes={"article"}, doi="10.1000/example")
        assert envelope.article is not None
        envelope.article.quality.asset_failures = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "source_url": "https://example.test/figure-1.png",
                "status": 403,
                "content_type": "text/html; charset=UTF-8",
                "title_snippet": "Just a moment...",
                "body_snippet": "Just a moment... Please enable JavaScript and Cookies.",
                "reason": "aws_waf_challenge",
                "challenge_provider": "aws_waf",
                "recovery_attempts": [
                    {
                        "status": "failed",
                        "url": "https://example.test/figure-page",
                        "reason": "aws_waf_challenge",
                    }
                ],
            }
        ]
        envelope.quality = envelope.article.quality
        envelope.article.assets = [
            Asset(
                kind="figure",
                heading="Figure 1",
                download_tier="full_size",
                browser_backend="scrapling",
                final_fetcher="scrapling",
                recovery_attempts=[
                    {"stage": "direct", "status": 403},
                    {"stage": "browser", "reason": "recovered"},
                ],
            )
        ]

        payload = payload_from_envelope(envelope, request)
        round_trip = envelope_from_payload(payload)

        self.assertEqual(payload["quality"]["asset_failures"][0]["status"], 403)
        self.assertEqual(
            payload["quality"]["asset_failures"][0]["reason"], "aws_waf_challenge"
        )
        self.assertIsNotNone(round_trip)
        assert round_trip is not None
        assert round_trip.article is not None
        self.assertEqual(
            round_trip.quality.asset_failures[0]["title_snippet"], "Just a moment..."
        )
        self.assertEqual(
            round_trip.quality.asset_failures[0]["recovery_attempts"][0]["status"],
            "failed",
        )
        self.assertEqual(
            round_trip.quality.asset_failures[0]["challenge_provider"], "aws_waf"
        )
        self.assertEqual(
            payload["article"]["assets"][0]["browser_backend"], "scrapling"
        )
        self.assertEqual(round_trip.article.assets[0].final_fetcher, "scrapling")
        self.assertEqual(
            round_trip.article.assets[0].recovery_attempts[0]["status"], 403
        )

    def test_fetch_cache_write_creates_only_lock_and_fingerprinted_sidecar(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            request = FetchPaperRequest(query="10.1000/example", modes=["markdown"])
            envelope = sample_envelope(modes={"markdown"}, doi="10.1000/example")

            FetchCache(download_dir).write_fetch_envelope(envelope, request)
            files = sorted(item.name for item in download_dir.iterdir())
            lock_dir_exists = cache_lock_dir(download_dir).is_dir()

        self.assertTrue(lock_dir_exists)
        self.assertEqual(len(files), 2)
        self.assertIn(LOCK_DIRNAME, files)
        self.assertNotIn(".paper-fetch-cache.json", files)
        self.assertNotIn("10.1000_example.fetch-envelope.json", files)

    def test_fetch_cache_keeps_request_variants_and_credential_scopes_separate(
        self,
    ) -> None:
        doi = "10.1000/example"
        credential_scope = "credential:" + ("a" * 64)
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            public_cache = FetchCache(
                download_dir,
                credential_scope=PUBLIC_CREDENTIAL_SCOPE,
            )
            credential_cache = FetchCache(
                download_dir,
                credential_scope=credential_scope,
            )
            markdown_request = FetchPaperRequest(
                query=doi,
                modes=["markdown"],
                prefer_cache=True,
            )
            metadata_request = FetchPaperRequest(
                query=doi,
                modes=["metadata"],
                prefer_cache=True,
            )
            public_markdown = sample_envelope(modes={"markdown"}, doi=doi)
            public_markdown.markdown = "# Public markdown\n"
            public_metadata = sample_envelope(modes={"metadata"}, doi=doi)
            assert public_metadata.metadata is not None
            public_metadata.metadata.title = "Public metadata"
            private_markdown = sample_envelope(modes={"markdown"}, doi=doi)
            private_markdown.markdown = "# Credential markdown\n"

            public_cache.write_fetch_envelope(public_markdown, markdown_request)
            public_cache.write_fetch_envelope(public_metadata, metadata_request)
            credential_cache.write_fetch_envelope(
                private_markdown,
                markdown_request,
            )

            variant_paths = list(
                download_dir.glob("10.1000_example.*.fetch-envelope.json")
            )
            with RuntimeContext(env={}, download_dir=download_dir) as context:
                public_markdown_hit = public_cache.load_fetch_envelope(
                    markdown_request,
                    resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                        doi
                    ),
                    context=context,
                )
                public_metadata_hit = public_cache.load_fetch_envelope(
                    metadata_request,
                    resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                        doi
                    ),
                    context=context,
                )
                credential_hit = credential_cache.load_fetch_envelope(
                    markdown_request,
                    resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                        doi
                    ),
                    context=context,
                )

        self.assertEqual(len(variant_paths), 3)
        assert public_markdown_hit is not None
        assert (
            public_metadata_hit is not None and public_metadata_hit.metadata is not None
        )
        assert credential_hit is not None
        self.assertEqual(public_markdown_hit.markdown, "# Public markdown\n")
        self.assertEqual(public_metadata_hit.metadata.title, "Public metadata")
        self.assertEqual(credential_hit.markdown, "# Credential markdown\n")
