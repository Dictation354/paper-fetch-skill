from __future__ import annotations
from paper_fetch.models import Quality
import tempfile
import unittest
from pathlib import Path
from paper_fetch.delivery.fetch_cache import FetchCache
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.models import Asset, FetchEnvelope
from paper_fetch.runtime import RuntimeContext
from tests.support.fetch_fixtures import (
    sample_article,
    sample_resolved_query,
    write_binary,
)


class McpLoggingInlineImageTests(unittest.TestCase):
    def test_cached_envelope_with_out_of_scope_asset_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            scope = base / "scope"
            scope.mkdir()
            outside = base / "outside.png"
            write_binary(outside, size=32)
            article = sample_article()
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Outside",
                    path=str(outside),
                    section="body",
                    downloaded_bytes=32,
                )
            ]
            envelope = FetchEnvelope(
                doi=article.doi,
                source=article.source,
                article=article,
                markdown="# Example",
                quality=Quality(has_fulltext=True),
            )
            request = FetchPaperRequest(
                query="10.1000/example",
                modes=["article"],
                prefer_cache=True,
            )
            cache = FetchCache(scope)
            cache.write_fetch_envelope(envelope, request)

            restored = cache.load_fetch_envelope(
                request,
                resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                    "10.1000/example"
                ),
                context=RuntimeContext(env={}, download_dir=scope),
            )

        self.assertIsNone(restored)
