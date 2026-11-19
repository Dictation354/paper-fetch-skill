from __future__ import annotations

import hashlib
import platform
import tempfile
import unittest
from pathlib import Path

from paper_fetch.delivery._scoped_fs import (
    cache_file_lock,
    fetch_envelope_lock_path,
    read_scoped_file,
)


class ScopedFilesystemTests(unittest.TestCase):
    def test_scoped_file_accepts_equivalent_filesystem_alias_for_root(self) -> None:
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
            payload = b"# Saved full text\n"
            markdown.write_bytes(payload)
            expected_markdown = markdown.resolve()

            opened_via_alias = read_scoped_file(aliased_download_dir, str(markdown))
            opened_via_canonical = read_scoped_file(
                aliased_download_dir, str(expected_markdown)
            )

        self.assertEqual(opened_via_alias, (expected_markdown, payload))
        self.assertEqual(opened_via_canonical, (expected_markdown, payload))

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
                read_scoped_file(download_dir, str(cached), max_bytes=len(payload) - 1)
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

    def test_fetch_envelope_lock_creates_lock_file_in_scoped_lock_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            lock_path = fetch_envelope_lock_path(download_dir, "10.1000/example")
            with cache_file_lock(lock_path):
                self.assertTrue(lock_path.parent.is_dir())


if __name__ == "__main__":
    unittest.main()
