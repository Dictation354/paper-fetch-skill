from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from paper_fetch.delivery.receipts import save_reading_artifacts
from paper_fetch.extraction.html._runtime import body_metrics
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.manifest import build_manifest_record
from paper_fetch.manifest_writer import write_manifest_record
from paper_fetch.models import Asset, FetchEnvelope, Metadata
from paper_fetch.providers._html_references import extract_numbered_references_from_html
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
)
from paper_fetch.providers.base import ProviderContent
from paper_fetch.runtime import RuntimeContext
from paper_fetch.targeted_assets import (
    capture_asset_context,
    context_from_manifest,
    discover_content_images,
    fetch_selected_assets,
)
from tests.golden_criteria import golden_criteria_asset
from tests.paths import FIXTURE_DIR
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.support._paper_fetch_support import RecordingTransport, http_response
from tests.support.canonical_content import comparable_cell
from tests.support.fetch_fixtures import sample_article
from tests.support.markdown_presentation import visible_markdown
from tests.support.wiley_page_assets import png_bytes

SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
PNAS_COLLATERAL_FIXTURE = golden_criteria_asset(
    "10.1073/pnas.2309123120", "original.html"
)
SCIENCE_PERSPECTIVE_FIXTURE = golden_criteria_asset(
    "10.1126/science.aeg3511", "original.html"
)
SCIENCE_ADP0212_FIXTURE = golden_criteria_asset(
    "10.1126/science.adp0212", "original.html"
)


def test_wiley_formula_positions_and_selection_from_retained_body(tmp_path):
    doi = "10.1111/gcb.15322"
    source = f"https://onlinelibrary.wiley.com/doi/full/{doi}"
    fixture = golden_criteria_asset(doi, "original.html").read_bytes()
    markdown, _ = extract_atypon_browser_workflow_markdown(
        fixture.decode("utf-8"), source, "wiley", metadata={"doi": doi}
    )
    asset_root = "https://onlinelibrary.wiley.com/cms/asset"
    remote_url = (
        f"{asset_root}/9841141f-ff64-4347-a2f1-c0fa2b92a994/gcb15322-math-0001.png"
    )
    local_url = (
        f"{asset_root}/14d2ee09-ab40-4788-b91d-81bf2381e170/gcb15322-math-0002.png"
    )
    image_bytes = png_bytes(100, 100)
    local_path = tmp_path / "math 2.png"
    local_path.write_bytes(image_bytes)
    article = sample_article()
    article.doi = doi
    article.source = "wiley_browser"
    article.acquisition = None
    article.metadata = Metadata(title="Wiley replay", landing_page_url=source)
    article.assets = [
        Asset(kind="formula", heading="", url=local_url, path=str(local_path))
    ]
    remote_image = f"![Formula]({remote_url})"
    local_image = f"![Formula]({local_url})"
    other_image = f"![Formula]({remote_url}?other=1)"
    markdown = (
        markdown.rstrip()
        + f"\n\n式 {remote_image} {local_image} {remote_image} {other_image}\n"
    )
    transport = RecordingTransport(
        {("GET", remote_url): http_response(remote_url, image_bytes, "image/png")}
    )

    with RuntimeContext(env={}, transport=transport, clients={}) as runtime:
        capture_asset_context(
            article,
            ProviderContent(
                route_kind="html",
                source_url=source,
                content_type="text/html",
                body=fixture,
            ),
            provider="wiley",
            client=None,
            context=runtime,
        )
        envelope = FetchEnvelope(
            doi=doi, source=article.source, article=article, markdown=markdown
        )
        delivery = tmp_path / "reading"
        artifacts = save_reading_artifacts(delivery, envelope=envelope)
        record = build_manifest_record(
            tool_version="8.1.0",
            index=1,
            attempt=1,
            query=doi,
            request_parameters={},
            asset_profile="none",
            envelope=envelope,
            output_artifacts=artifacts,
        )
        manifest = write_manifest_record(delivery / "manifest.json", record)
        assets = json.loads((delivery / "images.json").read_text())["assets"]
        remote = next(asset for asset in assets if asset["url"] == remote_url)
        local = next(asset for asset in assets if asset["url"] == local_url)

        lines = (delivery / "body.md").read_text().splitlines()
        figures = [asset for asset in assets if asset["kind"] == "figure"]
        assert len(figures) == 4
        for number, figure in enumerate(figures, 1):
            image = f"![Figure {number}]({figure['url']})"
            figure_line = lines.index(image) + 1
            assert figure["body_positions"] == [{"line": figure_line, "column": 1}]

        original_line = next(
            i for i, line in enumerate(lines, 1) if remote_image in line
        )
        last_line = lines[-1]
        rewritten = "![Formula](../math%202.png)"
        assert local_url not in last_line and rewritten in last_line
        assert remote["body_positions"] == [
            {
                "line": original_line,
                "column": lines[original_line - 1].index(remote_image) + 1,
            },
            {"line": len(lines), "column": 3},
            {"line": len(lines), "column": last_line.rindex(remote_image) + 1},
        ]
        assert local["body_positions"][-1] == {
            "line": len(lines),
            "column": last_line.index(rewritten) + 1,
        }
        assert len(local["body_positions"]) == 2

        restored = context_from_manifest(manifest)
        result = fetch_selected_assets(
            restored,
            asset_ids=[remote["asset_id"]],
            output_dir=str(tmp_path / "selected"),
            runtime=runtime,
        )
    (selected,) = result["results"]
    assert selected["asset_id"] == remote["asset_id"] and selected["status"] == "ok"
    assert Path(selected["path"]).read_bytes() == image_bytes
    assert [call["url"] for call in transport.calls] == [remote_url]


