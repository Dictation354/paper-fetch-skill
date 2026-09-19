from __future__ import annotations
import unittest
from bs4 import BeautifulSoup
from paper_fetch.extraction.html.semantics import (
    has_explicit_reference_marker,
    identity_category,
    looks_like_explicit_body_container,
    looks_like_reference_anchor,
    looks_like_reference_href,
)


class HtmlSemanticsTests(unittest.TestCase):
    def test_identity_category_maps_canonical_tokens(self) -> None:
        self.assertEqual(identity_category("section property articleBody"), "body")
        self.assertEqual(
            identity_category("section id data-availability"), "data_availability"
        )
        self.assertEqual(
            identity_category("section id data-code-availability"), "data_availability"
        )
        self.assertEqual(
            identity_category("section id code-availability"), "code_availability"
        )
        self.assertEqual(
            identity_category("section class software-availability"),
            "code_availability",
        )
        self.assertEqual(
            identity_category("ol class references-list"), "references_or_back_matter"
        )
        self.assertEqual(identity_category("aside class share-toolbar"), "ancillary")
        self.assertEqual(
            identity_category("section id rightslink-section"), "ancillary"
        )
        self.assertEqual(
            identity_category("section id author-information-section"), "ancillary"
        )
        self.assertEqual(
            identity_category("section id additional-information-section"), "ancillary"
        )
        self.assertEqual(identity_category("section class profiles-panel"), "ancillary")
        self.assertEqual(identity_category("aside class subscribe-cta"), "ancillary")
        self.assertEqual(
            identity_category("section class structured-abstract"), "abstract"
        )

    def test_looks_like_explicit_body_container_uses_shared_identity_rules(
        self,
    ) -> None:
        soup = BeautifulSoup(
            "<section property='articleBody'>Body</section>", "html.parser"
        )
        self.assertTrue(looks_like_explicit_body_container(soup.section))

    def test_reference_anchor_semantics_cover_common_markers(self) -> None:
        soup = BeautifulSoup(
            """
<p>
  <a data-test="citation-ref" href="#x">1</a>
  <a role="doc-biblioref" href="#x">2</a>
  <a class="biblink" href="#x">3</a>
  <a data-xml-rid="ref4" href="#x">4</a>
  <a ref-type="bibr" rid="ref5" href="#x">5</a>
  <a href="/article#core-collateral-r6">6</a>
  <a href="#fig1">Figure</a>
</p>
""",
            "html.parser",
        )
        anchors = soup.find_all("a")

        self.assertTrue(
            all(looks_like_reference_anchor(anchor) for anchor in anchors[:6])
        )
        self.assertTrue(has_explicit_reference_marker(anchors[4]))
        self.assertTrue(looks_like_reference_href("/article#bib12"))
        self.assertFalse(looks_like_reference_anchor(anchors[6]))
        self.assertFalse(looks_like_reference_href("#fig1"))


if __name__ == "__main__":
    unittest.main()
