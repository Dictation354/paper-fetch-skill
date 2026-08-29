from __future__ import annotations

import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from paper_fetch.providers._article_markdown_common import render_inline_text
from paper_fetch.providers import (
    _article_markdown_elsevier_document as elsevier_document,
)
from paper_fetch.providers import _elsevier_xml_rules as elsevier_rules
from paper_fetch.providers import _article_markdown_math as article_markdown_math
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.runtime import RuntimeContext
from paper_fetch.models import article_from_markdown, article_from_structure
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset


def build_elsevier_markdown(
    xml_body: bytes,
    *,
    assets: list[dict[str, str]] | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    article_metadata = {
        "doi": "10.1016/test",
        "title": "Elsevier Markdown Example",
        "journal_title": "Example Journal",
        "published": "2026-01-01",
        "landing_page_url": "https://example.test/article",
        "abstract": "",
    }
    if metadata:
        article_metadata.update(metadata)

    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / "10.1016_test.xml"
        xml_path.write_bytes(xml_body)
        prepared_assets: list[dict[str, str]] = []
        for asset in assets or []:
            prepared = dict(asset)
            if prepared.get("path"):
                asset_path = Path(tmpdir) / Path(prepared["path"]).name
                asset_path.write_bytes(b"fake")
                prepared["path"] = str(asset_path)
            prepared_assets.append(prepared)
        markdown_path = elsevier_document.write_article_markdown(
            provider="elsevier",
            metadata=article_metadata,
            xml_body=xml_body,
            output_dir=Path(tmpdir),
            xml_path=str(xml_path),
            assets=prepared_assets,
        )

        assert markdown_path is not None
        return Path(markdown_path).read_text(encoding="utf-8")


def _load_elsevier_golden_xml(doi: str) -> bytes:
    return golden_criteria_asset(doi, "original.xml").read_bytes()


def _load_elsevier_scenario_xml(name: str) -> bytes:
    return golden_criteria_scenario_asset(name, "original.xml").read_bytes()


def _render_elsevier_golden_markdown(
    doi: str,
    *,
    assets: list[dict[str, str]] | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    article_metadata = {
        "doi": doi,
        "title": f"Elsevier Golden Fixture {doi}",
    }
    if metadata:
        article_metadata.update(metadata)
    return build_elsevier_markdown(
        _load_elsevier_golden_xml(doi),
        assets=assets,
        metadata=article_metadata,
    )


def _build_elsevier_golden_structure(doi: str):
    xml_body = _load_elsevier_golden_xml(doi)
    slug = doi.replace("/", "_")
    return elsevier_document.build_article_structure(
        provider="elsevier",
        metadata={"doi": doi, "title": f"Elsevier Golden Fixture {doi}"},
        xml_body=xml_body,
        xml_path=Path(f"{slug}.xml"),
        assets=elsevier_provider.extract_elsevier_asset_references(xml_body),
    )


def _assert_markdown_table_row(
    test_case: unittest.TestCase,
    markdown: str,
    cells: list[str],
    *,
    allow_more_cells: bool = False,
) -> None:
    cell_pattern = r"\s*\|\s*".join(re.escape(cell) for cell in cells)
    suffix = r"(?:\s*\|.*)?$" if allow_more_cells else r"\s*\|$"
    test_case.assertRegex(markdown, rf"(?m)^\|\s*{cell_pattern}{suffix}")


class ElsevierMarkdownTests(unittest.TestCase):
    def test_elsevier_document_module_remains_importable(self) -> None:
        self.assertTrue(callable(elsevier_document.build_article_structure))
        self.assertTrue(callable(elsevier_document.build_markdown_document))
        self.assertTrue(callable(elsevier_document.write_article_markdown))
        self.assertTrue(callable(article_markdown_math.render_mathml_expression))

    def test_elsevier_cached_xml_root_is_reused_read_only(self) -> None:
        xml_body = b"""
        <full-text-retrieval-response xmlns:ce="http://www.elsevier.com/xml/common/dtd">
          <ce:object ref="gr1" type="image" category="thumbnail" mimetype="image/jpeg">https://example.test/gr1.jpg</ce:object>
        </full-text-retrieval-response>
        """
        context = RuntimeContext(env={})

        root = elsevier_provider.elsevier_xml_root_from_payload(
            xml_body,
            context=context,
            source_url="https://example.test/article",
        )
        cached_root = elsevier_provider.elsevier_xml_root_from_payload(
            xml_body,
            context=context,
            source_url="https://example.test/article",
        )

        self.assertIs(root, cached_root)
        assert root is not None
        before = ET.tostring(root)
        references = elsevier_provider.extract_elsevier_asset_references(
            xml_body,
            context=context,
            source_url="https://example.test/article",
            xml_root=root,
        )

        self.assertEqual(ET.tostring(root), before)
        self.assertEqual(references[0]["source_ref"], "gr1")
        self.assertEqual(references[0]["source_url"], "https://example.test/gr1.jpg")

    def test_build_article_structure_extracts_authors_from_author_groups(self) -> None:
        xml_body = golden_criteria_scenario_asset(
            "elsevier_author_groups_minimal", "original.xml"
        ).read_bytes()

        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={
                "doi": "10.1016/test-authors",
                "title": "Elsevier Author Example",
                "landing_page_url": "https://example.test/article",
            },
            xml_body=xml_body,
            xml_path=Path("10.1016_test-authors.xml"),
            assets=[],
        )

        self.assertIsNotNone(structure)
        assert structure is not None
        self.assertEqual(
            structure.authors, ["Jane Doe", "Smith, J.", "Open Climate Consortium"]
        )

    def test_elsevier_structure_builder_dispatch_rejects_unknown_provider(self) -> None:
        structure = elsevier_document.build_article_structure(
            provider="not_elsevier",
            metadata={"doi": "10.1016/test", "title": "Unsupported"},
            xml_body=b"<article/>",
            xml_path=Path("unsupported.xml"),
            assets=[],
        )

        self.assertIsNone(structure)
        self.assertIsNone(
            elsevier_document.build_markdown_document(
                provider="not_elsevier",
                metadata={"doi": "10.1016/test", "title": "Unsupported"},
                xml_body=b"<article/>",
                xml_path=Path("unsupported.xml"),
                assets=[],
            )
        )

    def test_elsevier_asset_group_requires_numbered_author_manuscript_key(self) -> None:
        self.assertEqual(
            elsevier_rules.infer_elsevier_asset_group_key("am1.docx"), "am1"
        )
        self.assertEqual(
            elsevier_rules.infer_elsevier_asset_group_key("frame123.pdf"),
            "frame123.pdf",
        )
        self.assertTrue(
            elsevier_rules.should_ignore_elsevier_section_title("Graphical Abstract")
        )

    def test_build_article_structure_extracts_numbered_xml_references(self) -> None:
        """rule: rule-elsevier-xml-references"""
        doi = "10.1016/j.agrformet.2024.109975"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.agrformet.2024.109975.xml"),
            assets=[],
        )

        assert structure is not None
        self.assertGreater(len(structure.references), 20)
        first_reference = structure.references[0]
        self.assertTrue(first_reference.raw.startswith("1. A. Anav, P. Friedlingstein"))
        self.assertIn(
            "Spatiotemporal patterns of terrestrial gross primary production: a review",
            first_reference.raw,
        )
        self.assertIn("Reviews of Geophysics, 53(3): 785-818", first_reference.raw)
        self.assertIn("10.1002/2015rg000483", first_reference.raw)
        self.assertIn("[Anav et al., 2015]", first_reference.raw)

        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            doi=doi,
            abstract_lines=[],
            body_lines=["A short body paragraph keeps the article renderable."],
            figure_entries=[],
            table_entries=[],
            supplement_entries=[],
            conversion_notes=[],
            references=structure.references,
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("1. A. Anav, P. Friedlingstein", rendered)
        self.assertNotIn(
            "- Spatiotemporal patterns of terrestrial gross primary production: a review",
            rendered,
        )

    def test_elsevier_references_fall_back_without_skipping_bib_entries(self) -> None:
        root = ET.fromstring(
            """
<root>
  <bib-reference id="bib1">
    <label>1</label>
    <reference>
      <contribution><title><maintitle>Structured title</maintitle></title></contribution>
      <host><sourcetitle>Structured Journal</sourcetitle><date>2024</date></host>
    </reference>
  </bib-reference>
  <bib-reference id="bib2">
    <label>2</label>
    <source-text>Raw fallback reference text for the second citation.</source-text>
  </bib-reference>
  <bib-reference id="bib3">
    <label>3</label>
  </bib-reference>
</root>
"""
        )

        references = elsevier_document.extract_elsevier_references(root)

        self.assertEqual(len(references), 3)
        self.assertTrue(references[0].raw.startswith("1. 2024. Structured title"))
        self.assertEqual(
            references[1].raw, "2. Raw fallback reference text for the second citation."
        )
        self.assertEqual(references[2].raw, "3. [Reference text unavailable]")

    def test_article_from_structure_preserves_inline_elsevier_figures(self) -> None:
        """rule: rule-elsevier-inline-figure-table-placement"""
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Observed patterns are shown in <ce:cross-ref refid="fig1">Fig. 1</ce:cross-ref>.</ce:para>
      </ce:section>
    </ce:sections>
    <ce:floats>
      <ce:figure id="fig1">
        <ce:label>Fig. 1</ce:label>
        <ce:caption>
          <ce:simple-para>Observed response figure.</ce:simple-para>
        </ce:caption>
        <ce:link locator="gr1" />
      </ce:figure>
    </ce:floats>
  </body>
