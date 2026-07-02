from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from ._manifest_sync import (
    MANIFESTS_DIR,
    load_manifest_schema,
    load_yaml,
)


REQUIRED_DOI_PURPOSES = {"structure", "figure", "references"}
DISCOVERY_PROOF_PURPOSES = ("table", "formula", "supplementary")
PLACEHOLDER_PATTERN = re.compile(r"\b(?:todo|tbd|unknown)\b", re.IGNORECASE)
PURPOSE_QUERY_KEYWORDS = {
    "table": ("table",),
    "formula": ("formula", "equation", "math", "mathml", "latex"),
    "supplementary": (
        "supplementary",
        "supplemental",
        "supplement",
        "supporting information",
    ),
}
PURPOSE_SIGNAL_PATTERNS = {
    "table": re.compile(
        r"\bbody[-_ ]?tables?\b|\btable[-_ ]?block[-_ ]?rendering\b|"
        r"\bhtml[-_ ]?fulltext[-_ ]?inline[-_ ]?table\b|\btables?\b|"
        r"\btable\s+\d+\b",
        re.IGNORECASE,
    ),
    "formula": re.compile(
        r"\bmath[-_ ]?markup\b|\bformula[-_ ]?images?\b|\bmathjax\b|"
        r"\bmathml\b|\bformula\b|\bequations?\b|\blatex\b",
        re.IGNORECASE,
    ),
    "supplementary": re.compile(
        r"\bsupplementary\b|\bsupplemental\b|\bsupplement\b|"
        r"\bsupporting information\b",
        re.IGNORECASE,
    ),
}
WEAK_NULL_REASON_PATTERN = re.compile(
    r"^\s*(?:未找到样本|没找到样本|not found|no sample found|sample not found)\s*\.?\s*$",
    re.IGNORECASE,
)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalized_doi(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip().rstrip(".")


def _provider_identity_terms(manifest: dict) -> set[str]:
    routing = (
        manifest.get("routing") if isinstance(manifest.get("routing"), dict) else {}
    )
    values: list[object] = [
        manifest.get("name"),
        manifest.get("display_source"),
        *(routing.get("doi_prefixes") or []),
        *(routing.get("domains") or []),
        *(routing.get("domain_suffixes") or []),
        *(routing.get("publisher_aliases") or []),
        routing.get("crossref_publisher"),
    ]
    terms: set[str] = set()
    for value in values:
        if not value:
            continue
        term = _normalized_text(value).rstrip("/")
        if term:
            terms.add(term)
            terms.add(term.replace("_", " "))
            terms.add(term.replace(" ", ""))
    return terms


def _query_mentions_provider_identity(query: str, manifest: dict) -> bool:
    normalized = _normalized_text(query)
    compact = normalized.replace(" ", "")
    for term in _provider_identity_terms(manifest):
        if term in normalized or term.replace(" ", "") in compact:
            return True
    return False


def _query_mentions_purpose(query: str, purpose: str) -> bool:
    normalized = _normalized_text(query)
    return any(keyword in normalized for keyword in PURPOSE_QUERY_KEYWORDS[purpose])


def _rejection_for(entry: dict, doi: str) -> str | None:
    normalized = _normalized_doi(doi)
    for candidate, reason in (entry.get("rejections") or {}).items():
        if _normalized_doi(candidate) == normalized:
            return str(reason)
    return None


def _text_has_purpose_signal(text: str, purpose: str) -> bool:
    return bool(PURPOSE_SIGNAL_PATTERNS[purpose].search(text))


def _strong_signal_dois_from_manifest(manifest: dict, purpose: str) -> set[str]:
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    candidates: list[dict] = [
        sample for sample in doi_samples.values() if isinstance(sample, dict)
    ]
    candidates.extend(
        sample
        for sample in manifest.get("extra_fixtures") or []
        if isinstance(sample, dict)
    )
    signal_dois: set[str] = set()
    for sample in candidates:
        doi = _normalized_doi(sample.get("doi"))
        if doi is None:
            continue
        signal_text = yaml.safe_dump(
            {
                "evidence_reason": sample.get("evidence_reason"),
                "observed_signals": sample.get("observed_signals"),
            },
            allow_unicode=True,
            sort_keys=True,
        )
        if _text_has_purpose_signal(signal_text, purpose):
            signal_dois.add(doi)
    return signal_dois


def _strong_signal_dois_from_cleaning_evidence(
    manifest_path: Path,
    manifest: dict,
    purpose: str,
) -> set[str]:
    evidence_path = (
        manifest_path.parent.parent
        / "cleaning-chain-proposals"
        / f"{manifest['name']}.yml"
    )
    if not evidence_path.is_file():
        return set()
    data = load_yaml(evidence_path)
    deltas = data.get("proposed_markdown_contract_delta")
    if not isinstance(deltas, dict):
        return set()
    signal_dois: set[str] = set()
    for delta in deltas.values():
        if not isinstance(delta, dict):
            continue
        doi = _normalized_doi(delta.get("doi"))
        suggested = delta.get("suggested_must_include_from_fixtures") or []
        signal_text = " ".join(str(value) for value in suggested)
        if doi and _text_has_purpose_signal(signal_text, purpose):
            signal_dois.add(doi)
    return signal_dois


def _specific_same_doi_rejection(reason: str | None) -> bool:
    normalized = _normalized_text(reason)
    return "same doi" in normalized and any(
        phrase in normalized
        for phrase in (
            "not suitable",
            "not selected",
            "not promoted",
            "different purpose",
            "does not expose",
            "lacks",
            "not stable",
        )
    )


def _assert_discovery_proof(manifest_path: Path, manifest: dict) -> None:
    fixtures = manifest["fixtures"]
    doi_samples = fixtures["doi_samples"]
    proof = fixtures["discovery_proof"]
    source_queries = manifest["generation"]["source_queries"]
    source_query_text = _normalized_text(
        "\n".join(str(query) for query in source_queries)
    )

    for purpose in DISCOVERY_PROOF_PURPOSES:
        sample = doi_samples[purpose]
        entry = proof[purpose]
        sample_doi = _normalized_doi(sample.get("doi"))
        selected_doi_value = entry.get("selected_doi")
        selected_doi = _normalized_doi(selected_doi_value)
        assert selected_doi_value == sample.get("doi"), (
            f"{manifest_path}: fixtures.discovery_proof.{purpose}.selected_doi "
            "must match fixtures.doi_samples"
        )

        for query in entry["queries"]:
            assert _query_mentions_provider_identity(query, manifest), (
                f"{manifest_path}: discovery_proof.{purpose}.queries item "
                f"{query!r} must include provider name, domain, or DOI prefix"
            )
            assert _query_mentions_purpose(query, purpose), (
                f"{manifest_path}: discovery_proof.{purpose}.queries item "
                f"{query!r} must include a {purpose} purpose keyword"
            )
            assert _normalized_text(query) in source_query_text, (
                f"{manifest_path}: generation.source_queries must cover "
                f"discovery_proof.{purpose}.queries item {query!r}"
            )

        candidates = [_normalized_doi(candidate) for candidate in entry["candidates"]]
        candidates = [candidate for candidate in candidates if candidate is not None]
        assert len(candidates) == len(set(candidates)), (
            f"{manifest_path}: discovery_proof.{purpose}.candidates "
            "must not contain duplicate DOIs"
        )
        if sample_doi is not None:
            assert entry["exhausted"] is False, (
                f"{manifest_path}: discovery_proof.{purpose}.exhausted must be "
                "false when a DOI sample is selected"
            )
            assert sample_doi in candidates, (
                f"{manifest_path}: discovery_proof.{purpose}.candidates must "
                "include selected_doi"
            )
        else:
            assert entry["selected_doi"] is None, (
                f"{manifest_path}: discovery_proof.{purpose}.selected_doi must be null"
            )
            assert entry["exhausted"] is True, (
                f"{manifest_path}: discovery_proof.{purpose}.exhausted must be "
                "true when fixtures.doi_samples is null"
            )
            assert candidates, (
                f"{manifest_path}: null {purpose} discovery proof must record "
                "at least one rejected candidate DOI"
            )
            assert not WEAK_NULL_REASON_PATTERN.fullmatch(sample["evidence_reason"]), (
                f"{manifest_path}: {purpose} null evidence_reason must explain "
                "the exhausted search, not just say no sample was found"
            )
            assert not WEAK_NULL_REASON_PATTERN.fullmatch(entry["evidence_summary"]), (
                f"{manifest_path}: discovery_proof.{purpose}.evidence_summary "
                "must explain the exhausted search"
            )

        for candidate in candidates:
            if candidate == selected_doi:
                continue
            assert _rejection_for(entry, candidate), (
                f"{manifest_path}: discovery_proof.{purpose}.rejections must "
                f"explain why candidate {candidate!r} was not selected"
            )

        if sample_doi is None:
            signal_dois = _strong_signal_dois_from_manifest(
                manifest, purpose
            ) | _strong_signal_dois_from_cleaning_evidence(
                manifest_path, manifest, purpose
            )
            for signal_doi in sorted(signal_dois):
                rejection = _rejection_for(entry, signal_doi)
                assert _specific_same_doi_rejection(rejection), (
                    f"{manifest_path}: {purpose} is null but local evidence "
                    f"contains a strong {purpose} signal for DOI {signal_doi}; "
                    "select that DOI or reject it with a specific same DOI reason"
                )


def load_schema():
    return load_manifest_schema()


def iter_manifest_paths() -> list[Path]:
    return sorted(MANIFESTS_DIR.glob("*.yml"))


def test_provider_manifest_schema_is_valid_json_schema() -> None:
    schema = load_schema()

    Draft202012Validator.check_schema(schema)


def test_all_provider_manifests_pass_schema_and_local_invariants() -> None:
    schema = load_schema()
    validator = Draft202012Validator(schema)
    manifest_paths = iter_manifest_paths()
    assert manifest_paths

    for manifest_path in manifest_paths:
        manifest = load_yaml(manifest_path)
        errors = sorted(
            validator.iter_errors(manifest), key=lambda error: error.json_path
        )
        assert not errors, [
            f"{manifest_path}: {error.json_path}: {error.message}" for error in errors
        ]

        assert manifest["name"] == manifest_path.stem
        assert isinstance(manifest["main_path"], list)
        assert manifest["main_path"], f"{manifest_path}: main_path must not be empty"
        route_sources = manifest.get("route_sources") or {}
        assert isinstance(route_sources, dict), (
            f"{manifest_path}: route_sources must be an object"
        )
        for step, source in route_sources.items():
            assert step in manifest["main_path"], (
                f"{manifest_path}: route_sources.{step} must reference "
                "a step from main_path"
            )
            assert source, f"{manifest_path}: route_sources.{step} must not be empty"
        if route_sources:
            assert manifest["display_source"] in set(route_sources.values()), (
                f"{manifest_path}: display_source must appear in route_sources values"
            )
        route_contract = manifest["route_contract"]
        for step in manifest["main_path"]:
            assert step in route_contract, (
                f"{manifest_path}: route_contract.{step} is required "
                "for every main_path step"
            )
            assert route_contract[step]["success_requires"], (
                f"{manifest_path}: route_contract.{step}.success_requires "
                "must not be empty"
            )
        assert isinstance(manifest["docs"], dict)
        assert manifest["docs"]["providers_md_capability_row"]
        assert manifest["docs"]["changelog_summary"]
        doi_samples = manifest["fixtures"]["doi_samples"]
        markdown_contract = manifest["markdown_contract"]
        for purpose in REQUIRED_DOI_PURPOSES:
            assert doi_samples[purpose]["doi"], (
                f"{manifest_path}: {purpose} DOI is required"
            )
        _assert_discovery_proof(manifest_path, manifest)
        for purpose, sample in doi_samples.items():
            doi = sample.get("doi")
            if not doi:
                continue
            assert purpose in markdown_contract, (
                f"{manifest_path}: markdown_contract.{purpose} is required "
                "for every non-null DOI sample"
            )
            purpose_contract = markdown_contract[purpose]
            assert purpose_contract["doi"] == doi, (
                f"{manifest_path}: markdown_contract.{purpose}.doi must "
                "match fixtures.doi_samples"
            )
            assert purpose_contract["must_include"], (
                f"{manifest_path}: markdown_contract.{purpose}.must_include "
                "must not be empty"
            )
            assert purpose_contract["must_not_include"], (
                f"{manifest_path}: markdown_contract.{purpose}.must_not_include "
                "must not be empty"
            )
        for index, extra_fixture in enumerate(manifest.get("extra_fixtures") or []):
            assert extra_fixture["doi"], (
                f"{manifest_path}: extra_fixtures[{index}].doi is required"
            )
            assert extra_fixture["evidence_url"], (
                f"{manifest_path}: extra_fixtures[{index}].evidence_url is required"
            )
            assert extra_fixture["evidence_reason"], (
                f"{manifest_path}: extra_fixtures[{index}].evidence_reason is required"
            )
            assert extra_fixture["observed_signals"], (
                f"{manifest_path}: extra_fixtures[{index}].observed_signals "
                "must not be empty"
            )
            extra_contract = extra_fixture.get("markdown_contract")
            if extra_contract is None:
                continue
            assert extra_contract["doi"] == extra_fixture["doi"], (
                f"{manifest_path}: extra_fixtures[{index}].markdown_contract.doi "
                "must match extra fixture DOI"
            )
            assert extra_contract["must_include"], (
                f"{manifest_path}: extra_fixtures[{index}].markdown_contract."
                "must_include must not be empty"
            )
            assert extra_contract["must_not_include"], (
                f"{manifest_path}: extra_fixtures[{index}].markdown_contract."
                "must_not_include must not be empty"
            )

        rendered = yaml.safe_dump(manifest, allow_unicode=True, sort_keys=True)
        assert not PLACEHOLDER_PATTERN.search(rendered), manifest_path


def test_discovery_proof_is_required_by_schema() -> None:
    schema = load_schema()
    manifest = copy.deepcopy(load_yaml(MANIFESTS_DIR / "mdpi.yml"))
    del manifest["fixtures"]["discovery_proof"]

    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: error.json_path,
    )

    assert any("discovery_proof" in error.message for error in errors)


