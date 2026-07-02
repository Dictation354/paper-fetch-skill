from __future__ import annotations

import json
from pathlib import Path

from tests.script_modules import load_script_module


def test_discover_brief_contains_required_search_contract() -> None:
    module = load_script_module("onboard_from_manifests")

    brief = module.build_discover_brief(
        provider="mdpi",
        domain="mdpi.com",
        doi_prefix="10.3390",
        output_manifest="onboarding/manifests/mdpi.yml",
    )

    assert brief["task_id"] == "mdpi-discover-manifest"
    assert brief["current_step"] == "discover-manifest"
    assert brief["runtime"] == "coding-agent-subagent"
    assert brief["schema"] == "onboarding/provider-manifest.schema.json"
    assert brief["hard_constraints"] == "onboarding/hard-constraints.md"
    assert brief["provider_seed"] == {
        "name": "mdpi",
        "domain": "mdpi.com",
        "doi_prefix_hint": "10.3390",
    }
    assert brief["output_manifest"] == "onboarding/manifests/mdpi.yml"
    assert brief["evidence_pack"] == {
        "path": ".paper-fetch-runs/mdpi-onboarding/discovery/evidence-pack.json",
        "producer": "prepare-discovery",
        "required_before_worker": True,
        "worker_should_use_as_evidence_not_manifest_source": True,
    }
    assert "route_contract" in brief["contract_templates"]
    assert "markdown_contract" in brief["contract_templates"]
    assert brief["autofix_policy"]["coordinator_runs_before_validate"] is True
    assert brief["search_requirements"]["routing"] == [
        "doi_prefixes",
        "domains",
        "domain_suffixes",
        "crossref_publisher",
    ]
    assert brief["search_requirements"]["doi_sample_purposes"] == [
        "structure",
        "table",
        "formula",
        "figure",
        "supplementary",
        "references",
        "pdf_fallback",
        "abstract_only",
        "access_gate",
        "empty_shell",
    ]
    assert brief["search_requirements"]["mandatory_discovery_proof"] == {
        "purposes": ["table", "formula", "supplementary"],
        "minimum_queries_per_purpose": 3,
        "query_must_include": [
            "provider name, provider domain, or DOI prefix",
            "purpose keyword",
        ],
        "candidate_pool_required": True,
        "worker_must_search_beyond_seed_doi": True,
        "record_rejections_by_doi": True,
        "selected_doi_must_match_doi_samples": True,
    }
    assert brief["output_requirements"][
        "optional_null_sample_purposes_require_discovery_proof"
    ] == ["table", "formula", "supplementary"]
    assert brief["files_allowed_to_modify"] == ["onboarding/manifests/mdpi.yml"]
    assert {"src/", "tests/", "docs/providers.md", "CHANGELOG.md"}.issubset(
        set(brief["files_must_not_modify"])
    )
    assert brief["no_commit"] is True


