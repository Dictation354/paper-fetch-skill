from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from paper_fetch import utils
from paper_fetch.providers import _article_markdown_common as markdown_common
from tests.paths import REPO_ROOT


class FetchCommonTests(unittest.TestCase):
    def test_sanitize_filename_truncates_long_values_with_stable_hash_suffix(self) -> None:
        long_name = "10.1016/" + ("a" * 260)

        sanitized = utils.sanitize_filename(long_name)

        self.assertLessEqual(len(sanitized), 180)
        self.assertRegex(sanitized, r"_[0-9a-f]{8}$")

    def test_sanitize_filename_uses_hash_fallback_for_non_ascii_titles(self) -> None:
        sanitized = utils.sanitize_filename("这是一个非常长的中文标题" * 30)

        self.assertRegex(sanitized, r"^fulltext_[0-9a-f]{8}$")

    def test_dedupe_authors_uses_semantic_name_key(self) -> None:
        authors = utils.dedupe_authors(["Zhang, San", "San Zhang", "Alice Example"])

        self.assertEqual(authors, ["Zhang, San", "Alice Example"])

    def test_runtime_dependencies_are_declared_explicitly_and_not_patch_pinned(self) -> None:
        with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)

        dependencies = list(pyproject["project"]["dependencies"])

        self.assertIn("pydantic>=2,<3", dependencies)
        self.assertIn("urllib3>=2.2,<3", dependencies)
        self.assertTrue(all("==" not in dependency for dependency in dependencies))

    def test_article_markdown_common_reexports_shared_normalize_text(self) -> None:
        self.assertIs(markdown_common.normalize_text, utils.normalize_text)

    def test_save_payload_is_atomic_when_replacing_existing_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "article.pdf"
            target.write_bytes(b"old")

            saved = utils.save_payload(target, b"new")

            self.assertEqual(saved, str(target))
            self.assertEqual(target.read_bytes(), b"new")
            self.assertFalse((Path(tmpdir) / "article.pdf.part").exists())

    def test_save_payload_preserves_existing_file_when_temp_write_fails(self) -> None:
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "article.pdf"
            target.write_bytes(b"old")

            def fail_once(self: Path, data: bytes) -> int:
                if self.name.endswith(".part"):
                    raise OSError("disk full")
                return original_write_bytes(self, data)

            original_write_bytes = Path.write_bytes
            with mock.patch.object(Path, "write_bytes", autospec=True, side_effect=fail_once):
                with self.assertRaises(OSError):
                    utils.save_payload(target, b"new")

            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse((Path(tmpdir) / "article.pdf.part").exists())

    def test_build_asset_output_path_prefers_content_type_over_url_suffix(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_path = utils.build_asset_output_path(
                Path(tmpdir),
                "https://example.test/figure.jpg",
                "image/webp",
                "https://example.test/figure.jpg",
                set(),
            )

        self.assertEqual(output_path.suffix, ".webp")
        self.assertEqual(output_path.name, "figure.webp")

    def test_extension_from_content_type_maps_web_image_formats(self) -> None:
        expected = {
            "image/bmp": ".bmp",
            "image/x-ms-bmp": ".bmp",
            "image/vnd.microsoft.icon": ".ico",
            "image/x-icon": ".ico",
            "image/apng": ".apng",
            "image/heic": ".heic",
            "image/heif": ".heif",
            "image/svg+xml; charset=utf-8": ".svg",
        }

        for content_type, suffix in expected.items():
            with self.subTest(content_type=content_type):
                self.assertEqual(utils.extension_from_content_type(content_type), suffix)

    def test_build_asset_output_path_prefers_explicit_filename_before_url_path(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output_path = utils.build_asset_output_path(
                Path(tmpdir),
                "https://onlinelibrary.wiley.com/action/downloadSupplement",
                "application/octet-stream",
                "https://onlinelibrary.wiley.com/action/downloadSupplement",
                set(),
                preferred_filename="gcb16414-sup-0001-FigureS1.docx",
            )

        self.assertEqual(output_path.name, "gcb16414-sup-0001-FigureS1.docx")


if __name__ == "__main__":
    unittest.main()
