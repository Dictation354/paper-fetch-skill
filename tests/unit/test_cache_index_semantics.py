from __future__ import annotations

import hashlib
import json
import platform
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from paper_fetch.mcp.cache_index import (
    IDENTITY_PROOF_MARKDOWN_REGISTRATION,
    cache_index_path,
    read_scoped_file,
    register_markdown_entry,
)
from paper_fetch.mcp.cache_payloads import get_cached_payload, list_cached_payload
from paper_fetch.models import AcquisitionProvenance
from paper_fetch.utils import sanitize_filename
from tests.unit._mcp_support import create_cached_downloads

TEST_ACQUISITION = AcquisitionProvenance(
    provider="crossref",
    route="metadata",
    representation="metadata",
    transport="api",
)


def _write_markdown(
    path: Path,
    *,
    doi: str,
    source: str = "unit_test",
    has_fulltext: bool = True,
    content_kind: str = "fulltext",
    completed_at: str | None = None,
) -> None:
    metadata: dict[str, object] = {
        "doi": doi,
        "source": source,
        "has_fulltext": has_fulltext,
        "content_kind": content_kind,
        "acquisition": {
            "provider": TEST_ACQUISITION.provider,
            "route": TEST_ACQUISITION.route,
            "representation": TEST_ACQUISITION.representation,
            "transport": TEST_ACQUISITION.transport,
            "fallback_used": TEST_ACQUISITION.fallback_used,
        },
    }
    if completed_at is not None:
        metadata["completed_at"] = completed_at
    path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n\n# Local paper\n",
        encoding="utf-8",
    )


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

            listed = list_cached_payload(download_dir=download_dir)
            cached = get_cached_payload(doi=doi, download_dir=download_dir)
            index_after = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(listed["entries"], [])
        self.assertEqual(listed["index_status"], "version_mismatch")
        self.assertEqual(cached["status"], "miss")
        self.assertEqual(cached["index_status"], "version_mismatch")
        self.assertEqual(cached["entries"], [])
        self.assertEqual(index_after["version"], 0)

    def test_preferred_markdown_prioritizes_fulltext_then_completion_time(self) -> None:
        doi = "10.1000/versions"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            metadata_only = download_dir / "metadata-newest.md"
            fulltext_old = download_dir / "fulltext-old.md"
            fulltext_new = download_dir / "fulltext-new.md"
            _write_markdown(
                metadata_only,
                doi=doi,
                has_fulltext=False,
                content_kind="metadata_only",
                completed_at="2026-01-01T00:00:00Z",
            )
            _write_markdown(
                fulltext_old,
                doi=doi,
                completed_at="2024-01-01T00:00:00Z",
            )
            _write_markdown(
                fulltext_new,
                doi=doi,
                completed_at="2025-01-01T00:00:00Z",
            )
            for path, has_fulltext, content_kind, completed_at in (
                (metadata_only, False, "metadata_only", "2026-01-01T00:00:00Z"),
                (fulltext_old, True, "fulltext", "2024-01-01T00:00:00Z"),
                (fulltext_new, True, "fulltext", "2025-01-01T00:00:00Z"),
            ):
                register_markdown_entry(
                    download_dir,
                    doi,
                    path,
                    source="unit_test",
                    acquisition=TEST_ACQUISITION,
                    has_fulltext=has_fulltext,
                    content_kind=content_kind,
                    completed_at=completed_at,
                )

            payload = get_cached_payload(doi=doi, download_dir=download_dir)

        self.assertEqual(len(payload["entries"]), 3)
        self.assertEqual(
            Path(payload["preferred"]["markdown"]["path"]).name,
            fulltext_new.name,
        )
        self.assertTrue(payload["preferred"]["markdown"]["has_fulltext"])
        self.assertEqual(payload["preferred"]["markdown"]["content_kind"], "fulltext")

    def test_explicit_registration_tracks_saved_path_and_invalidates_on_change(
        self,
    ) -> None:
        doi_a = "10.1000/registered"
        doi_b = "10.1000/replacement"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            markdown = download_dir / "Author_2026_Title.md"
            markdown.write_text("# Saved full text\n", encoding="utf-8")

            registered = register_markdown_entry(
                download_dir,
                f"https://doi.org/{doi_a.upper()}",
                markdown,
                source="unit_test",
                acquisition=TEST_ACQUISITION,
                has_fulltext=True,
                content_kind="fulltext",
            )
            payload_a = get_cached_payload(doi=doi_a, download_dir=download_dir)
            _write_markdown(markdown, doi=doi_b)
            changed_payload_a = get_cached_payload(doi=doi_a, download_dir=download_dir)
            payload_b = get_cached_payload(doi=doi_b, download_dir=download_dir)

        self.assertIsNotNone(registered)
        assert registered is not None
        self.assertEqual(
            registered["identity_proof"], IDENTITY_PROOF_MARKDOWN_REGISTRATION
        )
        self.assertEqual(
            payload_a["preferred"]["markdown"]["path"], str(markdown.resolve())
        )
        self.assertEqual(changed_payload_a["status"], "miss")
        # Editing an explicitly registered file invalidates both its DOI and its
        # old scope provenance. The replacement needs explicit registration.
        self.assertEqual(payload_b["status"], "miss")

    def test_cache_scope_accepts_equivalent_filesystem_alias_for_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            if platform.system() == "Darwin":
                canonical_root = root.resolve()
                root_alias = None
                for canonical_prefix, alias_prefix in (
                    (Path("/private/var"), Path("/var")),
                    (Path("/private/tmp"), Path("/tmp")),
                ):
                    try:
                        relative_root = canonical_root.relative_to(canonical_prefix)
                    except ValueError:
                        continue
                    candidate = alias_prefix / relative_root
                    if (
                        candidate != canonical_root
                        and candidate.resolve() == canonical_root
                    ):
                        root_alias = candidate
                        break
                if root_alias is None:
                    self.skipTest(
                        "native macOS temporary directory exposes neither the "
                        "/var nor /tmp system alias"
                    )
                root = root_alias
                self.assertNotEqual(root, canonical_root)
                self.assertEqual(root.resolve(), canonical_root)
            real_root = root / "real"
            download_dir = real_root / "papers"
            download_dir.mkdir(parents=True)
            alias_root = root / "alias"
            try:
                alias_root.symlink_to(real_root, target_is_directory=True)
            except OSError:
                self.skipTest("filesystem does not support directory symlinks")
            aliased_download_dir = alias_root / "papers"
            markdown = aliased_download_dir / "paper.md"
            markdown.write_text("# Saved full text\n", encoding="utf-8")
            expected_markdown = markdown.resolve()

            registered = register_markdown_entry(
                aliased_download_dir,
                "10.1000/alias",
                markdown,
                source="unit_test",
                acquisition=TEST_ACQUISITION,
                has_fulltext=True,
                content_kind="fulltext",
            )
            payload = get_cached_payload(
                doi="10.1000/alias",
                download_dir=aliased_download_dir,
            )

        self.assertIsNotNone(registered)
        self.assertEqual(payload["status"], "hit")
        self.assertEqual(
            payload["preferred"]["markdown"]["path"],
            str(expected_markdown),
        )

    def test_wrong_doi_fetch_envelope_sidecar_is_not_attributed_by_filename(
        self,
    ) -> None:
        doi_a = "10.1000/a"
        doi_b = "10.1000/b"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            sidecar = download_dir / f"{sanitize_filename(doi_a)}.fetch-envelope.json"
            sidecar.write_text(
                json.dumps({"payload": {"doi": doi_b}}), encoding="utf-8"
            )

            payload = get_cached_payload(doi=doi_a, download_dir=download_dir)

        self.assertEqual(payload["status"], "miss")
        self.assertEqual(payload["entries"], [])

    def test_explicit_registration_rejects_paths_outside_download_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            download_dir = root / "papers"
            download_dir.mkdir()
            outside_markdown = root / "outside.md"
            _write_markdown(outside_markdown, doi="10.1000/outside")

            registered = register_markdown_entry(
                download_dir,
                "10.1000/outside",
                outside_markdown,
                source="unit_test",
                acquisition=TEST_ACQUISITION,
                has_fulltext=True,
                content_kind="fulltext",
            )
            payload = get_cached_payload(
                doi="10.1000/outside", download_dir=download_dir
            )

        self.assertIsNone(registered)
        self.assertEqual(payload["status"], "miss")
        self.assertEqual(payload["entries"], [])

    def test_scoped_file_read_rejects_escape_symlink_and_integrity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            download_dir = root / "cache"
            download_dir.mkdir()
            cached = download_dir / "paper.md"
            payload = b"verified cache payload"
            cached.write_bytes(payload)

            self.assertEqual(
                read_scoped_file(
                    download_dir,
                    str(cached),
                    expected_size=len(payload),
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                ),
                (cached.resolve(), payload),
            )
            self.assertIsNone(
                read_scoped_file(
                    download_dir, str(cached), expected_size=len(payload) + 1
                )
            )
            self.assertIsNone(
                read_scoped_file(download_dir, str(cached), expected_sha256="0" * 64)
            )

            outside = root / "outside.md"
            outside.write_bytes(payload)
            self.assertIsNone(read_scoped_file(download_dir, str(outside)))
            linked = download_dir / "linked.md"
            try:
                linked.symlink_to(outside)
            except OSError:
                self.skipTest("filesystem does not support symlinks")
            self.assertIsNone(read_scoped_file(download_dir, str(linked)))

    def test_cache_miss_does_not_open_network_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            with mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("cache lookup must stay offline"),
            ) as create_connection:
                payload = get_cached_payload(
                    doi="10.1000/missing", download_dir=download_dir
                )

        self.assertEqual(payload["status"], "miss")
        create_connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
