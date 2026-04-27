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
from tests.block_fixtures import block_asset
from tests.golden_criteria import golden_criteria_asset


def _fixture_heading(path, phrase: str) -> tuple[str, str]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        text = " ".join(tag.stripped_strings)
        if phrase.casefold() in text.casefold():
            return str(tag.name), text
    raise AssertionError(f"Heading containing {phrase!r} was not found in {path}")


class HtmlSemanticsTests(unittest.TestCase):
    def test_heading_category_maps_canonical_headings(self) -> None:
        self.assertEqual(heading_category("h2", "Abstract"), "abstract")
        self.assertEqual(heading_category("h2", "Data availability statement"), "data_availability")
        self.assertEqual(heading_category("h2", "Code availability"), "code_availability")
        self.assertEqual(heading_category("h2", "Software availability statement"), "code_availability")
        self.assertEqual(heading_category("h2", "Data, code, and materials availability"), "data_availability")
        self.assertEqual(heading_category("h2", "References"), "references_or_back_matter")
        back_matter_fixture_headings = (
            (golden_criteria_asset("10.1038/nature13376", "original.html"), "Acknowledgements"),
            (golden_criteria_asset("10.1111/gcb.15322", "original.html"), "Research funding"),
            (golden_criteria_asset("10.1126/sciadv.abg9690", "original.html"), "Statement of Competing Interests"),
            (block_asset("10.1007/s00382-018-4286-0", "raw.html"), "Electronic supplementary material"),
        )
        for path, phrase in back_matter_fixture_headings:
            tag_name, text = _fixture_heading(path, phrase)
            with self.subTest(heading=text):
                self.assertEqual(heading_category(tag_name, text), "references_or_back_matter")
        self.assertEqual(heading_category("h2", "Metrics"), "ancillary")
        for path, phrase in (
            (golden_criteria_asset("10.1126/sciadv.abg9690", "original.html"), "Permissions"),
            (golden_criteria_asset("10.1007/s10584-011-0143-4", "article.html"), "Open Access"),
        ):
            tag_name, text = _fixture_heading(path, phrase)
            with self.subTest(heading=text):
                self.assertEqual(heading_category(tag_name, text), "ancillary")
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
        self.assertEqual(identity_category("section id data-code-availability"), "data_availability")
        self.assertEqual(identity_category("section id code-availability"), "code_availability")
        self.assertEqual(identity_category("section class software-availability"), "code_availability")
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
        self.assertEqual(markdown_heading_category("Code Availability"), "code_availability")
        self.assertEqual(markdown_heading_category("Data, Materials, and Software Availability"), "data_availability")
        self.assertEqual(markdown_heading_category("References"), "references_or_back_matter")
        for path, phrase in (
            (golden_criteria_asset("10.1038/nature13376", "original.html"), "Acknowledgements"),
            (golden_criteria_asset("10.1111/gcb.15322", "original.html"), "Research funding"),
            (golden_criteria_asset("10.1126/sciadv.abg9690", "original.html"), "Statement of Competing Interests"),
            (block_asset("10.1007/s00382-018-4286-0", "raw.html"), "Electronic supplementary material"),
        ):
            _tag_name, text = _fixture_heading(path, phrase)
            with self.subTest(heading=text):
                self.assertEqual(markdown_heading_category(text), "references_or_back_matter")
        self.assertEqual(markdown_heading_category("Rights and permissions"), "auxiliary")
        for path, phrase in (
            (golden_criteria_asset("10.1126/sciadv.abg9690", "original.html"), "Permissions"),
            (golden_criteria_asset("10.1007/s10584-011-0143-4", "article.html"), "Open Access"),
        ):
            _tag_name, text = _fixture_heading(path, phrase)
            with self.subTest(heading=text):
                self.assertEqual(markdown_heading_category(text), "auxiliary")
        self.assertEqual(markdown_heading_category("Results"), "body_heading")


if __name__ == "__main__":
    unittest.main()
