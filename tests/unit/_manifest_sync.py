from __future__ import annotations

import json
import pprint
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

import paper_fetch.providers  # noqa: F401
from paper_fetch.provider_catalog import SOURCE_PROVIDER_MAP
from paper_fetch.providers._registry import ProviderBundle, provider_bundle


REPO_ROOT = Path(__file__).resolve().parents[2]
ONBOARDING_DIR = REPO_ROOT / "onboarding"
KNOWN_PROVIDERS_PATH = ONBOARDING_DIR / "known-providers.yml"
MANIFEST_SCHEMA_PATH = ONBOARDING_DIR / "provider-manifest.schema.json"
MANIFESTS_DIR = ONBOARDING_DIR / "manifests"
STRICT_SYNC_BACK_STATUSES = frozenset({"ready", "live"})
DRAFT_COMPATIBLE_SYNC_BACK_STATUSES = frozenset({"draft", "implemented"})


@dataclass(frozen=True)
class ManifestCase:
    provider: str
    status: str
    manifest_path: Path
    manifest: Mapping[str, Any]
    bundle: ProviderBundle


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must load as a mapping")
    return data


def load_known_provider_entries() -> tuple[dict[str, Any], ...]:
    data = load_yaml(KNOWN_PROVIDERS_PATH)
    providers = data.get("providers")
    if not isinstance(providers, list):
        raise AssertionError(f"{KNOWN_PROVIDERS_PATH}: providers must be a list")
    return tuple(entry for entry in providers if isinstance(entry, dict))


def load_manifest_schema() -> dict[str, Any]:
    return json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_manifest(manifest_path: Path, manifest: Mapping[str, Any]) -> None:
    validator = Draft202012Validator(load_manifest_schema())
    errors = sorted(validator.iter_errors(manifest), key=lambda error: error.json_path)
    if errors:
        details = [
            f"{manifest_path}: {error.json_path}: {error.message}" for error in errors
        ]
        raise AssertionError(details)


def iter_manifest_cases() -> tuple[ManifestCase, ...]:
    cases: list[ManifestCase] = []
    for entry in load_known_provider_entries():
        manifest_value = entry.get("manifest_path")
        if manifest_value is None:
            continue
        manifest_path = REPO_ROOT / str(manifest_value)
        manifest = load_yaml(manifest_path)
        validate_manifest(manifest_path, manifest)
        provider = str(entry["name"])
        cases.append(
            ManifestCase(
                provider=provider,
                status=str(entry["status"]),
                manifest_path=manifest_path,
                manifest=manifest,
                bundle=provider_bundle(provider),
            )
        )
    return tuple(cases)


def manifest_asset_default(manifest: Mapping[str, Any]) -> str:
    asset_profile = manifest["asset_profile"]
    if asset_profile.get("body"):
        return "body"
    if asset_profile.get("all"):
        return "all"
    return "none"


def normalized_sequence(values: Any) -> tuple[str, ...]:
    return tuple(sorted(str(value) for value in values or ()))


def normalized_publisher(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().rstrip(".").split())


def drift_message(
    *,
    provider: str,
    manifest_path: Path,
    field_path: str,
    manifest_value: Any,
    code_value: Any,
) -> str:
    relative_path = manifest_path.relative_to(REPO_ROOT)
    return "\n".join(
        [
            "manifest/code drift detected",
            f"provider: {provider}",
            f"manifest path: {relative_path.as_posix()}",
            f"field path: {field_path}",
            f"manifest value: {pprint.pformat(manifest_value, sort_dicts=True)}",
            f"code value: {pprint.pformat(code_value, sort_dicts=True)}",
        ]
    )


def assert_synced(
    case: ManifestCase,
    field_path: str,
    manifest_value: Any,
    code_value: Any,
) -> None:
    assert manifest_value == code_value, drift_message(
        provider=case.provider,
        manifest_path=case.manifest_path,
        field_path=field_path,
        manifest_value=manifest_value,
        code_value=code_value,
    )


def is_strict_sync_back_status(status: str) -> bool:
    return status in STRICT_SYNC_BACK_STATUSES


def sync_back_value_is_unset(value: Any) -> bool:
    return value is None or value == [] or value == {}


def source_is_registered_or_placeholder(source: str, bundle: ProviderBundle) -> bool:
    registered_provider = SOURCE_PROVIDER_MAP.get(source)
    if registered_provider is not None:
        return registered_provider == bundle.catalog.name
    return source in bundle.sources


