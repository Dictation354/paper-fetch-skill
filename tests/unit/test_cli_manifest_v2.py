from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest import mock
from uuid import UUID

import pytest

from paper_fetch import cli
from paper_fetch import runtime as runtime_module
from paper_fetch.manifest import (
    ManifestBuilderDependencies,
    ManifestRecordStatus,
    parse_manifest_record,
)
from paper_fetch.manifest_writer import ManifestAuditStatus, audit_manifest_path
from paper_fetch.models import AcquisitionProvenance, Asset, SemanticLosses
from paper_fetch.providers import springer as springer_provider
from paper_fetch.providers._asset_retry import merge_asset_retry_results
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.quality.assets import build_asset_quality_summary
from paper_fetch.reason_codes import MANAGED_CHROME_EXITED_BEFORE_CDP, RATE_LIMITED
from paper_fetch.tracing import trace_event
from paper_fetch.workflow.acceptance import (
    AssetAcceptanceStatus,
    OverallAcceptanceStatus,
)

from .test_workflow_acceptance import _envelope


RUN_ID = UUID("10000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("20000000-0000-4000-8000-000000000002")
STARTED_AT = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 7, 10, 8, 1, tzinfo=UTC)


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "batch_results": None,
        "batch_concurrency": 1,
        "format": "markdown",
        "asset_profile": "none",
        "include_refs": "all",
        "max_tokens": "full_text",
        "no_download": True,
        "save_markdown_to_disk": False,
        "output": "-",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _fixed_deps(
    *, record_ids: tuple[UUID, ...] = (RECORD_ID,)
) -> ManifestBuilderDependencies:
    uuids = iter(record_ids)
    return ManifestBuilderDependencies(
        clock=lambda: COMPLETED_AT,
        uuid_factory=lambda: next(uuids),
    )


def _build_record(
    tmp_path: Path,
    *,
    args: argparse.Namespace | None = None,
    result: cli.SingleFetchResult | None = None,
    error: Exception | None = None,
):
    deps = _fixed_deps()
    return cli._build_cli_manifest_record(
        cli.CliManifestBuildContext(
            args=args or _args(),
            output_dir=tmp_path,
            artifact_mode="none",
            run_id=RUN_ID,
            tool_version="3.1.0",
            deps=deps,
        ),
        cli.CliManifestAttempt(
            index=1,
            query="10.1000/acceptance",
            started_at=STARTED_AT,
            completed_at=COMPLETED_AT,
        ),
        result=result,
        error=error,
    )


def test_single_manifest_is_explicit_atomic_and_hashes_final_output(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "article.md"
    manifest_path = tmp_path / "result.manifest.json"
    uuids = iter((RUN_ID, RECORD_ID))
    times = iter((STARTED_AT, COMPLETED_AT))
    deps = ManifestBuilderDependencies(
        clock=lambda: next(times),
        uuid_factory=lambda: next(uuids),
    )
    envelope = _envelope()

    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=envelope),
        mock.patch.object(cli, "package_version", return_value="3.1.0"),
        mock.patch.object(cli, "DEFAULT_MANIFEST_BUILDER_DEPENDENCIES", deps),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        exit_code = cli.main(
            [
                "fetch",
                "--query",
                "10.1000/acceptance",
                "--output",
                str(output_path),
                "--output-dir",
                str(tmp_path),
                "--artifact-mode",
                "none",
                "--asset-profile",
                "none",
                "--manifest",
                str(manifest_path),
            ]
        )

    assert exit_code == 0
    assert output_path.exists()
    assert manifest_path.exists()
    assert not output_path.with_suffix(".md.part").exists()
    assert not manifest_path.with_suffix(".json.part").exists()

    record = parse_manifest_record(json.loads(manifest_path.read_text("utf-8")))
    primary = record.output_artifacts[0]
    body = output_path.read_bytes()
    assert record.run_id == RUN_ID
    assert record.record_id == RECORD_ID
    assert record.schema_version == 2
    assert record.tool_version == "3.1.0"
    assert record.started_at == STARTED_AT
    assert record.completed_at == COMPLETED_AT
    assert len(record.request_fingerprint) == 64
    assert record.request.parameters["format"] == "markdown"
    assert record.status == "ok"
    assert record.acceptance.overall == OverallAcceptanceStatus.COMPLETE
    assert [event.stage for event in record.trace[:2]] == ["resolve", "fulltext"]
    assert record.fallback_codes == ()
    assert record.output_path == str(output_path)
    assert primary.size == len(body)
    assert primary.sha256 == hashlib.sha256(body).hexdigest()
    assert primary.verification_status == "verified"
    assert list(record.legacy_projection().to_dict()) == [
        "index",
        "query",
        "status",
        "doi",
        "source",
        "output_path",
        "saved_markdown_path",
        "warnings",
        "error",
    ]


