from __future__ import annotations

from dataclasses import fields
import unittest
import urllib.parse

from paper_fetch.providers import (
    _atypon_browser_workflow_profiles as atypon_profiles,
    _script_json,
    browser_workflow,
)
from paper_fetch.providers._atypon_browser_workflow_profiles import (
    ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES,
    build_html_candidates,
    build_pdf_candidates,
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page,
    site_rule_for_publisher,
    publisher_profile,
)
from paper_fetch.providers._pdf_candidates import extract_pdf_candidate_urls_from_html
from paper_fetch.provider_catalog import PROVIDER_CATALOG
from paper_fetch.providers.base import RawFulltextPayload
from paper_fetch.providers.acs import AcsClient
from paper_fetch.providers.aip import AipClient
from paper_fetch.providers.ams import AmsClient
from paper_fetch.providers.pnas import PnasClient
from paper_fetch.providers.mdpi import MdpiClient
from paper_fetch.providers.mdpi import MDPI_BROWSER_PROFILE
from paper_fetch.providers.iop import IOP_BROWSER_PROFILE
from paper_fetch.providers.annualreviews import ANNUALREVIEWS_BROWSER_PROFILE
from paper_fetch.providers.royalsocietypublishing import (
    ROYAL_SOCIETY_BROWSER_PROFILE,
)
from paper_fetch.providers.science import ScienceClient
from paper_fetch.providers.wiley import WileyClient
from tests.provider_benchmark_samples import provider_benchmark_sample


SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
ACS_SAMPLE = provider_benchmark_sample("acs")
AIP_SAMPLE = provider_benchmark_sample("aip")


