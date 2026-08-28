from __future__ import annotations

from paper_fetch_devtools.markdown_quality import (
    build_agent_markdown_quality_report,
    build_fresh_markdown_quality_prompt,
    build_markdown_quality_prompt,
    build_pending_markdown_quality_report,
    validate_markdown_quality_report,
)


BASE = {
    "provider": "demo",
    "doi": "10.1234/demo",
    "sample_id": "10.1234_demo",
    "markdown_path": "tests/fixtures/golden_criteria/10.1234_demo/extracted.md",
    "prompt_path": "tests/fixtures/golden_criteria/10.1234_demo/markdown-quality-prompt.md",
}


def test_prompt_contains_review_task_paths_contract_and_semantic_risks() -> None:
    prompt = build_markdown_quality_prompt(
        **BASE,
        purpose="supplementary",
        report_path="tests/fixtures/golden_criteria/10.1234_demo/markdown-quality.json",
    )

    assert "Markdown Quality Agent Review" in prompt
    assert "Read the Markdown as a human reviewer" in prompt
    assert BASE["markdown_path"] in prompt
    assert BASE["prompt_path"] in prompt
    assert "Fixture purpose: `supplementary`" in prompt
    assert "schema_version" in prompt
    assert '"review_method": "agent_prompt"' in prompt
    assert "Semantic Risks To Check" in prompt
    assert "asset_contract.figures.purposes" in prompt
    assert "Broken tables" in prompt
    assert "References" in prompt
    assert "missing recognizable numbering or labels" in prompt


def test_fresh_prompt_requires_rereading_current_extracted_markdown() -> None:
    prompt = build_fresh_markdown_quality_prompt(
        **BASE,
        purpose="formula",
        report_path=".paper-fetch-runs/demo/fresh-markdown-quality.json",
        markdown_sha256="a" * 64,
    )

    assert "Fresh Markdown Quality Review" in prompt
    assert "Open and read the current Markdown file from disk" in prompt
    assert "Fresh report to write" in prompt
    assert "Fixture purpose: `formula`" in prompt
    assert BASE["markdown_path"] in prompt
    assert '"fresh_review": true' in prompt
    assert "unnumbered/unlabeled references when references are expected" in prompt


def test_pending_pass_and_fail_report_schema_validation() -> None:
    pending = build_pending_markdown_quality_report(**BASE)
    passing = build_agent_markdown_quality_report(
        **BASE,
        status="pass",
        reviewed_by="codex-agent",
        reviewed_at="2026-05-23T00:00:00Z",
    )
    failing = build_agent_markdown_quality_report(
        **BASE,
        status="fail",
        issues=[
            {
                "id": "broken-table",
                "severity": "high",
                "blocking": True,
                "summary": "Table rows are semantically unusable.",
            }
        ],
        reviewed_by="codex-agent",
        reviewed_at="2026-05-23T00:00:00Z",
    )

    assert pending["status"] == "pending_agent_review"
    assert validate_markdown_quality_report(pending) == []
    assert validate_markdown_quality_report(passing) == []
    assert validate_markdown_quality_report(failing) == []
    assert failing["blocking_issue_count"] == 1


def test_report_validation_rejects_legacy_or_inconsistent_agent_reports() -> None:
    legacy = {
        "schema_version": 1,
        "provider": "demo",
        "doi": "10.1234/demo",
        "sample_id": "10.1234_demo",
        "markdown_path": BASE["markdown_path"],
        "status": "pass",
        "issues": [],
        "blocking_issue_count": 0,
    }
    inconsistent = build_agent_markdown_quality_report(
        **BASE,
        status="pass",
        issues=[
            {
                "id": "bad",
                "severity": "high",
                "blocking": True,
                "summary": "Blocking issue.",
            }
        ],
        reviewed_by="codex-agent",
        reviewed_at="2026-05-23T00:00:00Z",
    )

    assert "schema_version must be 2" in validate_markdown_quality_report(legacy)
    assert any(
        "status pass cannot include blocking issues" == error
        for error in validate_markdown_quality_report(inconsistent)
    )


def test_module_does_not_infer_issues_from_markdown_content() -> None:
    suspicious_markdown = (
        "# Demo\n\n## Abstract\n\n[open](javascript:;)\n\n## Abstract\n"
    )
    report = build_pending_markdown_quality_report(**BASE)

    assert suspicious_markdown
    assert report["issues"] == []
    assert report["status"] == "pending_agent_review"
