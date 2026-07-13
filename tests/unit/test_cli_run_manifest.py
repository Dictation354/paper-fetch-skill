from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
import io
import json
from pathlib import Path
from unittest import mock
from uuid import UUID

import pytest

from paper_fetch import cli
from paper_fetch.http import RequestCancelledError
from paper_fetch.manifest import ManifestBuilderDependencies
from paper_fetch.manifest_writer import (
    ManifestAuditStatus,
    RunManifestState,
    RunManifestStore,
    audit_manifest_path,
    read_manifest_events,
    read_run_manifest,
)

from .test_workflow_acceptance import _envelope


RUN_ID = UUID("50000000-0000-4000-8000-000000000001")
STARTED_AT = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "batch_results": str(tmp_path / "events.jsonl"),
        "run_manifest": str(tmp_path / "run-manifest.json"),
        "resume": None,
        "overwrite": False,
        "batch_concurrency": 1,
        "format": "markdown",
        "asset_profile": "none",
        "include_refs": "all",
        "max_tokens": "full_text",
        "no_download": True,
        "save_markdown_to_disk": False,
        "save_output_copy": False,
        "primary_output_to_output_dir": True,
        "output": "-",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _deps() -> ManifestBuilderDependencies:
    tick = -1

    def clock() -> datetime:
        nonlocal tick
        tick += 1
        return STARTED_AT + timedelta(seconds=tick)

    return ManifestBuilderDependencies(clock=clock)


def _markdown(*, doi: str, source: str, marker: str = "initial") -> str:
    return f"""---
doi: {doi}
source: {source}
has_fulltext: true
content_kind: fulltext
completed_at: 2026-07-13T10:00:00+00:00
---
# {marker}

Accepted body text.
"""


def _fetcher(tmp_path: Path, calls: list[str], *, marker: str = "initial"):
    def run_single(_args, *, query: str, **_kwargs):
        calls.append(query)
        envelope = _envelope()
        envelope.doi = query
        if envelope.article is not None:
            envelope.article.doi = query
        output_path = tmp_path / f"paper-{query.rsplit('/', 1)[-1]}.md"
        output_path.write_text(
            _markdown(
                doi=query,
                source=envelope.source or "elsevier_xml",
                marker=marker,
            ),
            encoding="utf-8",
        )
        return cli.SingleFetchResult(envelope=envelope, output_path=output_path)

    return run_single


