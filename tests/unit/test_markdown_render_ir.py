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
                "page_url": None,
                "locator": None,
                "image_fallback_url": None,
            },
        )
        self.assertEqual(
            render_table(table),
            [
                "Table 1",
                "",
                "Observed values.",
                "",
                "| A | B |",
                "| --- | --- |",
                "| 1 | 2 |",
                "",
                "Footnote.",
                "",
            ],
        )

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
