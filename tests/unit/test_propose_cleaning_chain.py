from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import yaml

from scripts import propose_cleaning_chain as cleaning


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "propose_cleaning_chain.py"


def _mdpi_subset_manifest() -> dict:
    manifest = yaml.safe_load(
        (REPO_ROOT / "onboarding" / "manifests" / "mdpi.yml").read_text(
            encoding="utf-8"
        )
    )
    doi_samples = manifest["fixtures"]["doi_samples"]
    manifest["fixtures"]["doi_samples"] = {
        "structure": doi_samples["structure"],
        "table": doi_samples["table"],
    }
    manifest["markdown_contract"] = {
        "structure": manifest["markdown_contract"]["structure"],
        "table": manifest["markdown_contract"]["table"],
    }
    manifest.pop("extra_fixtures", None)
    return manifest


def test_cleaning_proposal_contains_fixture_provenance_and_contract_delta() -> None:
    proposal = cleaning.build_cleaning_chain_proposal(
        _mdpi_subset_manifest(),
        manifest_path="onboarding/manifests/mdpi.yml",
    )

    assert proposal["schema_version"] == 1
    assert proposal["provider"] == "mdpi"
    assert proposal["fixtures_digest"]
    assert all(item["sha256"] for item in proposal["fixtures_digest"])
    assert proposal["raw_fixture_inventory"]
    assert all(item["raw_path"] for item in proposal["raw_fixture_inventory"])
    assert proposal["raw_baselines"]
    assert all(
        baseline["markdown_source"] != "unavailable"
        for baseline in proposal["raw_baselines"].values()
    )
    assert proposal["content_anchors"]
    assert {"structure", "table"} <= set(proposal["proposed_markdown_contract_delta"])
    assert (
        "missing_must_include"
        in proposal["proposed_markdown_contract_delta"]["structure"]
    )
    assert isinstance(
        proposal["proposed_markdown_contract_delta"]["structure"][
            "dead_must_not_include"
        ],
        dict,
    )
    assert proposal["repeated_boilerplate_candidates"]
    first_candidate = proposal["repeated_boilerplate_candidates"][0]
    assert first_candidate["provenance"]
    assert {"fixture_path", "purpose", "line", "text"} <= set(
        first_candidate["provenance"][0]
    )


