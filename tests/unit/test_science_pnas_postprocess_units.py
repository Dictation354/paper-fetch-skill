from __future__ import annotations

import unittest

from paper_fetch.providers.science_pnas import extract_science_pnas_markdown
from tests.golden_criteria import golden_criteria_scenario_asset


class SciencePnasPostprocessUnitTests(unittest.TestCase):
    def test_extract_science_pnas_markdown_normalizes_title_subscript_line_breaks(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>
            Projections of future forest degradation and CO
            <sub>2</sub>
            emissions for the Brazilian Amazon
          </h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract summary remains available.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This paragraph represents the body of the article and should remain after title normalization.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.example-subscript-title",
            "science",
            metadata={"doi": "10.1126/science.example-subscript-title"},
        )

        self.assertIn(
            "# Projections of future forest degradation and CO<sub>2</sub> emissions for the Brazilian Amazon",
            markdown,
        )
        self.assertNotIn("CO\n<sub>2</sub>", markdown)

    def test_extract_science_pnas_markdown_flattens_multilevel_table_headers(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Multiheader Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the multiheader table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <figure class="table">
              <figcaption><span class="label">Table 1.</span> Spatial lag regressions.</figcaption>
              <table>
                <thead>
                  <tr>
                    <th colspan="3">Nondegraded forest</th>
                    <th colspan="3">Degradation in normal precipitation years</th>
                    <th colspan="3">Degradation in extreme drought years</th>
                  </tr>
                  <tr>
                    <th>Variable</th>
                    <th>Estimate</th>
                    <th>P value</th>
                    <th>Variable</th>
                    <th>Estimate</th>
                    <th>P value</th>
                    <th>Variable</th>
                    <th>Estimate</th>
                    <th>P value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Spatial coefficient</td>
                    <td>0.90</td>
                    <td>0.000</td>
                    <td>Spatial coefficient</td>
                    <td>0.824</td>
                    <td>0.000</td>
                    <td>Spatial coefficient</td>
                    <td>0.773</td>
                    <td>0.000</td>
                  </tr>
                </tbody>
              </table>
            </figure>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.multiheader-table-example",
            "science",
            metadata={"doi": "10.1126/science.multiheader-table-example", "title": "Science Multiheader Table Example"},
        )

        self.assertIn("**Table 1.** Spatial lag regressions.", markdown)
        self.assertIn("| Nondegraded forest / Variable |", markdown)
        self.assertIn("Degradation in normal precipitation years / Estimate", markdown)
        self.assertIn("Degradation in extreme drought years / P value", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Spatial coefficient\s*\|\s*0\.90\s*\|\s*0\.000\s*\|\s*Spatial coefficient\s*\|\s*0\.824\s*\|\s*0\.000\s*\|\s*Spatial coefficient\s*\|\s*0\.773\s*\|\s*0\.000\s*\|",
        )

    def test_extract_science_pnas_markdown_flattens_rowspan_table_body_cells(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Rowspan Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the rowspan table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <figure class="table">
              <figcaption><span class="label">Table 2.</span> CO<sub>2</sub> balance simulated in the scenarios.</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Period</th>
                    <th>Sustainable scenario</th>
                    <th>Fragmentation scenario</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th rowspan="2">CO<sub>2</sub> (Gt CO<sub>2</sub>)</th>
                    <td>1960–2019</td>
                    <td>37.23</td>
                    <td>36.99</td>
                  </tr>
                  <tr>
                    <td>2020–2050</td>
                    <td>1.31</td>
                    <td>24.07</td>
                  </tr>
                </tbody>
              </table>
            </figure>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.rowspan-table-example",
            "science",
            metadata={"doi": "10.1126/science.rowspan-table-example", "title": "Science Rowspan Table Example"},
        )

        self.assertIn("**Table 2.** CO<sub>2</sub> balance simulated in the scenarios.", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Metric\s*\|\s*Period\s*\|\s*Sustainable scenario\s*\|\s*Fragmentation scenario\s*\|",
        )
        self.assertRegex(
            markdown,
            r"\|\s*CO<sub>2</sub>\s*\(Gt CO<sub>2</sub>\)\s*\|\s*1960–2019\s*\|\s*37\.23\s*\|\s*36\.99\s*\|",
        )
        self.assertRegex(
            markdown,
            r"\|\s*CO<sub>2</sub>\s*\(Gt CO<sub>2</sub>\)\s*\|\s*2020–2050\s*\|\s*1\.31\s*\|\s*24\.07\s*\|",
        )

    def test_extract_science_pnas_markdown_falls_back_complex_table_to_bullets(self) -> None:
        """rule: rule-table-flatten-or-list"""
        html = golden_criteria_scenario_asset("table_flatten_or_list", "complex_table.html").read_text(
            encoding="utf-8"
        )

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/complex-table-example",
            "wiley",
            metadata={"doi": "10.1111/complex-table-example", "title": "Complex Table Example"},
        )

        self.assertIn("**Table 1.** Complex grouped values.", markdown)
        self.assertIn("- Group: Group A; Values: Alpha / Beta", markdown)
        self.assertNotIn("| Group | Values |", markdown)


if __name__ == "__main__":
    unittest.main()
