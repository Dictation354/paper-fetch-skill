from __future__ import annotations

import unittest
from unittest import mock
from pathlib import Path
import tempfile

from paper_fetch import publisher_identity
from paper_fetch.providers.base import (
    ProviderClient,
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.providers._reference_doi import reference_doi_match


class PublisherIdentityTests(unittest.TestCase):
    def test_normalize_doi_handles_url_and_prefix(self) -> None:
        self.assertEqual(
            publisher_identity.normalize_doi(
                "https://doi.org/10.1016/J.RSE.2026.115369"
            ),
            "10.1016/j.rse.2026.115369",
        )
        self.assertEqual(
            publisher_identity.normalize_doi("doi:10.1111/ABC"),
            "10.1111/abc",
        )
        self.assertEqual(
            publisher_identity.normalize_doi(
                "https://doi.org/10.1175/1520-0469%281967%29024%3C0241%3ATEOTAW%3E2.0.CO%3B2"
            ),
            "10.1175/1520-0469(1967)024<0241:teotaw>2.0.co;2",
        )
        self.assertEqual(
            publisher_identity.normalize_doi(
                "https://doi.org/10.1002/(SICI)1097-4571(199505)46:4%3C282::AID-ASI5%3E3.0.CO%3B2-0"
            ),
            "10.1002/(sici)1097-4571(199505)46:4<282::aid-asi5>3.0.co;2-0",
        )

    def test_normalize_doi_falls_back_when_idutils_is_unavailable(self) -> None:
        original_import_module = publisher_identity.importlib.import_module

        def import_without_idutils(name: str, *args, **kwargs):
            if name == "idutils":
                raise ImportError("missing idutils")
            return original_import_module(name, *args, **kwargs)

        publisher_identity._idutils_module.cache_clear()
        try:
            with mock.patch.object(
                publisher_identity.importlib,
                "import_module",
                side_effect=import_without_idutils,
            ):
                self.assertEqual(
                    publisher_identity.normalize_doi("doi:10.1111/ABC"),
                    "10.1111/abc",
                )
        finally:
            publisher_identity._idutils_module.cache_clear()

    def test_infer_provider_from_doi(self) -> None:
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1038/nphys1170"), "springer"
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1016/j.solener.2024.01.001"),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1111/example"), "wiley"
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1126/science.ady3136"),
            "science",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1073/pnas.81.23.7500"),
            "pnas",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_doi("10.1021/acsomega.4c03987"),
            "acs",
        )

    def test_identity_failure_precedes_any_related_asset_write(self) -> None:
        class IdentityClient(ProviderClient):
            name = "identity-test"

            def __init__(self) -> None:
                self.asset_calls = 0

            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                del doi, metadata, context
                content = ProviderContent(
                    route_kind="xml",
                    source_url="https://example.test/wrong.xml",
                    content_type="application/xml",
                    body=b"<article />",
                    merged_metadata={
                        "doi": "10.1000/wrong",
                        "identity_evidence": {"doi": "10.1000/wrong"},
                    },
                )
                return RawFulltextPayload(
                    provider=self.name,
                    source_url=content.source_url,
                    content_type=content.content_type,
                    body=content.body,
                    content=content,
                )

            def download_related_assets(self, *args, **kwargs):
                del args, kwargs
                self.asset_calls += 1
                raise AssertionError("identity mismatch must stop asset downloads")

            def to_article_model(self, *args, **kwargs):
                del args, kwargs
                raise AssertionError("identity mismatch must stop conversion")

        client = IdentityClient()
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ProviderFailure) as raised:
                client.fetch_result(
                    "10.1000/expected",
                    {"doi": "10.1000/expected", "title": "Expected"},
                    Path(tmpdir),
                    asset_profile="all",
                )

        self.assertEqual(raised.exception.code, "identity_mismatch")
        self.assertEqual(client.asset_calls, 0)

    def test_extract_doi_handles_embedded_text_and_trailing_punctuation(self) -> None:
        self.assertEqual(
            publisher_identity.extract_doi(
                "Find it at DOI: 10.1016/J.RSE.2026.115369)."
            ),
            "10.1016/j.rse.2026.115369",
        )
        self.assertEqual(
            publisher_identity.extract_doi(
                "doi=10.1175/1520-0469(1967)024&lt;0241:TEOTAW&gt;2.0.CO;2"
            ),
            "10.1175/1520-0469(1967)024<0241:teotaw>2.0.co;2",
        )
        self.assertEqual(
            publisher_identity.extract_doi(
                "URL https://doi.org/10.1002/(SICI)1097-4571(199505)46:4%3C282::AID-ASI5%3E3.0.CO%3B2-0"
            ),
            "10.1002/(sici)1097-4571(199505)46:4<282::aid-asi5>3.0.co;2-0",
        )
        self.assertEqual(
            publisher_identity.extract_doi("HTML doi:10.1000/example</p>"),
            "10.1000/example",
        )
        self.assertIsNone(publisher_identity.extract_doi("No DOI here."))

    def test_extract_doi_from_url_strips_known_provider_route_suffixes(self) -> None:
        cases = {
            "https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1101972/full": "10.3389/fmars.2023.1101972",
            "https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1101972/pdf": "10.3389/fmars.2023.1101972",
            "https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1101972/xml": "10.3389/fmars.2023.1101972",
            "https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1101972/epub": "10.3389/fmars.2023.1101972",
            "https://iopscience.iop.org/article/10.1088/1748-9326/ab7d02/pdf?download=true": "10.1088/1748-9326/ab7d02",
            "https://onlinelibrary.wiley.com/wol1/doi/10.1111/example/fullpdf": "10.1111/example",
            "https://link.springer.com/content/pdf/10.1038%2Fexample.pdf": "10.1038/example",
        }

        for url, doi in cases.items():
            with self.subTest(url=url):
                self.assertEqual(publisher_identity.extract_doi_from_url(url), doi)

    def test_extract_doi_from_url_handles_query_parameter_doi(self) -> None:
        self.assertEqual(
            publisher_identity.extract_doi_from_url(
                "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0123456&type=manuscript"
            ),
            "10.1371/journal.pone.0123456",
        )

    def test_extract_doi_from_url_preserves_unknown_provider_suffixes(self) -> None:
        self.assertEqual(
            publisher_identity.extract_doi_from_url(
                "https://example.org/doi/10.1234/foo/pdf"
            ),
            "10.1234/foo/pdf",
        )

    def test_extract_doi_from_url_preserves_sici_doi_params(self) -> None:
        self.assertEqual(
            publisher_identity.extract_doi_from_url(
                "https://doi.org/10.1175/1520-0469(1967)024<0241:TEOTAW>2.0.CO;2"
            ),
            "10.1175/1520-0469(1967)024<0241:teotaw>2.0.co;2",
        )

    def test_reference_doi_match_handles_sici_doi(self) -> None:
        match = reference_doi_match(
            "10.1002/(SICI)1097-4571(199505)46:4<282::AID-ASI5>3.0.CO;2-0"
        )

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(
            publisher_identity.normalize_doi(match.group(0)),
            "10.1002/(sici)1097-4571(199505)46:4<282::aid-asi5>3.0.co;2-0",
        )

    def test_infer_provider_from_publisher(self) -> None:
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("Springer Nature"),
            "springer",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("Elsevier BV"), "elsevier"
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("Elsevier Ltd"), "elsevier"
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("Elsevier Masson SAS"),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("John Wiley & Sons"),
            "wiley",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "American Association for the Advancement of Science"
            ),
            "science",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "Proceedings of the National Academy of Sciences of the United States of America"
            ),
            "pnas",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "American Chemical Society"
            ),
            "acs",
        )

    def test_infer_provider_from_url(self) -> None:
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
            ),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://www.sciencedirect.com/science/article/pii/S0021863496900852"
            ),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://www.springernature.com/gp/journal/12345"
            ),
            "springer",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://onlinelibrary.wiley.com/doi/10.1111/example"
            ),
            "wiley",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://www.science.org/doi/full/10.1126/science.ady3136"
            ),
            "science",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://www.pnas.org/doi/10.1073/pnas.81.23.7500"
            ),
            "pnas",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://pubs.acs.org/doi/10.1021/acsomega.4c03987"
            ),
            "acs",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url(
                "https://newjournal.copernicus.org/articles/1/1/2026/"
            ),
            "copernicus",
        )
        self.assertIsNone(
            publisher_identity.infer_provider_from_url(
                "https://science.org.example.test/doi/test"
            )
        )

    def test_infer_provider_from_signals_prefers_domain_then_publisher_then_doi(
        self,
    ) -> None:
        candidates = publisher_identity.ordered_provider_candidates(
            landing_urls=[
                "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
            ],
            publishers=["Springer Nature"],
            doi="10.1111/example",
        )

        self.assertEqual(
            candidates,
            [
                ("elsevier", "domain"),
                ("springer", "publisher"),
                ("wiley", "doi"),
            ],
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_signals(
                landing_urls=[
                    "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"
                ],
                publishers=["Springer Nature"],
                doi="10.1111/example",
            ),
            "elsevier",
        )

    def test_validate_extracted_identity_rejects_explicit_doi_mismatch(self) -> None:
        result = publisher_identity.validate_extracted_identity(
            {"doi": "10.1000/expected", "title": "Expected title"},
            {},
            {"doi": "10.1000/other", "title": "Expected title"},
        )

        self.assertTrue(result.mismatch)
        self.assertEqual(result.method, "doi")
        self.assertEqual(result.expected_doi, "10.1000/expected")
        self.assertEqual(result.observed_doi, "10.1000/other")

    def test_validate_extracted_identity_accepts_strong_title_when_doi_missing(
        self,
    ) -> None:
        result = publisher_identity.validate_extracted_identity(
            {"doi": "10.1000/expected", "title": "A reproducible research article"},
            {},
            {"title": "A reproducible research article"},
        )

        self.assertFalse(result.mismatch)
        self.assertEqual(result.status, "match")
        self.assertEqual(result.method, "title")

    def test_validate_extracted_identity_applies_arxiv_version_rules(self) -> None:
        unversioned = publisher_identity.validate_extracted_identity(
            {"doi": "10.48550/arXiv.2605.06665"},
            {},
            {"arxiv_id": "2605.06665v2"},
        )
        mismatched_version = publisher_identity.validate_extracted_identity(
            {"doi": "10.48550/arXiv.2605.06665v1"},
            {},
            {"arxiv_id": "2605.06665v2"},
        )

        self.assertEqual(unversioned.status, "match")
        self.assertTrue(mismatched_version.mismatch)


if __name__ == "__main__":
    unittest.main()
