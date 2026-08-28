from __future__ import annotations

from typing import get_args
import unittest
import xml.etree.ElementTree as ET

from paper_fetch import publisher_identity
from paper_fetch.provider_catalog import (
    DEFAULT_BODY_TEXT_THRESHOLDS,
    PROVIDER_CATALOG,
    ProviderRouteSpec,
    ProviderSpec,
    SOURCE_PROVIDER_MAP,
    api_like_hosts,
    compile_route_execution_policy_for_kind,
    default_asset_profile_for_provider,
    default_asset_profile_for_source,
    is_official_provider,
    known_article_source_names,
    matching_provider_domain,
    official_provider_names,
    provider_api_url_template,
    provider_base_domains,
    provider_body_text_thresholds,
    provider_crossref_pdf_position,
    provider_domain_matches,
    provider_emits_html_managed_marker,
    provider_for_source,
    provider_for_xml_source,
    provider_html_path_templates,
    provider_managed_abstract_only_names,
    provider_metadata_probe_short_circuit,
    provider_names,
    provider_pdf_source_path_templates,
    provider_pdf_path_templates,
    provider_persists_provider_html,
    provider_display_names,
    provider_supports_metadata_api_probe,
    provider_status_order,
    sources_by_provider,
)
from paper_fetch.extraction.html.provider_rules import (
    COMMON_ACCESS_BLOCK_TOKENS,
    IEEE_ACCESS_BLOCK_TEXT_TOKENS,
    IEEE_AVAILABILITY_DROP_KEYWORDS,
    IEEE_EXTRACTION_CLEANUP_SELECTORS,
    SPRINGER_NATURE_DISPLAY_FORMULA_SELECTORS,
    SPRINGER_NATURE_FORMULA_CONTAINER_TOKENS,
)
from paper_fetch.quality.html_profiles import site_rule_for_publisher
from paper_fetch_devtools.quality_issues import EXPECTED_FULLTEXT_SOURCES_BY_PROVIDER
from paper_fetch.models.schema import SourceKind
from paper_fetch.providers import _pdf_candidates, html_springer_nature
from paper_fetch import utils
from paper_fetch.mcp.fetch_tool import _PROVIDER_STATUS_ORDER
from paper_fetch.providers.registry import build_clients
from paper_fetch.workflow import fulltext, routing


class DummyTransport:
    pass


