from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from paper_fetch.delivery.cache_inspection import (
    get_cached_payload,
    list_cached_payload,
)
from tests.support.fetch_fixtures import create_cached_downloads


class McpBatchResolvePayloadTests(unittest.TestCase):
    def test_list_cached_payload_reads_current_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_downloads(download_dir, "10.1000/example")

            listed = list_cached_payload(download_dir=download_dir)

        self.assertEqual(len(listed["entries"]), 3)

    def test_get_cached_payload_returns_explicitly_registered_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_downloads(download_dir, "10.1000/example")

            payload = get_cached_payload(
                doi="10.1000/example",
                download_dir=download_dir,
            )
            listed = list_cached_payload(download_dir=download_dir)

        self.assertEqual(payload["status"], "hit")
        self.assertEqual(len(payload["entries"]), 3)
        self.assertIsNotNone(payload["preferred"]["markdown"])
        self.assertIsNotNone(payload["preferred"]["primary_payload"])
        self.assertEqual(len(payload["preferred"]["assets"]), 1)
        self.assertEqual(len(listed["entries"]), 3)
