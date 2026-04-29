from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from paper_fetch.providers._article_markdown_common import render_inline_text
from paper_fetch.providers import _article_markdown_elsevier_document as elsevier_document
from paper_fetch.providers import _article_markdown_math as article_markdown_math
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


class ElsevierMarkdownTests(unittest.TestCase):
    def test_elsevier_document_module_remains_importable(self) -> None:
        self.assertTrue(callable(elsevier_document.build_article_structure))
        self.assertTrue(callable(elsevier_document.build_markdown_document))
        self.assertTrue(callable(elsevier_document.write_article_markdown))
        self.assertTrue(callable(article_markdown_math.render_mathml_expression))

    def test_build_article_structure_extracts_authors_from_author_groups(self) -> None:
        xml_body = golden_criteria_scenario_asset("elsevier_author_groups_minimal", "original.xml").read_bytes()

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
        self.assertEqual(structure.authors, ["Jane Doe", "Smith, J.", "Open Climate Consortium"])

    def test_build_article_structure_extracts_numbered_xml_references(self) -> None:
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
        self.assertIn("Spatiotemporal patterns of terrestrial gross primary production: a review", first_reference.raw)
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
        self.assertNotIn("- Spatiotemporal patterns of terrestrial gross primary production: a review", rendered)

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
        self.assertEqual(references[1].raw, "2. Raw fallback reference text for the second citation.")
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
            metadata={"doi": "10.1016/figure-preserve", "title": "Elsevier Figure Preserve"},
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
            metadata={"doi": "10.1016/figure-preserve", "title": "Elsevier Figure Preserve"},
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

        self.assertEqual(rendered.count("![Fig. 1](body_assets/figure-preserve-fig1.jpeg)"), 1)
        self.assertIn("Observed response figure.", rendered)
        self.assertNotIn("## Additional Figures", rendered)

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
        self.assertIn("$$\nF_{crit} = \\sum\\limits_{t_{p}}^{SOS_{y0}}R_{f}\n$$", markdown)
        self.assertLess(markdown.index("(26)"), markdown.index("$$"))

    def _assert_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:mml="http://www.w3.org/1998/Math/MathML">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Climate data</ce:section-title>
        <ce:para>Air temperature (<mml:math><mml:mi>T</mml:mi></mml:math>) and dewpoint temperature (<mml:math><mml:msub><mml:mi>T</mml:mi><mml:mi>d</mml:mi></mml:msub></mml:math>) were used:<ce:display><ce:formula id="fo1"><ce:label>(1)</ce:label><mml:math><mml:mi>VPD</mml:mi><mml:mo>=</mml:mo><mml:mi>T</mml:mi></mml:math></ce:formula></ce:display>where <mml:math><mml:msub><mml:mi>c</mml:mi><mml:mn>1</mml:mn></mml:msub></mml:math> is constant.</ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("Air temperature ($T$) and dewpoint temperature ($T_{d}$) were used:", markdown)
        self.assertIn("where $c_{1}$ is constant.", markdown)
        self.assertRegex(markdown, r"\$\$\n\{?VPD\}? = T\n\$\$")
        self.assertNotIn("$$\nT\n$$", markdown)
        self.assertNotIn("$$\nT_{d}\n$$", markdown)
        self.assertNotIn("$$\nc_{1}\n$$", markdown)

    def _assert_formula_placeholder_is_visible_and_counted_when_conversion_fails(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Methods</ce:section-title>
        <ce:para>
          <ce:display>
            <ce:formula id="fo1">
              <ce:label>(1)</ce:label>
            </ce:formula>
          </ce:display>
        </ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

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

    def test_elsevier_formula_rendering_contracts(self) -> None:
        cases = [
            ("real_display_formula", self._assert_real_elsevier_display_formula_renders_as_formula_block),
            ("inline_math_stays_inline", self._assert_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks),
            ("formula_placeholder_on_failure", self._assert_formula_placeholder_is_visible_and_counted_when_conversion_fails),
        ]

        for label, assertion in cases:
            with self.subTest(label=label):
                assertion()

    def test_elsevier_complex_table_spans_are_semantically_expanded(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Data</ce:section-title>
        <ce:display>
          <ce:table id="tbl1">
            <ce:label>Table 1</ce:label>
            <ce:caption>Grouped station data.</ce:caption>
            <ce:tgroup cols="3">
              <ce:colspec colname="c1" />
              <ce:colspec colname="c2" />
              <ce:colspec colname="c3" />
              <ce:thead>
                <ce:row>
                  <ce:entry namest="c1" nameend="c2">Station group</ce:entry>
                  <ce:entry>Value</ce:entry>
                </ce:row>
              </ce:thead>
              <ce:tbody>
                <ce:row>
                  <ce:entry morerows="1">Hydrometric</ce:entry>
                  <ce:entry>Station A</ce:entry>
                  <ce:entry>10</ce:entry>
                </ce:row>
                <ce:row>
                  <ce:entry>Station B</ce:entry>
                  <ce:entry>20</ce:entry>
                </ce:row>
              </ce:tbody>
            </ce:tgroup>
          </ce:table>
        </ce:display>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("| Station group | Station group | Value |", markdown)
        self.assertIn("| Hydrometric | Station A | 10 |", markdown)
        self.assertIn("| Hydrometric | Station B | 20 |", markdown)
        self.assertIn("Merged table spans were semantically expanded", markdown)

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

        self.assertIn("![Fig. A.1](figure-a1.jpg)", appendix_section)
        self.assertIn(
            "Map of the locations of the offshore wind farms Vindeby, Horns Rev. 1, and Alpha Ventus, and three FINO meteorological masts.",
            appendix_section,
        )

    def _assert_real_elsevier_appendix_figure_stays_in_appendix_when_referenced_from_body(self) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        body_reference_idx = markdown.index("Fig. A.1 indicates locations.")
        appendix_idx = markdown.index("### Appendix")
        figure_idx = markdown.index("![Fig. A.1](figure-a1.jpg)")

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
        self.assertIn("| Reference | SAR | Location |", appendix_section)

    def test_elsevier_appendix_context_contracts(self) -> None:
        cases = [
            ("real_appendix_figure", self._assert_real_elsevier_appendix_figure_renders_as_figure_block),
            (
                "real_appendix_reference_stays_in_body",
                self._assert_real_elsevier_appendix_figure_stays_in_appendix_when_referenced_from_body,
            ),
            ("real_appendix_table", self._assert_real_elsevier_appendix_table_renders_as_markdown_table),
        ]

        for label, assertion in cases:
            with self.subTest(label=label):
                assertion()

    def test_supplementary_display_is_omitted_from_body_and_listed_with_caption(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Core body text.</ce:para>
      </ce:section>
      <ce:section>
        <ce:section-title>Supplementary data</ce:section-title>
        <ce:para>
          <ce:display>
            <ce:e-component id="ec1">
              <ce:label>Supplementary material 1</ce:label>
              <ce:caption>
                <ce:simple-para>Extra dataset.</ce:simple-para>
              </ce:caption>
              <ce:link locator="mmc1" />
            </ce:e-component>
          </ce:display>
        </ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

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

        self.assertIn("where *x*<sub>i</sub> and *x*<sub>j</sub> represent the grid unit values", markdown)
        self.assertIn("*t*<sub>m</sub> refers to the tie.", markdown)
        self.assertNotIn("where *x*\n*i*", markdown)
        self.assertNotIn("and *x*\n*j*", markdown)

    def test_graphical_abstract_assets_do_not_appear_in_additional_figures(self) -> None:
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

    def _render_real_elsevier_body_table_markdown(self) -> str:
        return _render_elsevier_golden_markdown("10.1016/j.jhydrol.2021.126210")

    def _assert_real_elsevier_body_table_is_inserted_near_reference(self) -> None:
        markdown = self._render_real_elsevier_body_table_markdown()
        reference_idx = markdown.index("The detailed information on the hydro-meteorological data is given in Table 1")
        caption_idx = markdown.index("Study area and data used in this study.")
        header_idx = markdown.index("| Type | Location | Station |")

        self.assertLess(reference_idx, caption_idx)
        self.assertLess(caption_idx, header_idx)
        self.assertLess(header_idx - reference_idx, 500)

    def _assert_real_elsevier_complex_body_table_prefers_lossy_markdown_over_image_fallback(self) -> None:
        markdown = self._render_real_elsevier_body_table_markdown()

        self.assertIn("| Hydrometric | China | Jiuzhou | 385 | 1960–2006 | 23°04′12″N | 114°35′24″E | Water Conservancy", markdown)
        self.assertIn("## Conversion Notes", markdown)
        self.assertIn(
            "- Table 1: Merged table spans were semantically expanded into rectangular Markdown cells; rowspan/colspan layout fidelity was reduced.",
            markdown,
        )
        self.assertNotIn("- Table 1: None", markdown)
        self.assertNotIn("![Table 1]", markdown)

    def _assert_real_elsevier_consumed_table_is_not_appended_by_article_model(self) -> None:
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

        self.assertTrue(any(asset.kind == "table" and asset.render_state == "inline" for asset in article.assets))
        self.assertGreater(article.quality.semantic_losses.table_layout_degraded_count, 0)
        self.assertEqual(article.quality.semantic_losses.table_lossy_count, 0)
        self.assertIn("table_layout_degraded", article.quality.flags)
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
        self.assertIn("| A | B |", markdown)

    def test_elsevier_golden_fixture_classifies_data_and_code_availability_sections(self) -> None:
        doi = "10.1016/j.rse.2025.114648"
        markdown = _render_elsevier_golden_markdown(doi)
        article = article_from_markdown(
            source="elsevier_xml",
            metadata={"title": f"Elsevier Golden Fixture {doi}"},
            doi=doi,
            markdown_text=markdown,
        )

        section_pairs = [(section.heading, section.kind) for section in article.sections]
        self.assertIn(("Data availability", "data_availability"), section_pairs)
        self.assertIn(("Code availability", "code_availability"), section_pairs)

    def test_elsevier_table_placement_contracts(self) -> None:
        cases = [
            ("real_body_table_inserted_near_reference", self._assert_real_elsevier_body_table_is_inserted_near_reference),
            (
                "real_complex_body_table_prefers_lossy_markdown",
                self._assert_real_elsevier_complex_body_table_prefers_lossy_markdown_over_image_fallback,
            ),
            ("real_consumed_table_not_appended_by_article_model", self._assert_real_elsevier_consumed_table_is_not_appended_by_article_model),
            ("synthetic_unreferenced_float_table", self._assert_unreferenced_body_table_is_listed_in_additional_tables),
        ]

        for label, assertion in cases:
            with self.subTest(label=label):
                assertion()

    def test_xml_multilingual_abstract_preserves_parallel_abstract_sections(self) -> None:
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