class ProviderCatalogTests(unittest.TestCase):
    def test_registry_clients_are_declared_in_catalog(self) -> None:
        clients = build_clients(DummyTransport(), {})

        self.assertEqual(set(clients), set(PROVIDER_CATALOG))
        for name, client in clients.items():
            self.assertEqual(client.name, name)

    def test_catalog_defaults_and_status_order_are_complete(self) -> None:
        valid_asset_profiles = {"none", "body", "all"}
        status_order = provider_status_order()

        self.assertEqual(set(status_order), set(PROVIDER_CATALOG))
        self.assertEqual(len(status_order), len(set(status_order)))
        self.assertEqual(
            list(status_order),
            [
                spec.name
                for spec in sorted(
                    PROVIDER_CATALOG.values(), key=lambda item: item.status_order
                )
            ],
        )
        for spec in PROVIDER_CATALOG.values():
            self.assertIn(spec.asset_default, valid_asset_profiles)
            self.assertEqual(
                default_asset_profile_for_provider(spec.name), spec.asset_default
            )
            self.assertTrue(spec.client_factory_path)
            self.assertEqual(
                provider_supports_metadata_api_probe(spec.name),
                spec.probe_capability == "metadata_api",
            )

    def test_body_asset_providers_declare_bounded_explicit_asset_routes(self) -> None:
        browser_recovery_without_direct_retries = {
            "wiley",
            "science",
            "pnas",
            "ieee",
            "mdpi",
            "royalsocietypublishing",
            "acs",
            "iop",
            "aip",
            "tandf",
        }

        for spec in PROVIDER_CATALOG.values():
            if spec.asset_default == "none":
                continue
            with self.subTest(provider=spec.name):
                asset_routes = [
                    route for route in spec.routes if route.kind == "assets"
                ]
                self.assertTrue(asset_routes)
                policy = compile_route_execution_policy_for_kind(spec.name, "assets")
                self.assertEqual(policy.timeout_seconds, 20)
                self.assertEqual(policy.asset_concurrency_cap, 2)
                if spec.name in browser_recovery_without_direct_retries:
                    self.assertEqual(policy.transient_retries, 0)

    def test_explicit_routes_are_not_augmented(self) -> None:
        spec = ProviderSpec(
            name="example",
            display_name="Example",
            official=True,
            domains=("example.test",),
            doi_prefixes=("10.9999/",),
            publisher_aliases=("example",),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="example:Client",
            status_order=99,
            routes=(
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    timeout_seconds=20,
                    concurrency=2,
                ),
            ),
        )

        self.assertEqual(
            [(route.name, route.kind) for route in spec.routes],
            [("assets", "assets")],
        )

    def test_body_asset_provider_without_explicit_asset_route_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit assets route"):
            ProviderSpec(
                name="invalid",
                display_name="Invalid",
                official=True,
                domains=("invalid.test",),
                doi_prefixes=("10.9998/",),
                publisher_aliases=("invalid",),
                asset_default="body",
                probe_capability="routing_signal",
                provider_managed_abstract_only=False,
                client_factory_path="invalid:Client",
                status_order=100,
                routes=(ProviderRouteSpec(name="direct_html", kind="html"),),
            )

    def test_wiley_tries_verified_doi_route_before_full_route(self) -> None:
        self.assertEqual(
            provider_html_path_templates("wiley"),
            ("/doi/{doi}", "/doi/full/{doi}"),
        )

    def test_provider_rule_constants_keep_shared_and_incremental_layers(self) -> None:
        self.assertTrue(
            set(COMMON_ACCESS_BLOCK_TOKENS) < set(IEEE_ACCESS_BLOCK_TEXT_TOKENS)
        )
        self.assertIn("institutional sign in", IEEE_ACCESS_BLOCK_TEXT_TOKENS)
        self.assertIn("purchase access", IEEE_ACCESS_BLOCK_TEXT_TOKENS)

        for selector in ("script", "style", "noscript", "iframe", "button", "input"):
            self.assertNotIn(selector, IEEE_EXTRACTION_CLEANUP_SELECTORS)
        self.assertIn("accesstype", IEEE_EXTRACTION_CLEANUP_SELECTORS)
        self.assertNotIn("accessType", IEEE_EXTRACTION_CLEANUP_SELECTORS)
        self.assertIn("select", IEEE_EXTRACTION_CLEANUP_SELECTORS)
        self.assertIn("textarea", IEEE_EXTRACTION_CLEANUP_SELECTORS)
        self.assertIn(".zoom-container", IEEE_EXTRACTION_CLEANUP_SELECTORS)
        self.assertIn("button[data-docId]", IEEE_EXTRACTION_CLEANUP_SELECTORS)

        for keyword in ("download", "metrics", "recommend", "rightslink"):
            self.assertNotIn(keyword, IEEE_AVAILABILITY_DROP_KEYWORDS)
            self.assertIn(keyword, site_rule_for_publisher("ieee")["drop_keywords"])
        self.assertIn("references-modal", IEEE_AVAILABILITY_DROP_KEYWORDS)

        self.assertEqual(
            SPRINGER_NATURE_DISPLAY_FORMULA_SELECTORS,
            tuple(f".{token}" for token in SPRINGER_NATURE_FORMULA_CONTAINER_TOKENS),
        )

    def test_official_and_provider_managed_sets_are_catalog_derived(self) -> None:
        self.assertEqual(
            set(official_provider_names()),
            {name for name, spec in PROVIDER_CATALOG.items() if spec.official},
        )
        self.assertEqual(
            provider_managed_abstract_only_names(),
            {
                name
                for name, spec in PROVIDER_CATALOG.items()
                if spec.provider_managed_abstract_only
            },
        )

    def test_runtime_provider_order_constants_are_catalog_derived(self) -> None:
        self.assertEqual(
            set(routing.OFFICIAL_PROVIDER_NAMES), set(official_provider_names())
        )
        self.assertEqual(
            set(fulltext.PROVIDER_MANAGED_ABSTRACT_ONLY_PROVIDERS),
            set(provider_managed_abstract_only_names()),
        )
        self.assertEqual(_PROVIDER_STATUS_ORDER, provider_names())
        self.assertEqual(_PROVIDER_STATUS_ORDER, provider_status_order())

    def test_provider_display_name_helper_wraps_catalog(self) -> None:
        for name, display_name in provider_display_names().items():
            self.assertEqual(utils.provider_display_name(name), display_name)

        self.assertEqual(utils.provider_display_name("pnas"), "PNAS")
        self.assertEqual(utils.provider_display_name("ams"), "AMS")
        self.assertEqual(
            utils.provider_display_name("unknown-provider"), "Unknown Provider"
        )
        self.assertEqual(utils.provider_display_name(""), "Provider")

    def test_is_official_provider_follows_catalog(self) -> None:
        for name, spec in PROVIDER_CATALOG.items():
            self.assertEqual(is_official_provider(name), spec.official)

        self.assertTrue(is_official_provider(" Elsevier "))
        self.assertFalse(is_official_provider("crossref"))
        self.assertFalse(is_official_provider("unknown"))
        self.assertFalse(is_official_provider(None))

    def test_source_asset_defaults_follow_provider_catalog(self) -> None:
        for source, provider in SOURCE_PROVIDER_MAP.items():
            self.assertEqual(
                default_asset_profile_for_source(source),
                default_asset_profile_for_provider(provider),
            )
        self.assertEqual(default_asset_profile_for_source("unknown_source"), "none")

    def test_provider_for_source_follows_source_provider_map(self) -> None:
        for source, provider in SOURCE_PROVIDER_MAP.items():
            self.assertEqual(provider_for_source(source), provider)

        self.assertEqual(provider_for_source(" Elsevier_XML "), "elsevier")
        self.assertIsNone(provider_for_source("unknown_source"))
        self.assertIsNone(provider_for_source(None))

    def test_known_article_source_names_include_all_source_keys(self) -> None:
        self.assertEqual(known_article_source_names(), frozenset(SOURCE_PROVIDER_MAP))

    def test_source_kind_literal_matches_known_article_sources(self) -> None:
        self.assertEqual(frozenset(get_args(SourceKind)), known_article_source_names())

    def test_sources_by_provider_are_derived_from_source_provider_map(self) -> None:
        expected = {}
        for source, provider in SOURCE_PROVIDER_MAP.items():
            expected.setdefault(provider, set()).add(source)

        self.assertEqual(
            sources_by_provider(),
            {provider: frozenset(sources) for provider, sources in expected.items()},
        )
        self.assertEqual(EXPECTED_FULLTEXT_SOURCES_BY_PROVIDER, sources_by_provider())

    def test_every_declared_source_maps_to_catalog_provider(self) -> None:
        for source, provider in SOURCE_PROVIDER_MAP.items():
            with self.subTest(source=source):
                self.assertIn(provider, PROVIDER_CATALOG)
                self.assertEqual(provider_for_source(source), provider)

        self.assertEqual(provider_for_source("springer_pdf"), "springer")

    def test_api_like_hosts_are_catalog_derived(self) -> None:
        self.assertIn("scopus.com", api_like_hosts())
        self.assertIn("www.scopus.com", api_like_hosts())
        self.assertTrue(
            utils.is_api_like_url("https://www.scopus.com/inward/record.uri?scp=123")
        )
        self.assertTrue(utils.is_api_like_url("https://api.example.org/v1/articles"))
        self.assertFalse(
            utils.is_api_like_url("https://www.scopus.com.evil.test/landing")
        )

    def test_springer_nature_host_helpers_read_catalog_domains(self) -> None:
        self.assertTrue(provider_domain_matches("springer", "www.nature.com"))
        self.assertEqual(
            matching_provider_domain("springer", "www.nature.com"), "nature.com"
        )
        self.assertTrue(
            html_springer_nature.is_springer_nature_url(
                "https://www.nature.com/articles/example"
            )
        )
        self.assertTrue(
            html_springer_nature.is_nature_url(
                "https://www.nature.com/articles/example"
            )
        )
        self.assertFalse(
            html_springer_nature.is_nature_url(
                "https://link.springer.com/article/example"
            )
        )
        self.assertFalse(provider_domain_matches("springer", "springer.com.evil.test"))

        candidates = _pdf_candidates.build_springer_pdf_candidates(
            "10.1038/example",
            {},
            source_url="https://www.nature.com/articles/example",
        )
        self.assertIn("https://www.nature.com/articles/example.pdf", candidates)

    def test_provider_api_templates_are_catalog_derived(self) -> None:
        self.assertEqual(
            provider_api_url_template("wiley", "tdm_pdf"),
            "https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
        )
        self.assertIsNone(provider_api_url_template("springer", "tdm_pdf"))

    def test_atypon_browser_route_templates_are_catalog_derived(self) -> None:
        self.assertEqual(
            provider_base_domains("science"), ("www.science.org", "science.org")
        )
        self.assertEqual(
            provider_html_path_templates("science"), ("/doi/full/{doi}", "/doi/{doi}")
        )
        self.assertEqual(
            provider_pdf_path_templates("pnas"),
            (
                "/doi/epdf/{doi}",
                "/doi/pdf/{doi}?download=true",
                "/doi/pdf/{doi}",
            ),
        )
        self.assertEqual(provider_pdf_path_templates("ams"), ())
        self.assertEqual(provider_base_domains("acs"), ("pubs.acs.org",))
        self.assertEqual(
            provider_html_path_templates("acs"), ("/doi/full/{doi}", "/doi/{doi}")
        )
        self.assertEqual(provider_crossref_pdf_position("wiley"), 1)

    def test_springer_pdf_templates_are_catalog_derived(self) -> None:
        self.assertEqual(provider_base_domains("springer"), ("link.springer.com",))
        self.assertEqual(
            provider_pdf_path_templates("springer"),
            ("/content/pdf/{doi_quoted}.pdf",),
        )
        source_templates = provider_pdf_source_path_templates("springer")
        self.assertEqual(len(source_templates), 1)
        self.assertEqual(source_templates[0].domain, "nature.com")
        self.assertEqual(source_templates[0].path_prefix, "/articles/")
        self.assertEqual(source_templates[0].path_template, "{source_path}.pdf")

        candidates = _pdf_candidates.build_springer_pdf_candidates(
            "10.1038/example",
            {},
            source_url="https://www.nature.com/articles/example",
        )
        self.assertEqual(
            candidates,
            [
                "https://www.nature.com/articles/example.pdf",
                "https://link.springer.com/content/pdf/10.1038%2Fexample.pdf",
            ],
        )

    def test_provider_catalog_mapping_is_read_only(self) -> None:
        with self.assertRaises(TypeError):
            PROVIDER_CATALOG["arxiv"] = PROVIDER_CATALOG["arxiv"]  # type: ignore[index]

    def test_arxiv_metadata_probe_short_circuit_is_catalog_derived(self) -> None:
        callback = provider_metadata_probe_short_circuit("arxiv")

        self.assertIsNotNone(callback)
        result = routing.probe_official_provider(
            "arxiv",
            doi="10.48550/arxiv.2605.06663",
            clients={},
        )

        self.assertEqual(result.state, "positive")
        self.assertEqual(result.metadata["provider"], "arxiv")
        self.assertEqual(result.metadata["arxiv_id"], "2605.06663")
        self.assertEqual(result.metadata["pdf_url"], "https://arxiv.org/pdf/2605.06663")
        self.assertIsNone(provider_metadata_probe_short_circuit("elsevier"))

    def test_provider_html_persistence_is_catalog_derived(self) -> None:
        self.assertTrue(provider_persists_provider_html("springer"))
        self.assertTrue(provider_persists_provider_html("arxiv"))
        self.assertFalse(provider_persists_provider_html("wiley"))
        self.assertFalse(provider_persists_provider_html(None))

    def test_xml_source_provider_inference_is_catalog_derived(self) -> None:
        self.assertEqual(
            provider_for_xml_source(
                "full-text-retrieval-response",
                "/tmp/10.1016_example/original.xml",
            ),
            "elsevier",
        )
        self.assertEqual(
            provider_for_xml_source(
                "article",
                "/tmp/10.5194_acp-24-1-2024/original.xml",
            ),
            "copernicus",
        )
        self.assertEqual(
            provider_for_xml_source("article", "/tmp/10.1038_example/original.xml"),
            "springer",
        )
        self.assertEqual(
            provider_for_xml_source("unknown-root", "/tmp/payload.xml"),
            "unknown",
        )
        neutral = ET.fromstring("<article />")
        self.assertEqual(
            provider_for_xml_source(
                "article",
                "/tmp/payload.xml",
                xml_root=neutral,
            ),
            "unknown",
        )
        for doi, publisher, expected in (
            ("10.1038/example", "Springer Nature", "springer"),
            ("10.5194/example", "Copernicus Publications", "copernicus"),
            ("10.1371/example", "Public Library of Science", "plos"),
            ("10.3389/example", "Frontiers Media S.A.", "frontiers"),
        ):
            with self.subTest(doi=doi):
                root = ET.fromstring(
                    "<article><front><journal-meta>"
                    f"<publisher><publisher-name>{publisher}</publisher-name></publisher>"
                    "</journal-meta><article-meta>"
                    f'<article-id pub-id-type="doi">{doi}</article-id>'
                    "</article-meta></front></article>"
                )
                self.assertEqual(
                    provider_for_xml_source(
                        "article",
                        "/tmp/payload.xml",
                        xml_root=root,
                    ),
                    expected,
                )
        conflict = ET.fromstring(
            "<article><front><journal-meta><publisher>"
            "<publisher-name>Frontiers Media S.A.</publisher-name>"
            "</publisher></journal-meta><article-meta>"
            '<article-id pub-id-type="doi">10.1371/conflict</article-id>'
            "</article-meta></front></article>"
        )
        self.assertEqual(
            provider_for_xml_source(
                "article",
                "/tmp/payload.xml",
                xml_root=conflict,
            ),
            "unknown",
        )

    def test_provider_fallback_and_body_thresholds_are_catalog_derived(self) -> None:
        self.assertFalse(provider_emits_html_managed_marker("crossref"))
        self.assertFalse(provider_emits_html_managed_marker("copernicus"))
        self.assertTrue(provider_emits_html_managed_marker("springer"))
        self.assertEqual(provider_body_text_thresholds("copernicus").min_chars, 500)
        self.assertEqual(
            provider_body_text_thresholds("springer"), DEFAULT_BODY_TEXT_THRESHOLDS
        )
        self.assertEqual(
            provider_body_text_thresholds("ams"), DEFAULT_BODY_TEXT_THRESHOLDS
        )

    def test_fulltext_provider_attempt_skips_non_official_catalog_provider(
        self,
    ) -> None:
        class ExplodingProvider:
            def fetch_result(self, *args, **kwargs):
                raise AssertionError(
                    "non-official providers should not enter fulltext provider attempts"
                )

        warnings: list[str] = []
        source_trail: list[str] = []

        article = fulltext._try_official_provider(
            doi="10.5555/example",
            metadata={},
            provider_name="crossref",
            strategy=fulltext.FetchStrategy(),
            artifact_store=object(),
            context=object(),
            clients={"crossref": ExplodingProvider()},
            outputs=fulltext._ProviderAttemptOutputs(
                warnings=warnings,
                source_trail=source_trail,
            ),
        )

        self.assertIsNone(article)
        self.assertEqual(warnings, [])
        self.assertEqual(source_trail, [])

    def test_catalog_preserves_publisher_doi_domain_inference(self) -> None:
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1038/nphys1170"), "springer"
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1016/j.solener.2024.01.001"),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1109/ACCESS.2024.3352924"),
            "ieee",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.5194/acp-24-1-2024"),
            "copernicus",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1175/jcli-d-23-0738.1"),
            "ams",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1021/acsomega.4c03987"),
            "acs",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.48550/arXiv.2605.06663"),
            "arxiv",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("John Wiley & Sons"),
            "wiley",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("Copernicus Publications"),
            "copernicus",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("arXiv"), "arxiv"
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "American Meteorological Society"
            ),
            "ams",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "Institute of Electrical and Electronics Engineers"
            ),
            "ieee",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "American Chemical Society"
            ),
            "acs",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
            ),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://ieeexplore.ieee.org/document/10388355/"
            ),
            "ieee",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://acp.copernicus.org/articles/24/1/2024/"
            ),
            "copernicus",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://cp.copernicus.org/articles/19/1/2023/"
            ),
            "copernicus",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://egusphere.copernicus.org/preprints/2026/example/"
            ),
            "copernicus",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://brand-new-journal.copernicus.org/articles/1/1/2026/"
            ),
            "copernicus",
        )
        self.assertIsNone(
            publisher_identity.infer_provider_from_url(
                "https://copernicus.org.example.test/articles/1"
            )
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://arxiv.org/abs/2605.06663v1"
            ),
            "arxiv",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml"
            ),
            "ams",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://pubs.acs.org/doi/10.1021/acsomega.4c03987"
            ),
            "acs",
        )
        self.assertEqual(
            publisher_identity.ordered_provider_candidates(
                landing_urls=[
                    "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
                ],
                publishers=["Springer Nature"],
                doi="10.1111/example",
            ),
            [("elsevier", "domain"), ("springer", "publisher"), ("wiley", "doi")],
        )


if __name__ == "__main__":
    unittest.main()
