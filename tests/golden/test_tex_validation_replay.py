"""Replay the seven archived sources from the original MathJax failure report."""

import hashlib
import json
import os
import subprocess

import pytest

from tests.paths import REPO_ROOT
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture

CONTRACTS = json.loads(
    (
        REPO_ROOT
        / "tests/fixtures/golden_criteria/_scenarios/review_contracts/expected.json"
    ).read_text()
)


@pytest.mark.parametrize("sample_id", CONTRACTS["samples"])
def test_archived_formula_fallbacks_match_persisted_latex_and_original_containers(
    sample_id, tmp_path
):
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader:
        pytest.skip("requires an explicitly selected installed LitRoot")
    fixture = golden_corpus_fixture_for_doi(sample_id.replace("_", "/", 1))
    article = build_article_from_fixture(fixture)
    actual = tmp_path / "replay.md"
    actual.write_text(
        article.to_ai_markdown(
            include_refs="all", max_tokens="full_text", asset_profile="all"
        )
    )
    baseline = REPO_ROOT / "tests/fixtures/golden_criteria" / sample_id / "extracted.md"
    reviewed = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts/review_markdown_math.mjs"),
            "--modules-root",
            reader,
            "--include-formulas",
            str(actual),
            str(baseline),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert reviewed.returncode == 0, reviewed.stderr or reviewed.stdout[-1000:]
    replay, persisted = json.loads(reviewed.stdout)["files"]
    expected = CONTRACTS["samples"][sample_id]
    current = expected["current"]
    assert persisted["sha256"] == current["baseline_sha256"]
    assert (replay["formulas"], replay["inline"], replay["display"]) == (
        current["formulas"],
        current["inline"],
        current["display"],
    )

    def formula_signature(row):
        return [
            (n["expression"], n["displayMode"], n["context"])
            for n in row["formulaNodes"]
        ]

    assert formula_signature(replay) == formula_signature(persisted)
    containers = [(n["displayMode"], n["context"]) for n in replay["formulaNodes"]]
    assert (
        hashlib.sha256(
            json.dumps(containers, separators=(",", ":")).encode()
        ).hexdigest()
        == current["container_sha256"]
    )
    diagnostics = article.quality.semantic_losses.formula_diagnostics
    fallbacks = [d for d in diagnostics if d["source_tex"] and d["backend"]]
    assert len(fallbacks) == expected["mathml_fallbacks"]
    assert all(d["valid"] and d["validation_errors"] for d in fallbacks)
    assert article.quality.semantic_losses.formula_fallback_count >= len(fallbacks)
    if sample_id.endswith("0811.2625v2"):
        assert any("small-caps" in d["style_degradations"] for d in fallbacks)
    errors = expected["original_errors"]
    assert len(errors) == expected["previous_errors"]
    for path, digest in expected["source_hashes"].items():
        assert hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest() == digest
    for error in errors:
        assert any(
            d["valid"]
            and (
                d["source_tex"] == error["expression"]
                or (
                    not d["source_tex"]
                    and " ".join(d["final_latex"].split())
                    == " ".join(error["expression"].split())
                )
            )
            for d in diagnostics
        ), error