</full-text-retrieval-response>
"""
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={
                "doi": "10.1016/figure-preserve",
                "title": "Elsevier Figure Preserve",
            },
            xml_body=xml_body,
            xml_path=Path("10.1016_figure-preserve.xml"),
            assets=[
                {
                    "asset_type": "image",
                    "source_ref": "gr1",
                    "path": "body_assets/figure-preserve-fig1.jpeg",
                }
            ],
        )

        assert structure is not None
        self.assertEqual(len(structure.figure_entries), 1)
        self.assertEqual(len(structure.used_figure_keys), 1)
        article = article_from_structure(
            source="elsevier_xml",
            metadata={
                "doi": "10.1016/figure-preserve",
                "title": "Elsevier Figure Preserve",
            },
            doi="10.1016/figure-preserve",
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertEqual(
            rendered.count("![Figure 1](body_assets/figure-preserve-fig1.jpeg)"), 1
        )
        self.assertIn("Observed response figure.", rendered)
        self.assertNotIn("## Additional Figures", rendered)

    def test_article_from_structure_preserves_remote_elsevier_figure_links_without_local_assets(
        self,
    ) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Observed patterns are shown in <ce:cross-ref refid="fig1">Fig. 1</ce:cross-ref>.</ce:para>
      </ce:section>
    </ce:sections>
    <ce:floats>
      <ce:figure id="fig1">
        <ce:label>Fig. 1</ce:label>
        <ce:caption>
          <ce:simple-para>Observed response figure.</ce:simple-para>
        </ce:caption>
        <ce:link locator="gr1" />
      </ce:figure>
    </ce:floats>
  </body>
</full-text-retrieval-response>
"""
        remote_url = (
            "https://api.elsevier.com/content/object/eid/gr1?httpAccept=%2A%2F%2A"
        )
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={
                "doi": "10.1016/figure-preserve",
                "title": "Elsevier Figure Preserve",
            },
            xml_body=xml_body,
            xml_path=Path("10.1016_figure-preserve.xml"),
            assets=[
                {
                    "asset_type": "image",
                    "source_ref": "gr1",
                    "source_url": remote_url,
                }
            ],
        )

        assert structure is not None
        self.assertEqual(structure.figure_entries[0]["link"], remote_url)
        self.assertNotIn("path", structure.figure_entries[0])
        article = article_from_structure(
            source="elsevier_xml",
            metadata={
                "doi": "10.1016/figure-preserve",
                "title": "Elsevier Figure Preserve",
            },
            doi="10.1016/figure-preserve",
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        rendered = article.to_ai_markdown(asset_profile="none", max_tokens="full_text")

        self.assertEqual(rendered.count(f"![Figure 1]({remote_url})"), 1)
        self.assertEqual(article.assets[0].original_url, remote_url)

    def test_mathml_nested_subscripts_are_grouped_for_katex(self) -> None:
        math_node = ET.fromstring(
            """
<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML">
  <mml:msub>
    <mml:msub>
      <mml:mi>NDVI</mml:mi>
      <mml:mrow>
        <mml:mi>d</mml:mi>
        <mml:mo>-</mml:mo>
        <mml:mi>w</mml:mi>
      </mml:mrow>
    </mml:msub>
    <mml:mi>cli</mml:mi>
  </mml:msub>
</mml:math>
"""
        )

        expression = article_markdown_math.render_mathml_expression(math_node)

        self.assertEqual(expression, "{NDVI_{d - w}}_{cli}")

    def _assert_real_elsevier_display_formula_renders_as_formula_block(self) -> None:
        markdown = _render_elsevier_golden_markdown("10.1016/j.agrformet.2024.109975")

        self.assertIn("(26)", markdown)
        self.assertRegex(
            markdown,
            r"\$\$\nF_\{crit\} = \\sum(?:\\limits)?_\{t_\{p\}\}\^\{SOS_\{y0\}\}\s*R_\{f\}\n\$\$",
        )
        self.assertLess(markdown.index("(26)"), markdown.index("$$"))

    def _assert_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks(
        self,
    ) -> None:
        xml_body = _load_elsevier_scenario_xml("elsevier_formula_inline_display")

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn(
            "Air temperature ($T$) and dewpoint temperature ($T_{d}$) were used:",
            markdown,
        )
        self.assertIn("where $c_{1}$ is constant.", markdown)
        self.assertRegex(markdown, r"\$\$\n\{?VPD\}? = T\n\$\$")
        self.assertNotIn("$$\nT\n$$", markdown)
        self.assertNotIn("$$\nT_{d}\n$$", markdown)
        self.assertNotIn("$$\nc_{1}\n$$", markdown)

    def _assert_formula_placeholder_is_visible_and_counted_when_conversion_fails(
        self,
    ) -> None:
        xml_body = _load_elsevier_scenario_xml("elsevier_formula_missing")

        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={
                "doi": "10.1016/formula-missing",
                "title": "Formula Missing Example",
                "landing_page_url": "https://example.test/article",
            },
            xml_body=xml_body,
            xml_path=Path("10.1016_formula-missing.xml"),
            assets=[],
        )

        assert structure is not None
        self.assertIn("[Formula unavailable: (1)]", "\n".join(structure.body_lines))
        self.assertEqual(structure.semantic_losses.formula_missing_count, 1)
        self.assertIn(
            "- (1): Formula could not be converted; an explicit placeholder was inserted.",
            structure.conversion_notes,
        )

    def test_elsevier_real_display_formula_renders_as_formula_block(self) -> None:
        """rule: rule-elsevier-formula-rendering"""
        self._assert_real_elsevier_display_formula_renders_as_formula_block()

    def test_elsevier_inline_math_symbols_stay_inline(self) -> None:
        """rule: rule-elsevier-formula-rendering"""
        self._assert_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks()

    def test_elsevier_formula_placeholder_is_visible_when_conversion_fails(
        self,
    ) -> None:
        """rule: rule-elsevier-formula-rendering"""
        self._assert_formula_placeholder_is_visible_and_counted_when_conversion_fails()

    def test_elsevier_formula_locator_uses_highest_priority_official_objects(
        self,
    ) -> None:
        xml_body = b"""
<full-text-retrieval-response
    xmlns:ce="http://www.elsevier.com/xml/common/dtd"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
  <ce:object ref="fx1_sml.jpg" type="IMAGE-DOWNSAMPLED" mimetype="image/jpeg">https://example.test/fx1-small.jpg</ce:object>
  <ce:object ref="fx1_lrg.jpg" type="IMAGE-HIGH-RES" mimetype="image/jpeg">https://example.test/fx1-large.jpg</ce:object>
  <ce:object ref="fx2_lrg.jpg" type="IMAGE-HIGH-RES" mimetype="image/jpeg">https://example.test/fx2-large.jpg</ce:object>
  <originalText><xocs:doc><xocs:serial-item><article><body>
    <ce:sections><ce:section><ce:section-title>Methods</ce:section-title>
      <ce:formula><ce:label>(1)</ce:label><ce:link locator="fx1"/></ce:formula>
      <ce:formula><ce:label>(2)</ce:label><ce:link xlink:href="objects/fx2_lrg.jpg"/></ce:formula>
    </ce:section></ce:sections>
  </body></article></xocs:serial-item></xocs:doc></originalText>
</full-text-retrieval-response>
"""

        references = elsevier_provider.extract_elsevier_asset_references(xml_body)
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": "10.1016/formula-images", "title": "Formula images"},
            xml_body=xml_body,
            xml_path=Path("10.1016_formula-images.xml"),
            assets=references,
        )

        assert structure is not None
        markdown = "\n".join(structure.body_lines)
        self.assertIn("![Formula](https://example.test/fx1-large.jpg)", markdown)
        self.assertIn("![Formula](https://example.test/fx2-large.jpg)", markdown)
        self.assertNotIn("fx1-small.jpg", markdown)
        self.assertNotIn("[Formula unavailable", markdown)
        self.assertEqual(structure.semantic_losses.formula_fallback_count, 2)
        self.assertEqual(structure.semantic_losses.formula_missing_count, 0)
        self.assertEqual(structure.figure_entries, [])
        self.assertEqual(
            {reference["asset_type"] for reference in references},
            {"image"},
        )

    def test_elsevier_formula_locator_without_object_keeps_missing_placeholder(
        self,
    ) -> None:
        xml_body = b"""
<full-text-retrieval-response
    xmlns:ce="http://www.elsevier.com/xml/common/dtd"
    xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
  <originalText><xocs:doc><xocs:serial-item><article><body>
    <ce:sections><ce:section><ce:section-title>Methods</ce:section-title>
      <ce:formula><ce:label>(9)</ce:label><ce:link locator="fx9"/></ce:formula>
    </ce:section></ce:sections>
  </body></article></xocs:serial-item></xocs:doc></originalText>
</full-text-retrieval-response>
"""

        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": "10.1016/formula-missing-object", "title": "Missing"},
            xml_body=xml_body,
            xml_path=Path("10.1016_formula-missing-object.xml"),
            assets=[],
        )

        assert structure is not None
        self.assertIn("[Formula unavailable: (9)]", "\n".join(structure.body_lines))
        self.assertEqual(structure.semantic_losses.formula_fallback_count, 0)
        self.assertEqual(structure.semantic_losses.formula_missing_count, 1)

    def test_elsevier_formula_classification_leaves_ordinary_appendix_fx_unchanged(
        self,
    ) -> None:
        xml_body = b"""
<full-text-retrieval-response
    xmlns:ce="http://www.elsevier.com/xml/common/dtd"
    xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
  <ce:object ref="fx1_lrg.jpg" type="IMAGE-HIGH-RES" mimetype="image/jpeg">https://example.test/fx1-large.jpg</ce:object>
  <originalText><xocs:doc><xocs:serial-item><article><body>
    <ce:appendices><ce:appendix>
      <ce:figure><ce:label>Figure A.1</ce:label><ce:link locator="fx1"/></ce:figure>
    </ce:appendix></ce:appendices>
  </body></article></xocs:serial-item></xocs:doc></originalText>
</full-text-retrieval-response>
"""

        references = elsevier_provider.extract_elsevier_asset_references(xml_body)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["asset_type"], "appendix_image")

    def test_elsevier_formula_locator_prefers_downloaded_local_asset(self) -> None:
        xml_body = b"""
<full-text-retrieval-response
    xmlns:ce="http://www.elsevier.com/xml/common/dtd"
    xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
  <ce:object ref="fx1_lrg.jpg" type="IMAGE-HIGH-RES" mimetype="image/jpeg">https://example.test/fx1-large.jpg</ce:object>
  <originalText><xocs:doc><xocs:serial-item><article><body>
    <ce:sections><ce:section><ce:section-title>Methods</ce:section-title>
      <ce:formula><ce:label>(1)</ce:label><ce:link locator="fx1"/></ce:formula>
    </ce:section></ce:sections>
  </body></article></xocs:serial-item></xocs:doc></originalText>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(
            xml_body,
            assets=[
                {
                    "asset_type": "image",
                    "source_ref": "fx1_lrg.jpg",
                    "source_url": "https://example.test/fx1-large.jpg",
                    "path": "formula-1.jpg",
                }
            ],
        )

        self.assertIn("![Formula](formula-1.jpg)", markdown)
        self.assertNotIn("![Formula](https://example.test/fx1-large.jpg)", markdown)
        self.assertNotIn("## Figures", markdown)

    def test_elsevier_multi_tgroup_mixed_results_count_only_failed_group(
        self,
    ) -> None:
        xml_body = b"""
