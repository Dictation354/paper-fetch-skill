"""Shared compact acceptance projections for fetch responses."""

from __future__ import annotations

from typing import Any

from ..workflow.acceptance import FetchAcceptanceReport
from ..workflow.batch_routing import expected_doi_from_query

__all__ = ["compact_acceptance_payload", "expected_doi_from_query"]


def compact_acceptance_payload(
    report: FetchAcceptanceReport,
) -> dict[str, Any]:
    """Project the canonical report into the CLI receipt v1 contract."""

    asset = report.asset
    body = asset.body_assets
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
            {
                **asset.model_dump(mode="json", exclude={"body_assets"}),
                "total": asset.discovered,
                "preview": asset.preview,
                **{f"body_{key}": value for key, value in body.model_dump().items()},
                "has_local_body_assets": body.local > 0,
                "all_body_assets_local": body.all_local,
                "all_body_assets_full_size": body.all_full_size,
                "remote_links_preserved": asset.remote_only_count > 0,
            }
            if asset.requested
            else {
                "requested": False,
                "profile": asset.profile,
            }
        ),
    }
