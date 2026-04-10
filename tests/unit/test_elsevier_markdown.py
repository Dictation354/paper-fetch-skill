from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from paper_fetch.providers import _article_markdown as article_markdown


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
        markdown_path = article_markdown.write_article_markdown(
            provider="elsevier",
            metadata=article_metadata,
            xml_body=xml_body,
            output_dir=Path(tmpdir),
            xml_path=str(xml_path),
            assets=prepared_assets,
        )

        assert markdown_path is not None
        return Path(markdown_path).read_text(encoding="utf-8")


class ElsevierMarkdownTests(unittest.TestCase):
    def test_article_markdown_facade_exports_expected_helpers(self) -> None:
        self.assertTrue(callable(article_markdown.render_mathml_expression))
        self.assertTrue(callable(article_markdown.build_article_structure))
        self.assertTrue(callable(article_markdown.write_article_markdown))

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

        expression = article_markdown.render_mathml_expression(math_node)

        self.assertEqual(expression, "{NDVI_{d - w}}_{cli}")

    def test_display_formula_renders_as_formula_block(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:mml="http://www.w3.org/1998/Math/MathML">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Methods</ce:section-title>
        <ce:para>We define the index as follows:<ce:display><ce:formula id="fo1"><ce:label>(1)</ce:label><mml:math><mml:mi>EVI</mml:mi><mml:mo>=</mml:mo><mml:mfrac><mml:mrow><mml:mn>2.5</mml:mn><mml:mo>&#xd7;</mml:mo><mml:mi>NIR</mml:mi></mml:mrow><mml:mrow><mml:mi>RED</mml:mi></mml:mrow></mml:mfrac></mml:math></ce:formula></ce:display></ce:para>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(
            xml_body,
            metadata={"title": "Formula Example"},
        )

        self.assertIn("We define the index as follows:", markdown)
        self.assertIn("$$", markdown)
        self.assertRegex(markdown, r"\{?EVI\}? = \\frac\{2\.5 \\times \{?NIR\}?\}\{RED\}")
        self.assertIn("(1)", markdown)

    def test_appendix_display_figure_renders_as_figure_block(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:xlink="http://www.w3.org/1999/xlink">
  <body>
    <ce:appendices>
      <ce:section>
        <ce:section-title>Appendix</ce:section-title>
        <ce:para>
          <ce:display>
            <ce:figure id="f001">
              <ce:label>Fig. A1</ce:label>
              <ce:caption>
                <ce:simple-para>Appendix figure caption.</ce:simple-para>
              </ce:caption>
              <ce:link locator="fx1" xlink:type="simple" xlink:href="pii:test/fx1" />
            </ce:figure>
          </ce:display>
        </ce:para>
      </ce:section>
    </ce:appendices>
  </body>
</full-text-retrieval-response>
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "figure.jpg"
            markdown = build_elsevier_markdown(
                xml_body,
                metadata={"title": "Appendix Figure Example"},
                assets=[
                    {
                        "asset_type": "appendix_image",
                        "source_ref": "fx1",
                        "path": str(asset_path),
                    }
                ],
            )

        self.assertIn("### Appendix", markdown)
        self.assertIn("![Fig. A1](figure.jpg)", markdown)
        self.assertIn("Appendix figure caption.", markdown)
        self.assertNotIn("$$", markdown)

    def test_appendix_figure_stays_in_appendix_when_referenced_from_body(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:xlink="http://www.w3.org/1999/xlink">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>See Fig. A1 for details.</ce:para>
      </ce:section>
    </ce:sections>
    <ce:appendices>
      <ce:section>
        <ce:section-title>Appendix</ce:section-title>
        <ce:para>
          <ce:display>
            <ce:figure id="f001">
              <ce:label>Fig. A1</ce:label>
              <ce:caption>
                <ce:simple-para>Appendix figure caption.</ce:simple-para>
              </ce:caption>
              <ce:link locator="fx1" xlink:type="simple" xlink:href="pii:test/fx1" />
            </ce:figure>
          </ce:display>
        </ce:para>
      </ce:section>
    </ce:appendices>
  </body>
</full-text-retrieval-response>
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "figure.jpg"
            markdown = build_elsevier_markdown(
                xml_body,
                metadata={"title": "Appendix Heading Example"},
                assets=[
                    {
                        "asset_type": "appendix_image",
                        "source_ref": "fx1",
                        "path": str(asset_path),
                    }
                ],
            )

        self.assertIn("### Results", markdown)
        self.assertIn("See Fig. A1 for details.", markdown)
        self.assertIn("### Appendix", markdown)
        self.assertIn("![Fig. A1](figure.jpg)", markdown)
        self.assertEqual(markdown.count("![Fig. A1](figure.jpg)"), 1)
        self.assertLess(markdown.index("### Results"), markdown.index("### Appendix"))
        self.assertLess(markdown.index("### Appendix"), markdown.index("![Fig. A1](figure.jpg)"))

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

    def test_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks(self) -> None:
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

    def test_body_table_is_inserted_near_reference(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Performance is summarized in <ce:cross-ref refid="t0005">Table 1</ce:cross-ref><ce:float-anchor refid="t0005"/>.</ce:para>
        <ce:table id="t0005">
          <ce:label>Table 1</ce:label>
          <ce:caption>
            <ce:simple-para>Model performance.</ce:simple-para>
          </ce:caption>
          <tgroup cols="2">
            <thead>
              <row>
                <entry>Metric</entry>
                <entry>Value</entry>
              </row>
            </thead>
            <tbody>
              <row>
                <entry>RMSE</entry>
                <entry>1.2</entry>
              </row>
            </tbody>
          </tgroup>
          <ce:legend>
            <ce:simple-para>Values are means.</ce:simple-para>
          </ce:legend>
        </ce:table>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("Performance is summarized in Table 1.", markdown)
        self.assertIn("Table 1", markdown)
        self.assertIn("Model performance.", markdown)
        self.assertIn("| Metric | Value |", markdown)
        self.assertIn("| RMSE | 1.2 |", markdown)
        self.assertIn("Values are means.", markdown)
        self.assertNotIn("## Additional Tables", markdown)

    def test_complex_body_table_uses_image_fallback_and_conversion_notes(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd" xmlns:xlink="http://www.w3.org/1999/xlink">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>See <ce:cross-ref refid="t0005">Table 1</ce:cross-ref> for the full layout.</ce:para>
        <ce:table id="t0005">
          <ce:label>Table 1</ce:label>
          <ce:caption>
            <ce:simple-para>Complex layout.</ce:simple-para>
          </ce:caption>
          <ce:link locator="tbl1" xlink:type="simple" xlink:href="pii:test/tbl1" />
          <tgroup cols="2">
            <tbody>
              <row>
                <entry morerows="1">Merged</entry>
                <entry>B</entry>
              </row>
              <row>
                <entry>C</entry>
              </row>
            </tbody>
          </tgroup>
          <ce:legend>
            <ce:simple-para>Original note.</ce:simple-para>
          </ce:legend>
        </ce:table>
      </ce:section>
    </ce:sections>
  </body>
</full-text-retrieval-response>
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "tbl1.png"
            markdown = build_elsevier_markdown(
                xml_body,
                assets=[
                    {
                        "asset_type": "table_asset",
                        "source_ref": "tbl1",
                        "path": str(asset_path),
                    }
                ],
            )

        self.assertIn("![Table 1](tbl1.png)", markdown)
        self.assertIn("Original note.", markdown)
        self.assertIn("## Conversion Notes", markdown)
        self.assertIn(
            "- Table 1: Table content could not be fully converted to Markdown; the original table image is retained below.",
            markdown,
        )
        self.assertLess(markdown.index("![Table 1](tbl1.png)"), markdown.index("## Conversion Notes"))

    def test_unreferenced_body_table_is_listed_in_additional_tables(self) -> None:
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

    def test_appendix_display_table_renders_as_markdown_table(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:appendices>
      <ce:section>
        <ce:section-title>Appendix</ce:section-title>
        <ce:para>
          <ce:display>
            <ce:table id="tblA1">
              <ce:label>Table A1</ce:label>
              <ce:caption>
                <ce:simple-para>Appendix table caption.</ce:simple-para>
              </ce:caption>
              <tgroup cols="2">
                <thead>
                  <row>
                    <entry>Column A</entry>
                    <entry>Column B</entry>
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
          </ce:display>
        </ce:para>
      </ce:section>
    </ce:appendices>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("### Appendix", markdown)
        self.assertIn("Table A1", markdown)
        self.assertIn("Appendix table caption.", markdown)
        self.assertIn("| Column A | Column B |", markdown)
        self.assertIn("| 1 | 2 |", markdown)
        self.assertNotIn("$$", markdown)


if __name__ == "__main__":
    unittest.main()
