from __future__ import annotations
from __future__ import annotations
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset
from paper_fetch.models import article_from_structure
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.providers import (
    _article_markdown_elsevier_document as elsevier_document,
)
from pathlib import Path
import xml.etree.ElementTree as ET
import unittest
import tempfile
import re
from paper_fetch.providers._article_markdown_common import render_inline_text
from paper_fetch.providers import _article_markdown_xml as article_markdown_xml
from paper_fetch.providers import _elsevier_objects as elsevier_objects
from paper_fetch.providers import _elsevier_xml_rules as elsevier_rules
from paper_fetch.providers import _article_markdown_math as article_markdown_math
from paper_fetch.runtime import RuntimeContext


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
    def test_xml_name_matching_preserves_provider_specific_name_forms(self) -> None:
        self.assertEqual(article_markdown_xml.xml_local_name("title"), "title")
        self.assertEqual(
            article_markdown_xml.xml_local_name("{urn:paper-fetch:test}title"),
            "title",
        )
        self.assertEqual(
            article_markdown_xml.xml_local_name("ce:title"),
            "ce:title",
        )

        colon_only = ET.Element("root")
        colon_only.append(ET.Comment("non-element nodes must remain ignored"))
        ET.SubElement(colon_only, "ce:title").text = "Colon title"
        self.assertIsNone(article_markdown_xml.first_child(colon_only, "title"))

        for style, prefix in (
            ("plain", ""),
            ("clark", "{urn:paper-fetch:test}"),
            ("colon", "ce:"),
        ):
            with self.subTest(style=style):
                root = ET.Element("root")
                root.append(ET.Comment("non-element nodes must remain ignored"))
                formula = ET.SubElement(root, f"{prefix}formula")
                ET.SubElement(
                    formula,
                    f"{prefix}link",
                    {"locator": "fx1"},
                )
                resource = ET.SubElement(
                    root,
                    f"{prefix}object",
                    {
                        "ref": "fx1_lrg.jpg",
                        "type": "IMAGE-HIGH-RES",
                        "mimetype": "image/jpeg",
                    },
                )
                resource.text = f"https://example.test/{style}.jpg"

                references = elsevier_objects.extract_elsevier_object_references(root)

                self.assertEqual(len(references), 1)
                self.assertEqual(references[0]["asset_type"], "image")
                self.assertEqual(
                    references[0]["source_url"],
                    f"https://example.test/{style}.jpg",
                )

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

    def test_elsevier_asset_group_recognizes_author_manuscript_aliases(self) -> None:
        for value in (
            "am",
            "am.pdf",
            "1-s2.0-S1470160X24005971-am",
            "1-s2.0-S1470160X24005971-am.pdf",
            " AM.PDF ",
            "https://api.elsevier.com/content/object/eid/1-s2.0-S1470160X24005971-AM.PDF?httpAccept=%2A%2F%2A#download",
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    elsevier_rules.infer_elsevier_asset_group_key(value), "am"
                )
        for value, expected in (
            ("am1.docx", "am1"),
            ("1-s2.0-S1470160X24005971-am1.docx", "am1"),
            ("frame123.pdf", "frame123.pdf"),
            ("am.docx", "am.docx"),
            ("exam.pdf", "exam.pdf"),
            ("paper-am.pdf", "paper-am.pdf"),
            (
                "1-s2.0-S1470160X24005971-am.pdf.bak",
                "1-s2.0-s1470160x24005971-am.pdf.bak",
            ),
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    elsevier_rules.infer_elsevier_asset_group_key(value), expected
                )
        self.assertTrue(
            elsevier_rules.should_ignore_elsevier_section_title("Graphical Abstract")
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

    def test_xml_sibling_abstracts_preserve_structured_paragraphs_in_source_order(
        self,
    ) -> None:
        xml_body = b"""<article xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <ce:abstract>
    <ce:abstract-sec><ce:simple-para>Introduccion breve.</ce:simple-para></ce:abstract-sec>
    <ce:abstract-sec><ce:section-title>Objetivo</ce:section-title>
      <ce:simple-para>Evaluar <ce:italic>habilidades</ce:italic>.</ce:simple-para>
    </ce:abstract-sec>
  </ce:abstract>
  <ce:abstract xml:lang="en">
    <ce:abstract-sec><ce:section-title>Introduction</ce:section-title>
      <ce:simple-para>Short introduction.</ce:simple-para>
    </ce:abstract-sec>
    <ce:abstract-sec><ce:section-title>Objective</ce:section-title>
      <ce:simple-para>Assess <ce:italic>skills</ce:italic>.</ce:simple-para>
    </ce:abstract-sec>
  </ce:abstract>
  <body><ce:para>Body text.</ce:para></body>
</article>"""
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"abstract": "Metadata fallback must not replace XML abstracts."},
            xml_body=xml_body,
            xml_path=Path("article.xml"),
            assets=[],
        )

        self.assertIsNotNone(structure)
        assert structure is not None
        self.assertEqual(
            structure.abstract_lines,
            [
                "Introduccion breve.",
                "",
                "### Objetivo",
                "",
                "Evaluar *habilidades*.",
                "",
                "### Introduction",
                "",
                "Short introduction.",
                "",
                "### Objective",
                "",
                "Assess *skills*.",
                "",
            ],
        )
        self.assertEqual(structure.body_lines, ["Body text.", ""])

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

    def test_elsevier_inline_math_symbols_stay_inline(self) -> None:
        self._assert_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks()

    def test_elsevier_formula_placeholder_is_visible_when_conversion_fails(
        self,
    ) -> None:
        self._assert_formula_placeholder_is_visible_and_counted_when_conversion_fails()

    def test_elsevier_complex_table_spans_are_normalized_without_quality_loss(
        self,
    ) -> None:
        xml_body = _load_elsevier_scenario_xml("elsevier_complex_table_span")

        markdown = build_elsevier_markdown(xml_body)

        _assert_markdown_table_row(
            self, markdown, ["Station group", "Station group", "Value"]
        )
        _assert_markdown_table_row(self, markdown, ["Hydrometric", "Station A", "10"])
        _assert_markdown_table_row(self, markdown, ["Hydrometric", "Station B", "20"])
        self.assertNotIn("Merged table spans were semantically expanded", markdown)

    def test_supplementary_display_is_omitted_from_body_and_listed_with_caption(
        self,
    ) -> None:
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


