from __future__ import annotations
import re
from paper_fetch.providers import _ieee_html, _ieee_metadata, _ieee_url
from tests.support._ieee_provider_support import *

# ruff: noqa: F403,F405


class IeeeProviderPdfGoldenTests(unittest.TestCase):
    def test_synthetic_pdf_candidate_order_contract(
        self,
    ) -> None:
        fixtures = [
            ("10.1109/MPER.1985.5526567", "5526567"),
            ("10.1109/PGEC.1967.264619", "4038993"),
        ]

        for doi, article_number in fixtures:
            with self.subTest(doi=doi):
                landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
                html = golden_criteria_asset(doi, "landing.html").read_text(
                    encoding="utf-8"
                )
                landing_metadata = _ieee_metadata._parse_landing_metadata(html)
                attempt = _ieee_metadata.IeeeLandingAttempt(
                    normalized_doi=doi,
                    landing_url=landing_url,
                    response_url=landing_url,
                    html_text=html,
                    merged_metadata={
                        "pdfUrl": landing_metadata["pdfUrl"],
                        "pdfPath": landing_metadata["pdfPath"],
                    },
                    article_number=article_number,
                    landing_metadata=landing_metadata,
                )

                self.assertEqual(
                    _ieee_url._pdf_candidates(attempt),
                    [
                        f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                        f"https://ieeexplore.ieee.org/iel7/{article_number}.pdf",
                        f"https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber={article_number}",
                    ],
                )

    def test_real_ieee_html_golden_samples_preserve_semantics(self) -> None:
        for label, (doi, article_number) in IEEE_REAL_HTML_SAMPLES.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmpdir:
                    extraction, article, markdown = _real_ieee_fixture_article(
                        doi=doi,
                        article_number=article_number,
                        tmpdir=Path(tmpdir),
                    )

                    self.assertNotIn("[Formula unavailable]", markdown)
                    self.assertNotIn("[Formula unavailable]", extraction.markdown_text)
                    self.assertEqual(
                        article.quality.semantic_losses.formula_missing_count, 0
                    )
                    self.assertNotIn("SECTION I.", markdown)
                    self.assertNotIn(",,", markdown)
                    self.assertNotIn("(e.g., and)", markdown)
                    self.assertNotIn("## Figures", markdown)
                    self.assertNotIn("## Tables", markdown)
                    self.assertGreater(len(article.references), 0)
                    self.assertTrue(
                        any(
                            not reference.raw.lower().startswith("10.")
                            for reference in article.references
                        ),
                        msg=f"{label} references should use IEEE raw citation text, not DOI-only metadata.",
                    )
                    self.assertNotRegex(
                        markdown.split("## References", 1)[1],
                        r"(?m)^-\s+",
                        msg=f"{label} references should not append fallback bullet entries after IEEE numbered references.",
                    )

                    if label == "ACCESS":
                        self.assertIn("## Introduction", markdown)
                        self.assertIn(
                            "### A. Background on Near-Data Processing", markdown
                        )
                        section_text = "\n\n".join(
                            section.text for section in article.sections
                        )
                        for prefix, listing in [
                            ("standard processing system.", "Listing 1"),
                            ("post-processing.", "Listing 2"),
                            ("NDPmulator).", "Listing 3"),
                            ("ndaccAlloc).", "Listing 4"),
                        ]:
                            with self.subTest(listing=listing):
                                self.assertRegex(
                                    section_text,
                                    re.escape(prefix)
                                    + r"\n\n!\["
                                    + re.escape(listing)
                                    + r"\]\(",
                                )
                                self.assertNotIn(f"{prefix}![{listing}]", section_text)
                    elif label == "CICTN":
                        # original.html deqn1/deqn2 tex-math: preserve operands,
                        # multiplication and numbering, not just formula markers.
                        equations = markdown.split("$$")[1::2]
                        self.assertIn(
                            r"\begin{equation*}{\text{P}}({\text{Risk}}) = {\text{P}}({\text{Age}})*{\text{P}}({\text{Sex}})*{\text{P}}({\text{Time}})\tag{1}\end{equation*}",
                            [e.strip() for e in equations],
                        )
                        self.assertIn(
                            r"\begin{equation*}{\text{Risk Index}} = {\text{P}}({\text{Risk}})*{\text{Crime Score}}\tag{2}\end{equation*}",
                            [e.strip() for e in equations],
                        )
                        self.assertGreaterEqual(extraction.marker_counts["formulas"], 4)
                        self.assertGreaterEqual(len(article.assets), 10)
                    elif label == "TBME":
                        table_iii = next(
                            asset
                            for asset in article.assets
                            if asset.heading.upper().startswith("TABLE III")
                        )
                        self.assertEqual(table_iii.kind, "table")
                        self.assertTrue(table_iii.path)
                        self.assertTrue(Path(table_iii.path).is_file())
                        self.assertNotIn("Formula 1", json.dumps(article.to_dict()))
                    elif label == "TCOMM":
                        self.assertIn("### Theorem 1:", markdown)
                        self.assertIn("#### Proof:", markdown)
                        self.assertNotIn("introduced in, is now", markdown)
                    elif label == "TDEI":
                        # original.html #fig1; helper GIF bytes remain placeholders.
                        large = "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu1-3373549-large.gif"
                        small = "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu1-3373549-small.gif"
                        figure = next(
                            a
                            for a in extraction.extracted_assets
                            if a.get("url") == large
                        )
                        self.assertEqual(figure["kind"], "figure")
                        self.assertEqual(figure["preview_url"], small)
                        self.assertEqual(
                            figure["caption"], "Fig. 1. Layout of experimental device."
                        )
                        localized = next(
                            a for a in article.assets if a.download_url == large
                        )
                        self.assertEqual(localized.kind, "figure")
                        self.assertEqual(localized.original_url, small)
                        self.assertIn(localized.path, markdown)
                        self.assertLess(
                            markdown.index(localized.path),
                            markdown.index("Layout of experimental device."),
                        )
                        self.assertGreaterEqual(markdown.count("!["), 10)
                    elif label == "TE":
                        self.assertIn("## Appendix A", markdown)
                        self.assertIn("## Appendix B", markdown)
                    elif label == "TIM":
                        section_levels = {
                            section.heading: section.level
                            for section in article.sections
                        }
                        self.assertEqual(section_levels["A. Problem Definition"], 3)
                        self.assertEqual(section_levels["1) NTU RGB+D 120:"], 4)
                        self.assertGreater(len(article.metadata.keywords), 0)

    def test_ieee_tim_fixture_original_html_is_parsed_as_body(self) -> None:
        fixture = golden_criteria_asset("10.1109/TIM.2024.3509573", "original.html")
        source_url = (
            "https://ieeexplore.ieee.org/rest/document/10772041/?logAccess=true"
        )

        extraction = _ieee_html._extract_ieee_html(
            fixture.read_text(encoding="utf-8"),
            source_url,
            metadata={"title": "IEEE TIM Article"},
        )

        self.assertIn("Overall Framework", extraction.markdown_text)
        self.assertIn(
            "Adaptive Multimetric Distance Aggregation Module", extraction.markdown_text
        )
        self.assertGreaterEqual(extraction.marker_counts["sections"], 2)
        self.assertGreaterEqual(extraction.marker_counts["formulas"], 1)
        self.assertGreaterEqual(extraction.marker_counts["tables"], 1)

    def test_ieee_golden_criteria_manifest_records_expected_shapes(self) -> None:
        samples = golden_criteria_manifest()["samples"]
        expected_shapes = {
            "10.1109/ACCESS.2024.3352924": (
                "10388355",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TBME.2024.3434477": (
                "10612240",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TCOMM.2024.3395332": (
                "10511075",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TDEI.2024.3373549": (
                "10459335",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TIM.2024.3509573": (
                "10772041",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TE.2024.3376795": (
                "10496257",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/CICTN64563.2025.10932570": (
                "10932570",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/RITA.2026.3668995": (
                "11417163",
                "ieee_html",
                "dynamic_html",
                "multimedia.json",
            ),
            "10.1109/MPER.1985.5526567": (
                "5526567",
                "ieee_pdf",
                "pdf_fallback",
                "landing.html",
            ),
            "10.1109/PGEC.1967.264619": (
                "4038993",
                "ieee_pdf",
                "pdf_fallback",
                "landing.html",
            ),
        }

        ieee_samples = {
            sample["doi"]: sample
            for sample in samples.values()
            if sample.get("publisher") == "ieee"
        }

        self.assertEqual(set(ieee_samples), set(expected_shapes))
        for doi, (
            article_number,
            expected_source,
            expected_route,
            required_asset,
        ) in expected_shapes.items():
            with self.subTest(doi=doi):
                sample = ieee_samples[doi]
                self.assertEqual(sample["article_number"], article_number)
                self.assertEqual(sample["expected_source"], expected_source)
                self.assertEqual(sample["expected_route"], expected_route)
                self.assertEqual(sample["expected_content_kind"], "fulltext")
                self.assertEqual(sample["expected_live_status"], "fulltext")
                self.assertNotIn("expected_review_status", sample)
                self.assertNotIn("out_of_scope_reason", sample)
                self.assertIn(required_asset, sample["assets"])
                for fixture_path in sample["assets"].values():
                    self.assertTrue(
                        (REPO_ROOT / fixture_path).is_file(), msg=fixture_path
                    )
