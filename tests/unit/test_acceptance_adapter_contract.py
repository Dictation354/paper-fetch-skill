from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from paper_fetch import cli
from paper_fetch.manifest import ManifestRecord, build_manifest_record
from paper_fetch.mcp.fetch_cache import (
    FetchCache,
    envelope_from_payload,
    payload_from_envelope,
    request_cache_payload,
)
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.models import AssetQualitySummary, SemanticLosses
from paper_fetch.workflow.acceptance import (
    FetchAcceptanceReport,
    evaluate_fetch_acceptance,
)

from .test_workflow_acceptance import _envelope


def _contract_envelope():
    envelope = _envelope(
        losses=SemanticLosses(table_layout_degraded_count=1),
    )
    asset_summary = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        total=2,
        local=1,
        full_size=1,
        failed=1,
        placeholder_suspected=1,
        failure_codes=["image_fetch_error"],
    )
    envelope.quality.asset_summary = asset_summary
    assert envelope.article is not None
    envelope.article.quality.asset_summary = asset_summary
    return envelope


def _summary(report: FetchAcceptanceReport) -> dict[str, str]:
    return {
        "status": "evaluated",
        "overall": report.overall.value,
        "identity": report.identity.status.value,
        "fetch": report.fetch.status.value,
        "content": report.content.status.value,
        "asset": report.asset.status.value,
        "output": report.output.status.value,
        "provenance": report.provenance.status.value,
    }


def test_cli_mcp_cache_and_manifest_adapters_share_acceptance_contract(
    tmp_path: Path,
) -> None:
    request = FetchPaperRequest.model_validate(
        {
            "query": "10.1000/acceptance",
            "modes": ["article", "markdown"],
            "strategy": {"asset_profile": "body"},
        }
    )
    requested_outputs = request.requested_modes()
    expected = evaluate_fetch_acceptance(
        _contract_envelope(),
        asset_profile="body",
        requested_outputs=requested_outputs,
        expected_doi=request.query,
    )

    mcp_payload = payload_from_envelope(_contract_envelope(), request)
    mcp_report = evaluate_fetch_acceptance(
        envelope_from_payload(mcp_payload),
        asset_profile="body",
        requested_outputs=requested_outputs,
        expected_doi=request.query,
    )

    manifest_record = build_manifest_record(
        tool_version="3.1.0",
        index=1,
        attempt=1,
        query=request.query,
        request_parameters=request_cache_payload(request),
        asset_profile="body",
        envelope=_contract_envelope(),
        requested_outputs=requested_outputs,
        expected_doi=request.query,
    )

    cli_output = tmp_path / "cli-output.json"
    cli_manifest = tmp_path / "cli-manifest.json"
    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=_contract_envelope()),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        exit_code = cli.main(
            [
                "fetch",
                "--query",
                request.query,
                "--format",
                "both",
                "--output",
                str(cli_output),
                "--output-dir",
                str(tmp_path),
                "--artifact-mode",
                "none",
                "--asset-profile",
                "body",
                "--manifest",
                str(cli_manifest),
            ]
        )
    cli_record = ManifestRecord.model_validate_json(
        cli_manifest.read_text(encoding="utf-8")
    )

    cache = FetchCache(tmp_path / "cache")
    cache.write_fetch_envelope(_contract_envelope(), request)
    cache_payload = cache.get_payload(
        request.query,
        request=request,
        detail="compact",
    )

    assert exit_code == 0
    assert mcp_report == expected
    assert manifest_record.acceptance == expected
    assert cli_record.acceptance == expected
    assert cache_payload["acceptance"] == _summary(expected)