def test_single_manifest_hashes_primary_and_saved_markdown_outputs(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "article.json"
    manifest_path = tmp_path / "result.json"

    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=_envelope()),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        exit_code = cli.main(
            [
                "--query",
                "10.1000/acceptance",
                "--format",
                "json",
                "--output",
                str(output_path),
                "--output-dir",
                str(tmp_path),
                "--save-markdown",
                "--asset-profile",
                "none",
                "--manifest",
                str(manifest_path),
            ]
        )

    record = parse_manifest_record(json.loads(manifest_path.read_text("utf-8")))
    assert exit_code == 0
    assert record.output_path == str(output_path)
    assert record.saved_markdown_path is not None
    assert {artifact.kind for artifact in record.output_artifacts} == {
        "primary_json",
        "saved_markdown",
    }
    for artifact in record.output_artifacts:
        body = Path(artifact.path).read_bytes()
        assert artifact.size == len(body)
        assert artifact.sha256 == hashlib.sha256(body).hexdigest()
        assert artifact.verification_status == "verified"


def test_single_default_does_not_write_a_manifest(tmp_path: Path) -> None:
    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "resolve_cli_download_dir", return_value=tmp_path),
        mock.patch.object(cli, "fetch_paper", return_value=_envelope()),
        mock.patch.object(cli, "write_manifest_record") as write_manifest,
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        exit_code = cli.main(
            [
                "--query",
                "10.1000/acceptance",
                "--artifact-mode",
                "none",
                "--asset-profile",
                "none",
            ]
        )

    assert exit_code == 0
    write_manifest.assert_not_called()


def test_single_manifest_cannot_overwrite_the_primary_output(tmp_path: Path) -> None:
    output_path = tmp_path / "article.md"
    stderr = io.StringIO()

    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=_envelope()),
        redirect_stdout(io.StringIO()),
        redirect_stderr(stderr),
    ):
        exit_code = cli.main(
            [
                "--query",
                "10.1000/acceptance",
                "--output",
                str(output_path),
                "--output-dir",
                str(tmp_path),
                "--manifest",
                str(output_path),
            ]
        )

    assert exit_code == 1
    assert output_path.read_text("utf-8").startswith("# Acceptance Article")
    assert "must not overwrite" in json.loads(stderr.getvalue())["reason"]


