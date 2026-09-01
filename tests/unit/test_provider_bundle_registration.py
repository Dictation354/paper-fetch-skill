from __future__ import annotations

import pytest

from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    ProviderRouteSpec,
    ProviderSpec,
)
from paper_fetch.providers._registry import (
    iter_provider_bundles,
    validate_provider_identity_conflicts,
)


def _identity_spec(
    name: str,
    *,
    domains: tuple[str, ...] = (),
    domain_suffixes: tuple[str, ...] = (),
    doi_prefixes: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
) -> ProviderSpec:
    return ProviderSpec(
        name=name,
        display_name=name,
        official=True,
        domains=domains,
        domain_suffixes=domain_suffixes,
        doi_prefixes=doi_prefixes,
        publisher_aliases=aliases,
        asset_default="none",
        probe_capability="routing_signal",
        provider_managed_abstract_only=False,
        client_factory_path=f"tests:{name}",
        status_order=900 + len(name),
        html_capable=False,
        routes=(ProviderRouteSpec(name="metadata", kind="metadata"),),
    )


def test_each_provider_bundle_is_exported_once() -> None:
    bundles = tuple(iter_provider_bundles())
    names = tuple(bundle.catalog.name for bundle in bundles)

    assert len(names) == len(set(names))
    assert set(names) == set(PROVIDER_CATALOG)
    assert len(names) >= 10


@pytest.mark.parametrize(
    ("left", "right", "token"),
    [
        (
            _identity_spec("left", aliases=("Example Publishing",)),
            _identity_spec("right", aliases=("example-publishing",)),
            "alias",
        ),
        (
            _identity_spec("left", doi_prefixes=("10.1234/",)),
            _identity_spec("right", doi_prefixes=("10.1234/journal",)),
            "doi_prefix",
        ),
        (
            _identity_spec("left", domains=("journal.example",)),
            _identity_spec("right", domain_suffixes=("example",)),
            "domain_exact_suffix",
        ),
        (
            _identity_spec("left", domain_suffixes=("journals.example",)),
            _identity_spec("right", domain_suffixes=("example",)),
            "domain_suffix",
        ),
    ],
)
def test_registry_rejects_unresolved_identity_conflicts(
    left: ProviderSpec,
    right: ProviderSpec,
    token: str,
) -> None:
    with pytest.raises(ValueError, match=token):
        validate_provider_identity_conflicts(left, right)
