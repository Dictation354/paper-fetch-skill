from __future__ import annotations

from tests.golden_corpus import (
    iter_golden_corpus_fixtures,
    iter_golden_corpus_representative_fixtures,
)
from tests.golden_corpus_adapters import adapter_provider_names, golden_corpus_adapter


def test_golden_corpus_adapters_cover_all_fixture_providers() -> None:
    fixture_providers = {fixture.provider for fixture in iter_golden_corpus_fixtures()}

    assert fixture_providers == set(adapter_provider_names())


def test_golden_corpus_adapters_declare_contracts_for_all_fixture_routes() -> None:
    for fixture in iter_golden_corpus_fixtures():
        contract = golden_corpus_adapter(fixture.provider).contract_for_fixture(fixture)

        assert fixture.route_kind == contract.route_kind
        assert fixture.content_type.startswith(contract.content_prefix)


def test_golden_corpus_adapters_provide_one_representative_per_provider() -> None:
    representatives = iter_golden_corpus_representative_fixtures()

    assert {fixture.provider for fixture in representatives} == set(
        adapter_provider_names()
    )
