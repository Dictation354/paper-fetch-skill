from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

import paper_fetch.providers as provider_entries
from paper_fetch.extraction.html.provider_rules import PROVIDER_HTML_RULES
from paper_fetch.provider_catalog import PROVIDER_CATALOG, SOURCE_PROVIDER_MAP
from paper_fetch.providers._registry import (
    ProviderBundle,
    ProviderRenderPolicy,
    iter_provider_bundles,
    provider_bundle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_provider_entry_discovery_imports_new_bundle_modules_without_central_edit(
    tmp_path: Path,
) -> None:
    provider_dir = tmp_path / "paper_fetch" / "providers"
    provider_dir.mkdir(parents=True)
    (provider_dir / "autodiscovered.py").write_text(
        """
from __future__ import annotations

from paper_fetch.provider_catalog import ProviderSpec
from paper_fetch.providers._registry import ProviderBundle, register_provider_bundle


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="autodiscovered",
            display_name="Autodiscovered",
            official=True,
            domains=("autodiscovered.example",),
            doi_prefixes=("10.4242/",),
            publisher_aliases=("autodiscovered",),
            asset_default="none",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.autodiscovered:AutodiscoveredClient",
            status_order=998,
            html_capable=False,
        ),
        sources=("autodiscovered_html",),
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

assert ".autodiscovered" in tuple(provider_entries._PROVIDER_ENTRY_MODULES)
assert PROVIDER_CATALOG["autodiscovered"].domains == ("autodiscovered.example",)
assert SOURCE_PROVIDER_MAP["autodiscovered_html"] == "autodiscovered"
assert provider_for_source("autodiscovered_html") == "autodiscovered"
assert provider_bundle("autodiscovered").catalog.html_capable is False
""",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )

    assert probe.returncode == 0, probe.stderr


def test_provider_entry_discovery_ignores_comments_and_docstrings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_dir = tmp_path / "paper_fetch" / "providers"
    provider_dir.mkdir(parents=True)
    (provider_dir / "ignored.py").write_text(
        '''
"""A docstring mentioning register_provider_bundle(ProviderBundle(...))."""

# register_provider_bundle(ProviderBundle(...))
TEXT = "register_provider_bundle(ProviderBundle(...))"
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        provider_entries,
        "__path__",
        [str(provider_dir), *list(provider_entries.__path__)],
    )
    provider_entries._DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE.clear()
    try:
        discovered = tuple(provider_entries._PROVIDER_ENTRY_MODULES)
    finally:
        provider_entries._DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE.clear()

    assert ".ignored" not in discovered
    assert "paper_fetch.providers.ignored" not in sys.modules


def test_provider_entry_discovery_reuses_ast_scan_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_dir = tmp_path / "paper_fetch" / "providers"
    provider_dir.mkdir(parents=True)
    (provider_dir / "cached.py").write_text(
        """
from __future__ import annotations

from paper_fetch.providers._registry import register_provider_bundle


def register() -> None:
    register_provider_bundle(object())
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        provider_entries,
        "__path__",
        [str(provider_dir), *list(provider_entries.__path__)],
    )
    original_declares = provider_entries._module_declares_provider_bundle
    dynamic_calls: list[str] = []

    def count_dynamic_scan(module_name: str) -> bool:
        if module_name == "cached":
            dynamic_calls.append(module_name)
        return original_declares(module_name)

    provider_entries._DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE.clear()
    monkeypatch.setattr(
        provider_entries,
        "_module_declares_provider_bundle",
        count_dynamic_scan,
    )
    try:
        assert ".cached" in tuple(provider_entries._PROVIDER_ENTRY_MODULES)
        assert len(provider_entries._PROVIDER_ENTRY_MODULES) >= len(
            provider_entries._BUILTIN_PROVIDER_ENTRY_MODULES
        )
        assert ".cached" in provider_entries._PROVIDER_ENTRY_MODULES
    finally:
        provider_entries._DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE.clear()

    assert dynamic_calls == ["cached"]


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