def test_single_failure_manifest_preserves_exit_code_and_null_output_fields(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "failed.json"
    uuids = iter((RUN_ID, RECORD_ID))
    times = iter((STARTED_AT, COMPLETED_AT))
    deps = ManifestBuilderDependencies(
        clock=lambda: next(times),
        uuid_factory=lambda: next(uuids),
    )
    stderr = io.StringIO()

    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(
            cli,
            "fetch_paper",
            side_effect=ProviderFailure(
                "no_access", "Forbidden", warnings=["license required"]
            ),
        ),
        mock.patch.object(cli, "package_version", return_value="3.1.0"),
        mock.patch.object(cli, "DEFAULT_MANIFEST_BUILDER_DEPENDENCIES", deps),
        redirect_stdout(io.StringIO()),
        redirect_stderr(stderr),
    ):
        exit_code = cli.main(
            [
                "--query",
                "10.1000/acceptance",
                "--output-dir",
                str(tmp_path),
                "--manifest",
                str(manifest_path),
            ]
        )

    record = parse_manifest_record(json.loads(manifest_path.read_text("utf-8")))
    assert exit_code == 3
    assert json.loads(stderr.getvalue())["status"] == "no_access"
    assert record.record_status == ManifestRecordStatus.FAILED
    assert record.status == "no_access"
    assert record.output_path is None
    assert record.saved_markdown_path is None
    assert record.output_artifacts == ()
    assert record.warnings == ("license required",)


def test_failed_manifest_preserves_managed_chrome_stage_code_and_summary(
    tmp_path: Path,
) -> None:
    error = ProviderFailure(
        MANAGED_CHROME_EXITED_BEFORE_CDP,
        "managed_chrome_startup: Chrome exited. Chrome stderr: profile locked",
        trace=[
            trace_event(
                "managed_chrome_startup",
                "wiley_html",
                "fail",
                code=MANAGED_CHROME_EXITED_BEFORE_CDP,
                message="Chrome stderr: profile locked",
            )
        ],
    )

    record = _build_record(tmp_path, error=error)

    assert record.record_status == ManifestRecordStatus.FAILED
    assert record.error is not None
    assert record.error.status == MANAGED_CHROME_EXITED_BEFORE_CDP
    assert record.trace[0].stage == "managed_chrome_startup"
    assert record.trace[0].code == MANAGED_CHROME_EXITED_BEFORE_CDP
    assert record.trace[0].message == "Chrome stderr: profile locked"
    assert MANAGED_CHROME_EXITED_BEFORE_CDP in record.failure_codes


def test_successful_pdf_fallback_keeps_html_browser_failure_degraded(
    tmp_path: Path,
) -> None:
    envelope = _envelope(
        trace=[
            trace_event(
                "fulltext",
                "wiley_html",
                "fail",
                code="managed_chrome_cdp_timeout",
                message="CDP startup timed out.",
            ),
            trace_event("fulltext", "wiley_pdf_fallback", "ok"),
        ]
    )

    record = _build_record(
        tmp_path,
        result=cli.SingleFetchResult(envelope),
    )

    assert record.status == "ok"
    assert record.acceptance.overall == OverallAcceptanceStatus.DEGRADED
    assert "managed_chrome_cdp_timeout" in record.failure_codes
    assert "managed_chrome_cdp_timeout" in record.fallback_codes


@pytest.mark.parametrize(
    ("envelope", "asset_profile", "overall", "asset_status"),
    [
        (
            _envelope(),
            "none",
            OverallAcceptanceStatus.COMPLETE,
            AssetAcceptanceStatus.NOT_REQUESTED,
        ),
        (
            _envelope("metadata_only"),
            "none",
            OverallAcceptanceStatus.LIMITED,
            AssetAcceptanceStatus.NOT_REQUESTED,
        ),
        (
            _envelope(
                assets=[
                    Asset(
                        kind="figure",
                        heading="Figure 1",
                        path="preview.jpg",
                        download_tier="preview",
                    )
                ]
            ),
            "body",
            OverallAcceptanceStatus.DEGRADED,
            AssetAcceptanceStatus.DEGRADED,
        ),
        (
            _envelope(asset_failures=[{"code": "asset_download_failed"}]),
            "body",
            OverallAcceptanceStatus.DEGRADED,
            AssetAcceptanceStatus.FAILED,
        ),
    ],
)
def test_cli_adapter_exposes_fulltext_limited_and_asset_acceptance(
    tmp_path: Path,
    envelope,
    asset_profile: str,
    overall: OverallAcceptanceStatus,
    asset_status: AssetAcceptanceStatus,
) -> None:
    args = _args(asset_profile=asset_profile)
    record = _build_record(
        tmp_path,
        args=args,
        result=cli.SingleFetchResult(envelope),
    )

    assert record.status == "ok"
    assert record.acceptance.overall == overall
    assert record.asset_summary.status == asset_status


