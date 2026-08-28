from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from paper_fetch.extraction.html.provider_rules import PROVIDER_HTML_RULES
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    SOURCE_PROVIDER_MAP,
    ProviderRouteSpec,
    ProviderSpec,
)
from paper_fetch.providers._registry import (
    ProviderBundle,
    ProviderRenderPolicy,
    iter_provider_bundles,
    provider_bundle,
    validate_provider_identity_conflicts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _identity_spec(
    name: str,
    *,
    domains: tuple[str, ...] = (),
    domain_suffixes: tuple[str, ...] = (),
    doi_prefixes: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    identity_priority: int | None = None,
    identity_conflict_reason: str | None = None,
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
        identity_priority=identity_priority,
        identity_conflict_reason=identity_conflict_reason,
    )


def test_each_provider_bundle_is_registered_once() -> None:
    bundles = tuple(iter_provider_bundles())
    names = tuple(bundle.catalog.name for bundle in bundles)

    assert len(names) == len(set(names))
    assert set(names) == set(PROVIDER_CATALOG)
    assert len(names) >= 10


@pytest.mark.parametrize("name", tuple(PROVIDER_CATALOG))
def test_provider_bundle_round_trips_catalog_and_rules(name: str) -> None:
    bundle = provider_bundle(name)

    assert bundle.catalog == PROVIDER_CATALOG[name]
    for source in bundle.sources:
        assert SOURCE_PROVIDER_MAP[source] == name
    if bundle.html_rules is not None:
        assert PROVIDER_HTML_RULES[bundle.html_rules.name] == bundle.html_rules


def test_provider_bundle_fields_are_typed_and_frozen() -> None:
    bundle = provider_bundle("ieee")
    field_names = {field.name for field in fields(ProviderBundle)}

    assert {
        "catalog",
        "html_rules",
        "asset_retry",
        "metadata_merge",
        "sources",
        "render_policy",
    } <= field_names
    assert isinstance(bundle.metadata_merge, tuple)
    assert isinstance(bundle.sources, tuple)

    with pytest.raises(FrozenInstanceError):
        bundle.sources = ()  # type: ignore[misc]


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


def test_registry_allows_conflict_only_with_distinct_priority_and_reasons() -> None:
    left = _identity_spec(
        "left",
        domain_suffixes=("example",),
        identity_priority=20,
        identity_conflict_reason="Canonical parent registry owns this suffix.",
    )
    right = _identity_spec(
        "right",
        domains=("journal.example",),
        identity_priority=10,
        identity_conflict_reason="Legacy journal is lower-priority during migration.",
    )

    validate_provider_identity_conflicts(left, right)


def test_provider_bundle_rejects_mutable_sequence_fields() -> None:
    catalog = PROVIDER_CATALOG["crossref"]

    with pytest.raises(TypeError):
        ProviderBundle(catalog=catalog, metadata_merge=[])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ProviderBundle(catalog=catalog, sources=["crossref_meta"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ProviderBundle(catalog=catalog, render_policy=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ProviderRenderPolicy(mark_inline_assets=object())  # type: ignore[arg-type]


def test_provider_entry_modules_require_explicit_catalog_registration(
    tmp_path: Path,
) -> None:
    provider_dir = tmp_path / "paper_fetch" / "providers"
    provider_dir.mkdir(parents=True)
    (provider_dir / "explicit.py").write_text(
        """
from __future__ import annotations

from paper_fetch.provider_catalog import ProviderRouteSpec, ProviderSpec
from paper_fetch.providers._registry import ProviderBundle, register_provider_bundle


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="explicit",
            display_name="Explicit",
            official=True,
            domains=("explicit.example",),
            doi_prefixes=("10.4242/",),
            publisher_aliases=("explicit",),
            asset_default="none",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.explicit:ExplicitClient",
            status_order=998,
            html_capable=False,
            routes=(ProviderRouteSpec(name="metadata", kind="metadata"),),
        ),
        sources=("explicit_html",),
    )
)
""",
        encoding="utf-8",
    )

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
from pathlib import Path

import paper_fetch.providers as provider_entries
from paper_fetch.provider_catalog import PROVIDER_CATALOG, SOURCE_PROVIDER_MAP, provider_for_source
from paper_fetch.providers._registry import provider_bundle

provider_entries.__path__ = [
    str(Path({str(provider_dir)!r})),
    *list(provider_entries.__path__),
]
provider_entries.import_provider_entry_modules()

assert ".explicit" not in tuple(provider_entries._PROVIDER_ENTRY_MODULES)
assert "explicit" not in PROVIDER_CATALOG

provider_entries._PROVIDER_ENTRY_MODULES += (".explicit",)
provider_entries.import_provider_entry_modules()

assert PROVIDER_CATALOG["explicit"].domains == ("explicit.example",)
assert SOURCE_PROVIDER_MAP["explicit_html"] == "explicit"
assert provider_for_source("explicit_html") == "explicit"
assert provider_bundle("explicit").catalog.html_capable is False
""",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )

    assert probe.returncode == 0, probe.stderr


def _client_class_from_factory_path(factory_path: str) -> type:
    module_name, separator, attribute_path = factory_path.partition(":")
    assert separator, f"client_factory_path must use module:attribute: {factory_path}"
    target = importlib.import_module(module_name)
    for attribute in attribute_path.split("."):
        target = getattr(target, attribute)
    assert isinstance(target, type), f"client factory is not a class: {factory_path}"
    return target


def test_provider_client_waterfall_steps_are_waterfall_step_objects() -> None:
    from paper_fetch.providers._waterfall import WaterfallStep
    from paper_fetch.providers.base import ProviderClient

    offenders: list[str] = []
    for provider_name, spec in PROVIDER_CATALOG.items():
        client_class = _client_class_from_factory_path(spec.client_factory_path)
        if not issubclass(client_class, ProviderClient):
            offenders.append(f"{provider_name}: client does not inherit ProviderClient")
            continue
        for index, step in enumerate(getattr(client_class, "waterfall_steps", ())):
            if not isinstance(step, WaterfallStep):
                offenders.append(
                    f"{provider_name}.waterfall_steps[{index}] is {type(step).__name__}"
                )

    assert offenders == []
