from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from paper_fetch.extraction.html.semantics import (
    heading_category,
    identity_category,
    looks_like_explicit_body_container,
    markdown_heading_category,
    parse_markdown_heading,
)


class HtmlSemanticsTests(unittest.TestCase):
    def test_heading_category_maps_canonical_headings(self) -> None:
        self.assertEqual(heading_category("h2", "Abstract"), "abstract")
        self.assertEqual(heading_category("h2", "Data availability statement"), "data_availability")
        self.assertEqual(heading_category("h2", "References"), "references_or_back_matter")
        self.assertEqual(heading_category("h2", "Metrics"), "ancillary")
        self.assertEqual(heading_category("h2", "Corresponding author"), "ancillary")
        self.assertEqual(heading_category("h2", "Additional information"), "ancillary")
        self.assertEqual(heading_category("h2", "Rights and permissions"), "ancillary")
        self.assertEqual(heading_category("h2", "Profiles"), "ancillary")
        self.assertEqual(heading_category("h2", "Subscribe and save"), "ancillary")
        self.assertEqual(heading_category("h2", "Publisher's Note"), "ancillary")
        self.assertEqual(heading_category("h1", "Example title"), "front_matter")
        self.assertEqual(heading_category("h2", "Results"), "body_heading")

    def test_identity_category_maps_canonical_tokens(self) -> None:
        self.assertEqual(identity_category("section property articleBody"), "body")
        self.assertEqual(identity_category("section id data-availability"), "data_availability")
        self.assertEqual(identity_category("ol class references-list"), "references_or_back_matter")
        self.assertEqual(identity_category("aside class share-toolbar"), "ancillary")
        self.assertEqual(identity_category("section id rightslink-section"), "ancillary")
        self.assertEqual(identity_category("section id author-information-section"), "ancillary")
        self.assertEqual(identity_category("section id additional-information-section"), "ancillary")
        self.assertEqual(identity_category("section class profiles-panel"), "ancillary")
        self.assertEqual(identity_category("aside class subscribe-cta"), "ancillary")
        self.assertEqual(identity_category("section class structured-abstract"), "abstract")

    def test_looks_like_explicit_body_container_uses_shared_identity_rules(self) -> None:
        soup = BeautifulSoup("<section property='articleBody'>Body</section>", "html.parser")
        self.assertTrue(looks_like_explicit_body_container(soup.section))

    def test_markdown_heading_taxonomy_maps_article_sections(self) -> None:
        self.assertEqual(parse_markdown_heading("### Data Availability"), (3, "Data Availability"))
        self.assertEqual(markdown_heading_category("Abstract"), "abstract")
        self.assertEqual(markdown_heading_category("Editor's Summary"), "front_matter")
        self.assertEqual(markdown_heading_category("Data Availability"), "data_availability")
        self.assertEqual(markdown_heading_category("References"), "references_or_back_matter")
        self.assertEqual(markdown_heading_category("Rights and permissions"), "auxiliary")
        self.assertEqual(markdown_heading_category("Results"), "body_heading")


if __name__ == "__main__":
    unittest.main()