class AtyponBrowserWorkflowMarkdownTests(unittest.TestCase):
    def _extract_fixture_markdown(
        self,
        fixture_path,
        source_url: str,
        publisher: str,
        doi: str,
        *,
        title: str | None = None,
    ):
        metadata = {"doi": doi}
        if title:
            metadata["title"] = title
        html = fixture_path.read_text(encoding="utf-8")
        return extract_atypon_browser_workflow_markdown(
            html,
            source_url,
            publisher,
            metadata=metadata,
        )

    def _extract_sample_markdown(self, sample):
        return self._extract_fixture_markdown(
            FIXTURE_DIR / sample.fixture_name,
            sample.landing_url,
            sample.provider,
            sample.doi,
        )

    def test_pnas_abstract_fixture_is_rejected(self) -> None:
        html = golden_criteria_asset(
            "10.1073/pnas.2406303121", "abstract.html"
        ).read_text(encoding="utf-8")

        with self.assertRaises(HtmlExtractionFailure) as ctx:
            extract_atypon_browser_workflow_markdown(
                html,
                PNAS_SAMPLE.landing_url,
                "pnas",
                metadata={"doi": PNAS_SAMPLE.doi},
            )

        self.assertEqual(ctx.exception.reason, "abstract_only")

    def test_wiley_formula_image_fallbacks_are_preserved(self) -> None:
        fixture = golden_criteria_asset("10.1111/gcb.15322", "original.html")
        source_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322"
        original_path = (
            "/cms/asset/9841141f-ff64-4347-a2f1-c0fa2b92a994/gcb15322-math-0001.png"
        )
        soup = BeautifulSoup(fixture.read_text(encoding="utf-8"), "lxml")
        self.assertIsNotNone(soup.select_one(f'img[src="{original_path}"]'))
        markdown, _ = self._extract_fixture_markdown(
            fixture,
            source_url,
            "wiley",
            "10.1111/gcb.15322",
        )

        self.assertIn("**Equation 1.**", markdown)
        self.assertIn(f"![Formula]({urljoin(source_url, original_path)})", markdown)
        self.assertIn("gcb15322-math-0001.png", markdown)
        self.assertNotIn("**Equation 1.**![Formula]", markdown)

    def test_wiley_labeled_formula_image_fixture_does_not_render_label_as_math(
        self,
    ) -> None:
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_asset("10.1111/gcb.16011", "original.html"),
            "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16011",
            "wiley",
            "10.1111/gcb.16011",
        )

        for equation_number in range(1, 7):
            self.assertIn(f"**Equation {equation_number}.**", markdown)
        self.assertIn("gcb16011-math-0001.png", markdown)
        self.assertIn("gcb16011-math-0016.png", markdown)
        self.assertNotIn("$$\n(1)\n$$", markdown)
        self.assertNotIn("$$\n(6)\n$$", markdown)

    def test_wiley_real_fixture_does_not_count_research_funding_as_body(self) -> None:
        fixture_path = golden_criteria_asset("10.1111/gcb.15322", "original.html")
        html = fixture_path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("research funding", html.casefold())

        markdown, info = self._extract_fixture_markdown(
            fixture_path,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
            "wiley",
            "10.1111/gcb.15322",
        )
        metrics = body_metrics(
            markdown,
            {"doi": "10.1111/gcb.15322"},
            section_hints=info.get("section_hints"),
            noise_profile="wiley",
        )

        self.assertNotIn("research funding", markdown.casefold())
        self.assertNotIn("research funding", metrics["text"].casefold())

    def test_science_real_fixture_does_not_leak_competing_interests_modal(self) -> None:
        fixture_path = golden_criteria_asset("10.1126/sciadv.abg9690", "original.html")
        html = fixture_path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("statement of competing interests", html.casefold())

        markdown, info = self._extract_fixture_markdown(
            fixture_path,
            "https://www.science.org/doi/10.1126/sciadv.abg9690",
            "science",
            "10.1126/sciadv.abg9690",
        )
        metrics = body_metrics(
            markdown,
            {"doi": "10.1126/sciadv.abg9690"},
            section_hints=info.get("section_hints"),
            noise_profile="science",
        )

        self.assertNotIn("statement of competing interests", markdown.casefold())
        self.assertNotIn("statement of competing interests", metrics["text"].casefold())

    def test_wiley_references_use_visible_citation_text_not_doi_only(self) -> None:
        cases = (
            (
                "10.1111/gcb.15322",
                (
                    "Atkinson",
                    "Inter-comparison of four models",
                    "Remote Sensing of Environment",
                ),
            ),
            (
                "10.1111/gcb.16998",
                ("AghaKouchak", "Remote sensing of drought", "Reviews of Geophysics"),
            ),
        )

        for doi, expected_tokens in cases:
            with self.subTest(doi=doi):
                html = golden_criteria_asset(doi, "original.html").read_text(
                    encoding="utf-8"
                )

                references = extract_numbered_references_from_html(html)

                self.assertGreater(len(references), 20)
                for token in expected_tokens:
                    self.assertIn(token, references[0]["raw"])
                self.assertNotEqual(references[0]["raw"], references[0]["doi"])
                self.assertNotIn("Google Scholar", references[0]["raw"])

    def test_wiley_fixture_renders_rule_table_as_markdown_table(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_asset("10.1111/cas.16395", "original.html"),
            "https://onlinelibrary.wiley.com/doi/full/10.1111/cas.16395",
            "wiley",
            "10.1111/cas.16395",
        )

        self.assertIn(
            "**Table 1.** AI-SaMD approved as a medical device in the field of oncology in Japan (as of May 2024).",
            markdown,
        )
        self.assertRegex(
            markdown,
            r"\| Research area\s+\| Approval number\s+\| Product\s+\| Manufacturer\s+\| Target inspection method\s+\| Class\s+\| Year of approval\s+\|",
        )
        self.assertNotIn(
            "Research areaApproval numberProductManufacturerTarget inspection methodClassYear of approval",
            markdown,
        )

    def test_science_real_tables_preserve_headers_cells_and_scripts(self) -> None:
        # abj3309 Table 1: three model groups, four header levels, nine columns.
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_asset("10.1126/sciadv.abj3309", "original.html"),
            "https://www.science.org/doi/10.1126/sciadv.abj3309",
            "science",
            "10.1126/sciadv.abj3309",
        )
        self.assertIn("**Table 1.** Spatial lag regressions.", markdown)
        table = markdown.split("**Table 1.**", 1)[1].split("\n\n", 2)[1]
        rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in table.splitlines()
            if line.startswith("|")
        ]
        for start, group, score, aic in (
            (0, "Nondegraded forest", "0.86", "−8,031"),
            (3, "Degradation in normal precipitation years", "0.59", "−16,099.5"),
            (6, "Degradation in extreme drought years", "0.46", "−27,777.8"),
        ):
            for offset, label in enumerate(("Variable", "Coefficient", "Prob.")):
                self.assertEqual(
                    rows[0][start + offset],
                    f"**{group}** / <strong><em>R</em><sup>2</sup>: {score}</strong> / "
                    f"**Akaike (AIC): {aic}** / **{label}**",
                )
        self.assertEqual(
            rows[2],
            [
                "Spatial coefficient",
                "0.90",
                "0.000",
                "Spatial coefficient",
                "0.824",
                "0.000",
                "Spatial<br>coefficient",
                "0.773",
                "0.000",
            ],
        )
        self.assertEqual(
            rows[4],
            [
                "Conservation units",
                "0.052",
                "0.000",
                "Historical<br>deforestation",
                "0.024",
                "0.000",
                "Water deficit<br>anomaly",
                "−2.834 × 10<sup>−5</sup>",
                "0.000",
            ],
        )
        compact = re.sub(r"\s+", " ", markdown)
        self.assertIn(
            "CO<sub>2</sub>",
            markdown.split("**Table 2.**", 1)[1].split("Net emissions", 1)[0],
        )
        self.assertIn("| Net emissions | 1960–2019 | 37.23 | 36.99 |", compact)
        self.assertIn("| Net emissions | 2020–2050 | 1.31 | 24.07 |", compact)

        # adm9732 Table 1: the final group declares rowspan=4 for three rows.
        # Covariate continuation rows must retain column/model association.
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_asset("10.1126/sciadv.adm9732", "original.html"),
            "https://www.science.org/doi/10.1126/sciadv.adm9732",
            "science",
            "10.1126/sciadv.adm9732",
        )
        self.assertIn("**Table 1.** Model selection table", markdown)
        self.assertNotIn("- Model: Pdev", markdown)
        compact = re.sub(r"\s+", " ", markdown)
        self.assertIn(
            "| Composition | 9 | 0.623 | 0.621 | 0 | 0.995 | MAP, Pdev, MAP\\*Pdev, MAP\\*Woody, MAP\\*Herb, Pdev\\*Woody, Pdev\\*Herb |",
            compact,
        )
        rows = [
            line for line in markdown.splitlines() if line.startswith("| Disturbance")
        ]
        self.assertEqual(len(rows), 1)
        self.assertIn("MAP\\*Pdev\\*1/√YSD", rows[0])

    def test_pnas_real_figure_identity_and_equation_bodies(self) -> None:
        markdown, _ = self._extract_sample_markdown(PNAS_SAMPLE)
        # original.html #fig01 and assistive MathML in #eqn1 / #eqn2.
        image = "![Figure 1](https://www.pnas.org/cms/10.1073/pnas.2406303121/asset/34644f03-1696-4e48-bd29-7cbd5f1b907b/assets/images/large/pnas.2406303121fig01.jpg)"
        caption = "Digitized nasal viral RNA and infectious virus from a SARS-CoV-2 human challenge study"
        self.assertEqual(markdown.count(image), 1)
        self.assertLess(markdown.index(image), markdown.index(caption))
        self.assertLess(markdown.index(caption), markdown.index("**Equation 1.**"))
        self.assertIn("**Equation 1.**\n\n$$\nV_{i} = f(V) = BV^{h},\n$$", markdown)
        equation = markdown.split("**Equation 2.**\n\n$$\n", 1)[1].split("\n$$", 1)[0]
        for expression in (
            r"\frac{dT}{dt} = - \beta V_{i}T - \phi IT + \rho R",
            r"\frac{dR}{dt} = \phi IT - \rho R",
            r"\frac{dE}{dt} = \beta V_{i}T - kE",
            r"\frac{dI}{dt} = kE - \delta I",
            r"\frac{dV}{dt} = \pi I - cV",
            r"V_{i} = f(V)",
        ):
            self.assertIn(comparable_cell(expression), comparable_cell(equation))

    def test_science_fixture_extracts_fulltext_markdown(self) -> None:
        markdown, info = self._extract_sample_markdown(SCIENCE_SAMPLE)

        self.assertEqual(
            visible_markdown(info["container_tag"]), visible_markdown("main")
        )
        self.assertIn(
            visible_markdown(
                "# Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration"
            ),
            visible_markdown(markdown),
        )
        self.assertIn(
            visible_markdown("Structured Abstract"), visible_markdown(markdown)
        )
        self.assertIn(visible_markdown("Discussion"), visible_markdown(markdown))
        self.assertIn(
            visible_markdown("Materials and methods"), visible_markdown(markdown)
        )
        self.assertIn("![Figure 1](", markdown)
        self.assertNotIn("**Figure 1.** .", markdown)
        self.assertIn(
            visible_markdown(
                "**Figure 1.** The niche discriminates regeneration from fibrosis after digit tip amputation. (**A**)"
            ),
            visible_markdown(markdown),
        )
        self.assertNotIn("amputation.(**A**)", markdown)

    def test_science_fixture_markdown_omits_frontmatter_and_collateral_noise(
        self,
    ) -> None:
        markdown, _ = self._extract_sample_markdown(SCIENCE_SAMPLE)

        self.assertNotIn("Full access", markdown)
        self.assertNotIn("Research Article", markdown)
        self.assertNotIn("Authors Info & Affiliations", markdown)
        self.assertNotIn("### Authors", markdown)
        self.assertNotIn("### Citations", markdown)
        self.assertNotIn("### View options", markdown)
        self.assertNotIn("View all articles by this author", markdown)
        self.assertNotIn("Purchase digital access to this article", markdown)
        self.assertNotIn("Copyright ©", markdown)

    def test_science_fixture_keeps_data_availability_and_graphical_summary(
        self,
    ) -> None:
        markdown, _ = self._extract_sample_markdown(SCIENCE_SAMPLE)

        self.assertIn("## Data, code, and materials availability", markdown)
        self.assertIn(
            "The ECM and tissue mechanics direct wound healing outcomes after digit amputations",
            markdown,
        )
        self.assertIn("![Figure 1](", markdown)

    def test_pnas_full_fixture_extracts_body_sections_from_real_html(self) -> None:
        markdown, info = self._extract_sample_markdown(PNAS_SAMPLE)

        self.assertIn(
            "# The kinetics of SARS-CoV-2 infection based on a human challenge study",
            markdown,
        )
        self.assertIn("## Significance", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn(
            "Severe acute respiratory syndrome coronavirus 2 (SARS-CoV-2) continues to spread worldwide",
            markdown,
        )
        self.assertIn("## Methods", markdown)
        self.assertIn("## Mathematical Models", markdown)
        self.assertIn("### Data", markdown)
        self.assertIn(
            "### The Relationship between Total and Infectious Virus", markdown
        )
        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("**Equation 2.**", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)
        self.assertLess(
            markdown.index("## Significance"), markdown.index("## Abstract")
        )
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Methods"))
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["content_kind"], "fulltext")

    def test_pnas_full_fixture_omits_real_page_collateral_noise(self) -> None:
        markdown, _ = self._extract_sample_markdown(PNAS_SAMPLE)

        self.assertNotIn("Recommended articles", markdown)
        self.assertNotIn("Download PDF", markdown)
        self.assertNotIn("Request permissions", markdown)
        self.assertNotIn("Google Scholar", markdown)
        self.assertNotIn("Sign up for PNAS alerts", markdown)
        self.assertNotIn("Learn More", markdown)
        self.assertNotIn("Vi=fV=BVh", markdown)
        self.assertNotIn("dTdt=", markdown)

    def test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown(
        self,
    ) -> None:
        markdown, _ = self._extract_sample_markdown(PNAS_SAMPLE)

        self.assertIn("## Data, Materials, and Software Availability", markdown)
        self.assertEqual(
            markdown.count("## Data, Materials, and Software Availability"), 1
        )
        self.assertNotIn("#### Data, Materials, and Software Availability", markdown)
        self.assertIn(
            "**Table 1.** Estimated population parameters for the DDRCM with humoral immune response",
            markdown,
        )
        self.assertRegex(
            markdown,
            r"\| Parameter\s+\| Description\s+\| Fixed Effects \(R\.S\.E\., %\)\s+\|",
        )
        self.assertNotIn(
            "**Figure** Estimated population parameters for the DDRCM with humoral immune response",
            markdown,
        )
        self.assertLess(markdown.index("**Figure 4.**"), markdown.index("**Table 1.**"))

    def test_pnas_collateral_data_availability_fixture_is_not_duplicated(self) -> None:
        markdown, info = self._extract_fixture_markdown(
            PNAS_COLLATERAL_FIXTURE,
            "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
            "pnas",
            "10.1073/pnas.2309123120",
        )

        self.assertIn(info["container_tag"], {"article", "main", "body"})
        self.assertEqual(
            markdown.count("## Data, Materials, and Software Availability"), 1
        )
        self.assertEqual(markdown.count("## Significance"), 1)
        self.assertEqual(markdown.count("## Abstract"), 1)
        self.assertNotIn("#### Data, Materials, and Software Availability", markdown)
        self.assertNotIn("community water fluoridation", markdown.lower())
        self.assertNotIn("tattoo ink accumulation", markdown.lower())
        self.assertEqual(
            [section["heading"] for section in info["abstract_sections"]],
            ["Significance", "Abstract"],
        )

    def test_wiley_full_fixture_extracts_body_sections_from_real_html(self) -> None:
        markdown, info = self._extract_sample_markdown(WILEY_SAMPLE)

        self.assertIn(
            "# Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
            markdown,
        )
        self.assertIn("## Abstract", markdown)
        self.assertIn(
            "Global vegetation greening has been widely confirmed in previous studies",
            markdown,
        )
        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertIn("## 2 MATERIALS AND METHODS", markdown)
        self.assertIn("## 3 RESULTS", markdown)
        self.assertIn("## 4 DISCUSSION", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)
        self.assertIn("CO<sub>2</sub> emission", markdown)
        self.assertIn("m<sup>2</sup> m<sup>−2</sup> year<sup>−1</sup>", markdown)
        self.assertNotIn("CO2 emission", markdown)
        self.assertNotIn("m2 m−2 year−1", markdown)
        self.assertNotIn("## Abbreviations", markdown)
        self.assertLess(
            markdown.index("## Abstract"), markdown.index("## 1 INTRODUCTION")
        )
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["content_kind"], "fulltext")

    def test_wiley_full_fixture_omits_real_page_collateral_noise(self) -> None:
        markdown, _ = self._extract_sample_markdown(WILEY_SAMPLE)

        self.assertNotIn("Publication History", markdown)
        self.assertNotIn("Article navigation and tools", markdown)
        self.assertNotIn("Download PDF", markdown)
        self.assertNotIn("About Wiley Online Library", markdown)

    def test_wiley_full_fixture_keeps_data_availability_and_source_declarations(
        self,
    ) -> None:
        markdown, _ = self._extract_sample_markdown(WILEY_SAMPLE)

        self.assertIn("## DATA AVAILABILITY STATEMENT", markdown)
        self.assertIn("## CONFLICT OF INTEREST", markdown)
        self.assertIn("The authors declare no competing interests.", markdown)
        self.assertNotIn("## Supporting Information", markdown)

    def test_science_perspective_fixture_extracts_fulltext_without_section_headings(
        self,
    ) -> None:
        markdown, info = self._extract_fixture_markdown(
            SCIENCE_PERSPECTIVE_FIXTURE,
            "https://www.science.org/doi/full/10.1126/science.aeg3511",
            "science",
            "10.1126/science.aeg3511",
        )

        self.assertIn(info["container_tag"], {"article", "main"})
        self.assertIn("# Magma plumbing beneath Yellowstone", markdown)
        self.assertIn(
            "Yellowstone is one of the most seismically active areas", markdown
        )
        self.assertIn("The findings of Cao", markdown)
        from markdown_it import MarkdownIt

        source = BeautifulSoup(SCIENCE_PERSPECTIVE_FIXTURE.read_bytes(), "lxml")
        rendered = BeautifulSoup(
            MarkdownIt("commonmark", {"html": True}).render(markdown), "lxml"
        )
        callouts = [
            a
            for a in source.select(
                'a[role="doc-biblioref"][href^="#core-collateral-R"]'
            )
        ]
        self.assertTrue(callouts)
        for callout in callouts:
            reference_id = callout["data-xml-rid"]
            self.assertIsNotNone(source.find(id=reference_id))
            target = urljoin(
                "https://www.science.org/doi/full/10.1126/science.aeg3511",
                "#" + reference_id,
            )
            self.assertTrue(
                any(
                    a["href"] == target and a.get_text() == callout.get_text()
                    for a in rendered.select("a[href]")
                )
            )
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertIn("body_sufficient", diagnostics["strong_positive_signals"])
        self.assertIn("aaas_user_entitled", diagnostics["strong_positive_signals"])
        self.assertGreaterEqual(diagnostics["figure_count"], 1)

    def test_science_adp0212_fixture_splits_display_equations_and_caption_sentences(
        self,
    ) -> None:
        markdown, extraction = self._extract_fixture_markdown(
            SCIENCE_ADP0212_FIXTURE,
            "https://www.science.org/doi/full/10.1126/science.adp0212",
            "science",
            "10.1126/science.adp0212",
        )

        source = "https://www.science.org/doi/full/10.1126/science.adp0212"
        images = discover_content_images(
            ProviderContent(
                route_kind="html",
                source_url=source,
                content_type="text/html",
                body=SCIENCE_ADP0212_FIXTURE.read_bytes(),
                diagnostics={"extraction": extraction},
            ),
            provider="science",
        )
        by_id = {asset.get("dom_id"): asset for asset in images}
        for number in (1, 2):
            caption = by_id[f"F{number}"]["caption"]
            self.assertTrue(caption.startswith(f"**Figure {number}.**"))
            self.assertIn(caption, markdown)

        self.assertIn(visible_markdown("**Equation 1.**"), visible_markdown(markdown))
        self.assertIn(visible_markdown("$$"), visible_markdown(markdown))
        self.assertIn(
            visible_markdown("where *P* is precipitation"), visible_markdown(markdown)
        )
        self.assertLess(
            markdown.index("**Equation 1.**"),
            markdown.index("where *P* is precipitation"),
        )
        self.assertIn(
            visible_markdown(
                "**Figure 2.** Regional change in daily precipitation variability from 1900 to 2020. Time series"
            ),
            visible_markdown(markdown),
        )


if __name__ == "__main__":
    unittest.main()