def test_discover_brief_yaml_has_no_sensitive_collection_or_sdk_prompts() -> None:
    module = load_script_module("onboard_from_manifests")
    brief = module.build_discover_brief(
        provider="mdpi",
        domain="mdpi.com",
        doi_prefix=None,
        output_manifest="onboarding/manifests/mdpi.yml",
    )

    rendered = module.to_yaml(brief).lower()

    forbidden_fragments = [
        "secret",
        "api key",
        "apikey",
        "token",
        "env var",
        "environment variable",
        "anthropic",
        "openai",
        "llm sdk",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in rendered


class FakeDiscoveryTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> dict[str, object]:
        query = kwargs.get("query")
        self.calls.append({"method": method, "url": url, "query": query})
        if url == "https://api.crossref.org/works":
            query_text = ""
            if isinstance(query, dict):
                query_text = str(query.get("query.bibliographic") or "")
            doi = (
                "10.5555/table1"
                if "table" in query_text.lower()
                else "10.5555/structure1"
            )
            payload = {
                "message": {
                    "items": [
                        {
                            "DOI": doi,
                            "title": [f"{query_text} Article"],
                            "container-title": ["Example Journal"],
                            "publisher": "Example Publisher",
                            "resource": {
                                "primary": {
                                    "URL": f"https://example.test/articles/{doi.rsplit('/', 1)[-1]}"
                                }
                            },
                            "reference": [{"unstructured": "Reference 1"}],
                        }
                    ]
                }
            }
            return {
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(payload).encode("utf-8"),
                "url": url,
            }
        if url == "https://api.openalex.org/works":
            payload = {
                "results": [
                    {
                        "doi": "https://doi.org/10.5555/table1",
                        "display_name": "OpenAlex duplicate table article",
                        "primary_location": {
                            "landing_page_url": "https://example.test/articles/table1",
                            "source": {"display_name": "Example Journal"},
                        },
                        "referenced_works_count": 3,
                    }
                ]
            }
            return {
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(payload).encode("utf-8"),
                "url": url,
            }
        html = """
<html><head><title>Example table article</title></head>
<body><article><h1>Article</h1><p>Abstract text.</p>
<table><tr><td>value</td></tr></table>
<figure><img src="/fig1.png" /></figure>
<h2>References</h2></article></body></html>
"""
        return {
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "body": html.encode("utf-8"),
            "url": url,
        }


def test_prepare_discovery_no_network_writes_query_plan_without_http(
    tmp_path: Path,
) -> None:
    module = load_script_module("onboard_from_manifests")
    transport = FakeDiscoveryTransport()

    pack = module.prepare_manifest_discovery(
        provider="example",
        domain="example.test",
        doi_prefix="10.5555",
        output_dir=tmp_path,
        no_network=True,
        transport=transport,
    )

    evidence_pack = tmp_path / "discovery" / "evidence-pack.json"
    assert evidence_pack.is_file()
    assert transport.calls == []
    assert pack["network"] == {"enabled": False}
    assert set(pack["query_plan"]) == set(module.DOI_SAMPLE_PURPOSES)
    assert len(pack["query_plan"]["table"]) == 3
    assert pack["doi_candidates"]["table"] == []


def test_prepare_discovery_scores_dedupes_and_probes_candidates(tmp_path: Path) -> None:
    module = load_script_module("onboard_from_manifests")
    transport = FakeDiscoveryTransport()

    pack = module.prepare_manifest_discovery(
        provider="example",
        domain="example.test",
        doi_prefix="10.5555",
        output_dir=tmp_path,
        no_network=False,
        transport=transport,
    )

    table_candidates = pack["doi_candidates"]["table"]
    assert [candidate["doi"] for candidate in table_candidates].count(
        "10.5555/table1"
    ) == 1
    top = table_candidates[0]
    assert top["confidence"] == "high"
    assert top["score"] >= 0.72
    assert {"body_tables", "references"} <= set(top["observed_signals"])
    assert any(
        call["url"] == "https://api.crossref.org/works" for call in transport.calls
    )
    assert any(
        call["url"] == "https://api.openalex.org/works" for call in transport.calls
    )


def _evidence_pack_with_candidate(
    *, score: float, confidence: str
) -> dict[str, object]:
    query_plan = {
        "table": [
            "example 10.5555 table DOI candidates",
            "site:example.test example table article DOI",
            "10.5555 table fixture discovery example",
        ],
        "formula": [
            "example 10.5555 formula DOI candidates",
            "site:example.test example formula article DOI",
            "10.5555 formula fixture discovery example",
        ],
        "supplementary": [
            "example 10.5555 supplementary DOI candidates",
            "site:example.test example supplementary article DOI",
            "10.5555 supplementary fixture discovery example",
        ],
    }
    return {
        "schema_version": 1,
        "provider": "example",
        "provider_seed": {
            "name": "example",
            "domain": "example.test",
            "doi_prefix_hint": "10.5555",
        },
        "query_plan": query_plan,
        "doi_candidates": {
            "table": [
                {
                    "doi": "10.5555/table1",
                    "evidence_url": "https://example.test/articles/table1",
                    "score": score,
                    "confidence": confidence,
                    "observed_signals": ["crossref_metadata", "body_tables"],
                    "rejection_hint": "Table signal is weaker than selected fixture.",
                }
            ],
            "formula": [],
            "supplementary": [],
        },
    }


def _minimal_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "example",
        "display_source": "example_html",
        "generation": {
            "generated_by": "ai_discovery",
            "generated_at": "2026-05-24T00:00:00Z",
            "source_queries": [],
            "confidence": "low",
        },
        "routing": {
            "primary": "doi_prefix",
            "doi_prefixes": ["10.5555/"],
            "domains": ["example.test"],
            "domain_suffixes": [],
            "publisher_aliases": ["example"],
            "crossref_publisher": None,
        },
        "main_path": ["article_html", "pdf_fallback", "metadata_only"],
        "success_criteria": {},
        "route_contract": {},
        "markdown_contract": {},
        "asset_profile": {"none": [], "body": [], "all": []},
        "asset_contract": {},
        "supplementary_scope": {"selector": None, "url_pattern": None},
        "abstract_only_strategy": "metadata_only",
        "probe": {
            "env_requirements": [],
            "requires_playwright": False,
            "requires_browser_runtime": False,
        },
        "fixtures": {
            "doi_samples": {
                purpose: {
                    "doi": None,
                    "evidence_url": "https://example.test/",
                    "evidence_reason": "Pending discovery.",
                    "observed_signals": [],
                    "confidence": "low",
                }
                for purpose in [
                    "structure",
                    "table",
                    "formula",
                    "figure",
                    "supplementary",
                    "references",
                    "pdf_fallback",
                    "abstract_only",
                    "access_gate",
                    "empty_shell",
                ]
            },
            "discovery_proof": {},
        },
        "extraction_hints": {},
        "owner_reuse_exceptions": [],
        "docs": {
            "providers_md_capability_row": "Example | pending",
            "changelog_summary": "Add Example.",
        },
    }