if __name__ == "__main__":
    unittest.main()


def test_elsevier_mathml_altimg_does_not_create_supplements_from_either_representation() -> (
    None
):
    xml = b"""<article xmlns:m="http://www.w3.org/1998/Math/MathML">
    <object ref="si1" type="ALTIMG" category="thumbnail">https://example.test/si1.svg</object>
    <attachment><attachment-type>ALTIMG</attachment-type><attachment-eid>1-s2.0-test-si1</attachment-eid><filename>si1.svg</filename></attachment>
    <m:math altimg="si1.svg"><m:mi>x</m:mi></m:math>
    <object ref="si2" type="SUPPLEMENTARY">https://example.test/si2.pdf</object>
    <attachment><attachment-eid>1-s2.0-test-si2</attachment-eid><filename>si2.pdf</filename></attachment>
    </article>"""
    refs = elsevier_provider.extract_elsevier_asset_references(xml)
    assert len(refs) == 1
    assert refs[0]["source_ref"] == "si2"
    assert refs[0]["asset_type"] == "supplementary"


def test_supplement_identity_survives_asset_order_and_article_rendering(tmp_path):
    from paper_fetch.providers._article_markdown_elsevier import (
        elsevier_supplement_entries,
    )

    root = ET.fromstring("""<article>
      <e-component><label>Supporting DOCX</label><caption>Methods</caption><link locator="mmc1"/></e-component>
      <e-component><label>Supporting PDF</label><caption>Data</caption><link locator="mmc2"/></e-component>
    </article>""")
    assets = [
        {"asset_type": "supplementary", "source_ref": ref, "path": str(tmp_path / name)}
        for ref, name in [("mmc1", "methods.docx"), ("mmc2", "data.pdf")]
    ]
    for ordered in (assets, assets[::-1]):
        entries = elsevier_supplement_entries(root, ordered, tmp_path / "article.md")
        assert [(e["heading"], e["link"], e["path"]) for e in entries] == [
            ("Supporting DOCX", "methods.docx", str(tmp_path / "methods.docx")),
            ("Supporting PDF", "data.pdf", str(tmp_path / "data.pdf")),
        ]
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": "10.1016/test", "title": "Test"},
            doi="10.1016/test",
            abstract_lines=[],
            body_lines=["Body text."],
            figure_entries=[],
            table_entries=[],
            supplement_entries=entries,
            conversion_notes=[],
        )
        assert [a.path for a in article.assets] == [a["path"] for a in assets]
        markdown = article.to_ai_markdown(max_tokens="full_text", asset_profile="all")
        assert f"[Supporting DOCX]({tmp_path / 'methods.docx'})" in markdown
        assert f"[Supporting PDF]({tmp_path / 'data.pdf'})" in markdown


if __name__ == "__main__":
    unittest.main()