def test_springer_formula_rendition_aliases_produce_complete_manifest(
    tmp_path: Path,
) -> None:
    fixture_dir = (
        Path(__file__).parents[1]
        / "fixtures"
        / "golden_criteria"
        / "10.1371_journal.pone.0015338"
        / "body_assets"
    )
    source_images = [
        fixture_dir / f"pone.0015338.e{index:03d}.png" for index in range(1, 5)
    ]
    extracted_assets: list[dict[str, object]] = []
    downloaded_assets: list[dict[str, object]] = []
    for index, (size, source_image) in enumerate(
        zip((220, 40, 35, 80), source_images, strict=True),
        start=1,
    ):
        filename = f"41586_2016_BFnature16457_IEq{index}_HTML.gif"
        preview_url = (
            f"https://media.springernature.com/lw{size}/springer-static/image/"
            f"art%3A10.1038%2Fnature16457/MediaObjects/{filename}"
        )
        full_url = preview_url.replace(f"/lw{size}/", "/full/")
        local_path = tmp_path / f"nature16457-formula-{index}.png"
        shutil.copyfile(source_image, local_path)
        extracted_assets.append(
            {
                "kind": "formula",
                "heading": f"Formula {index}",
                "original_url": preview_url,
                "url": preview_url,
            }
        )
        downloaded_assets.append(
            {
                "kind": "formula",
                "heading": f"Formula {index}",
                "original_url": full_url,
                "url": full_url,
                "path": str(local_path),
                "download_tier": "full",
            }
        )

    merged_assets = merge_asset_retry_results(
        extracted_assets,
        downloaded_assets,
        policy=springer_provider.SPRINGER_ASSET_RETRY_POLICY,
    )
    assets = [Asset(**item) for item in merged_assets]
    asset_summary = build_asset_quality_summary(
        assets,
        asset_profile="body",
        archive_enabled=True,
    )
    envelope = _envelope(assets=assets)
    envelope.doi = "10.1038/nature16457"
    envelope.source = "springer_html"
    assert envelope.article is not None
    envelope.article.doi = envelope.doi
    envelope.article.source = envelope.source
    envelope.acquisition = AcquisitionProvenance(
        provider="springer",
        route="direct_html",
        representation="html",
        transport="http",
    )
    envelope.article.acquisition = envelope.acquisition
    envelope.quality.asset_summary = asset_summary
    envelope.markdown = envelope.article.to_ai_markdown(
        asset_profile="body",
        include_refs="all",
        max_tokens="full_text",
    )

    output_path = tmp_path / "nature16457.md"
    manifest_path = tmp_path / "nature16457.manifest.json"
    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=envelope),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        exit_code = cli.main(
            [
                "fetch",
                "--query",
                envelope.doi,
                "--output",
                str(output_path),
                "--output-dir",
                str(tmp_path),
                "--artifact-mode",
                "markdown-assets",
                "--asset-profile",
                "body",
                "--manifest",
                str(manifest_path),
            ]
        )

    assert exit_code == 0
    record = parse_manifest_record(json.loads(manifest_path.read_text("utf-8")))
    assert len(merged_assets) == 4
    assert record.acceptance.overall == OverallAcceptanceStatus.COMPLETE
    assert record.asset_summary.status == AssetAcceptanceStatus.COMPLETE
    assert record.asset_summary.total == 4
    assert record.asset_summary.local == 4
    assert record.asset_summary.full_size == 4
    assert record.asset_summary.failed == 0
    assert record.asset_summary.remote_only_count == 0
    assert record.asset_summary.issue_codes == ()
    assert audit_manifest_path(manifest_path).status == ManifestAuditStatus.OK