<full-text-retrieval-response
    xmlns:ce="http://www.elsevier.com/xml/common/dtd"
    xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
  <originalText><xocs:doc><xocs:serial-item><article><body>
    <ce:sections><ce:section><ce:section-title>Results</ce:section-title>
      <ce:table id="tbl1">
        <ce:label>Table 1</ce:label>
        <ce:caption><ce:simple-para>Grouped risks.</ce:simple-para></ce:caption>
        <tgroup cols="2">
          <colspec colname="a1"/><colspec colname="a2"/>
          <thead>
            <row><entry namest="a1" nameend="a2">(a) WBGT</entry></row>
            <row><entry colname="a1">Day</entry><entry colname="a2">Risk</entry></row>
          </thead>
          <tbody><row><entry colname="a1">1</entry><entry colname="a2">Low</entry></row></tbody>
        </tgroup>
        <tgroup cols="2">
          <colspec colname="b1"/><colspec colname="b2"/>
          <thead><row><entry colname="b1">Day</entry><entry colname="b1">T</entry></row></thead>
          <tbody><row><entry colname="b1">2</entry><entry colname="b2">30</entry></row></tbody>
        </tgroup>
        <tgroup cols="3">
          <colspec colname="c1"/><colspec colname="c2"/><colspec colname="c3"/>
          <thead>
            <row><entry namest="c1" nameend="c3">(c) AT</entry></row>
            <row><entry colname="c1">Day</entry><entry colname="c2">Min</entry><entry colname="c3">Max</entry></row>
          </thead>
          <tbody><row><entry colname="c1">3</entry><entry colname="c2">29</entry><entry colname="c3">32</entry></row></tbody>
        </tgroup>
      </ce:table>
    </ce:section></ce:sections>
  </body></article></xocs:serial-item></xocs:doc></originalText>
