from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from paper_fetch import cli
from paper_fetch.delivery.fetch_cache import (
    FetchCache,
    envelope_from_payload,
    payload_from_envelope,
    request_cache_payload,
)
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.manifest import ManifestRecord, build_manifest_record
from paper_fetch.models import AssetQualitySummary, SemanticLosses
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import TraceContext, trace_event
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support.fetch_fixtures import sample_resolved_query
from tests.support.workflow_acceptance import _envelope


def _contract_envelope():
    envelope = _envelope(
        losses=SemanticLosses(table_layout_degraded_count=1),
    )
    asset_summary = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        discovered=2,
        local=1,
        full_size=1,
        failed=1,
        placeholder_suspected=1,
        failure_codes=["image_fetch_error"],
        issue_codes=[
            "asset_download_failure",
            "asset_placeholder_suspected",
        ],
    )
    envelope.quality.asset_summary = asset_summary
    assert envelope.article is not None
    envelope.article.quality.asset_summary = asset_summary
    envelope.trace = [
        trace_event("resolve", "doi_selected", "ok"),
        trace_event(
            "fulltext",
            "elsevier_html",
            "fail",
            code="browser_connect_timeout",
            context=TraceContext(attempt=1, attempt_id="html-1"),
        ),
        trace_event(
            "fulltext",
            "elsevier_xml",
            "ok",
            context=TraceContext(provider="elsevier", route="xml_api"),
        ),
    ]
    envelope.acquisition = envelope.acquisition.__class__(
        provider="elsevier",
        route="xml_api",
        representation="xml",
        transport="api",
        fallback_used=True,
    )
    envelope.article.acquisition = envelope.acquisition
    return envelope


def test_cli_cache_and_manifest_adapters_share_acceptance_contract(
    tmp_path: Path,
) -> None:
    request = FetchPaperRequest.model_validate(
        {
            "query": "10.1000/acceptance",
            "modes": ["article", "markdown"],
            "strategy": {"asset_profile": "body"},
            "prefer_cache": True,
        }
    )
    requested_outputs = request.requested_modes()
    expected = evaluate_fetch_acceptance(
        _contract_envelope(),
        asset_profile="body",
        requested_outputs=requested_outputs,
        expected_doi=request.query,
    )

    wire_payload = payload_from_envelope(_contract_envelope(), request)
    wire_report = evaluate_fetch_acceptance(
        envelope_from_payload(wire_payload),
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
        mock.patch.object(
            cli, "resolve_paper", return_value=sample_resolved_query(request.query)
        ),
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

    cache_dir = tmp_path / "cache"
    cache = FetchCache(cache_dir)
    cache.write_fetch_envelope(_contract_envelope(), request)
    with RuntimeContext(env={}, download_dir=cache_dir) as context:
        cached_envelope = cache.load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(),
            context=context,
        )
    assert cached_envelope is not None
    cached_report = evaluate_fetch_acceptance(
        cached_envelope,
        asset_profile="body",
        requested_outputs=requested_outputs,
        expected_doi=request.query,
    )

    assert exit_code == 0
    assert wire_report == expected
    assert manifest_record.acceptance == expected
    assert cli_record.acceptance == expected
    assert cached_report == expected
    assert tuple(wire_payload["quality"]["asset_summary"]["issue_codes"]) == (
        "asset_download_failure",
        "asset_placeholder_suspected",
    )
    assert manifest_record.acceptance.asset.issue_codes == (
        "asset_download_failure",
        "asset_placeholder_suspected",
    )
    assert cli_record.acceptance.asset.issue_codes == (
        "asset_download_failure",
        "asset_placeholder_suspected",
    )
    assert len(wire_payload["trace"]) == 3
    assert len(manifest_record.trace) == 3
    assert len(cli_record.trace) == 3
