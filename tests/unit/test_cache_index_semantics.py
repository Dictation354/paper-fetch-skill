from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paper_fetch.mcp.cache_index import INDEX_VERSION, cache_index_path
from paper_fetch.utils import sanitize_filename
from tests.unit._mcp_support import create_cached_downloads, mcp_tools


class CacheIndexSemanticsTests(unittest.TestCase):
    def test_old_index_version_is_not_silently_read_or_overwritten(self) -> None:
        doi = "10.1000/example"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_downloads(download_dir, doi)
            index_path = cache_index_path(download_dir)
            index_path.write_text(
                json.dumps({"version": 0, "entries": []}),
                encoding="utf-8",
            )

            listed = mcp_tools.list_cached_payload(download_dir=download_dir)
            cached = mcp_tools.get_cached_payload(doi=doi, download_dir=download_dir)
            index_after = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(listed["entries"], [])
        self.assertEqual(listed["index_status"], "version_mismatch")
        self.assertEqual(cached["status"], "hit")
        self.assertEqual(cached["index_status"], "version_mismatch")
        self.assertEqual(len(cached["entries"]), 3)
        self.assertEqual(index_after["version"], 0)

    def test_list_cached_rescan_rebuilds_index_from_fetch_envelope_sidecars(
        self,
    ) -> None:
        doi = "10.1000/sidecar"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            download_dir.mkdir(parents=True, exist_ok=True)
            sidecar_path = (
                download_dir / f"{sanitize_filename(doi)}.fetch-envelope.json"
            )
            sidecar_path.write_text(
                json.dumps({"payload": {"doi": doi}}),
                encoding="utf-8",
            )
            index_path = cache_index_path(download_dir)
            index_path.write_text(
                json.dumps({"version": 0, "entries": []}),
                encoding="utf-8",
            )

            listed = mcp_tools.list_cached_payload(
                download_dir=download_dir,
                cache_mode="rescan",
            )
            index_after = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(listed["index_status"], "ok")
        self.assertEqual(listed["cache_mode"], "rescan")
        self.assertEqual(index_after["version"], INDEX_VERSION)
        self.assertEqual(
            [entry["kind"] for entry in listed["entries"]], ["fetch_envelope"]
        )
        self.assertEqual(listed["entries"][0]["doi"], doi)


if __name__ == "__main__":
    unittest.main()
