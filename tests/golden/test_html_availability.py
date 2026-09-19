from __future__ import annotations
from paper_fetch.quality.html_availability import (
    assess_html_fulltext_availability,
)
import unittest
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.extraction.html._runtime import body_metrics
from paper_fetch.providers import _springer_html as springer_html
from paper_fetch.providers import browser_workflow
from tests.block_fixtures import block_asset
from tests.golden_criteria import golden_criteria_asset


SCIENCE_ENTITLED_FIXTURE = golden_criteria_asset(
    "10.1126/science.aeg3511", "original.html"
)
WILEY_ENTITLED_FIXTURE = golden_criteria_asset("10.1111/gcb.16998", "original.html")
PNAS_ENTITLED_FIXTURE = golden_criteria_asset(
    "10.1073/pnas.2309123120", "original.html"
)
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
        "abstract": markdown.split("## Access the full article", 1)[0]
        .split("## Abstract", 1)[1]
        .strip(),
    }


def _wiley_paywall_metadata(html: str, markdown: str) -> dict[str, str]:
    metadata = parse_html_metadata(
        html, "https://onlinelibrary.wiley.com/doi/abs/10.1111/gcb.16414"
    )
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
        "expected_blocking_fallback_signals": [
            "wiley_access_no",
            "wiley_format_viewed_abstract",
        ],
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
        "extractor": "science",
        "fallback_title": "Magma plumbing beneath Yellowstone",
    },
    "wiley": {
        "doi": "10.1111/gcb.16998",
        "provider": "wiley",
        "fixture": WILEY_ENTITLED_FIXTURE,
        "final_url": "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16998",
        "extractor": "wiley",
        "fallback_title": "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China",
    },
    "pnas": {
        "doi": "10.1073/pnas.2309123120",
        "provider": "pnas",
        "fixture": PNAS_ENTITLED_FIXTURE,
        "final_url": "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
        "extractor": "pnas",
        "fallback_title": "Amazon deforestation causes strong regional warming",
    },
}


def _extract_browser_workflow_markdown(
    publisher: str,
    html_text: str,
    source_url: str,
    *,
    metadata: dict[str, str] | None = None,
):
    return browser_workflow.extract_atypon_browser_workflow_markdown(
        html_text,
        source_url,
        publisher,
        metadata=metadata,
    )


class HtmlAvailabilityTests(unittest.TestCase):
    def _assert_rejected_browser_workflow_case(self, case_name: str) -> None:
        case = BROWSER_WORKFLOW_REJECT_CASES[case_name]
        html = block_asset(case["doi"], case["html_asset"]).read_text(encoding="utf-8")
        markdown = block_asset(case["doi"], case["markdown_asset"]).read_text(
            encoding="utf-8"
        )
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
        markdown, info = _extract_browser_workflow_markdown(
            case["extractor"],
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

    def test_body_metrics_excludes_real_structural_back_matter_and_chrome_headings(
        self,
    ) -> None:
        real_fixture_cases = (
            {
                "doi": "10.1111/gcb.15322",
                "raw_phrase": "research funding",
                "provider": "wiley",
                "source_url": "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
                "extractor": "wiley",
            },
            {
                "doi": "10.1126/sciadv.abg9690",
                "raw_phrase": "statement of competing interests",
                "provider": "science",
                "source_url": "https://www.science.org/doi/10.1126/sciadv.abg9690",
                "extractor": "science",
            },
        )
        for case in real_fixture_cases:
            with self.subTest(doi=case["doi"]):
                html = golden_criteria_asset(case["doi"], "original.html").read_text(
                    encoding="utf-8", errors="ignore"
                )
                self.assertIn(case["raw_phrase"], html.casefold())
                markdown, info = _extract_browser_workflow_markdown(
                    case["extractor"],
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

        nature_html = golden_criteria_asset(
            "10.1038/nature13376", "original.html"
        ).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        nature_html_text = nature_html.casefold()
        self.assertTrue("acknowledgements" in nature_html_text)
        self.assertTrue("rights and permissions" in nature_html_text)
        self.assertTrue("open access" in nature_html_text)
        nature_payload = springer_html.extract_html_payload(
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
        self.assertNotIn(
            "rights and permissions", nature_payload["markdown_text"].casefold()
        )
        self.assertNotIn("open access", nature_payload["markdown_text"].casefold())

    def test_assess_html_rejects_science_paywall_sample_with_abstract(self) -> None:
        self._assert_rejected_browser_workflow_case("science")

    def test_assess_html_accepts_science_entitled_fulltext_fixture(self) -> None:
        self._assert_accepted_browser_workflow_case("science")

    def test_assess_html_rejects_springer_paywall_samples_without_promoting_ancillary_sections(
        self,
    ) -> None:
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
                metadata = springer_html.parse_html_metadata(html, source_url)
                extraction_payload = springer_html.extract_html_payload(
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
                self.assertIn(
                    "access this article", diagnostics.blocking_fallback_signals
                )
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

    def test_assess_html_accepts_wiley_fulltext_fixture_despite_login_chrome(
        self,
    ) -> None:
        self._assert_accepted_browser_workflow_case("wiley")

    def test_assess_html_rejects_pnas_paywall_metadata_with_abstract(self) -> None:
        self._assert_rejected_browser_workflow_case("pnas")

    def test_assess_html_accepts_pnas_fulltext_fixture_despite_institutional_login_chrome(
        self,
    ) -> None:
        self._assert_accepted_browser_workflow_case("pnas")


if __name__ == "__main__":
    unittest.main()
