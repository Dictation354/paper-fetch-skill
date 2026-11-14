"""Shared compact acceptance projections for MCP fetch responses."""

from __future__ import annotations

from typing import Any

from ..workflow.acceptance import FetchAcceptanceReport
from ..workflow.batch_routing import expected_doi_from_query

__all__ = ["compact_acceptance_payload", "expected_doi_from_query"]


def compact_acceptance_payload(
    report: FetchAcceptanceReport,
) -> dict[str, Any]:
    """Project the canonical report into the bounded MCP acceptance contract."""

    return {
        **(
            {"target": report.target, "content_requested": report.content.requested}
            if report.target != "paper"
            else {}
        ),
        "overall": report.overall.value,
        "identity": report.identity.status.value,
        "fetch": report.fetch.status.value,
        "content": report.content.status.value,
        "asset": report.asset.status.value,
        "output": report.output.status.value,
        "provenance": report.provenance.status.value,
        "has_fulltext": report.content.has_fulltext,
        "has_abstract": report.content.has_abstract,
        "token_estimate": report.content.token_estimate,
        "asset_summary": (
            report.asset.model_dump(mode="json")
            if report.asset.requested
            else {
                "requested": False,
                "profile": report.asset.profile,
            }
        ),
    }


def acceptance_reason_codes(report: FetchAcceptanceReport) -> dict[str, Any]:
    return {
        name: list(getattr(report.provenance, name))
        for name in ("fallback_codes", "warning_codes", "failure_codes")
    }
