from dataclasses import replace

import pytest

from paper_fetch.providers._definitions import (
    PROVIDER_DEFINITIONS,
    validate_provider_definitions,
)
from paper_fetch.providers.registry import FailedProviderClient, build_clients


@pytest.mark.parametrize(
    "field, message",
    [
        ("name", "declared more than once"),
        ("status_order", "status_order conflict"),
        ("domains", "domain conflict"),
        ("sources", "source conflict"),
        ("implementation", "implementation conflict"),
        ("rules_aliases", "alias/profile conflict"),
        ("noise_profile", "alias/profile conflict"),
    ],
)
def test_definition_conflicts_fail_before_runtime_loading(field, message):
    first = PROVIDER_DEFINITIONS["springer"]
    second = PROVIDER_DEFINITIONS["wiley"]
    if field in {"name", "status_order", "domains"}:
        second = replace(
            second,
            catalog=replace(second.catalog, **{field: getattr(first.catalog, field)}),
        )
    elif field == "rules_aliases":
        second = replace(second, rules_aliases=(first.rules_name,))
    else:
        second = replace(second, **{field: getattr(first, field)})
    with pytest.raises(ValueError, match=message):
        validate_provider_definitions((first, second))


def test_definition_rejects_malformed_implementation_and_duplicate_source():
    definition = PROVIDER_DEFINITIONS["wiley"]
    for candidate, message in [
        (
            replace(definition, implementation="bad reference"),
            "implementation reference",
        ),
        (
            replace(definition, sources=("same", "same")),
            "source declared more than once",
        ),
    ]:
        with pytest.raises(ValueError, match=message):
            validate_provider_definitions((candidate,))


def test_selected_import_failure_is_isolated(monkeypatch):
    from paper_fetch.providers import registry

    original = registry.provider_bundle

    def load(name):
        if name == "wiley":
            raise ImportError("selected implementation unavailable")
        return original(name)

    monkeypatch.setattr(registry, "provider_bundle", load)
    clients = build_clients(
        transport=object(), env={}, provider_names=("crossref", "wiley")
    )
    assert isinstance(clients["wiley"], FailedProviderClient)
    assert clients["crossref"].name == "crossref"
