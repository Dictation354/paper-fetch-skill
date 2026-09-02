from __future__ import annotations

from dataclasses import asdict
import unittest

from paper_fetch.extraction.markdown_render import (
    MarkdownCaption,
    MarkdownFigure,
    MarkdownFormula,
    MarkdownList,
    MarkdownTable,
    render_caption,
    render_figure,
    render_formula,
    render_list,
    render_table,
    render_table_block,
)
from paper_fetch.extraction.markdown_render.table_format import (
    render_aligned_markdown_table,
)


class MarkdownRenderIrTests(unittest.TestCase):
    def test_table_ir_round_trips_and_renders(self) -> None:
        table = MarkdownTable(
            label="Table 1",
            caption="Observed values.",
            headers=["A", "B"],
            rows=[["A", "B"], ["1", "2"]],
            footnotes=("Footnote.",),
        )

        self.assertEqual(
            asdict(table),
            {
                "label": "Table 1",
                "caption": "Observed values.",
                "headers": ["A", "B"],
                "rows": [["A", "B"], ["1", "2"]],
                "footnotes": ("Footnote.",),
                "image_fallback_url": None,
                "fallback_message": "",
            },
        )
        self.assertEqual(
            render_table(table),
            [
                "Table 1",
                "",
                "Observed values.",
                "",
                "| A   | B   |",
                "| --- | --- |",
                "| 1   | 2   |",
                "",
                "Footnote.",
                "",
            ],
        )

    def test_table_renderer_consumes_headers_before_rows(self) -> None:
        table = MarkdownTable(
            label="Table 2",
            caption="",
            headers=["Column A", "Column B"],
            rows=[["value a", "value b"]],
        )

        markdown_lines = render_table(table)

        self.assertIn("| Column A | Column B |", markdown_lines)
        self.assertIn("| value a  | value b  |", markdown_lines)
        self.assertLess(
            markdown_lines.index("| Column A | Column B |"),
            markdown_lines.index("| value a  | value b  |"),
        )

    def test_table_renderer_uses_canonical_formatter_for_edge_cells(self) -> None:
        table = MarkdownTable(
            label="Table 3",
            caption="",
            headers=["Name", "Value"],
            rows=[["A|B", "first\nsecond"], ["ragged"]],
        )

        rendered = render_table(table)
        table_lines = [line for line in rendered if line.startswith("|")]

        self.assertEqual(
            table_lines,
            render_aligned_markdown_table(
                [["Name", "Value"], ["A|B", "first\nsecond"], ["ragged"]]
            ),
        )
        self.assertIn(r"A\|B", "\n".join(table_lines))
        self.assertIn("first<br>second", "\n".join(table_lines))
        self.assertEqual(
            {line.replace(r"\|", "").count("|") for line in table_lines}, {3}
        )

    def test_table_block_renders_fallback_message_without_image(self) -> None:
        rendered = render_table_block(
            {
                "kind": "fallback",
                "heading": "Table 4",
                "caption": "Unavailable table.",
                "fallback_message": "Table content could not be converted.",
            }
        )

        self.assertEqual(
            rendered,
            [
                "Table 4",
                "",
                "Unavailable table.",
                "",
                "Table content could not be converted.",
                "",
            ],
        )

    def test_table_block_renders_irregular_rows_as_readable_list(self) -> None:
        rendered = render_table_block(
            {
                "kind": "structured",
                "table_render_kind": "structured_list",
                "heading": "Table 5",
                "caption": "Irregular values.",
                "headers": ["Name", "Value"],
                "rows": [["A", "1"], ["B"]],
                "_table_prefix_rows": ["Group A"],
                "fallback_message": "Grid layout was reduced.",
                "footnotes": ["Source note."],
            }
        )

        self.assertEqual(
            rendered,
            [
                "Table 5",
                "",
                "Irregular values.",
                "",
                "Group A",
                "",
                "- Name: A; Value: 1",
                "- Name: B",
                "",
                "Grid layout was reduced.",
                "",
                "Source note.",
                "",
            ],
        )

    def test_table_block_renders_ordered_groups_with_shared_metadata_once(self) -> None:
        rendered = render_table_block(
            {
                "kind": "structured",
                "table_render_kind": "grouped",
                "heading": "Table 6",
                "caption": "Three heat indicators.",
                "footnotes": ["Source note."],
                "link": "table-6.png",
                "_table_groups": [
                    {
                        "table_render_kind": "structured",
                        "headers": ["Day", "WBGT"],
                        "rows": [["1", "28"]],
                        "_table_prefix_rows": ["(a) WBGT"],
                    },
                    {
                        "table_render_kind": "structured_list",
                        "headers": ["Day", "T"],
                        "rows": [["2", "30"], ["3"]],
                        "_table_prefix_rows": ["(b) T"],
                    },
                    {
                        "table_render_kind": "structured",
                        "headers": ["Day", "Low", "High"],
                        "rows": [["4", "29", "32"]],
                    },
                ],
            }
        )
        markdown = "\n".join(rendered)

        self.assertEqual(rendered.count("Table 6"), 1)
        self.assertEqual(markdown.count("Three heat indicators."), 1)
        self.assertEqual(markdown.count("Source note."), 1)
        self.assertEqual(markdown.count("![Table 6](table-6.png)"), 1)
        self.assertLess(markdown.index("(a) WBGT"), markdown.index("| Day"))
        self.assertLess(markdown.index("(b) T"), markdown.index("- Day: 2; T: 30"))
        self.assertLess(
            markdown.index("- Day: 3"),
            markdown.rindex("| Day"),
        )
        self.assertNotIn("Group 3", markdown)

    def test_figure_ir_round_trips_and_renders(self) -> None:
        figure = MarkdownFigure(
            label="Figure 1",
            caption="Rendered figure.",
            asset_url="figures/f1.png",
            alt="Figure 1",
        )

        self.assertEqual(asdict(figure)["asset_url"], "figures/f1.png")
        self.assertEqual(
            render_figure(figure),
            ["![Figure 1](figures/f1.png)", "", "Rendered figure.", ""],
        )

    def test_formula_caption_and_list_renderers(self) -> None:
        formula = MarkdownFormula(
            label="Equation 1.", latex="x = y + z", display_mode=True
        )
        caption = MarkdownCaption(label="Figure 2.", text="A caption.")
        items = MarkdownList(items=["First", "Second"], ordered=True)

        self.assertEqual(
            render_formula(formula), ["Equation 1.", "", "$$", "x = y + z", "$$", ""]
        )
        self.assertEqual(render_caption(caption), "**Figure 2.** A caption.")
        self.assertEqual(render_list(items), ["1. First", "2. Second", ""])

    def test_formula_renderer_normalizes_latex(self) -> None:
        formula = MarkdownFormula(
            label="",
            latex=r"P(SPI \unicode{x2A7D} - 1.64)",
            display_mode=False,
        )

        self.assertEqual(render_formula(formula), [r"$P(SPI \leqslant - 1.64)$", ""])


if __name__ == "__main__":
    unittest.main()
