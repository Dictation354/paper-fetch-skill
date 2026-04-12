from __future__ import annotations

import tomllib
import unittest

from paper_fetch import utils
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
        self.assertTrue(all("==" not in dependency for dependency in dependencies))


if __name__ == "__main__":
    unittest.main()
