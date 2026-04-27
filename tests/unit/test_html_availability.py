from __future__ import annotations

import unittest
from types import SimpleNamespace

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.extraction.html._runtime import body_metrics
from paper_fetch.providers import _pnas_html, _science_html, _springer_html, _wiley_html
from paper_fetch.quality.html_availability import (
    assess_html_fulltext_availability,
    assess_plain_text_fulltext_availability,
    assess_structured_article_fulltext_availability,
)
from tests.block_fixtures import block_asset
from tests.golden_criteria import golden_criteria_asset


SCIENCE_ENTITLED_FIXTURE = golden_criteria_asset("10.1126/science.aeg3511", "original.html")
WILEY_ENTITLED_FIXTURE = golden_criteria_asset("10.1111/gcb.16998", "original.html")
PNAS_ENTITLED_FIXTURE = golden_criteria_asset("10.1073/pnas.2309123120", "original.html")
SPRINGER_PAYWALL_SAMPLE_DOIS = (
    "10.1007/s00382-018-4286-0",
    "10.1007/s11430-021-9892-6",
    "10.1007/s12652-019-01399-8",
    "10.1007/s13351-020-9829-8",
)


def _science_paywall_metadata(_html: str, markdown: str) -> dict[str, str]:
    return {
        "title": "Magma plumbing beneath Yellowstone",
        "doi": "10.1126/science.aeg3511",
        "abstract": markdown.split("## Access the full article", 1)[0].split("## Abstract", 1)[1].strip(),
    }


def _wiley_paywall_metadata(html: str, markdown: str) -> dict[str, str]:
    metadata = parse_html_metadata(html, "https://onlinelibrary.wiley.com/doi/abs/10.1111/gcb.16414")
    return {
        **metadata,
        "title": "Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
        "abstract": markdown.split("## Abstract", 1)[1].strip(),
    }


def _pnas_paywall_metadata(_html: str, markdown: str) -> dict[str, str]:
    return {
        "title": "A discrete serotonergic circuit involved in the generation of tinnitus behavior",
        "doi": "10.1073/pnas.2509692123",
        "abstract": markdown.split("## Abstract", 1)[1].split("##", 1)[0].strip(),
        "citation_abstract_html_url": "https://www.pnas.org/doi/abs/10.1073/pnas.2509692123",
    }


BROWSER_WORKFLOW_REJECT_CASES = {
    "science": {
        "doi": "10.1126/science.aeg3511",
        "provider": "science",
        "html_asset": "raw.html",
        "markdown_asset": "extracted.md",
        "title": "Magma plumbing beneath Yellowstone",
        "final_url": "https://www.science.org/doi/full/10.1126/science.aeg3511",
        "metadata_builder": _science_paywall_metadata,
        "expected_blocking_fallback_signals": ["aaas_page_type_denial"],
    },
    "wiley": {
        "doi": "10.1111/gcb.16414",
        "provider": "wiley",
        "html_asset": "raw.html",
        "markdown_asset": "extracted.md",
        "title": "Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
        "final_url": "https://onlinelibrary.wiley.com/doi/abs/10.1111/gcb.16414",
        "metadata_builder": _wiley_paywall_metadata,
        "expected_blocking_fallback_signals": ["wiley_access_no", "wiley_format_viewed_abstract"],
    },
    "pnas": {
        "doi": "10.1073/pnas.2509692123",
        "provider": "pnas",
        "html_asset": "raw.html",
        "markdown_asset": "extracted.md",
        "title": "A discrete serotonergic circuit involved in the generation of tinnitus behavior",
        "final_url": "https://www.pnas.org/doi/full/10.1073/pnas.2509692123",
        "metadata_builder": _pnas_paywall_metadata,
        "expected_blocking_fallback_signals": ["pnas_paywall_no_access"],
    },
}