def test_markdown_baseline_uses_provider_golden_adapter(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[object] = []

    class FakeArticle:
        def to_ai_markdown(self, *, asset_profile: str, max_tokens: str) -> str:
            calls.append((asset_profile, max_tokens))
            return "## Produced by provider chain"

    fake_module = types.SimpleNamespace(
        build_article_from_fixture=lambda fixture: FakeArticle(),
    )
    fake_criteria = types.SimpleNamespace(
        golden_criteria_sample_for_doi=lambda doi: {
            "sample_id": "fake",
            "publisher": "fake",
            "doi": doi,
            "source_url": "https://example.test/article",
            "content_type": "text/html",
            "route_kind": "html",
        }
    )
    monkeypatch.setitem(sys.modules, "tests.golden_corpus", fake_module)
    monkeypatch.setitem(sys.modules, "tests.golden_criteria", fake_criteria)
    (tmp_path / "extracted.md").write_text("generic baseline", encoding="utf-8")

    markdown, source = cleaning._render_markdown_baseline(
        "10.1234/example",
        tmp_path,
        tmp_path / "original.html",
    )

    assert markdown == "## Produced by provider chain"
    assert source == "tests.golden_corpus:provider_adapter_production_chain"
    assert calls == [("body", "full_text")]


def test_plos_xml_baseline_uses_shared_jats_renderer(tmp_path: Path) -> None:
    raw_path = tmp_path / "original.xml"
    raw_path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<article xmlns:mml="http://www.w3.org/1998/Math/MathML">
  <front>
    <journal-meta><journal-title-group><journal-title>PLOS Test</journal-title></journal-title-group></journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">10.1371/journal.pone.test</article-id>
      <title-group><article-title>PLOS JATS Fixture</article-title></title-group>
      <contrib-group><contrib contrib-type="author"><name><surname>Curie</surname><given-names>Marie</given-names></name></contrib></contrib-group>
      <abstract><p>This abstract comes from JATS.</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec><title>Results</title><p>Body text proves the XML route.</p></sec>
  </body>
  <back><ref-list><ref id="r1"><mixed-citation>Reference text.</mixed-citation></ref></ref-list></back>
</article>
""",
        encoding="utf-8",
    )

    markdown, source = cleaning._render_markdown_baseline(
        "10.1371/journal.pone.test",
        tmp_path,
        raw_path,
        fixture_sample={
            "publisher": "plos",
            "doi": "10.1371/journal.pone.test",
            "source_url": "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.test&type=manuscript",
            "content_type": "text/xml",
            "route_kind": "xml",
            "fixture_family": "golden",
            "assets": {},
        },
        sample_id="plos-test",
    )

    assert (
        source == "paper_fetch.providers._article_markdown_jats:plos_manifest_fixture"
    )
    assert "PLOS JATS Fixture" in markdown
    assert "This abstract comes from JATS" in markdown
    assert "Body text proves the XML route" in markdown


def test_ieee_landing_only_fallback_fixtures_render_provider_managed_baselines() -> (
    None
):
    manifest = yaml.safe_load(
        (REPO_ROOT / "onboarding" / "manifests" / "ieee.yml").read_text(
            encoding="utf-8"
        )
    )
    doi_samples = manifest["fixtures"]["doi_samples"]
    manifest["fixtures"]["doi_samples"] = {
        "pdf_fallback": doi_samples["pdf_fallback"],
        "abstract_only": doi_samples["abstract_only"],
    }
    manifest["markdown_contract"] = {
        "pdf_fallback": manifest["markdown_contract"]["pdf_fallback"],
        "abstract_only": manifest["markdown_contract"]["abstract_only"],
    }

    inventory = cleaning.collect_fixture_inventory(manifest)
    baselines = cleaning.collect_baselines(inventory)

    assert [item["raw_path"] for item in inventory] == [
        "tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567/landing.html",
        "tests/fixtures/golden_criteria/10.1109_PGEC.1967.264619/landing.html",
    ]
    pdf_baseline = baselines["pdf_fallback:10.1109/mper.1985.5526567"]
    abstract_baseline = baselines["abstract_only:10.1109/pgec.1967.264619"]
    assert pdf_baseline["markdown_source"] == (
        "paper_fetch.providers.ieee:provider_managed_pdf_fallback_fixture"
    )
    assert "# IEEE legacy PDF fallback sample" in pdf_baseline["markdown"]
    assert abstract_baseline["markdown_source"] == (
        "paper_fetch.providers.ieee:provider_managed_abstract_only"
    )
    assert "## Abstract" in abstract_baseline["markdown"]


def test_oxfordacademic_pdf_fallback_is_excluded_from_html_cleaning_inventory() -> None:
    manifest = yaml.safe_load(
        (REPO_ROOT / "onboarding" / "manifests" / "oxfordacademic.yml").read_text(
            encoding="utf-8"
        )
    )
    doi_samples = manifest["fixtures"]["doi_samples"]
    manifest["fixtures"]["doi_samples"] = {
        "structure": doi_samples["structure"],
        "pdf_fallback": doi_samples["pdf_fallback"],
    }
    manifest["markdown_contract"] = {
        "structure": manifest["markdown_contract"]["structure"],
        "pdf_fallback": manifest["markdown_contract"]["pdf_fallback"],
    }

    inventory = cleaning.collect_fixture_inventory(manifest)
    skipped = cleaning.collect_skipped_cleaning_inventory_items(manifest)
    proposal = cleaning.build_cleaning_chain_proposal(
        manifest,
        manifest_path="onboarding/manifests/oxfordacademic.yml",
    )

    assert [item["purpose"] for item in inventory] == ["structure"]
    assert all(item["raw_path"].endswith("original.html") for item in inventory)
    assert [item["purpose"] for item in skipped] == ["pdf_fallback"]
    assert "pdf_fallback" not in proposal["proposed_markdown_contract_delta"]
    assert proposal["skipped_cleaning_inventory"] == skipped
    assert cleaning.contract_check_result(proposal)["status"] == "pass"


def test_cleaning_risk_and_token_conflict_helpers_report_risks() -> None:
    manifest = _mdpi_subset_manifest()
    inventory = cleaning.collect_fixture_inventory(manifest)
    baselines = cleaning.collect_baselines(inventory)
    risks = cleaning.detect_overcleaning_risks(inventory, baselines)
    conflicts = cleaning.token_conflict_report(
        [
            {
                "token": "Abstract",
            }
        ],
        baselines,
    )

    assert risks
    assert {"purpose", "doi", "fixture_path", "dom_path", "sample_text", "risk"} <= set(
        risks[0]
    )
    assert conflicts == [
        {
            "token": "Abstract",
            "raw_hits": [
                {"fixture": key, "purpose": value["purpose"]}
                for key, value in baselines.items()
                if "abstract" in cleaning.normalize_text(value["raw_text"]).lower()
            ],
            "markdown_baseline_hits": [
                {"fixture": key, "purpose": value["purpose"]}
                for key, value in baselines.items()
                if "abstract" in cleaning.normalize_text(value["markdown"]).lower()
            ],
            "possible_body_conflict": True,
        }
    ]


def test_cleaning_proposal_cli_writes_yaml(tmp_path: Path) -> None:
    manifest_path = tmp_path / "mdpi-subset.yml"
    output_path = tmp_path / "proposal.yml"
    manifest_path.write_text(
        yaml.safe_dump(_mdpi_subset_manifest(), sort_keys=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--manifest",
            str(manifest_path),
            "--write",
            "--output",
            str(output_path),
        ],
        check=True,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    proposal = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert payload["provider"] == "mdpi"
    assert payload["output"] == output_path.as_posix()
    assert proposal["schema_version"] == 2
    assert proposal["provider"] == "mdpi"
    assert proposal["fixtures_digest"]
    assert "raw_fixture_inventory" not in proposal
    assert not (tmp_path / "proposal.evidence.yml").exists()


def test_anchor_suggestions_are_normalized_and_deduped() -> None:
    deltas = cleaning.calibrate_markdown_contract(
        {
            "markdown_contract": {
                "structure": {
                    "doi": "10.0000/example",
                    "must_include": [],
                    "must_not_include": [],
                }
            }
        },
        {
            "structure:10.0000/example": {
                "markdown": "",
                "raw_text": "Abstract",
            }
        },
        [
            {"purpose": "structure", "text": "Abstract"},
            {"purpose": "structure", "text": " abstract "},
            {"purpose": "structure", "text": "Abstract\n"},
        ],
    )

    assert deltas["structure"]["suggested_must_include_from_fixtures"] == ["Abstract"]


def test_contract_check_classifies_dead_tokens_and_blocks_only_real_drift() -> None:
    proposal = {
        "provider": "sample",
        "fixtures_digest": [],
        "overcleaning_probes": [],
        "token_conflict_report": [],
        "proposed_markdown_contract_delta": {
            "structure": {
                "doi": "10.0000/example",
                "missing_must_include": ["Required body text"],
                "dead_must_not_include": cleaning.classify_dead_must_not_include(
                    [
                        "[Formula unavailable]",
                        "Download PDF",
                        "Impossible Site Token",
                    ]
                ),
            }
        },
    }

    result = cleaning.contract_check_result(proposal)

    assert result["status"] == "fail"
    assert result["failure_code"] == "MARKDOWN_CONTRACT_DRIFT"
    assert result["blocking"]["missing_must_include"] == [
        {
            "purpose": "structure",
            "doi": "10.0000/example",
            "token": "Required body text",
        }
    ]
    assert result["blocking"]["truly_vacuous"][0]["token"] == "Impossible Site Token"
    assert result["warnings"]["sentinel"][0]["token"] == "[Formula unavailable]"
    assert result["warnings"]["cross_route_guard"][0]["token"] == "Download PDF"


def test_check_contract_cli_warning_only_returns_zero(tmp_path: Path) -> None:
    manifest = _mdpi_subset_manifest()
    manifest["markdown_contract"] = {
        "structure": {
            "doi": manifest["fixtures"]["doi_samples"]["structure"]["doi"],
            "must_include": ["## Abstract"],
            "must_not_include": ["[Formula unavailable]", "Download Citation"],
        }
    }
    manifest_path = tmp_path / "mdpi-warning.yml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--manifest",
            str(manifest_path),
            "--check-contract",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    payload = yaml.safe_load(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["warnings"]["sentinel"]
    assert payload["warnings"]["cross_route_guard"]


def test_check_contract_cli_blocking_returns_nonzero(tmp_path: Path) -> None:
    manifest = _mdpi_subset_manifest()
    manifest["markdown_contract"] = {
        "structure": {
            "doi": manifest["fixtures"]["doi_samples"]["structure"]["doi"],
            "must_include": ["Missing body token that cannot pass"],
            "must_not_include": ["Impossible Site Token"],
        }
    }
    manifest_path = tmp_path / "mdpi-blocking.yml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--manifest",
            str(manifest_path),
            "--check-contract",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    payload = yaml.safe_load(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "fail"
    assert payload["blocking"]["missing_must_include"]
    assert payload["blocking"]["truly_vacuous"]