def _run(
    args: argparse.Namespace,
    tmp_path: Path,
    queries: list[str],
    *,
    calls: list[str],
    marker: str = "initial",
) -> int:
    with (
        mock.patch.object(
            cli,
            "run_single_fetch",
            side_effect=_fetcher(tmp_path, calls, marker=marker),
        ),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        return cli.run_batch_fetch(
            args,
            queries=queries,
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_deps(),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )


def test_new_batch_writes_atomic_run_summary_and_auditable_events(
    tmp_path: Path,
) -> None:
    args = _args(tmp_path)
    queries = ["10.1000/one", "10.1000/two"]
    calls: list[str] = []

    exit_code = _run(args, tmp_path, queries, calls=calls)

    manifest_path = Path(args.run_manifest)
    events_path = Path(args.batch_results)
    manifest = read_run_manifest(manifest_path)
    records = read_manifest_events(events_path)
    report = audit_manifest_path(manifest_path)
    assert exit_code == 0
    assert calls == queries
    assert manifest.state == RunManifestState.COMPLETED
    assert manifest.run_id == RUN_ID
    assert manifest.query_count == 2
    assert manifest.attempt_count == 2
    assert [item.query for item in manifest.inputs] == queries
    assert {record.index for record in records} == {1, 2}
    assert {record.attempt for record in records} == {1}
    assert len({record.record_id for record in records}) == 2
    assert report.status == ManifestAuditStatus.OK
    assert report.reusable_indices == (1, 2)
    assert not manifest_path.with_suffix(".json.part").exists()


def test_resume_skips_verified_output_and_appends_new_attempt_for_stale_output(
    tmp_path: Path,
) -> None:
    queries = ["10.1000/one", "10.1000/two"]
    initial_args = _args(tmp_path)
    _run(initial_args, tmp_path, queries, calls=[])
    stale_path = tmp_path / "paper-two.md"
    stale_path.write_text("user changed this file\n", encoding="utf-8")
    resume_args = _args(
        tmp_path,
        run_manifest=None,
        resume=str(tmp_path / "run-manifest.json"),
        overwrite=True,
    )
    calls: list[str] = []

    exit_code = _run(
        resume_args,
        tmp_path,
        queries,
        calls=calls,
        marker="retried",
    )

    records = read_manifest_events(tmp_path / "events.jsonl")
    report = audit_manifest_path(tmp_path / "run-manifest.json")
    assert exit_code == 0
    assert calls == ["10.1000/two"]
    assert [(record.index, record.attempt) for record in records] == [
        (1, 1),
        (2, 1),
        (2, 2),
    ]
    assert report.status == ManifestAuditStatus.OK
    assert report.reusable_indices == (1, 2)
    assert "# retried" in stale_path.read_text(encoding="utf-8")


def test_resume_requires_overwrite_before_replacing_changed_existing_output(
    tmp_path: Path,
) -> None:
    queries = ["10.1000/one"]
    _run(_args(tmp_path), tmp_path, queries, calls=[])
    output_path = tmp_path / "paper-one.md"
    output_path.write_text("user changed this file\n", encoding="utf-8")
    resume_args = _args(
        tmp_path,
        run_manifest=None,
        resume=str(tmp_path / "run-manifest.json"),
    )
    before = (tmp_path / "run-manifest.json").read_bytes()
    calls: list[str] = []

    with pytest.raises(cli.OutputOverwriteRequired, match="--overwrite"):
        _run(resume_args, tmp_path, queries, calls=calls)

    assert calls == []
    assert output_path.read_text(encoding="utf-8") == "user changed this file\n"
    assert (tmp_path / "run-manifest.json").read_bytes() == before


def test_resume_recreates_missing_output_without_overwrite(tmp_path: Path) -> None:
    queries = ["10.1000/one", "10.1000/two"]
    _run(_args(tmp_path), tmp_path, queries, calls=[])
    (tmp_path / "paper-two.md").unlink()
    resume_args = _args(
        tmp_path,
        run_manifest=None,
        resume=str(tmp_path / "run-manifest.json"),
    )
    calls: list[str] = []

    exit_code = _run(resume_args, tmp_path, queries, calls=calls, marker="restored")

    assert exit_code == 0
    assert calls == ["10.1000/two"]
    assert (tmp_path / "paper-two.md").exists()
    assert audit_manifest_path(tmp_path / "run-manifest.json").status == "ok"


@pytest.mark.parametrize("change", ["inputs", "configuration", "version"])
def test_resume_rejects_identity_changes_without_fetch_or_manifest_mutation(
    tmp_path: Path, change: str
) -> None:
    queries = ["10.1000/one"]
    _run(_args(tmp_path), tmp_path, queries, calls=[])
    args = _args(
        tmp_path,
        run_manifest=None,
        resume=str(tmp_path / "run-manifest.json"),
    )
    resumed_queries = list(queries)
    tool_version = "3.1.0"
    if change == "inputs":
        resumed_queries = ["10.1000/different"]
    elif change == "configuration":
        args.include_refs = "none"
    else:
        tool_version = "3.2.0"
    before = (tmp_path / "run-manifest.json").read_bytes()

    with (
        mock.patch.object(cli, "run_single_fetch") as fetch,
        pytest.raises(cli.ManifestResumeError),
    ):
        cli.run_batch_fetch(
            args,
            queries=resumed_queries,
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_deps(),
            run_id=RUN_ID,
            tool_version=tool_version,
        )

    fetch.assert_not_called()
    assert (tmp_path / "run-manifest.json").read_bytes() == before


def test_keyboard_interrupt_persists_recoverable_run_state(tmp_path: Path) -> None:
    args = _args(tmp_path)
    with (
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
        mock.patch.object(cli, "run_batch", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        cli.run_batch_fetch(
            args,
            queries=["10.1000/one"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_deps(),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    manifest = read_run_manifest(tmp_path / "run-manifest.json")
    report = audit_manifest_path(tmp_path / "run-manifest.json")
    assert manifest.state == RunManifestState.INTERRUPTED
    assert report.status == ManifestAuditStatus.MANIFEST_STALE
    assert report.retry_indices == (1,)


def test_request_cancellation_persists_cancelled_state_and_all_terminals(
    tmp_path: Path,
) -> None:
    args = _args(tmp_path)

    def cancelled(*_args, **_kwargs):
        raise RequestCancelledError("cancelled")

    with (
        mock.patch.object(cli, "run_single_fetch", side_effect=cancelled),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
    ):
        exit_code = cli.run_batch_fetch(
            args,
            queries=["10.1000/one", "10.1000/two"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_deps(),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    manifest = read_run_manifest(tmp_path / "run-manifest.json")
    records = read_manifest_events(tmp_path / "events.jsonl")
    assert exit_code == 1
    assert manifest.state == RunManifestState.CANCELLED
    assert len(records) == 2
    assert all(record.record_status == "aborted" for record in records)


def test_checkpoint_write_failure_keeps_auditable_running_summary(
    tmp_path: Path,
) -> None:
    args = _args(tmp_path)
    calls: list[str] = []
    with (
        mock.patch.object(
            cli,
            "run_single_fetch",
            side_effect=_fetcher(tmp_path, calls),
        ),
        mock.patch.object(
            cli, "build_http_transport_for_context", return_value=object()
        ),
        mock.patch.object(RunManifestStore, "write", side_effect=OSError("disk")),
        pytest.raises(cli.OutputDirectoryError, match="persist complete batch events"),
    ):
        cli.run_batch_fetch(
            args,
            queries=["10.1000/one"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
            manifest_deps=_deps(),
            run_id=RUN_ID,
            tool_version="3.1.0",
        )

    manifest = read_run_manifest(tmp_path / "run-manifest.json")
    assert manifest.state == RunManifestState.RUNNING
    assert len(read_manifest_events(tmp_path / "events.jsonl")) == 1
    assert audit_manifest_path(tmp_path / "run-manifest.json").status == (
        ManifestAuditStatus.MANIFEST_STALE
    )


def test_manifest_cli_is_read_only_and_uses_stable_json_exit_codes(
    tmp_path: Path,
) -> None:
    _run(_args(tmp_path), tmp_path, ["10.1000/one"], calls=[])
    manifest_path = tmp_path / "run-manifest.json"
    events_path = tmp_path / "events.jsonl"
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (manifest_path, events_path)
    }
    stdout = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
        ok_exit = cli.main(["manifest", "audit", str(manifest_path)])

    payload = json.loads(stdout.getvalue())
    assert ok_exit == 0
    assert payload["status"] == "ok"
    assert before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (manifest_path, events_path)
    }

    (tmp_path / "paper-one.md").write_text("changed\n", encoding="utf-8")
    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
        stale_exit = cli.main(["manifest", "reconcile", str(manifest_path)])
    assert stale_exit == 1
    assert json.loads(stdout.getvalue())["status"] == "manifest_stale"

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")
    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
        invalid_exit = cli.main(["manifest", "audit", str(invalid)])
    assert invalid_exit == 2
    assert json.loads(stdout.getvalue())["status"] == "invalid"


def test_single_output_and_manifest_replacement_require_overwrite(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "article.md"
    manifest_path = tmp_path / "single.manifest.json"
    output_path.write_text("keep me\n", encoding="utf-8")
    stderr = io.StringIO()

    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=_envelope()),
        redirect_stdout(io.StringIO()),
        redirect_stderr(stderr),
    ):
        refused = cli.main(
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

    assert refused == 1
    assert output_path.read_text(encoding="utf-8") == "keep me\n"
    assert not manifest_path.exists()
    assert "--overwrite" in json.loads(stderr.getvalue())["reason"]

    with (
        mock.patch.object(cli, "build_runtime_env", return_value={}),
        mock.patch.object(cli, "fetch_paper", return_value=_envelope()),
        redirect_stdout(io.StringIO()),
        redirect_stderr(io.StringIO()),
    ):
        replaced = cli.main(
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
                "--overwrite",
            ]
        )

    assert replaced == 0
    assert output_path.read_text(encoding="utf-8").startswith("# Acceptance Article")
    assert manifest_path.exists()