def serialize_bundle_sync_back(bundle: ProviderBundle) -> dict[str, Any]:
    rules = bundle.html_rules
    availability = rules.availability if rules is not None else None
    return {
        "datalayer_signal_set": serialize_datalayer_signal_set(
            availability.datalayer_signal_set if availability is not None else None
        ),
        "text_marker_signal_set": serialize_text_marker_signal_set(
            availability.text_marker_signal_set if availability is not None else None
        ),
        "front_matter": serialize_front_matter_rules(
            rules.front_matter if rules is not None else None
        ),
        "asset_retry": serialize_asset_retry(bundle.asset_retry),
        "metadata_merge": serialize_metadata_merge(bundle.metadata_merge),
    }


def serialize_datalayer_signal_set(signal_set: Any) -> dict[str, Any] | None:
    if signal_set is None:
        return None
    schema = signal_set.schema
    return {
        "schema": {
            "provider": schema.provider,
            "pattern": schema.pattern.pattern,
            "fields": {
                field: [list(path) for path in paths]
                for field, paths in sorted(schema.fields.items())
            },
            "required_fields": list(schema.required_fields),
        },
        "blocking_rules": [
            _serialize_datalayer_rule(rule) for rule in signal_set.blocking_rules
        ],
        "strong_rules": [
            _serialize_datalayer_rule(rule) for rule in signal_set.strong_rules
        ],
        "soft_rules": [
            _serialize_datalayer_rule(rule) for rule in signal_set.soft_rules
        ],
        "abstract_only_rules": [
            _serialize_datalayer_rule(rule) for rule in signal_set.abstract_only_rules
        ],
        "presence_rules": [
            {"field": field, "token": token}
            for field, token in signal_set.presence_rules
        ],
    }


def _serialize_datalayer_rule(rule: Any) -> dict[str, Any]:
    if hasattr(rule, "match"):
        return {
            "kind": "field_match",
            "match": _serialize_datalayer_match(rule.match),
            "token": rule.token,
        }
    if hasattr(rule, "matches"):
        return {
            "kind": "combo",
            "matches": [_serialize_datalayer_match(match) for match in rule.matches],
            "token": rule.token,
        }
    return {
        "kind": "contains",
        "field": rule.field,
        "substring": rule.substring,
        "token": rule.token,
    }


def _serialize_datalayer_match(match: Any) -> dict[str, Any]:
    return {
        "field": match.field,
        "expected": match.expected,
        "negate": bool(match.negate),
    }


def serialize_text_marker_signal_set(signal_set: Any) -> dict[str, Any] | None:
    if signal_set is None:
        return None
    return {
        "blocking_markers": _sorted_marker_rules(signal_set.blocking_rules),
        "positive_strong": _sorted_marker_rules(signal_set.strong_rules),
        "positive_soft": _sorted_marker_rules(signal_set.soft_rules),
        "abstract_only": _sorted_marker_rules(signal_set.abstract_only_rules),
    }


def _sorted_marker_rules(rules: Any) -> list[dict[str, Any]]:
    serialized = [_serialize_text_marker_rule(rule) for rule in rules]
    return sorted(
        serialized,
        key=lambda item: (
            item["substring"],
            item["token"],
            item["negate"],
            item["contains"],
            item["absent"],
            item["access_gate_context"],
        ),
    )


def _serialize_text_marker_rule(rule: Any) -> dict[str, Any]:
    return {
        "substring": rule.substring,
        "token": rule.token,
        "negate": bool(rule.negate),
        "contains": list(rule.contains),
        "absent": list(rule.absent),
        "access_gate_context": bool(rule.access_gate_context),
    }


def serialize_front_matter_rules(rules: Any) -> dict[str, Any] | None:
    if rules is None:
        return None
    return {
        "exact_texts": list(rules.exact_texts),
        "contains_tokens": list(rules.contains_tokens),
        "publication_keywords": list(rules.publication_keywords),
    }


def serialize_asset_retry(policy: Any) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "name": policy.name,
        "key_fn": callable_path(policy.key_fn),
        "retryable_failure": callable_path(policy.retryable_failure),
        "failure_match": callable_path(policy.failure_match),
    }


def serialize_metadata_merge(rules: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, rule in enumerate(rules or ()):
        for strategy in (
            "fill_empty",
            "overwrite",
            "concat_unique",
            "take_first_non_empty",
        ):
            for field in getattr(rule, strategy):
                entries.append(
                    {
                        "field": field,
                        "strategy": strategy,
                        "rule_index": index,
                    }
                )
    return sorted(
        entries,
        key=lambda item: (item["field"], item["strategy"], item["rule_index"]),
    )


def callable_path(value: Callable[..., Any] | None) -> str | None:
    if value is None:
        return None
    return f"{value.__module__}:{value.__qualname__}"
