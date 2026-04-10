from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import article_markdown


def build_springer_markdown(
    xml_body: bytes,
    *,
    assets: list[dict[str, str]] | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    article_metadata = {
        "doi": "10.1007/test",
        "title": "Springer Markdown Example",
        "journal_title": "Example Journal",
        "published": "2026-01-01",
        "landing_page_url": "https://example.test/article",
        "abstract": "",
    }
    if metadata:
        article_metadata.update(metadata)

    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / "10.1007_test.xml"
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
            provider="springer",
            metadata=article_metadata,
            xml_body=xml_body,
            output_dir=Path(tmpdir),
            xml_path=str(xml_path),
            assets=prepared_assets,
        )
        assert markdown_path is not None
        return Path(markdown_path).read_text(encoding="utf-8")


class SpringerMarkdownTests(unittest.TestCase):
    def test_figures_are_inserted_near_references(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec>
          <title>Results</title>
          <p>See <xref ref-type="fig" rid="Fig1">Fig. 1</xref> for the overview.</p>
          <fig id="Fig1">
            <label>Fig. 1</label>
            <caption><p>Overview figure.</p></caption>
            <graphic xlink:href="MediaObjects/Fig1.png" />
          </fig>
        </sec>
      </body>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(
            xml_body,
            assets=[
                {
                    "asset_type": "image",
                    "source_href": "MediaObjects/Fig1.png",
                    "path": "Fig1.png",
                }
            ],
        )

        self.assertIn("See Fig. 1 for the overview.", markdown)
        self.assertIn("![Fig. 1](Fig1.png)", markdown)
        self.assertIn("Overview figure.", markdown)
        self.assertNotIn("## Additional Figures", markdown)

    def test_figures_fallback_to_springer_static_url_when_asset_is_missing(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec>
          <title>Results</title>
          <p>See <xref ref-type="fig" rid="Fig1">Fig. 1</xref> for the overview.</p>
          <fig id="Fig1">
            <label>Fig. 1</label>
            <caption><p>Overview figure.</p></caption>
            <graphic xlink:href="MediaObjects/Fig1.png" />
          </fig>
        </sec>
      </body>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(xml_body, assets=[])

        self.assertIn(
            "![Fig. 1](https://static-content.springer.com/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png)",
            markdown,
        )

    def test_global_supplementary_materials_scan_prefers_caption_heading(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec><title>Results</title><p>Main text.</p></sec>
      </body>
      <app-group>
        <app id="App1" specific-use="web-only">
          <sec>
            <title>Supplementary information</title>
            <p>
              <supplementary-material id="MOESM1" xlink:title="Supplementary file">
                <media xlink:href="MediaObjects/Supp1.pdf">
                  <caption><p>Supplementary Information</p></caption>
                </media>
              </supplementary-material>
            </p>
          </sec>
        </app>
      </app-group>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(
            xml_body,
            assets=[
                {
                    "asset_type": "supplementary",
                    "source_href": "MediaObjects/Supp1.pdf",
                    "path": "Supp1.pdf",
                }
            ],
        )

        self.assertIn("## Supplementary Materials", markdown)
        self.assertIn("[Supplementary Information](Supp1.pdf): Supplementary file", markdown)

    def test_supplementary_materials_fallback_to_springer_static_url_when_asset_is_missing(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec><title>Results</title><p>Main text.</p></sec>
      </body>
      <app-group>
        <app id="App1" specific-use="web-only">
          <sec>
            <title>Supplementary information</title>
            <p>
              <supplementary-material id="MOESM1" xlink:title="Supplementary file">
                <media xlink:href="MediaObjects/Supp1.pdf">
                  <caption><p>Supplementary Information</p></caption>
                </media>
              </supplementary-material>
            </p>
          </sec>
        </app>
      </app-group>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(xml_body, assets=[])

        self.assertIn("## Supplementary Materials", markdown)
        self.assertIn(
            "[Supplementary Information](https://static-content.springer.com/esm/art%3A10.1007%2Ftest/MediaObjects/Supp1.pdf): Supplementary file",
            markdown,
        )

    def test_graphic_only_table_wrap_renders_image_and_footnotes(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec>
          <title>Results</title>
          <p>Measurements are summarized in <xref ref-type="table" rid="Tab1">Table 1</xref>.</p>
          <table-wrap id="Tab1">
            <label>Table 1</label>
            <caption><p>Observed values.</p></caption>
            <graphic xlink:href="MediaObjects/Tab1.png" />
            <table-wrap-foot>
              <p><sup>#</sup> Values are means.</p>
            </table-wrap-foot>
          </table-wrap>
        </sec>
      </body>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(
            xml_body,
            assets=[
                {
                    "asset_type": "image",
                    "source_href": "MediaObjects/Tab1.png",
                    "path": "Tab1.png",
                }
            ],
        )

        self.assertIn("Measurements are summarized in Table 1.", markdown)
        self.assertIn("Table 1", markdown)
        self.assertIn("Observed values.", markdown)
        self.assertIn("![Table 1](Tab1.png)", markdown)
        self.assertIn("<sup>#</sup> Values are means.", markdown)
        self.assertNotIn("## Additional Tables", markdown)

    def test_structured_table_wrap_renders_markdown_table(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response>
  <records>
    <article>
      <body>
        <sec>
          <title>Results</title>
          <table-wrap id="Tab1">
            <label>Table 1</label>
            <caption><p>Structured values.</p></caption>
            <table>
              <thead>
                <tr><th>Name</th><th>Value</th></tr>
              </thead>
              <tbody>
                <tr><td>A</td><td>1</td></tr>
                <tr><td>B</td><td>2</td></tr>
              </tbody>
            </table>
            <table-wrap-foot>
              <p>n = 2.</p>
            </table-wrap-foot>
          </table-wrap>
        </sec>
      </body>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(xml_body)

        self.assertIn("| Name | Value |", markdown)
        self.assertIn("| A | 1 |", markdown)
        self.assertIn("| B | 2 |", markdown)
        self.assertIn("n = 2.", markdown)

    def test_complex_table_wrap_has_explicit_fallback_when_not_semantic(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec>
          <title>Results</title>
          <table-wrap id="Tab1">
            <label>Table 1</label>
            <caption><p>Complex layout.</p></caption>
            <table>
              <tbody>
                <tr><td colspan="2">Merged</td></tr>
              </tbody>
            </table>
            <graphic xlink:href="MediaObjects/Tab1.png" />
          </table-wrap>
        </sec>
      </body>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(
            xml_body,
            assets=[
                {
                    "asset_type": "image",
                    "source_href": "MediaObjects/Tab1.png",
                    "path": "Tab1.png",
                }
            ],
        )

        self.assertIn("![Table 1](Tab1.png)", markdown)
        self.assertIn("## Conversion Notes", markdown)
        self.assertIn(
            "- Table 1: Table content could not be fully converted to Markdown; the original table image is retained below.",
            markdown,
        )
        self.assertLess(markdown.index("![Table 1](Tab1.png)"), markdown.index("## Conversion Notes"))

    def test_inline_and_display_formulas_are_rendered(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:mml="http://www.w3.org/1998/Math/MathML">
  <records>
    <article>
      <body>
        <sec>
          <title>Methods</title>
          <p>We model <inline-formula><mml:math><mml:msub><mml:mi>x</mml:mi><mml:mi>i</mml:mi></mml:msub></mml:math></inline-formula> as follows:<disp-formula><label>(1)</label><mml:math><mml:mfrac><mml:mi>a</mml:mi><mml:mi>b</mml:mi></mml:mfrac></mml:math></disp-formula></p>
        </sec>
      </body>
    </article>
  </records>
</response>
"""

        markdown = build_springer_markdown(xml_body)

        self.assertIn("We model $x_{i}$ as follows:", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("\\frac{a}{b}", markdown)
        self.assertIn("(1)", markdown)


if __name__ == "__main__":
    unittest.main()