</full-text-retrieval-response>
"""

        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": "10.1016/grouped-table", "title": "Grouped table"},
            xml_body=xml_body,
            xml_path=Path("10.1016_grouped-table.xml"),
            assets=[],
        )

        assert structure is not None
        markdown = "\n".join(structure.body_lines)
        self.assertEqual(markdown.count("Table 1"), 1)
        self.assertEqual(markdown.count("Grouped risks."), 1)
        self.assertLess(markdown.index("(a) WBGT"), markdown.index("| Day"))
        self.assertLess(markdown.index("- Day: 2; T: 30"), markdown.index("(c) AT"))
        self.assertLess(markdown.index("(c) AT"), markdown.rindex("| Day"))
        self.assertEqual(structure.semantic_losses.table_fallback_count, 1)
        self.assertEqual(structure.semantic_losses.table_layout_degraded_count, 1)

    def test_elsevier_regression_32_preserves_independent_table_groups(self) -> None:
        """rule: rule-xml-table-groups"""
        doi = "10.1016/j.apgeog.2012.04.006"
        structure = _build_elsevier_golden_structure(doi)

        assert structure is not None
        table = next(
            entry for entry in structure.table_entries if entry["heading"] == "Table 1"
        )
        groups = table["_table_groups"]
        rendered = "\n".join(elsevier_document.render_table_block(table))

        self.assertEqual([len(group["headers"]) for group in groups], [3, 5])
        self.assertEqual([len(group["rows"]) for group in groups], [5, 19])
        self.assertEqual(len(re.findall(r"(?m)^\| -+(?:\s+\|.*)$", rendered)), 2)
        self.assertEqual(rendered.count("Table 1"), 1)
        self.assertEqual(
            structure.semantic_losses.table_fallback_count,
            0,
        )
        self.assertEqual(
            structure.semantic_losses.table_layout_degraded_count,
            0,
        )

        root = ET.fromstring(_load_elsevier_golden_xml(doi))
        source_table = next(
            node
            for node in root.iter()
            if isinstance(node.tag, str)
            and elsevier_document.xml_local_name(node.tag) == "table"
            and any(
                elsevier_document.xml_local_name(child.tag) == "label"
                and elsevier_document.normalize_text("".join(child.itertext()))
                == "Table 1"
                for child in list(node)
                if isinstance(child.tag, str)
            )
        )
        self.assertEqual(
            [
                sum(
                    1
                    for row in group.iter()
                    if isinstance(row.tag, str)
                    and elsevier_document.xml_local_name(row.tag) in {"row", "tr"}
                )
                for group in source_table.iter()
                if isinstance(group.tag, str)
                and elsevier_document.xml_local_name(group.tag) == "tgroup"
            ],
            [6, 21],
        )

    def test_elsevier_regression_97_renders_wbgt_t_at_groups_in_order(self) -> None:
        """rule: rule-xml-table-groups"""
        doi = "10.1016/j.envres.2018.12.059"
        structure = _build_elsevier_golden_structure(doi)

        assert structure is not None
        table = next(
            entry for entry in structure.table_entries if entry["heading"] == "Table 2"
        )
        groups = table["_table_groups"]
        rendered = "\n".join(elsevier_document.render_table_block(table))

        self.assertEqual(
            [group.get("_table_prefix_rows") for group in groups],
            [["(a) WBGT"], ["(b) T"], ["(c) AT"]],
        )
        self.assertEqual([len(group["rows"]) for group in groups], [18, 18, 18])
        self.assertEqual(len(re.findall(r"(?m)^\| -+(?:\s+\|.*)$", rendered)), 3)
        self.assertLess(rendered.index("(a) WBGT"), rendered.index("(b) T"))
        self.assertLess(rendered.index("(b) T"), rendered.index("(c) AT"))
        self.assertEqual(structure.semantic_losses.table_fallback_count, 0)
        self.assertEqual(structure.semantic_losses.table_layout_degraded_count, 0)

        root = ET.fromstring(_load_elsevier_golden_xml(doi))
        source_table = next(
            node
            for node in root.iter()
            if isinstance(node.tag, str)
            and elsevier_document.xml_local_name(node.tag) == "table"
            and any(
                elsevier_document.xml_local_name(child.tag) == "label"
                and elsevier_document.normalize_text("".join(child.itertext()))
                == "Table 2"
                for child in list(node)
                if isinstance(child.tag, str)
            )
        )
        self.assertEqual(
            [
                sum(
                    1
                    for row in group.iter()
                    if isinstance(row.tag, str)
                    and elsevier_document.xml_local_name(row.tag) in {"row", "tr"}
                )
                for group in source_table.iter()
                if isinstance(group.tag, str)
                and elsevier_document.xml_local_name(group.tag) == "tgroup"
            ],
            [21, 21, 21],
        )

    def test_elsevier_regression_42_uses_two_official_formula_images(self) -> None:
        """rule: rule-elsevier-formula-rendering"""
        doi = "10.1016/j.uclim.2019.100528"
        structure = _build_elsevier_golden_structure(doi)

        assert structure is not None
        formula_lines = [
            line for line in structure.body_lines if line.startswith("![Formula](")
        ]
        self.assertEqual(len(formula_lines), 2)
        self.assertTrue(any("fx1_lrg.jpg" in line for line in formula_lines))
        self.assertTrue(any("fx2_lrg.jpg" in line for line in formula_lines))
        self.assertEqual(structure.semantic_losses.formula_fallback_count, 2)
        self.assertEqual(structure.semantic_losses.formula_missing_count, 0)
        self.assertFalse(
            any("[Formula unavailable" in line for line in structure.body_lines)
        )

        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Formula image regression"},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            semantic_losses=structure.semantic_losses,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        self.assertEqual(article.quality.confidence, "medium")
        self.assertIn("formula_fallback_present", article.quality.flags)

    def test_elsevier_complex_table_spans_are_normalized_without_quality_loss(
        self,
    ) -> None:
        """rule: rule-elsevier-complex-table-span-degradation"""
        xml_body = _load_elsevier_scenario_xml("elsevier_complex_table_span")

        markdown = build_elsevier_markdown(xml_body)

        _assert_markdown_table_row(
            self, markdown, ["Station group", "Station group", "Value"]
        )
        _assert_markdown_table_row(self, markdown, ["Hydrometric", "Station A", "10"])
        _assert_markdown_table_row(self, markdown, ["Hydrometric", "Station B", "20"])
        self.assertNotIn("Merged table spans were semantically expanded", markdown)

    def test_elsevier_real_multilevel_header_is_flattened_without_body_header_row(
        self,
    ) -> None:
        markdown = _render_elsevier_golden_markdown("10.1016/j.rse.2024.114346")

        _assert_markdown_table_row(
            self,
            markdown,
            [
                "Region",
                "Freeze-up date / Mean value (DOY)",
                "Freeze-up date / Trend (days per decade)",
                "Break-up date / Mean value (DOY)",
                "Break-up date / Trend (days per decade)",
                "Ice duration / Mean value (days)",
                "Ice duration / Trend (days per decade)",
            ],
        )
        self.assertNotRegex(
            markdown,
            r"(?m)^\|\s*Region\s*\|\s*Mean value \(DOY\)\s*\|\s*Trend",
        )

    def test_elsevier_overlapping_cals_columns_use_readable_list_fallback(
        self,
    ) -> None:
        xml_body = b"""
