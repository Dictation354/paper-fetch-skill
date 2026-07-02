from __future__ import annotations

import unittest

from paper_fetch.http.headers import header_value


class HeaderValueTests(unittest.TestCase):
    def test_header_value_is_case_insensitive(self) -> None:
        self.assertEqual(
            header_value({"Content-Type": "application/pdf"}, "content-type"),
            "application/pdf",
        )

    def test_header_value_handles_none_headers(self) -> None:
        self.assertEqual(header_value(None, "content-type"), "")

    def test_header_value_returns_default_for_missing_header(self) -> None:
        self.assertEqual(
            header_value({"x-other": "1"}, "content-type", "text/html"), "text/html"
        )


if __name__ == "__main__":
    unittest.main()
