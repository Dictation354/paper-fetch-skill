from __future__ import annotations

from dataclasses import replace
from datetime import datetime, UTC
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from paper_fetch.browser_preflight import BrowserPreflightResult
from paper_fetch.provider_catalog import provider_batch_concurrency
from paper_fetch_devtools.golden_criteria import benchmark_cli
from paper_fetch_devtools.golden_criteria.benchmark import (
    BenchmarkTrial,
    SAME_PROVIDER_PROBE_SAMPLES,
    _build_same_provider_probe,
    expectations_from_catalog,
    no_cache_transport,
    run_parallel_live_benchmark,
    select_benchmark_samples,
)
from paper_fetch_devtools.golden_criteria.live import (
    GoldenCriteriaLiveResult,
    build_report,
    run_golden_criteria_live_review,
)
from tests.unit._paper_fetch_support import build_envelope, sample_article


def _manifest(path: Path) -> Path:
    payload = {
        "samples": {
            "elsevier_sample": {
                "doi": "10.1016/example",
                "publisher": "elsevier",
                "title": "Direct sample",
                "source_url": "https://example.test/elsevier",
                "landing_url": "https://example.test/elsevier",
                "fixture_family": "golden",
            },
            "wiley_sample": {
                "doi": "10.1111/example",
                "publisher": "wiley",
                "title": "Browser sample",
                "source_url": "https://example.test/wiley",
                "landing_url": "https://example.test/wiley",
                "fixture_family": "golden",
            },
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _catalog():
    return {
        "elsevier": SimpleNamespace(
            doi="10.1016/example",
            accepted_sources=("elsevier_xml",),
            accepted_live_source_trail_groups=(("fulltext:elsevier_article_ok",),),
        ),
        "wiley": SimpleNamespace(
            doi="10.1111/example",
            accepted_sources=("wiley_browser",),
            accepted_live_source_trail_groups=(("fulltext:wiley_html_ok",),),
        ),
    }


def _wiley_probe_catalog():
    return {
        "wiley": SimpleNamespace(
            doi="10.1111/gcb.16414",
            accepted_sources=("wiley_browser",),
            accepted_live_source_trail_groups=(
                ("fulltext:wiley_html_ok",),
                (
                    "fulltext:wiley_pdf_browser_ok",
                    "fulltext:wiley_pdf_fallback_ok",
                ),
            ),
        )
    }


def _wiley_probe_manifest(path: Path) -> Path:
    samples = {}
    for doi in SAME_PROVIDER_PROBE_SAMPLES["wiley"]:
        sample_id = doi.replace("/", "_")
        samples[sample_id] = {
            "doi": doi,
            "publisher": "wiley",
            "title": doi,
            "source_url": f"https://example.test/{sample_id}",
            "landing_url": f"https://example.test/{sample_id}",
            "fixture_family": "golden",
        }
    path.write_text(json.dumps({"samples": samples}), encoding="utf-8")
    return path


def _provider_status(**_kwargs):
    return {
        "providers": [
            {
                "provider": provider,
                "status": "ready",
                "available": True,
                "notes": [],
                "checks": [],
            }
            for provider in ("elsevier", "wiley")
        ]
    }


def _result(
    *,
    sample_id: str,
    provider: str,
    doi: str,
    source: str | None,
    source_trail: list[str],
    acceptance: str = "complete",
    status: str = "fulltext",
) -> GoldenCriteriaLiveResult:
    return GoldenCriteriaLiveResult(
        sample_id=sample_id,
        provider=provider,
        doi=doi,
        title=sample_id,
        status=status,
        content_kind="fulltext" if status == "fulltext" else None,
        source=source,
        has_fulltext=status == "fulltext",
        warnings=[],
        source_trail=source_trail,
        asset_count=0,
        sample_output_dir=f"/tmp/{sample_id}",
        review_status="ok" if status == "fulltext" else "blocked",
        issue_categories=[],
        elapsed_seconds=1.0,
        stage_timings={"total_seconds": 1.0},
        acceptance={"overall": acceptance},
    )


def _fake_golden_report(output_dir: Path, concurrency: int, *, fail: bool = False):
    results = [
        _result(
            sample_id="elsevier_sample",
            provider="elsevier",
            doi="10.1016/example",
            source="elsevier_xml",
            source_trail=["fulltext:elsevier_article_ok"],
        ),
        _result(
            sample_id="wiley_sample",
            provider="wiley",
            doi="10.1111/example",
            source=None if fail else "wiley_browser",
            source_trail=[] if fail else ["fulltext:wiley_html_ok"],
            acceptance="failed" if fail else "complete",
            status="error" if fail else "fulltext",
        ),
    ]
    if fail:
        results[1] = replace(
            results[1],
            error_code="browser_timeout",
            error_message="Browser timed out.",
            failure_diagnostics={
                "provider": "wiley",
                "route": "browser_html",
                "stage": "dom_readiness",
                "http_status": 504,
                "error_category": "timeout",
                "retryable": True,
            },
        )
    return build_report(
        generated_at="2026-08-05T00:00:00+00:00",
        output_dir=output_dir,
        provider_status=_provider_status(),
        results=results,
        concurrency=concurrency,
        completion_order=["wiley_sample", "elsevier_sample"],
    )


def test_select_benchmark_samples_reuses_catalog_dois(tmp_path: Path) -> None:
    manifest = json.loads(_manifest(tmp_path / "manifest.json").read_text())
    expectations = expectations_from_catalog(_catalog())

    selected = select_benchmark_samples(
        manifest,
        expectations,
        providers=["wiley", "elsevier"],
    )

    assert [sample.sample_id for sample in selected] == [
        "wiley_sample",
        "elsevier_sample",
    ]


def test_no_cache_transport_disables_memory_metadata_and_disk_cache() -> None:
    transport = no_cache_transport()
    try:
        assert transport.cache_ttl == 0
        assert transport.metadata_cache_ttl == 0
        assert transport.cache_capacity == 0
        assert transport.disk_cache_dir is None
    finally:
        transport.close()


def test_parallel_benchmark_reports_speedup_and_no_drift(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    calls: list[int] = []
    clock_values = iter((0.0, 10.0, 10.0, 16.0, 16.0, 21.0))

    def fake_preflight(provider, **_kwargs):
        return BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="ready",
            reason_code="ok",
            stage="dom_readiness",
        )

    def fake_runner(**kwargs):
        calls.append(kwargs["concurrency"])
        return _fake_golden_report(kwargs["output_dir"], kwargs["concurrency"])

    report = run_parallel_live_benchmark(
        benchmark_catalog=_catalog(),
        manifest_path=manifest_path,
        output_dir=tmp_path / "benchmark",
        providers=["elsevier", "wiley"],
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        provider_status_fn=_provider_status,
        preflight_fn=fake_preflight,
        golden_runner_fn=fake_runner,
        clock=lambda: next(clock_values),
        now=datetime(2026, 8, 5, tzinfo=UTC),
    )

    assert calls == [1, 2, 4]
    assert [item.speedup_vs_baseline for item in report.summary_by_concurrency] == [
        1.0,
        1.667,
        2.0,
    ]
    assert report.comparisons == []
    assert report.failures == []
    assert report.success
    assert (tmp_path / "benchmark" / "benchmark.json").is_file()
    assert (tmp_path / "benchmark" / "benchmark.md").is_file()


def test_parallel_benchmark_continues_and_pinpoints_failure(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    calls: list[int] = []
    clock_values = iter((0.0, 8.0, 8.0, 13.0, 13.0, 17.0))

    def fake_preflight(provider, **_kwargs):
        return BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="ready",
            reason_code="ok",
        )

    def fake_runner(**kwargs):
        concurrency = kwargs["concurrency"]
        calls.append(concurrency)
        return _fake_golden_report(
            kwargs["output_dir"], concurrency, fail=concurrency == 2
        )

    report = run_parallel_live_benchmark(
        benchmark_catalog=_catalog(),
        manifest_path=manifest_path,
        output_dir=tmp_path / "benchmark",
        providers=["elsevier", "wiley"],
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        provider_status_fn=_provider_status,
        preflight_fn=fake_preflight,
        golden_runner_fn=fake_runner,
        clock=lambda: next(clock_values),
    )

    assert calls == [1, 2, 4]
    assert not report.success
    assert report.comparisons[0]["sample_id"] == "wiley_sample"
    failure = next(item for item in report.failures if item.get("sample_id"))
    assert failure["provider"] == "wiley"
    assert failure["route"] == "browser_html"
    assert failure["stage"] == "dom_readiness"
    assert failure["http_status"] == 504
    assert failure["retryable"] is True


def test_preflight_failure_blocks_only_its_provider_and_matrix_continues(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    calls: list[int] = []
    clock_values = iter((0.0, 8.0, 8.0, 13.0, 13.0, 17.0))

    def fake_preflight(provider, **_kwargs):
        return BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="challenge",
            reason_code="waf_challenge",
            stage="dom_readiness",
            message="Publisher challenge detected.",
        )

    def fake_runner(**kwargs):
        calls.append(kwargs["concurrency"])
        status = kwargs["provider_status_fn"]()
        by_provider = {item["provider"]: item for item in status.get("providers") or []}
        assert by_provider["elsevier"]["available"] is True
        assert by_provider["wiley"]["available"] is False
        return _fake_golden_report(kwargs["output_dir"], kwargs["concurrency"])

    report = run_parallel_live_benchmark(
        benchmark_catalog=_catalog(),
        manifest_path=manifest_path,
        output_dir=tmp_path / "benchmark",
        providers=["elsevier", "wiley"],
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        provider_status_fn=_provider_status,
        preflight_fn=fake_preflight,
        golden_runner_fn=fake_runner,
        clock=lambda: next(clock_values),
    )

    assert calls == [1, 2, 4]
    assert not report.success
    failure = next(item for item in report.failures if "sample_id" not in item)
    assert failure["provider"] == "wiley"
    assert failure["route"] == "browser_preflight"
    assert failure["stage"] == "dom_readiness"
    assert failure["code"] == "waf_challenge"


def test_trial_runner_failure_does_not_stop_later_concurrency_levels(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    calls: list[int] = []
    clock_values = iter((0.0, 8.0, 8.0, 13.0, 13.0, 17.0))

    def fake_preflight(provider, **_kwargs):
        return BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="ready",
            reason_code="ok",
        )

    def fake_runner(**kwargs):
        concurrency = kwargs["concurrency"]
        calls.append(concurrency)
        if concurrency == 2:
            raise RuntimeError("trial output failed")
        return _fake_golden_report(kwargs["output_dir"], concurrency)

    report = run_parallel_live_benchmark(
        benchmark_catalog=_catalog(),
        manifest_path=manifest_path,
        output_dir=tmp_path / "benchmark",
        providers=["elsevier", "wiley"],
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        provider_status_fn=_provider_status,
        preflight_fn=fake_preflight,
        golden_runner_fn=fake_runner,
        clock=lambda: next(clock_values),
    )

    assert calls == [1, 2, 4]
    failed_trial = next(trial for trial in report.trials if trial.concurrency == 2)
    assert failed_trial.attempted_count == 0
    assert failed_trial.error["code"] == "RuntimeError"
    assert any(failure.get("stage") == "trial_runner" for failure in report.failures)


def test_golden_live_concurrency_overlaps_providers_but_caps_browser_lane(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["samples"]["wiley_second"] = {
        "doi": "10.1111/example-two",
        "publisher": "wiley",
        "title": "Second browser sample",
        "source_url": "https://example.test/wiley-two",
        "landing_url": "https://example.test/wiley-two",
        "fixture_family": "golden",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    barrier = threading.Barrier(2)
    state_lock = threading.Lock()
    wiley_active = 0
    max_wiley_active = 0

    def fake_fetch(query, **_kwargs):
        nonlocal wiley_active, max_wiley_active
        is_wiley = query.startswith("10.1111/")
        if is_wiley:
            with state_lock:
                wiley_active += 1
                max_wiley_active = max(max_wiley_active, wiley_active)
        try:
            if query in {"10.1016/example", "10.1111/example"}:
                barrier.wait(timeout=2)
            article = sample_article()
            article.doi = query
            article.source = "wiley_browser" if is_wiley else "elsevier_xml"
            return build_envelope(article)
        finally:
            if is_wiley:
                with state_lock:
                    wiley_active -= 1

    report = run_golden_criteria_live_review(
        manifest_path=manifest_path,
        output_dir=tmp_path / "live",
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        fetch_paper_fn=fake_fetch,
        provider_status_fn=_provider_status,
        concurrency=2,
    )

    assert all(result.status == "fulltext" for result in report.results)
    assert max_wiley_active == 1
    assert set(report.completion_order) == {
        "elsevier_sample",
        "wiley_sample",
        "wiley_second",
    }


def test_default_wiley_lane_remains_one() -> None:
    assert provider_batch_concurrency("wiley") == 1


def test_golden_live_wiley_override_reaches_peak_two_and_records_worker_times(
    tmp_path: Path,
) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["samples"].pop("elsevier_sample")
    manifest["samples"]["wiley_second"] = {
        "doi": "10.1111/example-two",
        "publisher": "wiley",
        "title": "Second browser sample",
        "source_url": "https://example.test/wiley-two",
        "landing_url": "https://example.test/wiley-two",
        "fixture_family": "golden",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    barrier = threading.Barrier(2)

    def fake_fetch(query, **_kwargs):
        barrier.wait(timeout=2)
        article = sample_article()
        article.doi = query
        article.source = "wiley_browser"
        return build_envelope(article)

    report = run_golden_criteria_live_review(
        manifest_path=manifest_path,
        output_dir=tmp_path / "live",
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        fetch_paper_fn=fake_fetch,
        provider_status_fn=_provider_status,
        concurrency=2,
        lane_limit_overrides={"wiley": 2},
    )

    assert report.lane_limits == {"wiley": 2}
    assert report.provider_peak_in_flight == {"wiley": 2}
    assert all(result.worker_started_at is not None for result in report.results)
    assert all(
        result.worker_finished_at is not None
        and result.worker_finished_at >= result.worker_started_at
        for result in report.results
        if result.worker_started_at is not None
    )


def test_golden_live_concurrency_one_stays_a_serial_control(tmp_path: Path) -> None:
    manifest_path = _wiley_probe_manifest(tmp_path / "manifest.json")

    def fake_fetch(query, **_kwargs):
        article = sample_article()
        article.doi = query
        article.source = "wiley_browser"
        return build_envelope(article)

    report = run_golden_criteria_live_review(
        manifest_path=manifest_path,
        output_dir=tmp_path / "live",
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        fetch_paper_fn=fake_fetch,
        provider_status_fn=_provider_status,
        concurrency=1,
        lane_limit_overrides={"wiley": 2},
    )

    assert report.lane_limits == {"wiley": 1}
    assert report.provider_peak_in_flight == {"wiley": 1}


def test_wiley_probe_reports_capability_and_inherits_provider_route_expectation(
    tmp_path: Path,
) -> None:
    manifest_path = _wiley_probe_manifest(tmp_path / "manifest.json")
    calls: list[dict[str, object]] = []
    clock_values = iter((0.0, 3.0, 3.0, 6.0, 6.0, 8.0, 8.0, 10.0))

    def fake_preflight(provider, **_kwargs):
        return BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="ready",
            reason_code="ok",
        )

    def fake_runner(**kwargs):
        calls.append(kwargs)
        concurrency = kwargs["concurrency"]
        results = [
            replace(
                _result(
                    sample_id=doi.replace("/", "_"),
                    provider="wiley",
                    doi=doi,
                    source="wiley_browser",
                    source_trail=["fulltext:wiley_html_ok"],
                ),
                worker_started_at=float(index),
                worker_finished_at=float(index + 1),
            )
            for index, doi in enumerate(SAME_PROVIDER_PROBE_SAMPLES["wiley"])
        ]
        return build_report(
            generated_at="2026-08-05T00:00:00+00:00",
            output_dir=kwargs["output_dir"],
            provider_status=_provider_status(),
            results=results,
            concurrency=concurrency,
            lane_limits={"wiley": min(concurrency, 2)},
            provider_peak_in_flight={"wiley": min(concurrency, 2)},
        )

    report = run_parallel_live_benchmark(
        benchmark_catalog=_wiley_probe_catalog(),
        manifest_path=manifest_path,
        output_dir=tmp_path / "benchmark",
        same_provider_probe="wiley",
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        provider_status_fn=_provider_status,
        preflight_fn=fake_preflight,
        golden_runner_fn=fake_runner,
        clock=lambda: next(clock_values),
    )

    assert [(call["concurrency"]) for call in calls] == [1, 1, 2, 2]
    assert all(call["lane_limit_overrides"] == {"wiley": 2} for call in calls)
    assert all(
        result["route_accepted"] for trial in report.trials for result in trial.results
    )
    probe = report.same_provider_probe
    assert probe is not None
    assert probe["catalog_lane_limit"] == 1
    assert probe["requested_lane_limit"] == 2
    assert [item["peak_in_flight"] for item in probe["rounds"]] == [1, 1, 2, 2]
    assert probe["overlap_observed"] is True
    assert probe["speedup_is_success_criterion"] is False
    assert probe["verdict"] == "capable"
    assert report.success


def test_wiley_probe_preflight_failure_is_a_structured_blocker(
    tmp_path: Path,
) -> None:
    manifest_path = _wiley_probe_manifest(tmp_path / "manifest.json")
    clock_values = iter((0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0))

    def fake_preflight(provider, **_kwargs):
        return BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="challenge",
            reason_code="waf_challenge",
            stage="dom_readiness",
            message="Publisher challenge detected.",
        )

    def fake_runner(**kwargs):
        concurrency = kwargs["concurrency"]
        return build_report(
            generated_at="2026-08-05T00:00:00+00:00",
            output_dir=kwargs["output_dir"],
            provider_status=kwargs["provider_status_fn"](),
            results=[],
            concurrency=concurrency,
            lane_limits={"wiley": min(concurrency, 2)},
            provider_peak_in_flight={},
        )

    report = run_parallel_live_benchmark(
        benchmark_catalog=_wiley_probe_catalog(),
        manifest_path=manifest_path,
        output_dir=tmp_path / "benchmark",
        same_provider_probe="wiley",
        env={"PAPER_FETCH_RUN_LIVE": "1"},
        provider_status_fn=_provider_status,
        preflight_fn=fake_preflight,
        golden_runner_fn=fake_runner,
        clock=lambda: next(clock_values),
    )

    probe = report.same_provider_probe
    assert probe is not None
    assert probe["verdict"] == "blocked"
    assert probe["parallel_capable"] is None
    assert probe["blockers"][0]["code"] == "waf_challenge"
    assert probe["result_failures"] == []
    assert not report.success


def test_probe_does_not_report_quality_degradation_as_environment_blocker(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        _wiley_probe_manifest(tmp_path / "manifest.json").read_text(encoding="utf-8")
    )
    samples = select_benchmark_samples(
        manifest,
        expectations_from_catalog(_wiley_probe_catalog()),
        sample_ids=SAME_PROVIDER_PROBE_SAMPLES["wiley"],
    )
    result_payloads = [
        {
            "sample_id": sample.sample_id,
            "acceptance": "degraded" if index == 2 else "complete",
            "route_accepted": True,
            "worker_started_at": float(index),
            "worker_finished_at": float(index + 1),
        }
        for index, sample in enumerate(samples)
    ]
    trials = [
        BenchmarkTrial(
            concurrency=concurrency,
            repetition=repetition,
            wall_seconds=1.0,
            attempted_count=3,
            papers_per_second=3.0,
            status_counts={"fulltext": 3},
            acceptance_counts={"complete": 2, "degraded": 1},
            completion_order=[sample.sample_id for sample in samples],
            lane_limits={"wiley": concurrency},
            provider_peak_in_flight={"wiley": concurrency},
            report_json="report.json",
            report_markdown="report.md",
            results=result_payloads,
            error={},
        )
        for concurrency in (1, 2)
        for repetition in (1, 2)
    ]
    quality_failure = {
        "sample_id": samples[2].sample_id,
        "provider": "wiley",
        "route": "wiley_browser",
        "stage": None,
        "acceptance": "degraded",
        "route_accepted": True,
        "code": None,
        "http_status": None,
        "error_category": None,
        "retryable": None,
    }

    probe = _build_same_provider_probe(
        provider="wiley",
        samples=samples,
        trials=trials,
        comparisons=[],
        failures=[quality_failure],
    )

    assert probe["verdict"] == "results_incomplete"
    assert probe["parallel_capable"] is False
    assert probe["blockers"] == []
    assert probe["result_failures"] == [quality_failure]


def test_repetitions_and_concurrencies_are_validated(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path / "manifest.json")
    common = {
        "benchmark_catalog": _catalog(),
        "manifest_path": manifest_path,
        "output_dir": tmp_path / "benchmark",
        "providers": ["elsevier"],
        "env": {"PAPER_FETCH_RUN_LIVE": "1"},
    }
    with pytest.raises(ValueError, match="concurrencies"):
        run_parallel_live_benchmark(**common, concurrencies=[1, 1])
    with pytest.raises(ValueError, match="repetitions"):
        run_parallel_live_benchmark(**common, repetitions=0)
    with pytest.raises(ValueError, match="same_provider_probe cannot be combined"):
        run_parallel_live_benchmark(
            benchmark_catalog=_wiley_probe_catalog(),
            same_provider_probe="wiley",
            concurrencies=[1, 2],
        )
    with pytest.raises(ValueError, match="must not exceed 2"):
        run_golden_criteria_live_review(
            concurrency=3,
            lane_limit_overrides={"wiley": 3},
        )
    with pytest.raises(ValueError, match="providers"):
        run_parallel_live_benchmark(
            **{**common, "providers": ["elsevier", "elsevier"]},
        )

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="not empty"):
        run_parallel_live_benchmark(
            **{**common, "output_dir": occupied},
        )


@pytest.mark.parametrize(("success", "expected_exit"), [(True, 0), (False, 1)])
def test_benchmark_cli_exit_code_reflects_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    success: bool,
    expected_exit: int,
) -> None:
    output_dir = tmp_path / "benchmark"
    captured: dict[str, object] = {}
    report = SimpleNamespace(
        output_dir=str(output_dir),
        summary_by_concurrency=[],
        failures=[] if success else [{}],
        comparisons=[],
        success=success,
    )

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return report

    monkeypatch.setattr(benchmark_cli, "run_parallel_live_benchmark", fake_runner)

    exit_code = benchmark_cli.main(
        [
            "--output-dir",
            str(output_dir),
            "--concurrencies",
            "1",
            "4",
            "--providers",
            "elsevier",
        ],
        benchmark_catalog=_catalog(),
    )

    assert exit_code == expected_exit
    assert captured["concurrencies"] == [1, 4]
    assert captured["providers"] == ["elsevier"]


def test_benchmark_cli_same_provider_probe_uses_fixed_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "benchmark"
    captured: dict[str, object] = {}
    report = SimpleNamespace(
        output_dir=str(output_dir),
        summary_by_concurrency=[],
        failures=[],
        comparisons=[],
        same_provider_probe={
            "provider": "wiley",
            "verdict": "capable",
            "overlap_observed": True,
        },
        success=True,
    )

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return report

    monkeypatch.setattr(benchmark_cli, "run_parallel_live_benchmark", fake_runner)

    exit_code = benchmark_cli.main(
        [
            "--output-dir",
            str(output_dir),
            "--same-provider-probe",
            "wiley",
        ],
        benchmark_catalog=_wiley_probe_catalog(),
    )

    assert exit_code == 0
    assert captured["same_provider_probe"] == "wiley"
    assert captured["concurrencies"] is None
    assert captured["repetitions"] is None
    assert captured["providers"] is None
    assert captured["sample_ids"] is None


def test_benchmark_cli_rejects_probe_matrix_conflicts(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="2"):
        benchmark_cli.main(
            [
                "--output-dir",
                str(tmp_path / "benchmark"),
                "--same-provider-probe",
                "wiley",
                "--concurrencies",
                "1",
                "2",
            ],
            benchmark_catalog=_wiley_probe_catalog(),
        )
