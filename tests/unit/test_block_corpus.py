from __future__ import annotations

import unittest

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from tests.block_fixtures import iter_block_samples


class BlockCorpusTests(unittest.TestCase):
    def test_block_samples_do_not_classify_as_fulltext(self) -> None:
        for fixture in iter_block_samples():
            html_text = fixture.asset("raw.html").read_text(encoding="utf-8", errors="ignore")
            markdown_path = fixture.asset("extracted.md")
            markdown_text = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            metadata = parse_html_metadata(html_text, fixture.source_url or "https://example.test")

            diagnostics = assess_html_fulltext_availability(
                markdown_text,
                {
                    **metadata,
                    "title": fixture.title or metadata.get("title") or "",
                    "doi": fixture.doi,
                },
                provider=fixture.provider,
                html_text=html_text,
                title=fixture.title or None,
                final_url=fixture.source_url or None,
            )

            with self.subTest(provider=fixture.provider, doi=fixture.doi, content_kind=diagnostics.content_kind):
                self.assertFalse(diagnostics.accepted)
                self.assertNotEqual(diagnostics.content_kind, "fulltext")
                if diagnostics.blocking_fallback_signals:
                    continue
                self.assertIn(
                    diagnostics.reason,
                    {"insufficient_body", "structured_missing_body_sections"},
                    msg=(
                        "Expected blocking signals or a structural short-body rejection "
                        f"for {fixture.provider}:{fixture.doi}"
                    ),
                )
                self.assertIn(
                    diagnostics.content_kind,
                    {"metadata_only", "abstract_only"},
                    msg=f"Expected non-fulltext structural rejection for {fixture.provider}:{fixture.doi}",
                )


if __name__ == "__main__":
    unittest.main()