def test_discovery_proof_rejects_selected_doi_mismatch() -> None:
    manifest_path = MANIFESTS_DIR / "mdpi.yml"
    manifest = copy.deepcopy(load_yaml(manifest_path))
    manifest["fixtures"]["discovery_proof"]["table"]["selected_doi"] = (
        "10.3390/math11030657"
    )

    with pytest.raises(AssertionError, match="selected_doi"):
        _assert_discovery_proof(manifest_path, manifest)


def test_discovery_proof_rejects_queries_without_purpose_keyword() -> None:
    manifest_path = MANIFESTS_DIR / "mdpi.yml"
    manifest = copy.deepcopy(load_yaml(manifest_path))
    manifest["fixtures"]["discovery_proof"]["table"]["queries"] = [
        "MDPI 10.3390 DOI candidates",
        "site:mdpi.com MDPI article DOI candidates",
        "MDPI mdpi.com fixture discovery candidates",
    ]
    manifest["generation"]["source_queries"].extend(
        manifest["fixtures"]["discovery_proof"]["table"]["queries"]
    )

    with pytest.raises(AssertionError, match="purpose keyword"):
        _assert_discovery_proof(manifest_path, manifest)


def test_discovery_proof_schema_rejects_short_query_list() -> None:
    schema = load_schema()
    manifest = copy.deepcopy(load_yaml(MANIFESTS_DIR / "mdpi.yml"))
    manifest["fixtures"]["discovery_proof"]["table"]["queries"] = [
        "MDPI 10.3390 table DOI candidates"
    ]

    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: error.json_path,
    )

    assert any("is too short" in error.message for error in errors)


def test_null_purpose_rejects_unexplained_local_strong_signal() -> None:
    manifest_path = MANIFESTS_DIR / "annualreviews.yml"
    manifest = copy.deepcopy(load_yaml(manifest_path))
    table_sample = manifest["fixtures"]["doi_samples"]["table"]
    table_sample["doi"] = None
    table_sample["observed_signals"] = []
    proof = manifest["fixtures"]["discovery_proof"]["table"]
    proof["selected_doi"] = None
    proof["exhausted"] = True
    proof["candidates"] = ["10.1146/annurev-control-030123-013355"]
    proof["rejections"] = {
        "10.1146/annurev-control-030123-013355": (
            "Candidate was not selected for this purpose."
        )
    }

    with pytest.raises(AssertionError, match="strong table signal"):
        _assert_discovery_proof(manifest_path, manifest)


def test_annualreviews_table_fixture_is_not_null() -> None:
    manifest = load_yaml(MANIFESTS_DIR / "annualreviews.yml")
    table_sample = manifest["fixtures"]["doi_samples"]["table"]

    assert table_sample["doi"] == "10.1146/annurev-control-030123-013355"
    assert (
        manifest["fixtures"]["discovery_proof"]["table"]["selected_doi"]
        == table_sample["doi"]
    )