class AtyponBrowserWorkflowCandidateTests(unittest.TestCase):
    def test_shared_doi_path_builder_quotes_reserved_suffix_characters(self) -> None:
        doi = "10.1000/path?query#fragment%escape"
        for provider in ("acs", "aip", "wiley", "science", "pnas"):
            with self.subTest(provider=provider):
                candidates = [
                    *build_html_candidates(provider, doi),
                    *build_pdf_candidates(provider, doi, None),
                ]
                self.assertTrue(candidates)
                for candidate in candidates:
                    parsed = urllib.parse.urlsplit(candidate)
                    self.assertIn(parsed.query, {"", "download=true"})
                    self.assertEqual(parsed.fragment, "")
                    self.assertNotIn("query", parsed.query)
                    self.assertNotIn("fragment", parsed.query)
                    self.assertNotIn("escape", parsed.query)
                    self.assertIn("%3F", parsed.path)
                    self.assertIn("%23", parsed.path)
                    self.assertIn("%25", parsed.path)

    def test_atypon_profile_scope_is_catalog_aligned(self) -> None:
        self.assertEqual(
            ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES,
            ("science", "pnas", "wiley", "ams", "acs", "iop", "aip"),
        )
        self.assertTrue(
            set(ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES) <= set(PROVIDER_CATALOG)
        )
        with self.assertRaisesRegex(
            ValueError, "Unsupported Atypon browser-workflow HTML publisher"
        ):
            build_html_candidates("springer", "10.1007/example")

    def test_all_browser_profiles_derive_routing_fields_from_catalog(self) -> None:
        profiles = [
            ScienceClient.profile,
            PnasClient.profile,
            WileyClient.profile,
            AmsClient.profile,
            AcsClient.profile,
            AipClient.profile,
            MDPI_BROWSER_PROFILE,
            IOP_BROWSER_PROFILE,
            ANNUALREVIEWS_BROWSER_PROFILE,
            ROYAL_SOCIETY_BROWSER_PROFILE,
        ]
        for profile in profiles:
            with self.subTest(provider=profile.name):
                browser_workflow.validate_browser_profile_catalog_sync(profile)

    def test_atypon_profiles_register_provider_owned_callbacks(self) -> None:
        for name in ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES:
            with self.subTest(provider=name):
                profile = publisher_profile(name)
                self.assertTrue(
                    any(
                        getattr(profile.dom_hooks, field.name) is not None
                        for field in fields(profile.dom_hooks)
                    )
                )
                self.assertIsNotNone(profile.scoped_asset_extractor)

        self.assertIsNotNone(publisher_profile("science").is_front_matter_teaser_figure)
        self.assertIsNone(publisher_profile("springer").scoped_asset_extractor)

    def test_atypon_profile_modules_are_resolved_from_provider_names(self) -> None:
        self.assertFalse(hasattr(atypon_profiles, "_PUBLISHER_MODULES"))
        for name in ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES:
            with self.subTest(provider=name):
                module = atypon_profiles._publisher_module(name)
                self.assertIsNotNone(module)
                self.assertEqual(module.__name__, f"paper_fetch.providers._{name}_html")

    def test_site_rule_merges_default_and_publisher_overrides(self) -> None:
        cases = {
            "science": {
                "candidate_selectors": {
                    ".article__fulltext",
                    "[itemprop='articleBody']",
                },
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
                "candidate_selectors": {
                    ".article-section__content",
                    "[itemprop='articleBody']",
                },
                "remove_selectors": {".publicationHistory", ".cookie-banner"},
                "drop_keywords": {"access-widget", "rightslink"},
                "drop_text": {"Recommended articles", "Check for updates"},
            },
            "ams": {
                "candidate_selectors": {".NLM_body", "[itemprop='articleBody']"},
                "remove_selectors": {".article-tools", ".cookie-banner"},
                "drop_keywords": {"download", "rightslink"},
                "drop_text": {"Check for updates"},
            },
            "acs": {
                "candidate_selectors": {".article_content", "[itemprop='articleBody']"},
                "remove_selectors": {".articleMetrics", ".cookie-banner"},
                "drop_keywords": {"article-metrics", "rightslink"},
                "drop_text": {"Download Citation", "Check for updates"},
            },
            "aip": {
                "candidate_selectors": {"#itemFullTextId", "[itemprop='articleBody']"},
                "remove_selectors": {".article-metrics", ".cookie-banner"},
                "drop_keywords": {"article-metrics", "rightslink"},
                "drop_text": {"Download Citation", "Check for updates"},
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
            build_html_candidates("pnas", PNAS_SAMPLE.doi)[:2],
            [
                f"https://www.pnas.org/doi/full/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
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

    def test_pnas_and_mdpi_use_headless_fulltext_readiness_selectors(self) -> None:
        pnas_readiness = PnasClient(None, {}).require_profile().html_readiness
        self.assertIsNotNone(pnas_readiness)
        assert pnas_readiness is not None
        self.assertFalse(pnas_readiness.wait_for_article_body)
        self.assertEqual(pnas_readiness.selector, '[data-extent="bodymatter"]')

        mdpi_readiness = MdpiClient(None, {}).require_profile().html_readiness
        self.assertIsNotNone(mdpi_readiness)
        assert mdpi_readiness is not None
        self.assertTrue(mdpi_readiness.wait_for_article_body)
        self.assertIsNone(mdpi_readiness.selector)
        self.assertEqual(
            build_pdf_candidates("wiley", WILEY_SAMPLE.doi, None)[:4],
            [
                f"https://onlinelibrary.wiley.com/doi/epdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
            ],
        )
        ams_doi = "10.1175/jcli-d-23-0738.1"
        ams_landing = (
            "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml"
        )
        self.assertEqual(
            build_html_candidates("ams", ams_doi, ams_landing),
            [ams_landing],
        )
        self.assertEqual(build_pdf_candidates("ams", ams_doi, None), [])
        self.assertEqual(
            build_html_candidates("acs", ACS_SAMPLE.doi)[:2],
            [
                f"https://pubs.acs.org/doi/full/{ACS_SAMPLE.doi}",
                f"https://pubs.acs.org/doi/{ACS_SAMPLE.doi}",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("acs", ACS_SAMPLE.doi, None)[:3],
            [
                f"https://pubs.acs.org/doi/epdf/{ACS_SAMPLE.doi}",
                f"https://pubs.acs.org/doi/pdf/{ACS_SAMPLE.doi}",
                f"https://pubs.acs.org/doi/pdf/{ACS_SAMPLE.doi}?download=true",
            ],
        )
        self.assertEqual(
            build_html_candidates("aip", AIP_SAMPLE.doi)[:2],
            [
                f"https://pubs.aip.org/doi/full/{AIP_SAMPLE.doi}",
                f"https://pubs.aip.org/doi/{AIP_SAMPLE.doi}",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("aip", AIP_SAMPLE.doi, None)[:2],
            [
                f"https://pubs.aip.org/doi/epdf/{AIP_SAMPLE.doi}",
                f"https://pubs.aip.org/doi/pdf/{AIP_SAMPLE.doi}",
            ],
        )

    def test_provider_profiles_match_candidate_builder_priority(self) -> None:
        crossref_pdf_url = (
            f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf"
        )
        cases = (
            ("science", ScienceClient(None, {}), SCIENCE_SAMPLE.doi, None),
            ("pnas", PnasClient(None, {}), PNAS_SAMPLE.doi, None),
            ("wiley", WileyClient(None, {}), WILEY_SAMPLE.doi, crossref_pdf_url),
            ("acs", AcsClient(None, {}), ACS_SAMPLE.doi, None),
            ("aip", AipClient(None, {}), AIP_SAMPLE.doi, None),
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
                self.assertEqual(
                    client.html_candidates(doi, metadata),
                    build_html_candidates(provider, doi),
                )
                self.assertEqual(
                    client.pdf_candidates(doi, metadata),
                    build_pdf_candidates(provider, doi, pdf_url),
                )

    def test_ams_client_uses_explicit_pdf_candidates_without_atypon_default_pdf_paths(
        self,
    ) -> None:
        doi = "10.1175/jcli-d-23-0738.1"
        landing_url = (
            "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml"
        )
        crossref_pdf_url = "https://journals.ametsoc.org/downloadpdf/journals/clim/37/24/JCLI-D-23-0738.1.xml"
        client = AmsClient(None, {})

        self.assertEqual(
            client.html_candidates(doi, {"doi": doi, "landing_page_url": landing_url}),
            [landing_url],
        )
        self.assertEqual(
            client.pdf_candidates(
                doi,
                {
                    "doi": doi,
                    "landing_page_url": landing_url,
                    "fulltext_links": [
                        {"url": crossref_pdf_url, "content_type": "text/html"}
                    ],
                },
            ),
            [
                crossref_pdf_url,
                "https://journals.ametsoc.org/downloadpdf/journals/clim/37/24/JCLI-D-23-0738.1.pdf",
                "https://journals.ametsoc.org/downloadpdf/view/journals/clim/37/24/JCLI-D-23-0738.1.xml",
                "https://journals.ametsoc.org/downloadpdf/view/journals/clim/37/24/JCLI-D-23-0738.1.pdf",
            ],
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

    def test_extract_pdf_url_from_crossref_recognizes_ams_downloadpdf_links(
        self,
    ) -> None:
        pdf_url = "https://journals.ametsoc.org/downloadpdf/journals/clim/37/24/JCLI-D-23-0738.1.xml"

        self.assertEqual(
            extract_pdf_url_from_crossref(
                {"fulltext_links": [{"url": pdf_url, "content_type": "text/html"}]}
            ),
            pdf_url,
        )

    def test_extract_pdf_candidates_recognizes_pdfjs_default_url(self) -> None:
        html = """
        <html><head><script>
        PDFViewerApplicationOptions.set('defaultUrl',
          "/downloadpdf/view/journals/bams/aop/BAMS-D-24-0270.1/BAMS-D-24-0270.1.pdf?pdfJsInlineViewToken=1&amp;inlineView=true");
        </script></head></html>
        """

        self.assertEqual(
            extract_pdf_candidate_urls_from_html(
                html,
                "https://journals.ametsoc.org/pdfviewer/full/journals/bams/aop/BAMS-D-24-0270.1/BAMS-D-24-0270.1.xml",
            ),
            [
                "https://journals.ametsoc.org/downloadpdf/view/journals/bams/aop/BAMS-D-24-0270.1/BAMS-D-24-0270.1.pdf?pdfJsInlineViewToken=1&inlineView=true"
            ],
        )

    def test_provider_clients_use_canonical_browser_workflow_runtime(self) -> None:
        clients = (
            ScienceClient(None, {}),
            PnasClient(None, {}),
            WileyClient(None, {}),
            AmsClient(None, {}),
            AcsClient(None, {}),
        )

        for client in clients:
            with self.subTest(provider=client.name):
                self.assertIsInstance(client, browser_workflow.BrowserWorkflowClient)
                self.assertIsInstance(
                    client.profile, browser_workflow.ProviderBrowserProfile
                )

    def test_atypon_browser_workflow_client_alias_is_removed(self) -> None:
        self.assertFalse(hasattr(browser_workflow, "AtyponBrowserWorkflowClient"))
        self.assertFalse(
            hasattr(browser_workflow, "preferred_html_candidate_from_landing_page")
        )

    def test_provider_profile_article_source_label_and_hooks(self) -> None:
        cases = (
            (ScienceClient(None, {}), None, "Science", "science"),
            (PnasClient(None, {}), None, "PNAS", "pnas"),
            (WileyClient(None, {}), "wiley_browser", "Wiley", "wiley"),
            (AmsClient(None, {}), None, "AMS", "ams"),
            (AcsClient(None, {}), None, "ACS", "acs"),
        )

        for client, article_source_name, label, markdown_publisher in cases:
            with self.subTest(provider=client.name):
                self.assertEqual(
                    client.profile.article_source_name, article_source_name
                )
                self.assertEqual(
                    client.article_source(), article_source_name or client.name
                )
                self.assertEqual(client.provider_label(), label)
                self.assertEqual(client.profile.markdown_publisher, markdown_publisher)
                self.assertTrue(client.profile.shared_browser_image_fetcher)

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

        science_extract_authors = ScienceClient(
            None, {}
        ).profile.fallback_author_extractor
        pnas_extract_authors = PnasClient(None, {}).profile.fallback_author_extractor
        wiley_extract_authors = WileyClient(None, {}).profile.fallback_author_extractor
        ams_extract_authors = AmsClient(None, {}).profile.fallback_author_extractor
        acs_extract_authors = AcsClient(None, {}).profile.fallback_author_extractor
        assert science_extract_authors is not None
        assert pnas_extract_authors is not None
        assert wiley_extract_authors is not None
        assert ams_extract_authors is not None
        assert acs_extract_authors is not None

        self.assertEqual(
            science_extract_authors(science_html), ["Ada Lovelace", "Grace Hopper"]
        )
        self.assertEqual(pnas_extract_authors(pnas_html), ["PNAS DOM"])
        self.assertEqual(
            pnas_extract_authors(pnas_meta_only_html),
            ["Edward Example", "Dana Creator"],
        )
        self.assertEqual(wiley_extract_authors(wiley_html), ["Meta Author"])
        self.assertEqual(ams_extract_authors(wiley_html), ["Meta Author"])
        self.assertEqual(acs_extract_authors(wiley_html), ["Meta Author"])

        wiley_dom_only_html = """
        <html><body>
          <div class="accordion-tabbed">
            <p class="author-name">Ada Author <a data-test="orcid-link" href="https://orcid.org/0000">ORCID</a></p>
            <p class="author-name">Department of Biology, University of Example, Oxford, United Kingdom</p>
            <p class="author-name">Grace Author <a data-test="author-search-link">Search for more papers by this author</a></p>
          </div>
        </body></html>
        """
        self.assertEqual(
            wiley_extract_authors(wiley_dom_only_html), ["Ada Author", "Grace Author"]
        )

    def test_script_json_helpers_extract_balanced_payloads(self) -> None:
        html = """
        <html><script>
          AAASdataLayer = {"page":{"pageInfo":{"author":"Ada Lovelace|Grace Hopper","note":"};if("}}};
          dataLayer.push({"event":"article","authors":["Ada Lovelace"]});
        </script></html>
        """

        science_extract_authors = ScienceClient(
            None, {}
        ).profile.fallback_author_extractor
        assert science_extract_authors is not None
        self.assertEqual(
            science_extract_authors(html), ["Ada Lovelace", "Grace Hopper"]
        )
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

        article = client.to_article_model(
            {"doi": "10.1126/example", "title": "Example"}, raw_payload
        )

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
                f"https://www.pnas.org/doi/full/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
