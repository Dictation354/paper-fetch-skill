from __future__ import annotations

import unittest

from paper_fetch import publisher_identity
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    SOURCE_PROVIDER_MAP,
    default_asset_profile_for_provider,
    default_asset_profile_for_source,
    official_provider_names,
    provider_managed_abstract_only_names,
    provider_status_order,
)
from paper_fetch.providers.registry import build_clients


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
            [spec.name for spec in sorted(PROVIDER_CATALOG.values(), key=lambda item: item.status_order)],
        )
        for spec in PROVIDER_CATALOG.values():
            self.assertIn(spec.asset_default, valid_asset_profiles)
            self.assertEqual(default_asset_profile_for_provider(spec.name), spec.asset_default)
            self.assertTrue(spec.client_factory_path)

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
                if spec.abstract_only_policy == "provider_managed"
            },
        )

    def test_source_asset_defaults_follow_provider_catalog(self) -> None:
        for source, provider in SOURCE_PROVIDER_MAP.items():
            self.assertEqual(
                default_asset_profile_for_source(source),
                default_asset_profile_for_provider(provider),
            )
        self.assertEqual(default_asset_profile_for_source("unknown_source"), "none")

    def test_catalog_preserves_publisher_doi_domain_inference(self) -> None:
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1038/nphys1170"), "springer")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1016/j.solener.2024.01.001"), "elsevier")
        self.assertEqual(publisher_identity.infer_provider_from_publisher("John Wiley & Sons"), "wiley")
        self.assertEqual(
            publisher_identity.infer_provider_from_url("https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"),
            "elsevier",
        )
        self.assertEqual(
            publisher_identity.ordered_provider_candidates(
                landing_urls=["https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"],
                publishers=["Springer Nature"],
                doi="10.1111/example",
            ),
            [("elsevier", "domain"), ("springer", "publisher"), ("wiley", "doi")],
        )


if __name__ == "__main__":
    unittest.main()