BROWSER_WORKFLOW_ACCEPT_CASES = {
    "science": {
        "doi": "10.1126/science.aeg3511",
        "provider": "science",
        "fixture": SCIENCE_ENTITLED_FIXTURE,
        "final_url": "https://www.science.org/doi/full/10.1126/science.aeg3511",
        "extractor": _science_html.extract_markdown,
        "fallback_title": "Magma plumbing beneath Yellowstone",
    },
    "wiley": {
        "doi": "10.1111/gcb.16998",
        "provider": "wiley",
        "fixture": WILEY_ENTITLED_FIXTURE,
        "final_url": "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16998",
        "extractor": _wiley_html.extract_markdown,
        "fallback_title": "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China",
    },
    "pnas": {
        "doi": "10.1073/pnas.2309123120",
        "provider": "pnas",
        "fixture": PNAS_ENTITLED_FIXTURE,
        "final_url": "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
        "extractor": _pnas_html.extract_markdown,
        "fallback_title": "Amazon deforestation causes strong regional warming",
    },
}



class HtmlAvailabilityTests(unittest.TestCase):
    def _assert_rejected_browser_workflow_case(self, case_name: str) -> None:
        case = BROWSER_WORKFLOW_REJECT_CASES[case_name]
        html = block_asset(case["doi"], case["html_asset"]).read_text(encoding="utf-8")
        markdown = block_asset(case["doi"], case["markdown_asset"]).read_text(encoding="utf-8")
        diagnostics = assess_html_fulltext_availability(
            markdown,
            case["metadata_builder"](html, markdown),
            provider=case["provider"],
            html_text=html,
            title=case["title"],
            final_url=case["final_url"],
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        for signal in case["expected_blocking_fallback_signals"]:
            self.assertIn(signal, diagnostics.blocking_fallback_signals)

    def _assert_accepted_browser_workflow_case(self, case_name: str) -> None:
        case = BROWSER_WORKFLOW_ACCEPT_CASES[case_name]
        html = case["fixture"].read_text(encoding="utf-8")
        markdown, info = case["extractor"](
            html,
            case["final_url"],
            metadata={"doi": case["doi"]},
        )
        title = info.get("title") or case["fallback_title"]
        diagnostics = assess_html_fulltext_availability(
            markdown,
            {
                "title": title,
                "doi": case["doi"],
                "abstract": info.get("abstract_text") or "",
            },
            provider=case["provider"],
            html_text=html,
            title=title,
            final_url=case["final_url"],
            section_hints=info.get("section_hints"),
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertEqual(diagnostics.blocking_fallback_signals, [])

    def test_assess_html_fulltext_accepts_body_sufficient_html_without_figures(self) -> None:
        markdown = "# Example Article\n\n## Results\n\n" + ("Body text " * 120)
        diagnostics = assess_html_fulltext_availability(
            markdown,
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="generic",
            html_text="<html><body><article><div property='articleBody'>Body</div></article></body></html>",
            title="Example Article",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "body_sufficient")
        self.assertEqual(diagnostics.figure_count, 0)

    def test_assess_html_fulltext_rejects_figure_only_teaser(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\nFigure teaser only.",
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="generic",
            html_text=(
                "<html><body><article>"
                "<figure><img src='/fig1.png' /><figcaption>Teaser figure.</figcaption></figure>"
                "</article></body></html>"
            ),
            title="Example Article",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "insufficient_body")
        self.assertEqual(diagnostics.figure_count, 1)
        self.assertIn("has_figures", diagnostics.soft_positive_signals)

    def test_assess_html_fulltext_ignores_paywall_text_outside_body_container(self) -> None:
        body_text = " ".join(["Important body text with enough detail."] * 30)
        html = (
            "<html><body>"
            "<aside>Access through your institution. Purchase access.</aside>"
            "<article><section id='bodymatter' property='articleBody'>"
            "<h1>Example Article</h1>"
            "<h2>Abstract</h2><p>Short abstract.</p>"
            "<h2>Discussion</h2><p>"
            f"{body_text}"
            "</p></section></article>"
            "</body></html>"
        )
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\n## Abstract\n\nShort abstract.\n\n## Discussion\n\n" + body_text,
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="generic",
            html_text=html,
            title="Example Article",
            final_url="https://example.test/article",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "body_sufficient")
        self.assertNotIn("publisher_paywall", diagnostics.hard_negative_signals)
        self.assertIn("explicit_body_container", diagnostics.strong_positive_signals)

    def test_assess_html_fulltext_accepts_narrative_review_without_imrad_headings(self) -> None:
        paragraph = "This review paragraph provides enough narrative detail. It contains multiple sentences for structure. "
        html = (
            "<html><body><article>"
            "<h1>Review Example</h1>"
            f"<p>{paragraph * 2}</p>"
            f"<p>{paragraph * 2}</p>"
            "</article></body></html>"
        )
        diagnostics = assess_html_fulltext_availability(
            "# Review Example\n\n" + (paragraph * 2) + "\n\n" + (paragraph * 2),
            {"title": "Review Example", "doi": "10.1000/review", "article_type": "Review"},
            provider="generic",
            html_text=html,
            title="Review Example",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertIn("narrative_article_type", diagnostics.soft_positive_signals)
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 2)

    def test_assess_html_fulltext_rejects_access_gate_without_body_run(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\nCheck access to continue.\n\nPurchase access.",
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="generic",
            html_text=(
                "<html><body><article><h1>Example Article</h1>"
                "<div class='access-widget'>Check access to continue. Purchase access.</div>"
                "</article></body></html>"
            ),
            title="Example Article",
            final_url="https://example.test/article/access",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "publisher_paywall")

    def test_assess_html_fulltext_rejects_denial_block_inside_body_container(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\n## Abstract\n\nShort abstract.\n\n## Access the full article\n\nView all access options to continue reading this article.",
            {"title": "Example Article", "doi": "10.1000/example", "abstract": "Short abstract."},
            provider="generic",
            html_text=(
                "<html><body><article><section id='bodymatter' property='articleBody'>"
                "<h1>Example Article</h1>"
                "<h2>Abstract</h2><p>Short abstract.</p>"
                "<h2>Access the full article</h2>"
                "<p>View all access options to continue reading this article.</p>"
                "</section></article></body></html>"
            ),
            title="Example Article",
            final_url="https://example.test/article",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertIn("access the full article", diagnostics.blocking_fallback_signals)

    def test_assess_html_fulltext_rejects_references_only_page(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\n## References\n\n1. Example cited work.",
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="generic",
            html_text=(
                "<html><body><article><h1>Example Article</h1><h2>References</h2>"
                "<ol class='references'><li>Example cited work. Another sentence.</li></ol>"
                "</article></body></html>"
            ),
            title="Example Article",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "insufficient_body")

    def test_assess_html_fulltext_rejects_old_elsevier_abstract_page_with_keywords(self) -> None:
        # Mirrors older Elsevier pages like 10.1016/0304-4165(96)00054-2 where
        # browser HTML exposes abstract, keywords, and references but no body.
        abstract_text = (
            "Elongation factor Tu from Escherichia coli is known to polymerize at slightly acidic pH and low ionic "
            "strength. The structure and dynamics of these aggregates have been examined using imaging and "
            "spectroscopic methodologies."
        )
        keywords_block = (
            "Elongation factor Tu. EF-Tu. Polymerization. Light scattering. Phosphorescence. Microscopy. "
            "View Abstract. Copyright 1996 Published by Elsevier B.V."
        )
        diagnostics = assess_html_fulltext_availability(
            (
                "# Old Elsevier Example\n\n"
                "## Abstract\n\n"
                f"{abstract_text}\n\n"
                "## Keywords\n\n"
                f"{keywords_block}\n\n"
                "## References\n\n"
                "1. Example cited work. Another sentence."
            ),
            {
                "title": "Old Elsevier Example",
                "doi": "10.1016/0304-4165(96)00054-2",
                "abstract": abstract_text,
            },
            provider="elsevier",
            html_text=(
                "<html><body><article><section id='bodymatter' property='articleBody'>"
                "<h1>Old Elsevier Example</h1>"
                f"<h2>Abstract</h2><p>{abstract_text}</p>"
                "<h2>Keywords</h2>"
                f"<p>{keywords_block}</p>"
                "<h2>References</h2><ol><li>Example cited work. Another sentence.</li></ol>"
                "</section></article></body></html>"
            ),
            title="Old Elsevier Example",
            final_url="https://www.sciencedirect.com/science/article/pii/0304416596000542",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 0)
        self.assertEqual(diagnostics.body_metrics["word_count"], 0)
        self.assertEqual(diagnostics.body_metrics["body_paragraph_count"], 0)

    def test_assess_html_fulltext_rejects_old_elsevier_cited_by_footer_noise(self) -> None:
        abstract_text = (
            "Elongation factor Tu from Escherichia coli is known to polymerize at slightly acidic pH and low ionic "
            "strength. The structure and dynamics of these aggregates have been examined using imaging and "
            "spectroscopic methodologies."
        )
        diagnostics = assess_html_fulltext_availability(
            (
                "# Old Elsevier Example\n\n"
                "## Abstract\n\n"
                f"{abstract_text}\n\n"
                "Regular paper Old Elsevier Example\n\n"
                "## Cited by (0)\n\n"
                "All content on this site: Copyright 2026 Elsevier B.V., its licensors, and contributors."
            ),
            {
                "title": "Old Elsevier Example",
                "doi": "10.1016/0304-4165(96)00054-2",
                "abstract": abstract_text,
            },
            provider="elsevier",
            html_text=(
                "<html><body>"
                "<h1>Biochimica et Biophysica Acta (BBA) - General Subjects</h1>"
                "<h1>Regular paper Old Elsevier Example</h1>"
                f"<h2>Abstract</h2><p>{abstract_text}</p>"
                "<h2>Cited by (0)</h2>"
                "<p>All content on this site: Copyright 2026 Elsevier B.V., its licensors, and contributors.</p>"
                "</body></html>"
            ),
            title="Old Elsevier Example",
            final_url="https://www.sciencedirect.com/science/article/pii/0304416596000542?via=ihub",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 0)
        self.assertEqual(diagnostics.body_metrics["body_paragraph_count"], 0)

    def test_assess_html_fulltext_rejects_elsevier_canonical_abstract_preview(self) -> None:
        abstract_text = (
            "The UV-visible and NIR absorption spectrum of Nd(III) ions in 1,10-phenanthroline has been recorded and "
            "the observed bands are assigned to different electronic transitions."
        )
        diagnostics = assess_html_fulltext_availability(
            (
                "# Spectrum of Nd(III):1,10-phenanthroline\n\n"
                "## Abstract\n\n"
                f"{abstract_text}\n\n"
                "* et al.*### J. Inorg. Nucl. Chem.\n\n"
                "(1967)\n\n"
                "* et al.*### J. Quant. Spectry. Radiative Transfer\n\n"
                "(1983)"
            ),
            {
                "title": "Spectrum of Nd(III):1,10-phenanthroline",
                "doi": "10.1016/0167-577X(86)90024-8",
                "abstract": abstract_text,
            },
            provider="elsevier",
            html_text=(
                "<html class='Preview'><head>"
                "<link rel='canonical' href='https://www.sciencedirect.com/science/article/abs/pii/0167577X86900248' />"
                "</head><body><article>"
                "<h1>Spectrum of Nd(III):1,10-phenanthroline</h1>"
                f"<h2>Abstract</h2><p>{abstract_text}</p>"
                "<h2>Cited by (0)</h2>"
                "<p>* et al.* J. Inorg. Nucl. Chem. (1967)</p>"
                "<p>* et al.* J. Quant. Spectry. Radiative Transfer (1983)</p>"
                "</article></body></html>"
            ),
            title="Spectrum of Nd(III):1,10-phenanthroline",
            final_url="https://www.sciencedirect.com/science/article/pii/0167577X86900248?via=ihub",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertIn("canonical_abstract_url", diagnostics.blocking_fallback_signals)

    def test_assess_plain_text_accepts_short_editorial_when_marked_narrative(self) -> None:
        paragraph = "This editorial paragraph is concise but still carries full narrative meaning. It has a second sentence. "
        diagnostics = assess_plain_text_fulltext_availability(
            "# Editorial Example\n\nBy Alice Example\n\n" + (paragraph * 2) + "\n\n" + (paragraph * 2),
            {"title": "Editorial Example", "article_type": "Editorial"},
            title="Editorial Example",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertIn("narrative_article_type", diagnostics.soft_positive_signals)
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 2)

    def test_assess_plain_text_rejects_abstract_only_without_metadata_abstract(self) -> None:
        abstract_text = (
            "This abstract remains long enough to look substantial, but it is still only abstract prose. "
            "It adds a second sentence so the detector sees more than a stub. "
        )
        diagnostics = assess_plain_text_fulltext_availability(
            "# Abstract Example\n\n## Abstract\n\n" + (abstract_text * 3),
            {"title": "Abstract Example"},
            title="Abstract Example",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertEqual(diagnostics.body_metrics["word_count"], 0)

    def test_assess_plain_text_ignores_keywords_block_after_front_matter_heading(self) -> None:
        abstract_text = (
            "This abstract is substantial enough to look like article prose, but the page never exposes the main text. "
            "A second sentence keeps the abstract realistic."
        )
        diagnostics = assess_plain_text_fulltext_availability(
            (
                "# Old Elsevier Example\n\n"
                "## Abstract\n\n"
                f"{abstract_text}\n\n"
                "## Keywords\n\n"
                "Keyword one. Keyword two. Keyword three. View Abstract. Copyright 1996 Published by Elsevier B.V.\n\n"
                "## References\n\n"
                "1. Example cited work. Another sentence."
            ),
            {
                "title": "Old Elsevier Example",
                "abstract": abstract_text,
            },
            title="Old Elsevier Example",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 0)
        self.assertEqual(diagnostics.body_metrics["word_count"], 0)

    def test_assess_plain_text_ignores_article_type_prefixed_title_block(self) -> None:
        abstract_text = (
            "This abstract is substantial enough to look like article prose, but the page never exposes the main text. "
            "A second sentence keeps the abstract realistic."
        )
        diagnostics = assess_plain_text_fulltext_availability(
            (
                "# Old Elsevier Example\n\n"
                "## Abstract\n\n"
                f"{abstract_text}\n\n"
                "Regular paper Old Elsevier Example"
            ),
            {
                "title": "Old Elsevier Example",
                "abstract": abstract_text,
            },
            title="Old Elsevier Example",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 0)
        self.assertEqual(diagnostics.body_metrics["word_count"], 0)

    def test_assess_html_rejects_abstract_only_when_metadata_differs_only_by_punctuation(self) -> None:
        abstract_markdown = (
            "This abstract has line breaks and punctuation differences, but no article body survives filtering.\n"
            "A second sentence keeps it looking substantial."
        )
        diagnostics = assess_html_fulltext_availability(
            "# Abstract Example\n\n" + abstract_markdown,
            {
                "title": "Abstract Example",
                "abstract": "This abstract has line breaks and punctuation differences but no article body survives filtering. A second sentence keeps it looking substantial!",
                "citation_abstract_html_url": "https://example.test/article-abstract",
            },
            provider="generic",
            html_text=(
                "<html><head><meta name='WT.z_cg_type' content='Abstract' /></head>"
                "<body><article><p>"
                "This abstract has line breaks and punctuation differences, but no article body survives filtering. "
                "A second sentence keeps it looking substantial."
                "</p></article></body></html>"
            ),
            title="Abstract Example",
            final_url="https://example.test/article-abstract",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertIn("citation_abstract_html_url", diagnostics.soft_positive_signals)

    def test_assess_html_accepts_single_long_body_block_without_headings(self) -> None:
        paragraph = (
            "This narrative body paragraph is long enough to count as full text even without section headings. "
            "It includes a second sentence for prose structure. "
        )
        diagnostics = assess_html_fulltext_availability(
            "# Narrative Example\n\n" + (paragraph * 8),
            {"title": "Narrative Example", "doi": "10.1000/narrative"},
            provider="generic",
            html_text="<html><body><article><p>" + (paragraph * 8) + "</p></article></body></html>",
            title="Narrative Example",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertEqual(diagnostics.reason, "body_sufficient")

    def test_assess_html_rejects_science_paywall_sample_with_abstract(self) -> None:
        self._assert_rejected_browser_workflow_case("science")

    def test_assess_html_accepts_science_entitled_fulltext_fixture(self) -> None:
        self._assert_accepted_browser_workflow_case("science")

    def test_assess_html_rejects_springer_paywall_samples_without_promoting_ancillary_sections(self) -> None:
        ancillary_headings = {
            "Corresponding author",
            "Additional information",
            "Rights and permissions",
            "Profiles",
            "Subscribe and save",
            "Publisher's Note",
        }

        for doi in SPRINGER_PAYWALL_SAMPLE_DOIS:
            with self.subTest(doi=doi):
                html = block_asset(doi, "raw.html").read_text(encoding="utf-8")
                source_url = f"https://link.springer.com/article/{doi}"
                metadata = _springer_html.parse_html_metadata(html, source_url)
                extraction_payload = _springer_html.extract_html_payload(
                    html,
                    source_url,
                    title=str(metadata.get("title") or ""),
                )
                diagnostics = assess_html_fulltext_availability(
                    extraction_payload["markdown_text"],
                    metadata,
                    provider="springer",
                    html_text=html,
                    title=str(metadata.get("title") or ""),
                    final_url=source_url,
                    section_hints=extraction_payload["section_hints"],
                )

                self.assertFalse(diagnostics.accepted)
                self.assertEqual(diagnostics.content_kind, "abstract_only")
                self.assertEqual(diagnostics.reason, "abstract_only")
                self.assertIn("check access", diagnostics.blocking_fallback_signals)
                self.assertIn("access this article", diagnostics.blocking_fallback_signals)
                self.assertIn("buy now", diagnostics.blocking_fallback_signals)
                self.assertFalse(
                    ancillary_headings
                    & {
                        str(hint.get("heading") or "")
                        for hint in extraction_payload["section_hints"]
                        if hint.get("kind") == "body"
                    }
                )

    def test_assess_html_rejects_wiley_paywall_metadata_with_abstract(self) -> None:
        self._assert_rejected_browser_workflow_case("wiley")

    def test_assess_html_accepts_wiley_fulltext_fixture_despite_login_chrome(self) -> None:
        self._assert_accepted_browser_workflow_case("wiley")

    def test_assess_html_rejects_pnas_paywall_metadata_with_abstract(self) -> None:
        self._assert_rejected_browser_workflow_case("pnas")

    def test_assess_html_accepts_pnas_fulltext_fixture_despite_institutional_login_chrome(self) -> None:
        self._assert_accepted_browser_workflow_case("pnas")

    def test_body_metrics_excludes_nonliteral_data_availability_when_section_hints_are_present(self) -> None:
        markdown = (
            "# Example Article\n\n"
            "## Availability Statement\n\n"
            + ("The supporting dataset is archived in a repository with a persistent identifier. " * 20)
        )

        metrics = body_metrics(
            markdown,
            {"title": "Example Article"},
            section_hints=[
                {
                    "heading": "Availability Statement",
                    "level": 2,
                    "kind": "data_availability",
                    "order": 0,
                }
            ],
        )

        self.assertEqual(metrics["char_count"], 0)
        self.assertEqual(metrics["body_block_count"], 0)

    def test_body_metrics_excludes_real_structural_back_matter_and_chrome_headings(self) -> None:
        real_fixture_cases = (
            {
                "doi": "10.1111/gcb.15322",
                "raw_phrase": "research funding",
                "provider": "wiley",
                "source_url": "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
                "extractor": _wiley_html.extract_markdown,
            },
            {
                "doi": "10.1126/sciadv.abg9690",
                "raw_phrase": "statement of competing interests",
                "provider": "science",
                "source_url": "https://www.science.org/doi/10.1126/sciadv.abg9690",
                "extractor": _science_html.extract_markdown,
            },
        )
        for case in real_fixture_cases:
            with self.subTest(doi=case["doi"]):
                html = golden_criteria_asset(case["doi"], "original.html").read_text(encoding="utf-8", errors="ignore")
                self.assertIn(case["raw_phrase"], html.casefold())
                markdown, info = case["extractor"](
                    html,
                    case["source_url"],
                    metadata={"doi": case["doi"]},
                )
                metrics = body_metrics(
                    markdown,
                    {"doi": case["doi"]},
                    section_hints=info.get("section_hints"),
                    noise_profile=case["provider"],
                )

                self.assertNotIn(case["raw_phrase"], markdown.casefold())
                self.assertNotIn(case["raw_phrase"], metrics["text"].casefold())

        nature_html = golden_criteria_asset("10.1038/nature13376", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        nature_html_text = nature_html.casefold()
        self.assertTrue("acknowledgements" in nature_html_text)
        self.assertTrue("rights and permissions" in nature_html_text)
        self.assertTrue("open access" in nature_html_text)
        nature_payload = _springer_html.extract_html_payload(
            nature_html,
            "https://www.nature.com/articles/nature13376",
        )
        nature_metrics = body_metrics(
            nature_payload["markdown_text"],
            {"doi": "10.1038/nature13376"},
            section_hints=nature_payload["section_hints"],
            noise_profile="springer_nature",
        )

        self.assertNotIn("acknowledgements", nature_metrics["text"].casefold())
        self.assertNotIn("rights and permissions", nature_payload["markdown_text"].casefold())
        self.assertNotIn("open access", nature_payload["markdown_text"].casefold())

    def test_assess_plain_text_excludes_nonliteral_data_availability_when_section_hints_are_present(self) -> None:
        markdown = (
            "# Example Article\n\n"
            "## Availability Statement\n\n"
            + ("The supporting dataset is archived in a repository with a persistent identifier. " * 20)
        )

        diagnostics = assess_plain_text_fulltext_availability(
            markdown,
            {"title": "Example Article"},
            title="Example Article",
            section_hints=[
                {
                    "heading": "Availability Statement",
                    "level": 2,
                    "kind": "data_availability",
                    "order": 0,
                }
            ],
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "metadata_only")

    def test_assess_structured_article_accepts_single_narrative_body_section(self) -> None:
        article = SimpleNamespace(
            quality=SimpleNamespace(has_fulltext=True),
            sections=[
                SimpleNamespace(kind="abstract", text="Abstract only."),
                SimpleNamespace(
                    kind="commentary",
                    text=(
                        "This perspective section contains enough narrative detail to count as body text. "
                        "It includes a second sentence so the structure detector treats it as substantial prose."
                    ),
                ),
            ],
            assets=[],
            metadata=SimpleNamespace(title="Structured Narrative Example"),
        )

        diagnostics = assess_structured_article_fulltext_availability(article, title="Structured Narrative Example")

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "structured_body_sections")



if __name__ == "__main__":
    unittest.main()