def test_cli_adapter_publishes_semantic_losses(tmp_path: Path) -> None:
    envelope = _envelope(
        losses=SemanticLosses(
            table_fallback_count=2,
            table_layout_degraded_count=1,
            table_semantic_loss_count=1,
            formula_missing_count=3,
        )
    )
    record = _build_record(
        tmp_path,
        result=cli.SingleFetchResult(envelope),
    )

    assert record.semantic_losses.table_fallback_count == 2
    assert record.semantic_losses.table_layout_degraded_count == 1
    assert record.semantic_losses.table_semantic_loss_count == 1
    assert record.semantic_losses.formula_missing_count == 3


def test_batch_rate_limit_streams_one_terminal_record_per_input_and_aborts_lane(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.jsonl"
    args = _args(batch_results=str(results_path))
    calls: list[str] = []

    def run_single(_args, *, query: str, **_kwargs):
        calls.append(query)
        raise ProviderFailure(
            RATE_LIMITED,
            "Slow down.",
            retry_after_seconds=7,
        )

    record_ids = (
        UUID("20000000-0000-4000-8000-000000000001"),
        UUID("20000000-0000-4000-8000-000000000002"),
        UUID("20000000-0000-4000-8000-000000000003"),
    )
    with (
        mock.patch.object(cli, "run_single_fetch", side_effect=run_single),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        exit_code = cli.run_batch_fetch(
            args,
            queries=["10.1016/first", "10.1016/second", "10.1016/third"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_fixed_deps(record_ids=record_ids),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    records = [
        parse_manifest_record(json.loads(line))
        for line in results_path.read_text("utf-8").splitlines()
    ]
    assert exit_code == 4
    assert calls == ["10.1016/first"]
    assert len(records) == 3
    assert {record.index for record in records} == {1, 2, 3}
    assert len({record.record_id for record in records}) == 3
    assert {record.run_id for record in records} == {RUN_ID}
    assert [record.status for record in records] == [
        RATE_LIMITED,
        "aborted",
        "aborted",
    ]
    assert [record.record_status for record in records] == [
        ManifestRecordStatus.FAILED,
        ManifestRecordStatus.ABORTED,
        ManifestRecordStatus.ABORTED,
    ]
    assert all(record.output_path is None for record in records)
    assert all(record.saved_markdown_path is None for record in records)


def test_batch_rate_limit_keeps_an_unrelated_provider_lane_running(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.jsonl"
    args = _args(batch_results=str(results_path))
    calls: list[str] = []

    def run_single(_args, *, query: str, **_kwargs):
        calls.append(query)
        if query == "10.1016/limited":
            raise ProviderFailure(RATE_LIMITED, "Slow down.")
        envelope = _envelope()
        envelope.doi = query
        if envelope.article is not None:
            envelope.article.doi = query
        return cli.SingleFetchResult(envelope)

    with (
        mock.patch.object(cli, "run_single_fetch", side_effect=run_single),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        exit_code = cli.run_batch_fetch(
            args,
            queries=[
                "10.1016/limited",
                "10.1111/continues",
                "10.1016/aborted",
            ],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_fixed_deps(
                record_ids=(
                    UUID("30000000-0000-4000-8000-000000000001"),
                    UUID("30000000-0000-4000-8000-000000000002"),
                    UUID("30000000-0000-4000-8000-000000000003"),
                )
            ),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    records = [
        parse_manifest_record(json.loads(line))
        for line in results_path.read_text("utf-8").splitlines()
    ]
    assert exit_code == 4
    assert calls == ["10.1016/limited", "10.1111/continues"]
    assert [record.status for record in records] == [
        RATE_LIMITED,
        "ok",
        "aborted",
    ]


def test_batch_generic_exception_is_failed_and_does_not_drop_later_input(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.jsonl"
    args = _args(batch_results=str(results_path))

    def run_single(_args, *, query: str, **_kwargs):
        if query == "broken title":
            raise RuntimeError("worker exploded")
        return cli.SingleFetchResult(_envelope())

    with (
        mock.patch.object(cli, "run_single_fetch", side_effect=run_single),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        exit_code = cli.run_batch_fetch(
            args,
            queries=["broken title", "10.1000/acceptance"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_fixed_deps(
                record_ids=(
                    UUID("40000000-0000-4000-8000-000000000001"),
                    UUID("40000000-0000-4000-8000-000000000002"),
                )
            ),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    records = [
        parse_manifest_record(json.loads(line))
        for line in results_path.read_text("utf-8").splitlines()
    ]
    assert exit_code == 1
    assert [record.status for record in records] == ["error", "ok"]
    assert records[0].record_status == ManifestRecordStatus.FAILED
    assert records[0].error is not None
    assert records[0].error.reason == "worker exploded"


def test_batch_resolution_and_queue_time_do_not_consume_fetch_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results_path = tmp_path / "results.jsonl"
    args = _args(batch_results=str(results_path))
    clock = [300.0]
    observed: list[dict[str, object]] = []

    def resolve(query: str, *, context):
        context.request_started_at = 100.0
        return SimpleNamespace(
            query=query,
            provider_hint="test-provider",
            landing_url=None,
            doi="10.1000/resolved",
        )

    def run_single(_args, *, query, context, **_kwargs):
        observed.append(
            {
                "query": query,
                "request_started_at": context.request_started_at,
                "deadline": context.initialize_deadline(120.0),
                "remaining": context.remaining_seconds(),
                "session_cache": dict(context.session_cache),
            }
        )
        clock[0] += 200.0
        return cli.SingleFetchResult(_envelope())

    monkeypatch.setattr(runtime_module.time, "monotonic", lambda: clock[0])
    with (
        mock.patch.object(cli, "resolve_paper", side_effect=resolve),
        mock.patch.object(cli, "run_single_fetch", side_effect=run_single),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        exit_code = cli.run_batch_fetch(
            args,
            queries=["First generic paper title", "Second generic paper title"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_fixed_deps(
                record_ids=(
                    RECORD_ID,
                    UUID("20000000-0000-4000-8000-000000000003"),
                )
            ),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    assert exit_code == 0
    assert [item["request_started_at"] for item in observed] == [300.0, 500.0]
    assert [item["deadline"] for item in observed] == [420.0, 620.0]
    assert [item["remaining"] for item in observed] == [120.0, 120.0]
    assert all(item["session_cache"] for item in observed)


def test_metadata_only_batch_status_ok_remains_zero_exit(tmp_path: Path) -> None:
    results_path = tmp_path / "results.jsonl"
    args = _args(batch_results=str(results_path))
    outcome = cli.SingleFetchResult(_envelope("metadata_only"))

    with (
        mock.patch.object(cli, "run_single_fetch", return_value=outcome),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        exit_code = cli.run_batch_fetch(
            args,
            queries=["10.1000/acceptance"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_fixed_deps(),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    record = parse_manifest_record(json.loads(results_path.read_text("utf-8").strip()))
    assert exit_code == 0
    assert record.status == "ok"
    assert record.acceptance.overall == OverallAcceptanceStatus.LIMITED
    assert record.acceptance.content.has_fulltext is False


def test_batch_rejects_single_manifest_option(tmp_path: Path) -> None:
    query_file = tmp_path / "queries.txt"
    query_file.write_text("10.1000/acceptance\n", encoding="utf-8")
    stderr = io.StringIO()

    with redirect_stderr(stderr), pytest.raises(SystemExit) as raised:
        cli.main(
            [
                "--query-file",
                str(query_file),
                "--manifest",
                str(tmp_path / "single.json"),
            ]
        )

    assert raised.value.code == 2
    assert "single-paper only" in stderr.getvalue()
