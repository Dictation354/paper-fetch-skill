from __future__ import annotations

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
    INDEX_VERSION,
    cache_index_path,
    register_markdown_entry,
)
from paper_fetch.publisher_identity import normalize_doi
from paper_fetch.utils import sanitize_filename
from tests.unit._mcp_support import create_cached_downloads, mcp_tools


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

            listed = mcp_tools.list_cached_payload(download_dir=download_dir)
            cached = mcp_tools.get_cached_payload(doi=doi, download_dir=download_dir)
            index_after = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(listed["entries"], [])
        self.assertEqual(listed["index_status"], "version_mismatch")
        self.assertEqual(cached["status"], "hit")
        self.assertEqual(cached["index_status"], "version_mismatch")
        # Only the self-identifying Markdown remains public. DOI-local binary
        # artifacts without a trusted scope or sidecar proof fail closed.
        self.assertEqual(len(cached["entries"]), 1)
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

    def test_refresh_only_attributes_structured_markdown_to_matching_doi(self) -> None:
        doi_a = "10.1000/ABC+Def(1)"
        doi_b = "10.1000/other:paper"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            markdown_a = download_dir / "Smith_2025_First_Paper.md"
            markdown_b = download_dir / "Jones_2024_Second_Paper.md"
            unrelated = download_dir / "notes.md"
            bad_yaml = download_dir / "broken.md"
            _write_markdown(markdown_a, doi=doi_a)
            _write_markdown(markdown_b, doi=doi_b)
            unrelated.write_text("# Reading notes\n", encoding="utf-8")
            bad_yaml.write_text(
                "---\ndoi: [not: valid\n---\n# Broken\n", encoding="utf-8"
            )

            payload_a = mcp_tools.get_cached_payload(
                doi="HTTPS://DOI.ORG/10.1000/ABC+DEF(1)",
                download_dir=download_dir,
            )
            payload_b = mcp_tools.get_cached_payload(
                doi=doi_b.upper(), download_dir=download_dir
            )

        self.assertEqual(payload_a["doi"], normalize_doi(doi_a))
        self.assertEqual(
            [Path(entry["path"]).name for entry in payload_a["entries"]],
            [markdown_a.name],
        )
        self.assertEqual(
            [entry["doi"] for entry in payload_a["entries"]],
            [normalize_doi(doi_a)],
        )
        self.assertEqual(
            [Path(entry["path"]).name for entry in payload_b["entries"]],
            [markdown_b.name],
        )
        self.assertNotIn(markdown_b.name, str(payload_a))
        self.assertNotIn(unrelated.name, str(payload_a))
        self.assertNotIn(bad_yaml.name, str(payload_a))

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

            payload = mcp_tools.get_cached_payload(doi=doi, download_dir=download_dir)

        self.assertEqual(len(payload["entries"]), 3)
        self.assertEqual(
            Path(payload["preferred"]["markdown"]["path"]).name,
            fulltext_new.name,
        )
        self.assertTrue(payload["preferred"]["markdown"]["has_fulltext"])
        self.assertEqual(payload["preferred"]["markdown"]["content_kind"], "fulltext")

    def test_version_one_index_migration_discards_unproven_markdown_ownership(
        self,
    ) -> None:
        doi_a = "10.1000/a"
        doi_b = "10.1000/b"
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            markdown_a = download_dir / "author-a.md"
            markdown_b = download_dir / "author-b.md"
            unproven = download_dir / "notes.md"
            _write_markdown(markdown_a, doi=doi_a)
            _write_markdown(markdown_b, doi=doi_b)
            unproven.write_text("# Notes\n", encoding="utf-8")
            index_path = cache_index_path(download_dir)
            index_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {"doi": doi_a, "kind": "markdown", "path": str(markdown_a)},
                            {"doi": doi_a, "kind": "markdown", "path": str(markdown_b)},
                            {"doi": doi_a, "kind": "markdown", "path": str(unproven)},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = mcp_tools.get_cached_payload(doi=doi_a, download_dir=download_dir)
            migrated = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["index_status"], "repaired")
        self.assertIn("migrated", payload["index_reason"])
        self.assertEqual(migrated["version"], INDEX_VERSION)
        self.assertEqual(
            [Path(entry["path"]).name for entry in payload["entries"]],
            [markdown_a.name],
        )
        self.assertNotIn(markdown_b.name, str(payload))
        self.assertNotIn(unproven.name, str(migrated))

    def test_rescan_discovers_frontmatter_markdown_without_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            markdown_a = download_dir / "paper-a.md"
            markdown_b = download_dir / "paper-b.md"
            _write_markdown(markdown_a, doi="10.1000/a")
            _write_markdown(markdown_b, doi="10.1000/b")
            (download_dir / "bad.md").write_text(
                "---\ndoi: 10.1000/bad\nsource: x\nhas_fulltext: nope\n"
                "content_kind: fulltext\n---\n",
                encoding="utf-8",
            )
            cache_index_path(download_dir).write_text(
                json.dumps({"version": 0, "entries": []}), encoding="utf-8"
            )

            payload = mcp_tools.list_cached_payload(
                download_dir=download_dir, cache_mode="rescan"
            )

        self.assertEqual(payload["index_status"], "ok")
        self.assertEqual(payload["index_version"], INDEX_VERSION)
        self.assertEqual(
            {entry["doi"] for entry in payload["entries"]},
            {"10.1000/a", "10.1000/b"},
        )
        self.assertEqual(
            {Path(entry["path"]).name for entry in payload["entries"]},
            {markdown_a.name, markdown_b.name},
        )

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
                has_fulltext=True,
                content_kind="fulltext",
            )
            payload_a = mcp_tools.get_cached_payload(
                doi=doi_a, download_dir=download_dir
            )
            rescanned = mcp_tools.list_cached_payload(
                download_dir=download_dir, cache_mode="rescan"
            )
            _write_markdown(markdown, doi=doi_b)
            changed_payload_a = mcp_tools.get_cached_payload(
                doi=doi_a, download_dir=download_dir
            )
            payload_b = mcp_tools.get_cached_payload(
                doi=doi_b, download_dir=download_dir
            )

        self.assertIsNotNone(registered)
        assert registered is not None
        self.assertEqual(
            registered["identity_proof"], IDENTITY_PROOF_MARKDOWN_REGISTRATION
        )
        self.assertEqual(
            payload_a["preferred"]["markdown"]["path"], str(markdown.resolve())
        )
        self.assertEqual(len(rescanned["entries"]), 1)
        self.assertEqual(
            rescanned["entries"][0]["identity_proof"],
            IDENTITY_PROOF_MARKDOWN_REGISTRATION,
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
                has_fulltext=True,
                content_kind="fulltext",
            )
            payload = mcp_tools.get_cached_payload(
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

            payload = mcp_tools.get_cached_payload(doi=doi_a, download_dir=download_dir)

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
                has_fulltext=True,
                content_kind="fulltext",
            )
            payload = mcp_tools.get_cached_payload(
                doi="10.1000/outside", download_dir=download_dir
            )

        self.assertIsNone(registered)
        self.assertEqual(payload["status"], "miss")
        self.assertEqual(payload["entries"], [])

    def test_cache_miss_does_not_open_network_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            with mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("cache lookup must stay offline"),
            ) as create_connection:
                payload = mcp_tools.get_cached_payload(
                    doi="10.1000/missing", download_dir=download_dir
                )

        self.assertEqual(payload["status"], "miss")
        create_connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
