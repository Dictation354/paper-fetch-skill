from __future__ import annotations
from tests.golden_corpus import (
    golden_corpus_replay_inventory,
    iter_golden_corpus_fixtures,
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


def test_golden_corpus_inventory_separates_non_replay_evidence() -> None:
    inventory = golden_corpus_replay_inventory()

    assert inventory.count("unit_only") == 0
    for arxiv_id in ("0811.2625v2", "0905.2326v2", "2606.00587v2"):
        paper = next(
            record
            for record in inventory.records
            if record.sample_id == f"10.48550_arxiv.{arxiv_id}"
        )
        assert paper.category == "real_replay"
        assert paper.fixture is not None
    assert inventory.count("unexecutable") == 0
    assert inventory.count("real_replay") == len(iter_golden_corpus_fixtures())
    assert all(
        record.fixture is not None
        for record in inventory.records
        if record.category == "real_replay"
    )
    assert all(
        record.fixture is None
        for record in inventory.records
        if record.category != "real_replay"
    )
