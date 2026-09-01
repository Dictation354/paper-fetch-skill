from __future__ import annotations

import unittest

from paper_fetch.provider_catalog import (
    provider_domains,
    provider_landing_path_templates,
    provider_pdf_path_templates,
    provider_xml_path_templates,
)
from paper_fetch.providers.copernicus import _candidate_urls


DOI = "10.5194/acp-24-1-2024"
LANDING_URL = "https://acp.copernicus.org/articles/24/1/2024/"
XML_URL = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024.xml"
PDF_URL = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024.pdf"


class CopernicusProviderCatalogTests(unittest.TestCase):
    def test_copernicus_path_templates_are_catalog_derived(self) -> None:
        self.assertEqual(provider_domains("copernicus"), ("copernicus.org",))
        self.assertEqual(
            provider_landing_path_templates("copernicus"),
            ("/articles/{volume}/{page}/{year}/",),
        )
        self.assertEqual(
            provider_xml_path_templates("copernicus"),
            ("/articles/{volume}/{page}/{year}/{suffix}.xml",),
        )
        self.assertEqual(
            provider_pdf_path_templates("copernicus"),
            ("/articles/{volume}/{page}/{year}/{suffix}.pdf",),
        )
        self.assertEqual(provider_landing_path_templates("unknown"), ())
        self.assertEqual(provider_xml_path_templates(None), ())

    def test_copernicus_doi_templates_preserve_generated_urls(self) -> None:
        self.assertEqual(
            _candidate_urls(
                DOI,
                templates=provider_landing_path_templates("copernicus"),
            ),
            [LANDING_URL],
        )
        self.assertEqual(
            _candidate_urls(DOI, templates=provider_xml_path_templates("copernicus")),
            [XML_URL],
        )
        self.assertEqual(
            _candidate_urls(DOI, templates=provider_pdf_path_templates("copernicus")),
            [PDF_URL],
        )


if __name__ == "__main__":
    unittest.main()
