"""Agent-prompt contract for generated golden Markdown baselines."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
REVIEW_METHOD = "agent_prompt"
PENDING_STATUS = "pending_agent_review"
FINAL_STATUSES = {"pass", "fail"}
STATUS_VALUES = {PENDING_STATUS, *FINAL_STATUSES}
SEVERITY_VALUES = {"low", "medium", "high", "critical"}


def build_markdown_quality_prompt(
    *,
    provider: str,
    doi: str,
    sample_id: str,
    markdown_path: str,
    prompt_path: str,
    report_path: str,
    purpose: str | None = None,
) -> str:
    """Return the prompt an agent must use to author a Markdown quality report."""

    purpose_line = f"- Fixture purpose: `{purpose}`\n" if purpose else ""
    report_template = {
        "schema_version": SCHEMA_VERSION,
        "review_method": REVIEW_METHOD,
        "provider": provider,
        "doi": doi,
        "sample_id": sample_id,
        "markdown_path": markdown_path,
        "prompt_path": prompt_path,
        "status": "pass",
        "issues": [],
        "blocking_issue_count": 0,
        "reviewed_by": "<agent-or-operator-id>",
        "reviewed_at": "<UTC ISO-8601 timestamp>",
    }
    return (
        "# Markdown Quality Agent Review\n"
        "\n"
        "You are reviewing the committed Markdown baseline for provider onboarding.\n"
        "\n"
        "## Inputs\n"
        "\n"
        f"- Provider: `{provider}`\n"
        f"- DOI: `{doi}`\n"
        f"- Sample ID: `{sample_id}`\n"
        f"{purpose_line}"
        f"- Markdown to review: `{markdown_path}`\n"
        f"- Prompt path: `{prompt_path}`\n"
        f"- Report to write: `{report_path}`\n"
        "\n"
        "## Task\n"
        "\n"
        "Read the Markdown as a human reviewer. Judge whether it is a usable, "
        "provider-neutral semantic baseline for this article fixture. Do not mark "
        "the report pass by relying on deterministic regexes, fixture metadata, or "
        "the previous quality report. The decision must come from reviewing the "
        "Markdown content itself.\n"
        "\n"
        "## Semantic Risks To Check\n"
        "\n"
        "- Missing, duplicated, empty, or obviously misplaced title/abstract/body sections.\n"
        "- Publisher chrome, navigation, cookie text, license boilerplate, or download widgets mixed into article content.\n"
        "- Broken tables, orphan table rows, malformed formula blocks, or formula text glued to prose.\n"
        "- Missing figure captions, empty figure/table sections, or media placeholders presented as content.\n"
        "- Enforce `asset_contract.figures` only when this fixture purpose is listed in the provider manifest `asset_contract.figures.purposes`; for other purposes, remote figure links are not blocking by themselves.\n"
        "- For figure-contract purposes with `asset_contract.figures.inline: body`, missing body `![Figure ...](...)` images before References/Figures/Supplementary tail sections is blocking; a caption-only `## Figures` appendix is not enough.\n"
        "- For figure-contract purposes with `asset_contract.figures.download: required`, missing local asset-path rewrites for downloaded figure images is blocking; remote-only image links do not satisfy the asset contract.\n"
        "- References that are absent when expected from the article, missing recognizable numbering or labels, mostly DOI-only, duplicated, or polluted by unrelated text.\n"
        "- JavaScript placeholder links, unresolved template text, severe OCR noise, or repeated article fragments.\n"
        "- Any other semantic corruption that would make `extracted.md` unsafe as a golden Markdown baseline.\n"
        "\n"
        "## Output JSON Contract\n"
        "\n"
        'Write JSON to the report path using this schema. Use `status: "pass"` '
        'only when there are no blocking issues. Use `status: "fail"` when one '
        "or more blocking issues remain, and set `blocking_issue_count` to the "
        "number of issues whose `blocking` field is `true`.\n"
        "\n"
        "```json\n"
        f"{json.dumps(report_template, indent=2, sort_keys=True)}\n"
        "```\n"
        "\n"
        "Each issue must include `id`, `severity`, `blocking`, and `summary`; add "
        "`evidence` when a short excerpt or location helps. `reviewed_by` and "
        "`reviewed_at` are required for both `pass` and `fail` reports.\n"
    )


def build_fresh_markdown_quality_prompt(
    *,
    provider: str,
    doi: str,
    sample_id: str,
    markdown_path: str,
    prompt_path: str,
    report_path: str,
    markdown_sha256: str,
    purpose: str | None = None,
) -> str:
    """Return a prompt for a fresh machine review of the current Markdown file."""

    purpose_line = f"- Fixture purpose: `{purpose}`\n" if purpose else ""
    report_template = {
        "schema_version": SCHEMA_VERSION,
        "review_method": REVIEW_METHOD,
        "provider": provider,
        "doi": doi,
        "sample_id": sample_id,
        "markdown_path": markdown_path,
        "prompt_path": prompt_path,
        "status": "pass",
        "issues": [],
        "blocking_issue_count": 0,
        "reviewed_by": "<agent-or-operator-id>",
        "reviewed_at": "<UTC ISO-8601 timestamp>",
        "fresh_review": True,
        "source_markdown_sha256": markdown_sha256,
    }
    return (
        "# Fresh Markdown Quality Review\n"
        "\n"
        "You are independently judging the current extracted Markdown for provider onboarding.\n"
        "\n"
        "## Inputs\n"
        "\n"
        f"- Provider: `{provider}`\n"
        f"- DOI: `{doi}`\n"
        f"- Sample ID: `{sample_id}`\n"
        f"{purpose_line}"
        f"- Markdown to read now: `{markdown_path}`\n"
        f"- Markdown SHA-256 at dispatch: `{markdown_sha256}`\n"
        f"- Standing review instructions: `{prompt_path}`\n"
        f"- Fresh report to write: `{report_path}`\n"
        "\n"
        "## Task\n"
        "\n"
        "Open and read the current Markdown file from disk. Ignore any previous "
        "`markdown-quality.json` conclusion except as historical context if you "
        "happen to inspect it. The pass/fail decision must come from the current "
        "`extracted.md` content.\n"
        "\n"
        "Judge whether this Markdown is a usable semantic baseline. Blocking "
        "issues include missing, duplicated, empty, or misplaced title/abstract/body "
        "sections; publisher chrome or license/download widgets mixed into article "
        "content; broken tables; orphan rows; malformed formula blocks; formula "
        "text glued into prose; empty figure/table sections; missing captions; "
        "missing body inline `![Figure ...](...)` images or local downloaded asset "
        "paths only when this fixture purpose is listed in the provider manifest "
        "`asset_contract.figures.purposes`; "
        "missing or DOI-only references; unnumbered/unlabeled references when references "
        "are expected; missing back matter; JavaScript links; "
        "unresolved template text; severe OCR noise; and repeated article fragments.\n"
        "\n"
        "## Output JSON Contract\n"
        "\n"
        'Write JSON to the fresh report path using this schema. Use `status: "pass"` '
        'only when there are no blocking issues. Use `status: "fail"` when one '
        "or more blocking issues remain, and set `blocking_issue_count` to the "
        "number of issues whose `blocking` field is `true`.\n"
        "\n"
        "```json\n"
        f"{json.dumps(report_template, indent=2, sort_keys=True)}\n"
        "```\n"
        "\n"
        "Each issue must include `id`, `severity`, `blocking`, and `summary`; add "
        "`evidence` when a short excerpt or location helps.\n"
    )


def build_pending_markdown_quality_report(
    *,
    provider: str,
    doi: str,
    sample_id: str,
    markdown_path: str,
    prompt_path: str,
) -> dict[str, Any]:
    """Return the initial report snapshot before agent review has happened."""

    return {
        "schema_version": SCHEMA_VERSION,
        "review_method": REVIEW_METHOD,
        "provider": provider,
        "doi": doi,
        "sample_id": sample_id,
        "markdown_path": markdown_path,
        "prompt_path": prompt_path,
        "status": PENDING_STATUS,
        "issues": [],
        "blocking_issue_count": 0,
    }


def build_agent_markdown_quality_report(
    *,
    provider: str,
    doi: str,
    sample_id: str,
    markdown_path: str,
    prompt_path: str,
    status: str,
    issues: list[dict[str, Any]] | None = None,
    reviewed_by: str,
    reviewed_at: str,
) -> dict[str, Any]:
    """Build a final agent-authored report without inspecting Markdown content."""

    issue_list = list(issues or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "review_method": REVIEW_METHOD,
        "provider": provider,
        "doi": doi,
        "sample_id": sample_id,
        "markdown_path": markdown_path,
        "prompt_path": prompt_path,
        "status": status,
        "issues": issue_list,
        "blocking_issue_count": len(
            [
                issue
                for issue in issue_list
                if isinstance(issue, dict) and issue.get("blocking") is True
            ]
        ),
        "reviewed_by": reviewed_by,
        "reviewed_at": reviewed_at,
    }


def blocking_markdown_quality_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues = report.get("issues")
    if not isinstance(issues, list):
        return []
    return [
        issue
        for issue in issues
        if isinstance(issue, dict) and issue.get("blocking") is True
    ]


def _is_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_markdown_quality_report(report: Any) -> list[str]:
    """Return schema/contract errors for an agent-authored Markdown report."""

    if not isinstance(report, dict):
        return ["markdown quality report root must be an object"]

    errors: list[str] = []
    required = (
        "schema_version",
        "review_method",
        "provider",
        "doi",
        "sample_id",
        "markdown_path",
        "prompt_path",
        "status",
        "issues",
        "blocking_issue_count",
    )
    for field in required:
        if field not in report:
            errors.append(f"{field} is required")

    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if report.get("review_method") != REVIEW_METHOD:
        errors.append(f"review_method must be {REVIEW_METHOD!r}")

    for field in ("provider", "doi", "sample_id", "markdown_path", "prompt_path"):
        if field in report and not isinstance(report.get(field), str):
            errors.append(f"{field} must be a string")

    status = report.get("status")
    if status not in STATUS_VALUES:
        errors.append(f"status must be one of {sorted(STATUS_VALUES)}")

    issues = report.get("issues")
    if not isinstance(issues, list):
        errors.append("issues must be an array")
        issues = []

    blocking_count = 0
    for index, issue in enumerate(issues):
        if not isinstance(issue, dict):
            errors.append(f"issues[{index}] must be an object")
            continue
        for field in ("id", "severity", "blocking", "summary"):
            if field not in issue:
                errors.append(f"issues[{index}].{field} is required")
        if "id" in issue and not isinstance(issue.get("id"), str):
            errors.append(f"issues[{index}].id must be a string")
        if issue.get("severity") not in SEVERITY_VALUES:
            errors.append(
                f"issues[{index}].severity must be one of {sorted(SEVERITY_VALUES)}"
            )
        if "blocking" in issue and not isinstance(issue.get("blocking"), bool):
            errors.append(f"issues[{index}].blocking must be a boolean")
        if "summary" in issue and not isinstance(issue.get("summary"), str):
            errors.append(f"issues[{index}].summary must be a string")
        if issue.get("blocking") is True:
            blocking_count += 1

    declared_blocking_count = report.get("blocking_issue_count")
    if not isinstance(declared_blocking_count, int) or declared_blocking_count < 0:
        errors.append("blocking_issue_count must be a non-negative integer")
    elif declared_blocking_count != blocking_count:
        errors.append(
            "blocking_issue_count must equal the number of issues with blocking=true"
        )

    if status in FINAL_STATUSES:
        for field in ("reviewed_by", "reviewed_at"):
            if not isinstance(report.get(field), str) or not report.get(field):
                errors.append(f"{field} is required for pass/fail reports")
        reviewed_at = report.get("reviewed_at")
        if (
            isinstance(reviewed_at, str)
            and reviewed_at
            and not _is_datetime(reviewed_at)
        ):
            errors.append("reviewed_at must be an ISO-8601 timestamp")

    if status == "pass" and blocking_count:
        errors.append("status pass cannot include blocking issues")
    if status == "fail" and not blocking_count:
        errors.append("status fail must include at least one blocking issue")
    if status == PENDING_STATUS and blocking_count:
        errors.append("pending reports cannot include blocking issues")

    return errors


def markdown_quality_passed(report: dict[str, Any]) -> bool:
    return (
        validate_markdown_quality_report(report) == []
        and report.get("status") == "pass"
        and not blocking_markdown_quality_issues(report)
    )


def write_markdown_quality_prompt(path: Path, prompt: str) -> None:
    path.write_text(prompt, encoding="utf-8")


def write_markdown_quality_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
