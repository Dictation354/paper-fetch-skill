from __future__ import annotations

import unittest

from paper_fetch.providers import _pnas_html, _science_html, _script_json, _wiley_html, browser_workflow
from paper_fetch.providers._science_pnas_profiles import (
    build_html_candidates,
    build_pdf_candidates,
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page,
    site_rule_for_publisher,
)
from paper_fetch.providers.base import RawFulltextPayload
from paper_fetch.providers.pnas import PnasClient
from paper_fetch.providers.science import ScienceClient
from paper_fetch.providers.wiley import WileyClient
from tests.provider_benchmark_samples import provider_benchmark_sample


SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


class SciencePnasCandidateTests(unittest.TestCase):
    def test_site_rule_merges_default_and_publisher_overrides(self) -> None:
        cases = {
            "science": {
                "candidate_selectors": {".article__fulltext", "[itemprop='articleBody']"},
                "remove_selectors": {".article-header__access", ".cookie-banner"},
                "drop_keywords": {"advert", "rightslink"},
                "drop_text": {"Permissions", "Check for updates"},
            },
            "pnas": {
                "candidate_selectors": {".core-container", "[itemprop='articleBody']"},
                "remove_selectors": {".article__reference-links", ".cookie-banner"},
                "drop_keywords": {"tab-nav", "rightslink"},
                "drop_text": {"Check for updates"},
            },
            "wiley": {
                "candidate_selectors": {".article-section__content", "[itemprop='articleBody']"},
                "remove_selectors": {".publicationHistory", ".cookie-banner"},
                "drop_keywords": {"access-widget", "rightslink"},
                "drop_text": {"Recommended articles", "Check for updates"},
            },
        }

        for publisher, expectations in cases.items():
            with self.subTest(publisher=publisher):
                rule = site_rule_for_publisher(publisher)
                self.assertEqual(
                    len(rule["candidate_selectors"]),
                    len(set(rule["candidate_selectors"])),
                )
                self.assertEqual(
                    len(rule["remove_selectors"]),
                    len(set(rule["remove_selectors"])),
                )
                for key, values in expectations.items():
                    for value in values:
                        self.assertIn(value, rule[key])

    def test_candidate_builders_match_expected_priority(self) -> None:
        self.assertEqual(
            build_html_candidates("science", SCIENCE_SAMPLE.doi)[:2],
            [
                f"https://www.science.org/doi/full/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/{SCIENCE_SAMPLE.doi}",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("science", SCIENCE_SAMPLE.doi, None)[:3],
            [
                f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/pdf/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/pdf/{SCIENCE_SAMPLE.doi}?download=true",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("pnas", PNAS_SAMPLE.doi, None)[:3],
            [
                f"https://www.pnas.org/doi/epdf/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}?download=true",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("wiley", WILEY_SAMPLE.doi, None)[:4],
            [
                f"https://onlinelibrary.wiley.com/doi/epdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
            ],
        )

    def test_provider_profiles_match_candidate_builder_priority(self) -> None:
        crossref_pdf_url = f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf"
        cases = (
            ("science", ScienceClient(None, {}), SCIENCE_SAMPLE.doi, None),
            ("pnas", PnasClient(None, {}), PNAS_SAMPLE.doi, None),
            ("wiley", WileyClient(None, {}), WILEY_SAMPLE.doi, crossref_pdf_url),
        )

        for provider, client, doi, pdf_url in cases:
            with self.subTest(provider=provider):
                metadata = {
                    "doi": doi,
                    "fulltext_links": (
                        [{"url": pdf_url, "content_type": "unspecified"}]
                        if pdf_url
                        else []
                    ),
                }
                self.assertEqual(client.profile.name, provider)
                self.assertEqual(client.html_candidates(doi, metadata), build_html_candidates(provider, doi))
                self.assertEqual(
                    client.pdf_candidates(doi, metadata),
                    build_pdf_candidates(provider, doi, pdf_url),
                )

    def test_extract_pdf_url_from_crossref_recognizes_wiley_fullpdf_links(self) -> None:
        crossref_pdf_url = extract_pdf_url_from_crossref(
            {
                "fulltext_links": [
                    {
                        "url": f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
                        "content_type": "unspecified",
                    }
                ]
            }
        )

        self.assertEqual(
            crossref_pdf_url,
            f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
        )
        self.assertEqual(
            build_pdf_candidates("wiley", WILEY_SAMPLE.doi, crossref_pdf_url)[:5],
            [
                f"https://onlinelibrary.wiley.com/doi/epdf/{WILEY_SAMPLE.doi}",
                f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
                f"https://onlinelibrary.wiley.com/doi/pdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
            ],
        )

    def test_provider_clients_use_canonical_browser_workflow_runtime(self) -> None:
        clients = (ScienceClient(None, {}), PnasClient(None, {}), WileyClient(None, {}))

        for client in clients:
            with self.subTest(provider=client.name):
                self.assertIsInstance(client, browser_workflow.BrowserWorkflowClient)
                self.assertIsInstance(client.profile, browser_workflow.ProviderBrowserProfile)

    def test_science_pnas_client_alias_is_removed(self) -> None:
        self.assertFalse(hasattr(browser_workflow, "SciencePnasClient"))

    def test_provider_profile_article_source_label_and_hooks(self) -> None:
        cases = (
            (ScienceClient(None, {}), None, "Science", "science"),
            (PnasClient(None, {}), None, "PNAS", "pnas"),
            (WileyClient(None, {}), "wiley_browser", "Wiley", "wiley"),
        )

        for client, article_source_name, label, markdown_publisher in cases:
            with self.subTest(provider=client.name):
                self.assertEqual(client.profile.article_source_name, article_source_name)
                self.assertEqual(client.article_source(), article_source_name or client.name)
                self.assertEqual(client.provider_label(), label)
                self.assertEqual(client.profile.markdown_publisher, markdown_publisher)
                self.assertTrue(client.profile.shared_playwright_image_fetcher)

    def test_shared_author_helpers_preserve_provider_strategies(self) -> None:
        science_html = """
        <html><script>AAASdataLayer={"page":{"pageInfo":{"author":"Ada Lovelace|Grace Hopper"}}};</script>
        <body><div class="contributors"><div property="author"><span property="name">DOM Science</span></div></div></body></html>
        """
        pnas_html = """
        <html><head>
          <meta name="citation_author" content="Edward Example" />
          <meta name="dc.creator" content="Dana Creator" />
        </head><body>
          <div class="contributors"><div property="author"><span property="name">PNAS DOM</span></div></div>
        </body></html>
        """
        pnas_meta_only_html = """
        <html><head>
          <meta name="citation_author" content="Edward Example" />
          <meta name="dc.creator" content="Dana Creator" />
        </head><body></body></html>
        """
        wiley_html = """
        <html><head>
          <meta name="citation_author" content="Meta Author" />
        </head><body>
          <a class="author-name"><span>DOM Author</span></a>
        </body></html>
        """

        self.assertEqual(_science_html.extract_authors(science_html), ["Ada Lovelace", "Grace Hopper"])
        self.assertEqual(_pnas_html.extract_authors(pnas_html), ["PNAS DOM"])
        self.assertEqual(_pnas_html.extract_authors(pnas_meta_only_html), ["Edward Example", "Dana Creator"])
        self.assertEqual(_wiley_html.extract_authors(wiley_html), ["Meta Author"])

    def test_script_json_helpers_extract_balanced_payloads(self) -> None:
        html = """
        <html><script>
          AAASdataLayer = {"page":{"pageInfo":{"author":"Ada Lovelace|Grace Hopper","note":"};if("}}};
          dataLayer.push({"event":"article","authors":["Ada Lovelace"]});
        </script></html>
        """

        self.assertEqual(_science_html.extract_authors(html), ["Ada Lovelace", "Grace Hopper"])
        self.assertEqual(
            _script_json.extract_function_call_json(html, "dataLayer.push"),
            {"event": "article", "authors": ["Ada Lovelace"]},
        )

    def test_profile_author_fallback_populates_article_metadata(self) -> None:
        client = ScienceClient(None, {})
        html = """
        <html><script>AAASdataLayer={"page":{"pageInfo":{"author":"Ada Lovelace|Grace Hopper"}}};</script></html>
        """
        raw_payload = RawFulltextPayload(
            provider="science",
            source_url="https://www.science.org/doi/full/10.1126/example",
            content_type="text/html",
            body=html.encode("utf-8"),
            metadata={
                "route": "html",
                "markdown_text": "# Example\n\n## Results\n\n" + ("Body text " * 120),
                "source_trail": ["fulltext:science_html_ok"],
            },
        )

        article = client.to_article_model({"doi": "10.1126/example", "title": "Example"}, raw_payload)

        self.assertEqual(article.metadata.authors, ["Ada Lovelace", "Grace Hopper"])

    def test_html_candidates_prioritize_matching_landing_page_url(self) -> None:
        candidates = build_html_candidates(
            "science",
            SCIENCE_SAMPLE.doi,
            landing_page_url=f"https://science.org/doi/{SCIENCE_SAMPLE.doi}",
        )

        self.assertEqual(candidates[0], f"https://science.org/doi/{SCIENCE_SAMPLE.doi}")
        self.assertEqual(
            preferred_html_candidate_from_landing_page(
                "science",
                SCIENCE_SAMPLE.doi,
                f"https://science.org/doi/{SCIENCE_SAMPLE.doi}",
            ),
            f"https://science.org/doi/{SCIENCE_SAMPLE.doi}",
        )
        self.assertEqual(
            candidates[1:3],
            [
                f"https://science.org/doi/full/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/full/{SCIENCE_SAMPLE.doi}",
            ],
        )

    def test_html_candidates_ignore_non_matching_landing_page_url(self) -> None:
        candidates = build_html_candidates(
            "pnas",
            PNAS_SAMPLE.doi,
            landing_page_url=f"https://example.com/doi/{PNAS_SAMPLE.doi}",
        )

        self.assertIsNone(
            preferred_html_candidate_from_landing_page(
                "pnas",
                PNAS_SAMPLE.doi,
                f"https://example.com/doi/{PNAS_SAMPLE.doi}",
            )
        )
        self.assertEqual(
            candidates[:2],
            [
                f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/full/{PNAS_SAMPLE.doi}",
            ],
        )



if __name__ == "__main__":
    unittest.main()