def test_autofix_manifest_fills_contracts_and_high_confidence_sample() -> None:
    module = load_script_module("onboard_from_manifests")
    manifest = _minimal_manifest()

    result = module.autofix_manifest_data(
        manifest,
        _evidence_pack_with_candidate(score=0.9, confidence="high"),
    )

    assert result["changed"] is True
    table_sample = manifest["fixtures"]["doi_samples"]["table"]
    assert table_sample["doi"] == "10.5555/table1"
    assert (
        manifest["fixtures"]["discovery_proof"]["table"]["selected_doi"]
        == "10.5555/table1"
    )
    assert manifest["markdown_contract"]["table"]["doi"] == "10.5555/table1"
    assert manifest["route_contract"]["article_html"]["success_requires"]
    assert manifest["asset_contract"]["figures"]["purposes"] == ["figure"]
    assert set(manifest["fixtures"]["discovery_proof"]["table"]["queries"]) <= set(
        manifest["generation"]["source_queries"]
    )


def test_autofix_manifest_keeps_low_confidence_candidate_as_rejection_only() -> None:
    module = load_script_module("onboard_from_manifests")
    manifest = _minimal_manifest()

    module.autofix_manifest_data(
        manifest,
        _evidence_pack_with_candidate(score=0.3, confidence="low"),
    )

    table_sample = manifest["fixtures"]["doi_samples"]["table"]
    table_proof = manifest["fixtures"]["discovery_proof"]["table"]
    assert table_sample["doi"] is None
    assert table_proof["selected_doi"] is None
    assert table_proof["exhausted"] is True
    assert table_proof["candidates"] == ["10.5555/table1"]
    assert table_proof["rejections"]["10.5555/table1"]


def test_contract_templates_cover_supported_main_path_steps() -> None:
    module = load_script_module("onboard_from_manifests")

    templates = module._contract_templates_for_discovery()

    for step in [
        "landing_html",
        "article_html",
        "xml",
        "pdf_fallback",
        "abstract_only",
        "metadata_only",
    ]:
        assert templates["route_contract"][step]["success_requires"]
    assert templates["markdown_contract"]["table"]["must_include_hint"]
    assert templates["markdown_contract"]["table"]["must_not_include_hint"]
    assert templates["asset_contract"]["figures"]["with_body_figure_signal"] == {
        "inline": "body",
        "download": "required",
        "purposes": ["figure"],
        "exception_reason": None,
    }