<full-text-retrieval-response xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <coredata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Table fallback</dc:title></coredata>
  <originalText>
    <xocs:doc xmlns:xocs="http://www.elsevier.com/xml/xocs/dtd">
      <xocs:serial-item><article><body><ce:sections><ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:table id="tbl1">
          <ce:label>Table 1</ce:label>
          <ce:caption><ce:simple-para>Overlapping columns.</ce:simple-para></ce:caption>
          <tgroup cols="2">
            <colspec colname="c1"/><colspec colname="c2"/>
            <thead><row><entry colname="c1">A</entry><entry colname="c1">B</entry></row></thead>
            <tbody><row><entry colname="c1">1</entry><entry colname="c2">2</entry></row></tbody>
          </tgroup>
        </ce:table>
      </ce:section></ce:sections></body></article></xocs:serial-item>
    </xocs:doc>
  </originalText>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("- A: 1; B: 2", markdown)
        self.assertIn(
            "cell text was retained as a readable list",
            markdown,
        )
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": "10.1016/test", "title": "Table fallback"},
            xml_body=xml_body,
            xml_path=Path("10.1016_test.xml"),
            assets=[],
        )
        assert structure is not None
        self.assertEqual(structure.semantic_losses.table_fallback_count, 1)
        self.assertEqual(structure.semantic_losses.table_layout_degraded_count, 1)
        self.assertEqual(structure.semantic_losses.table_semantic_loss_count, 0)

    def test_elsevier_real_complex_table_records_successful_normalization(
        self,
    ) -> None:
        """rule: rule-elsevier-complex-table-span-degradation"""
        doi = "10.1016/j.jhydrol.2021.126210"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.jhydrol.2021.126210.xml"),
            assets=[],
        )

        assert structure is not None
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            semantic_losses=structure.semantic_losses,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        self.assertEqual(article.quality.semantic_losses.table_layout_degraded_count, 0)
        self.assertNotIn("table_layout_degraded", article.quality.flags)
        self.assertFalse(
            any(note.startswith("- Table 1:") for note in structure.conversion_notes)
        )

    def test_elsevier_inline_boundary_newlines_are_normalized(self) -> None:
        fragment = ET.fromstring(
            """
<fragment xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  Fig. 2<ce:break/>, Table 1<ce:break/>) and <ce:italic>HD</ce:italic><ce:break/>1 were normalized.
</fragment>
"""
        )

        text = render_inline_text(fragment)

        self.assertIn("Fig. 2, Table 1) and *HD*<sub>1</sub> were normalized.", text)
        self.assertNotIn("Fig. 2\n,", text)
        self.assertNotIn("Table 1\n)", text)

    def test_elsevier_xml_formatting_newlines_do_not_split_inline_operators(
        self,
    ) -> None:
        fragment = ET.fromstring(
            """
<fragment xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <ce:italic>r</ce:italic>
  <ce:hsp sp="0.25"/>=1.00; <ce:italic>T<ce:inf>leaf &lt;</ce:inf>
  <ce:hsp sp="0.25"/>T<ce:inf>air</ce:inf></ce:italic>.
</fragment>
"""
        )

        text = render_inline_text(fragment)

        self.assertEqual(text, "*r* =1.00; *Tleaf < Tair*.")
        self.assertNotIn("*r*\n=", text)
        self.assertNotIn("<\n", text)

    def _render_real_elsevier_appendix_markdown(self) -> str:
        return _render_elsevier_golden_markdown(
            "10.1016/j.rse.2026.115369",
            assets=[
                {
                    "asset_type": "appendix_image",
                    "source_ref": "fx1",
                    "path": "figure-a1.jpg",
                }
            ],
        )

    def _assert_real_elsevier_appendix_figure_renders_as_figure_block(self) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        appendix_section = markdown[markdown.index("### Appendix") :]

        self.assertIn("![Figure A.1](figure-a1.jpg)", appendix_section)
        self.assertIn(
            "Map of the locations of the offshore wind farms Vindeby, Horns Rev. 1, and Alpha Ventus, and three FINO meteorological masts.",
            appendix_section,
        )

    def _assert_real_elsevier_appendix_figure_stays_in_appendix_when_referenced_from_body(
        self,
    ) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        body_reference_idx = markdown.index("Fig. A.1 indicates locations.")
        appendix_idx = markdown.index("### Appendix")
        figure_idx = markdown.index("![Figure A.1](figure-a1.jpg)")

        self.assertLess(body_reference_idx, appendix_idx)
        self.assertLess(appendix_idx, figure_idx)

    def _assert_real_elsevier_appendix_table_renders_as_markdown_table(self) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        appendix_section = markdown[markdown.index("### Appendix") :]

        self.assertIn("Table A.1", appendix_section)
        self.assertIn(
            "List of publications on SAR-based wind resources using Envisat ASAR, ERS, and R-1.",
            appendix_section,
        )
        _assert_markdown_table_row(
            self,
            appendix_section,
            ["Reference", "SAR", "Location"],
            allow_more_cells=True,
        )

    def test_elsevier_appendix_figure_renders_as_figure_block(self) -> None:
        """rule: rule-elsevier-appendix-context"""
        self._assert_real_elsevier_appendix_figure_renders_as_figure_block()

    def test_elsevier_appendix_reference_keeps_asset_in_appendix(self) -> None:
        """rule: rule-elsevier-appendix-context"""
        self._assert_real_elsevier_appendix_figure_stays_in_appendix_when_referenced_from_body()

    def test_elsevier_appendix_table_renders_as_markdown_table(self) -> None:
        """rule: rule-elsevier-appendix-context"""
        self._assert_real_elsevier_appendix_table_renders_as_markdown_table()

    def test_supplementary_display_is_omitted_from_body_and_listed_with_caption(
        self,
    ) -> None:
        """rule: rule-elsevier-supplementary-materials"""
        xml_body = _load_elsevier_scenario_xml("elsevier_supplementary_display")

        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "supp.pdf"
            markdown = build_elsevier_markdown(
                xml_body,
                assets=[
                    {
                        "asset_type": "supplementary",
                        "source_ref": "mmc1",
                        "path": str(asset_path),
                    }
                ],
            )

        self.assertIn("### Results", markdown)
        self.assertIn("Core body text.", markdown)
        self.assertNotIn("### Supplementary data", markdown)
        self.assertNotIn("$$", markdown)
        self.assertIn("## Supplementary Materials", markdown)
        self.assertIn("[Supplementary material 1](supp.pdf): Extra dataset.", markdown)

    def test_supplementary_asset_without_display_is_listed_as_supplementary_material(
        self,
    ) -> None:
        """rule: rule-elsevier-supplementary-materials"""
        xml_body = _load_elsevier_scenario_xml("elsevier_supplementary_asset_only")

        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "dataset.xlsx"
            markdown = build_elsevier_markdown(
                xml_body,
                assets=[
                    {
                        "asset_type": "supplementary",
                        "source_ref": "mmc2",
                        "path": str(asset_path),
                    }
                ],
            )

        self.assertIn("Core body text.", markdown)
        self.assertIn("## Supplementary Materials", markdown)
        self.assertIn("[dataset.xlsx](dataset.xlsx)", markdown)
        self.assertNotIn("## Additional Figures", markdown)

    def test_real_supplementary_e_component_from_golden_xml_is_listed(self) -> None:
        """rule: rule-elsevier-supplementary-materials"""
        markdown = _render_elsevier_golden_markdown(
            "10.1016/j.ecolind.2024.112140",
            assets=[
                {
                    "asset_type": "supplementary",
                    "source_ref": "mmc1",
                    "path": "mmc1.docx",
                }
            ],
        )

        self.assertNotIn("### Supplementary data", markdown)
        self.assertIn("## Supplementary Materials", markdown)
        self.assertIn("[Supplementary Data 1](mmc1.docx)", markdown)

    def test_split_inline_variable_subscripts_are_rejoined_in_paragraphs(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Methods</ce:section-title>
        <ce:para>where <ce:italic>x</ce:italic>
<ce:italic>i</ce:italic>
and <ce:italic>x</ce:italic>
<ce:italic>j</ce:italic>
represent the grid unit values, and <ce:italic>t</ce:italic>
<ce:italic>m</ce:italic>
refers to the tie.</ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn(
            "where *x*<sub>i</sub> and *x*<sub>j</sub> represent the grid unit values",
            markdown,
        )
        self.assertIn("*t*<sub>m</sub> refers to the tie.", markdown)
        self.assertNotIn("where *x*\n*i*", markdown)
        self.assertNotIn("and *x*\n*j*", markdown)

    def test_graphical_abstract_assets_do_not_appear_in_additional_figures(
        self,
    ) -> None:
        """rule: rule-elsevier-graphical-abstract"""
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:xlink="http://www.w3.org/1999/xlink">
  <abstract>
    <ce:section>
      <ce:section-title>Graphical abstract</ce:section-title>
      <ce:para>
        <ce:display>
          <ce:figure id="gafig">
            <ce:label>Graphical Abstract</ce:label>
            <ce:link locator="ga1" xlink:type="simple" xlink:href="pii:test/ga1" />
          </ce:figure>
        </ce:display>
      </ce:para>
    </ce:section>
  </abstract>
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Body text only.</ce:para>
      </ce:section>
    </ce:sections>
    <ce:floats>
      <ce:figure id="f001">
        <ce:label>Fig. 1</ce:label>
        <ce:caption>
          <ce:simple-para>Body figure caption.</ce:simple-para>
        </ce:caption>
        <ce:link locator="gr1" xlink:type="simple" xlink:href="pii:test/gr1" />
      </ce:figure>
    </ce:floats>
  </body>
</full-text-retrieval-response>
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            body_path = Path(tmpdir) / "body.jpg"
            ga_path = Path(tmpdir) / "ga.jpg"
            markdown = build_elsevier_markdown(
                xml_body,
                assets=[
                    {
                        "asset_type": "image",
                        "source_ref": "gr1",
                        "path": str(body_path),
                    },
                    {
                        "asset_type": "graphical_abstract",
                        "source_ref": "ga1",
                        "path": str(ga_path),
                    },
                ],
            )

        self.assertIn("## Additional Figures", markdown)
        self.assertIn("### Fig. 1", markdown)
        self.assertIn("Body figure caption.", markdown)
        self.assertNotIn("Graphical Abstract", markdown)
        self.assertNotIn("ga.jpg", markdown)

    def test_graphical_abstract_only_document_does_not_create_additional_figures(
        self,
    ) -> None:
        """rule: rule-elsevier-graphical-abstract"""
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:xlink="http://www.w3.org/1999/xlink">
  <abstract>
    <ce:section>
      <ce:section-title>Graphical abstract</ce:section-title>
      <ce:para>
        <ce:display>
          <ce:figure id="gafig">
            <ce:label>Graphical Abstract</ce:label>
            <ce:link locator="ga1" xlink:type="simple" xlink:href="pii:test/ga1" />
          </ce:figure>
        </ce:display>
      </ce:para>
    </ce:section>
  </abstract>
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Body text only.</ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            ga_path = Path(tmpdir) / "ga.jpg"
            markdown = build_elsevier_markdown(
                xml_body,
                assets=[
                    {
                        "asset_type": "graphical_abstract",
                        "source_ref": "ga1",
                        "path": str(ga_path),
                    }
                ],
            )

        self.assertIn("Body text only.", markdown)
        self.assertNotIn("## Additional Figures", markdown)
        self.assertNotIn("Graphical Abstract", markdown)
        self.assertNotIn("ga.jpg", markdown)

    def test_real_graphical_abstract_from_golden_xml_is_excluded_from_figures(
        self,
    ) -> None:
        """rule: rule-elsevier-graphical-abstract"""
        doi = "10.1016/j.scitotenv.2022.158499"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.scitotenv.2022.158499.xml"),
            assets=[
                {
                    "asset_type": "image",
                    "source_ref": "gr1",
                    "path": "gr1.jpg",
                },
                {
                    "asset_type": "graphical_abstract",
                    "source_ref": "ga1",
                    "path": "ga1.jpg",
                },
            ],
        )

        assert structure is not None
        self.assertTrue(
            any(entry["path"] == "gr1.jpg" for entry in structure.figure_entries)
        )
        self.assertFalse(
            any(entry["path"] == "ga1.jpg" for entry in structure.figure_entries)
        )

    def _render_real_elsevier_body_table_markdown(self) -> str:
        return _render_elsevier_golden_markdown("10.1016/j.jhydrol.2021.126210")

    def _assert_real_elsevier_body_table_is_inserted_near_reference(self) -> None:
        markdown = self._render_real_elsevier_body_table_markdown()
        reference_idx = markdown.index(
            "The detailed information on the hydro-meteorological data is given in Table 1"
        )
        caption_idx = markdown.index("Study area and data used in this study.")
        header_match = re.search(
            r"(?m)^\|\s*Type\s*\|\s*Location\s*\|\s*Station\s*\|", markdown
        )
        self.assertIsNotNone(header_match)
        assert header_match is not None
        header_idx = header_match.start()

        self.assertLess(reference_idx, caption_idx)
        self.assertLess(caption_idx, header_idx)
        self.assertLess(header_idx - reference_idx, 500)

    def _assert_real_elsevier_complex_body_table_prefers_normalized_markdown_over_image_fallback(
        self,
    ) -> None:
        markdown = self._render_real_elsevier_body_table_markdown()

        _assert_markdown_table_row(
            self,
            markdown,
            [
                "Hydrometric",
                "China",
                "Jiuzhou",
                "385",
                "1960–2006",
                "23°04′12″N",
                "114°35′24″E",
                "Water Conservancy and Electric Power Bureau, Guangdong Province, China",
            ],
            allow_more_cells=True,
        )
        self.assertNotIn("Merged table spans were semantically expanded", markdown)
        self.assertNotIn("- Table 1: None", markdown)
        self.assertNotIn("![Table 1]", markdown)

    def _assert_real_elsevier_consumed_table_is_not_appended_by_article_model(
        self,
    ) -> None:
        doi = "10.1016/j.jhydrol.2021.126210"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.jhydrol.2021.126210.xml"),
            assets=[],
        )

        assert structure is not None
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            semantic_losses=structure.semantic_losses,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        rendered = article.to_ai_markdown(asset_profile="body")

        self.assertTrue(
            any(
                asset.kind == "table" and asset.render_state == "inline"
                for asset in article.assets
            )
        )
        self.assertEqual(article.quality.semantic_losses.table_layout_degraded_count, 0)
        self.assertEqual(article.quality.semantic_losses.table_lossy_count, 0)
        self.assertNotIn("table_layout_degraded", article.quality.flags)
        self.assertNotIn("table_semantic_loss", article.quality.flags)
        self.assertNotIn("## Additional Tables", rendered)
        self.assertEqual(rendered.count("Study area and data used in this study."), 1)

    def _assert_unreferenced_body_table_is_listed_in_additional_tables(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Main text only.</ce:para>
      </ce:section>
    </ce:sections>
    <ce:floats>
      <ce:table id="t0005">
        <ce:label>Table 1</ce:label>
        <ce:caption>
          <ce:simple-para>Floating table.</ce:simple-para>
        </ce:caption>
        <tgroup cols="2">
          <thead>
            <row>
              <entry>A</entry>
              <entry>B</entry>
            </row>
          </thead>
          <tbody>
            <row>
              <entry>1</entry>
              <entry>2</entry>
            </row>
          </tbody>
        </tgroup>
      </ce:table>
    </ce:floats>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("Main text only.", markdown)
        self.assertIn("## Additional Tables", markdown)
        self.assertIn("Floating table.", markdown)
        _assert_markdown_table_row(self, markdown, ["A", "B"])

    def test_elsevier_golden_fixture_classifies_data_and_code_availability_sections(
        self,
    ) -> None:
        """rule: rule-availability-section-kind-mapping"""
        doi = "10.1016/j.rse.2025.114648"
        markdown = _render_elsevier_golden_markdown(doi)
        article = article_from_markdown(
            source="elsevier_xml",
            metadata={"title": f"Elsevier Golden Fixture {doi}"},
            doi=doi,
            markdown_text=markdown,
        )

        section_pairs = [
            (section.heading, section.kind) for section in article.sections
        ]
        self.assertIn(("Data availability", "data_availability"), section_pairs)
        self.assertIn(("Code availability", "code_availability"), section_pairs)

    def test_elsevier_table_placement_contracts(self) -> None:
        cases = [
            (
                "real_body_table_inserted_near_reference",
                self._assert_real_elsevier_body_table_is_inserted_near_reference,
            ),
            (
                "real_complex_body_table_prefers_normalized_markdown",
                self._assert_real_elsevier_complex_body_table_prefers_normalized_markdown_over_image_fallback,
            ),
            (
                "real_consumed_table_not_appended_by_article_model",
                self._assert_real_elsevier_consumed_table_is_not_appended_by_article_model,
            ),
            (
                "synthetic_unreferenced_float_table",
                self._assert_unreferenced_body_table_is_listed_in_additional_tables,
            ),
        ]

        for label, assertion in cases:
            with self.subTest(label=label):
                assertion()

    def test_xml_multilingual_abstract_preserves_parallel_abstract_sections(
        self,
    ) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <abstract>
    <ce:section xml:lang="en">
      <ce:section-title>Abstract</ce:section-title>
      <ce:para>English abstract that should remain in the rendered markdown output.</ce:para>
    </ce:section>
    <ce:section xml:lang="pt">
      <ce:section-title>Resumo</ce:section-title>
      <ce:para>Resumo em portugues que deve permanecer como uma segunda secao de resumo.</ce:para>
    </ce:section>
  </abstract>
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>English results paragraph that should remain in the final markdown output.</ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("## Abstract", markdown)
        self.assertIn("## Resumo", markdown)
        self.assertIn("English abstract that should remain", markdown)
        self.assertIn("Resumo em portugues que deve permanecer", markdown)
        self.assertIn("English results paragraph that should remain", markdown)

    def test_xml_non_english_only_article_is_preserved(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <abstract xml:lang="pt">
    <ce:section>
      <ce:section-title>Resumo</ce:section-title>
      <ce:para>Resumo em portugues que deve permanecer porque nao existe variante paralela em outro idioma.</ce:para>
    </ce:section>
  </abstract>
  <body>
    <ce:sections>
      <ce:section xml:lang="pt">
        <ce:section-title>Resultados</ce:section-title>
        <ce:para>Texto principal em portugues que deve permanecer no markdown final.</ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("## Abstract", markdown)
        self.assertIn("Resumo em portugues que deve permanecer", markdown)
        self.assertIn("### Resultados", markdown)
        self.assertIn("Texto principal em portugues que deve permanecer", markdown)


if __name__ == "__main__":
    unittest.main()
