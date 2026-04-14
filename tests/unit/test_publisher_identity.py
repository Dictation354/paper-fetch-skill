from __future__ import annotations

import unittest

from paper_fetch import publisher_identity


class PublisherIdentityTests(unittest.TestCase):
    def test_normalize_doi_handles_url_and_prefix(self) -> None:
        self.assertEqual(
            publisher_identity.normalize_doi("https://doi.org/10.1016/J.RSE.2026.115369"),
            "10.1016/j.rse.2026.115369",
        )
        self.assertEqual(
            publisher_identity.normalize_doi("doi:10.1111/ABC"),
            "10.1111/abc",
        )

    def test_infer_provider_from_doi(self) -> None:
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1038/nphys1170"), "springer")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1016/j.solener.2024.01.001"), "elsevier")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1111/example"), "wiley")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1126/science.ady3136"), "science")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1073/pnas.81.23.7500"), "pnas")

    def test_extract_doi_handles_embedded_text_and_trailing_punctuation(self) -> None:
        self.assertEqual(
            publisher_identity.extract_doi("Find it at DOI: 10.1016/J.RSE.2026.115369)."),
            "10.1016/j.rse.2026.115369",
        )
        self.assertIsNone(publisher_identity.extract_doi("No DOI here."))

    def test_infer_provider_from_publisher(self) -> None:
        self.assertEqual(publisher_identity.infer_provider_from_publisher("Springer Nature"), "springer")
        self.assertEqual(publisher_identity.infer_provider_from_publisher("Elsevier BV"), "elsevier")
        self.assertEqual(publisher_identity.infer_provider_from_publisher("Elsevier Ltd"), "elsevier")
        self.assertEqual(publisher_identity.infer_provider_from_publisher("Elsevier Masson SAS"), "elsevier")
        self.assertEqual(publisher_identity.infer_provider_from_publisher("John Wiley & Sons"), "wiley")
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher("American Association for the Advancement of Science"),
            "science",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_publisher(
                "Proceedings of the National Academy of Sciences of the United States of America"
            ),
            "pnas",
        )

    def test_infer_provider_from_url(self) -> None:
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://www.sciencedirect.com/science/article/pii/S0021863496900852"),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://www.springernature.com/gp/journal/12345"),
            "springer",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://onlinelibrary.wiley.com/doi/10.1111/example"),
            "wiley",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://www.science.org/doi/full/10.1126/science.ady3136"),
            "science",
        )
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://www.pnas.org/doi/10.1073/pnas.81.23.7500"),
            "pnas",
        )

    def test_infer_provider_from_signals_prefers_domain_then_publisher_then_doi(self) -> None:
        candidates = publisher_identity.ordered_provider_candidates(
            landing_urls=["https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"],
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
                landing_urls=["https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"],
                publishers=["Springer Nature"],
                doi="10.1111/example",
            ),
            "elsevier",
        )


if __name__ == "__main__":
    unittest.main()
