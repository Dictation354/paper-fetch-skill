from __future__ import annotations

import ast
from dataclasses import fields
from importlib import util
from pathlib import Path

import paper_fetch.providers as provider_entries
from paper_fetch.extraction.html.availability_policy import AvailabilityPolicy
from paper_fetch.extraction.html.provider_rules import (
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from paper_fetch.providers._registry import iter_provider_bundles


def test_each_provider_bundle_has_catalog() -> None:
    for bundle in iter_provider_bundles():
        assert bundle.catalog is not None
        assert bundle.catalog.name


def test_provider_spec_declares_html_capability_default() -> None:
    field_map = {
        field.name: field
        for field in fields(type(next(iter_provider_bundles()).catalog))
    }

    assert field_map["html_capable"].default is True


def test_html_capable_provider_bundles_register_html_rules() -> None:
    for bundle in iter_provider_bundles():
        if bundle.catalog.html_capable:
            assert bundle.html_rules is not None, bundle.catalog.name


def test_registered_html_rules_include_required_facets() -> None:
    for bundle in iter_provider_bundles():
        rules = bundle.html_rules
        if rules is None:
            continue

        assert isinstance(rules, ProviderHtmlRules), bundle.catalog.name
        assert isinstance(rules.cleanup, ProviderCleanupRules), bundle.catalog.name
        assert isinstance(rules.front_matter, ProviderFrontMatterRules), (
            bundle.catalog.name
        )
        assert isinstance(rules.availability, AvailabilityPolicy), bundle.catalog.name


def test_html_availability_policies_have_signals_or_explicit_opt_out() -> None:
    for bundle in iter_provider_bundles():
        rules = bundle.html_rules
        if rules is None:
            continue

        availability = rules.availability
        assert (
            availability.datalayer_signal_set is not None
            or availability.text_marker_signal_set is not None
            or availability.overrides is not None
            or availability.no_signals
        ), bundle.catalog.name


def test_availability_policy_no_signals_can_be_constructed_explicitly() -> None:
    assert AvailabilityPolicy(no_signals=True).no_signals is True


def test_provider_entry_modules_register_provider_bundles() -> None:
    for module_name in provider_entries._PROVIDER_ENTRY_MODULES:
        qualified_name = f"{provider_entries.__name__}{module_name}"
        spec = util.find_spec(qualified_name)
        assert spec is not None
        assert spec.origin is not None
        module_path = Path(spec.origin)
        module_ast = ast.parse(module_path.read_text(), filename=str(module_path))

        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_provider_bundle"
            for node in ast.walk(module_ast)
        ), qualified_name
