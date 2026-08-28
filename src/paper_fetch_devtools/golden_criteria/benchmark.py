"""Parallel live benchmark orchestration over golden-criteria samples."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
import json
from pathlib import Path
import statistics
import time
from typing import Any

from paper_fetch.browser_preflight import (
    BrowserPreflightResult,
    preflight_browser_provider,
)
from paper_fetch.config import build_runtime_env, resolve_repo_root
from paper_fetch.http import HttpTransport
from paper_fetch.provider_catalog import (
    provider_batch_concurrency,
    provider_has_browser_route,
)
from paper_fetch.publisher_identity import normalize_doi
from paper_fetch.utils import normalize_text

from .live import (
    GoldenCriteriaLiveReport,
    GoldenCriteriaLiveResult,
    GoldenCriteriaLiveSample,
    ensure_live_opt_in,
    iter_golden_criteria_samples,
    load_manifest,
    provider_status_payload,
    run_golden_criteria_live_review,
)

DEFAULT_BENCHMARK_PROVIDERS = (
    "elsevier",
    "springer",
    "arxiv",
    "copernicus",
    "wiley",
    "science",
    "pnas",
    "mdpi",
)
DEFAULT_CONCURRENCIES = (1, 2, 4)
DEFAULT_REPETITIONS = 1
BENCHMARK_ROOT_NAME = "parallel-live-benchmark"
SAME_PROVIDER_PROBE_CONCURRENCIES = (1, 2)
SAME_PROVIDER_PROBE_REPETITIONS = 2
SAME_PROVIDER_PROBE_SAMPLES = {
    "wiley": (
        "10.1111/gcb.16414",
        "10.1111/gcb.16998",
        "10.1111/gcb.15322",
    )
}
SAME_PROVIDER_PROBE_LANE_LIMITS = {"wiley": 2}


@dataclass(frozen=True)
class BenchmarkExpectation:
    provider: str
    doi: str
    accepted_sources: tuple[str, ...] = ()
    accepted_trace_groups: tuple[tuple[str, ...], ...] = ()

    def accepts(self, result: GoldenCriteriaLiveResult) -> bool:
        if not self.accepted_sources:
            return True
        if len(self.accepted_sources) == 1:
            outcomes = tuple(
                (self.accepted_sources[0], group)
                for group in self.accepted_trace_groups
            )
        elif len(self.accepted_sources) == len(self.accepted_trace_groups):
            outcomes = tuple(
                zip(self.accepted_sources, self.accepted_trace_groups, strict=True)
            )
        else:
            return False
        return any(
            result.source == source
            and all(marker in result.source_trail for marker in trace_group)
            for source, trace_group in outcomes
        )


@dataclass(frozen=True)
class BenchmarkTrial:
    concurrency: int
    repetition: int
    wall_seconds: float
    attempted_count: int
    papers_per_second: float
    status_counts: dict[str, int]
    acceptance_counts: dict[str, int]
    completion_order: list[str]
    lane_limits: dict[str, int]
    provider_peak_in_flight: dict[str, int]
    report_json: str
    report_markdown: str
    results: list[dict[str, Any]]
    error: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkLevelSummary:
    concurrency: int
    repetitions: int
    median_wall_seconds: float
    median_papers_per_second: float
    speedup_vs_baseline: float
    complete_results: int
    non_complete_results: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParallelLiveBenchmarkReport:
    generated_at: str
    output_dir: str
    concurrencies: list[int]
    repetitions: int
    cache_policy: str
    browser_state_reused: bool
    samples: list[dict[str, Any]]
    provider_status: dict[str, Any]
    preflight: dict[str, dict[str, Any]]
    trials: list[BenchmarkTrial]
    summary_by_concurrency: list[BenchmarkLevelSummary]
    comparisons: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    same_provider_probe: dict[str, Any] | None
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "output_dir": self.output_dir,
            "concurrencies": list(self.concurrencies),
            "repetitions": self.repetitions,
            "cache_policy": self.cache_policy,
            "browser_state_reused": self.browser_state_reused,
            "samples": [dict(item) for item in self.samples],
            "provider_status": self.provider_status,
            "preflight": {
                provider: dict(payload) for provider, payload in self.preflight.items()
            },
            "trials": [trial.to_dict() for trial in self.trials],
            "summary_by_concurrency": [
                summary.to_dict() for summary in self.summary_by_concurrency
            ],
            "comparisons": [dict(item) for item in self.comparisons],
            "failures": [dict(item) for item in self.failures],
            "same_provider_probe": (
                dict(self.same_provider_probe)
                if self.same_provider_probe is not None
                else None
            ),
            "success": self.success,
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
            + "\n",
            encoding="utf-8",
        )

    def to_markdown(self) -> str:
        lines = [
            "# Parallel Live Benchmark",
            "",
            f"- Generated: `{self.generated_at}`",
            f"- Result: `{'pass' if self.success else 'fail'}`",
            f"- Concurrencies: `{', '.join(str(item) for item in self.concurrencies)}`",
            f"- Repetitions: `{self.repetitions}`",
            f"- Cache policy: `{self.cache_policy}`",
            f"- Browser state reused: `{str(self.browser_state_reused).lower()}`",
            "",
            "## Concurrency Summary",
            "",
            "| Concurrency | Repetitions | Median Wall (s) | Median Papers/s | Speedup | Complete | Non-complete |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for summary in self.summary_by_concurrency:
            lines.append(
                f"| {summary.concurrency} | {summary.repetitions} | "
                f"{summary.median_wall_seconds:.3f} | "
                f"{summary.median_papers_per_second:.3f} | "
                f"{summary.speedup_vs_baseline:.3f} | "
                f"{summary.complete_results} | {summary.non_complete_results} |"
            )
        lines.extend(
            [
                "",
                "## Sample Matrix",
                "",
                "| Sample | Provider | Path | DOI |",
                "| --- | --- | --- | --- |",
            ]
        )
        for sample in self.samples:
            lines.append(
                f"| `{sample['sample_id']}` | `{sample['provider']}` | "
                f"`{sample['access_path']}` | `{sample['doi']}` |"
            )
        lines.extend(["", "## Result Drift", ""])
        if self.comparisons:
            for comparison in self.comparisons:
                drift = ", ".join(comparison["changed_fields"]) or "none"
                lines.append(
                    f"- `{comparison['sample_id']}` c={comparison['concurrency']} "
                    f"repeat={comparison['repetition']}: `{drift}`"
                )
        else:
            lines.append("No cross-concurrency drift detected.")
        if self.same_provider_probe is not None:
            probe = self.same_provider_probe
            lines.extend(
                [
                    "",
                    "## Same-provider Probe",
                    "",
                    f"- Provider: `{probe['provider']}`",
                    f"- Verdict: `{probe['verdict']}`",
                    f"- Requested lane limit: `{probe['requested_lane_limit']}`",
                    f"- Overlap observed: `{str(probe['overlap_observed']).lower()}`",
                    f"- Results stable: `{str(probe['results_stable']).lower()}`",
                    "",
                    "| Concurrency | Repetition | Actual lane limit | Peak in-flight | Overlap |",
                    "| ---: | ---: | ---: | ---: | --- |",
                ]
            )
            for round_result in probe["rounds"]:
                lines.append(
                    f"| {round_result['concurrency']} | "
                    f"{round_result['repetition']} | "
                    f"{round_result['actual_lane_limit']} | "
                    f"{round_result['peak_in_flight']} | "
                    f"{str(round_result['overlap_observed']).lower()} |"
                )
        lines.extend(["", "## Failures", ""])
        if self.failures:
            for failure in self.failures:
                point = "/".join(
                    str(failure.get(key) or "-")
                    for key in ("provider", "route", "stage")
                )
                lines.append(
                    f"- `{failure.get('sample_id') or failure.get('provider') or 'benchmark_trial'}` "
                    f"c={failure.get('concurrency', '-')} "
                    f"repeat={failure.get('repetition', '-')}: "
                    f"`{failure.get('code') or failure.get('acceptance') or 'failed'}` "
                    f"at `{point}`"
                )
        else:
            lines.append("No unexpected failures.")
        return "\n".join(lines).rstrip() + "\n"

    def write_markdown(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")


TransportFactory = Callable[[], HttpTransport]
PreflightFn = Callable[..., BrowserPreflightResult]
GoldenRunnerFn = Callable[..., GoldenCriteriaLiveReport]


def _requires_browser_runtime(provider: str) -> bool:
    provider_key = normalize_text(provider).lower()
    return provider_has_browser_route(provider_key)


def timestamped_benchmark_output_dir(*, now: datetime | None = None) -> Path:
    active_now = now or datetime.now(UTC)
    timestamp = active_now.strftime("%Y%m%d-%H%M%S")
    return resolve_repo_root() / "live-downloads" / BENCHMARK_ROOT_NAME / timestamp


def no_cache_transport() -> HttpTransport:
    return HttpTransport(
        cache_ttl=0,
        metadata_cache_ttl=0,
        cache_capacity=0,
        disk_cache_dir=None,
    )


def _validate_positive_values(
    values: Sequence[int], *, name: str, maximum: int = 8
) -> tuple[int, ...]:
    normalized = tuple(values)
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= maximum
        for value in normalized
    ):
        raise ValueError(f"{name} values must be integers from 1 to {maximum}")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} values must be unique")
    return normalized


def expectations_from_catalog(
    catalog: Mapping[str, Any],
) -> dict[str, BenchmarkExpectation]:
    expectations: dict[str, BenchmarkExpectation] = {}
    for provider, sample in catalog.items():
        doi = normalize_doi(str(getattr(sample, "doi", "")))
        if not doi:
            continue
        expectations[doi] = BenchmarkExpectation(
            provider=normalize_text(provider).lower(),
            doi=doi,
            accepted_sources=tuple(getattr(sample, "accepted_sources", ()) or ()),
            accepted_trace_groups=tuple(
                tuple(group)
                for group in (
                    getattr(sample, "accepted_live_source_trail_groups", ()) or ()
                )
            ),
        )
    return expectations


def select_benchmark_samples(
    manifest: Mapping[str, Any],
    expectations: Mapping[str, BenchmarkExpectation],
    *,
    providers: Sequence[str] | None = None,
    sample_ids: Sequence[str] | None = None,
) -> list[GoldenCriteriaLiveSample]:
    all_samples = iter_golden_criteria_samples(manifest)
    by_doi = {normalize_doi(sample.doi): sample for sample in all_samples}
    by_id = {sample.sample_id: sample for sample in all_samples}
    if sample_ids:
        selected: list[GoldenCriteriaLiveSample] = []
        missing: list[str] = []
        for value in sample_ids:
            normalized = normalize_text(value)
            sample = by_id.get(normalized) or by_doi.get(normalize_doi(normalized))
            if sample is None:
                missing.append(normalized)
            elif sample not in selected:
                selected.append(sample)
        if missing:
            raise ValueError(f"Unknown golden sample(s): {', '.join(missing)}")
        return selected

    provider_order = tuple(providers or DEFAULT_BENCHMARK_PROVIDERS)
    normalized_providers = tuple(
        normalize_text(provider).lower() for provider in provider_order
    )
    if len(set(normalized_providers)) != len(normalized_providers):
        raise ValueError("providers must not contain duplicates")
    selected = []
    missing_providers = []
    for provider_key in normalized_providers:
        expectation = next(
            (item for item in expectations.values() if item.provider == provider_key),
            None,
        )
        sample = by_doi.get(expectation.doi) if expectation is not None else None
        if sample is None:
            missing_providers.append(provider_key)
        else:
            selected.append(sample)
    if missing_providers:
        raise ValueError(
            "No benchmark-backed golden sample for provider(s): "
            + ", ".join(missing_providers)
        )
    return selected


def _preflight_payload(result: BrowserPreflightResult) -> dict[str, Any]:
    payload = asdict(result)
    if result.storage_state_path is not None:
        payload["storage_state_path"] = str(result.storage_state_path)
    return payload


def _provider_status_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        normalize_text(entry.get("provider")).lower(): dict(entry)
        for entry in payload.get("providers") or []
        if isinstance(entry, Mapping) and normalize_text(entry.get("provider"))
    }


def _apply_preflight_status(
    provider_status: Mapping[str, Any],
    preflight: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = copy.deepcopy(dict(provider_status))
    for entry in payload.get("providers") or []:
        provider = normalize_text(entry.get("provider")).lower()
        preflight_entry = preflight.get(provider)
        if not preflight_entry or preflight_entry.get("status") == "ready":
            continue
        status = normalize_text(preflight_entry.get("status")).lower() or "error"
        entry["available"] = False
        entry["status"] = status
        entry.setdefault("checks", []).append(
            {
                "name": "browser_preflight",
                "status": status,
                "message": preflight_entry.get("message"),
                "details": {
                    "reason_code": preflight_entry.get("reason_code"),
                    "stage": preflight_entry.get("stage"),
                },
            }
        )
    return payload


def _trial_result_payload(
    result: GoldenCriteriaLiveResult,
    expectation: BenchmarkExpectation | None,
) -> dict[str, Any]:
    acceptance = normalize_text(result.acceptance.get("overall")).lower() or "failed"
    route_accepted = expectation.accepts(result) if expectation is not None else True
    return {
        "sample_id": result.sample_id,
        "provider": result.provider,
        "doi": result.doi,
        "status": result.status,
        "source": result.source,
        "source_trail": list(result.source_trail),
        "acceptance": acceptance,
        "route_accepted": route_accepted,
        "expected_outcome": result.expected_outcome,
        "elapsed_seconds": result.elapsed_seconds,
        "stage_timings": dict(result.stage_timings),
        "error_code": result.error_code,
        "error_message": result.error_message,
        "failure_diagnostics": dict(result.failure_diagnostics),
        "trace": [dict(item) for item in result.trace],
        "diagnostic_artifacts": [dict(item) for item in result.diagnostic_artifacts],
        "worker_started_at": result.worker_started_at,
        "worker_finished_at": result.worker_finished_at,
    }


def _build_level_summaries(
    trials: Sequence[BenchmarkTrial], concurrencies: Sequence[int]
) -> list[BenchmarkLevelSummary]:
    grouped = {
        concurrency: [trial for trial in trials if trial.concurrency == concurrency]
        for concurrency in concurrencies
    }
    baseline = statistics.median(
        trial.wall_seconds for trial in grouped[concurrencies[0]]
    )
    summaries = []
    for concurrency in concurrencies:
        items = grouped[concurrency]
        wall = statistics.median(trial.wall_seconds for trial in items)
        throughput = statistics.median(trial.papers_per_second for trial in items)
        acceptance_counts = Counter(
            result["acceptance"] for trial in items for result in trial.results
        )
        complete = acceptance_counts.get("complete", 0)
        trial_error_count = sum(1 for trial in items if trial.error)
        summaries.append(
            BenchmarkLevelSummary(
                concurrency=concurrency,
                repetitions=len(items),
                median_wall_seconds=round(wall, 3),
                median_papers_per_second=round(throughput, 3),
                speedup_vs_baseline=round(baseline / wall, 3) if wall > 0 else 0.0,
                complete_results=complete,
                non_complete_results=(
                    sum(acceptance_counts.values()) - complete + trial_error_count
                ),
            )
        )
    return summaries


def _build_comparisons(
    trials: Sequence[BenchmarkTrial], *, baseline_concurrency: int
) -> list[dict[str, Any]]:
    baseline_by_key = {
        (trial.repetition, result["sample_id"]): result
        for trial in trials
        if trial.concurrency == baseline_concurrency
        for result in trial.results
    }
    comparisons: list[dict[str, Any]] = []
    for trial in trials:
        if trial.concurrency == baseline_concurrency:
            continue
        for result in trial.results:
            baseline = baseline_by_key.get((trial.repetition, result["sample_id"]))
            changed_fields = [
                field
                for field in ("status", "source", "acceptance", "route_accepted")
                if baseline is None or baseline.get(field) != result.get(field)
            ]
            if changed_fields:
                comparisons.append(
                    {
                        "sample_id": result["sample_id"],
                        "provider": result["provider"],
                        "concurrency": trial.concurrency,
                        "repetition": trial.repetition,
                        "baseline_concurrency": baseline_concurrency,
                        "changed_fields": changed_fields,
                        "baseline": baseline,
                        "observed": result,
                    }
                )
    return comparisons


def _build_failures(
    trials: Sequence[BenchmarkTrial],
    preflight: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for provider, result in preflight.items():
        if result.get("status") == "ready":
            continue
        failures.append(
            {
                "provider": provider,
                "route": "browser_preflight",
                "stage": result.get("stage"),
                "code": result.get("reason_code") or result.get("status"),
                "message": result.get("message"),
                "diagnostics": result.get("diagnostics") or {},
            }
        )
    for trial in trials:
        if trial.error:
            failures.append(
                {
                    "route": "benchmark_trial",
                    "stage": "trial_runner",
                    "concurrency": trial.concurrency,
                    "repetition": trial.repetition,
                    **trial.error,
                }
            )
        for result in trial.results:
            if result["expected_outcome"]:
                continue
            if result["acceptance"] == "complete" and result["route_accepted"]:
                continue
            diagnostics = result["failure_diagnostics"]
            failures.append(
                {
                    "sample_id": result["sample_id"],
                    "provider": diagnostics.get("provider") or result["provider"],
                    "route": diagnostics.get("route") or result["source"],
                    "stage": diagnostics.get("stage"),
                    "concurrency": trial.concurrency,
                    "repetition": trial.repetition,
                    "acceptance": result["acceptance"],
                    "route_accepted": result["route_accepted"],
                    "code": result["error_code"],
                    "message": result["error_message"],
                    "http_status": diagnostics.get("http_status"),
                    "error_category": diagnostics.get("error_category"),
                    "retryable": diagnostics.get("retryable"),
                    "trace": result["trace"],
                    "diagnostic_artifacts": result["diagnostic_artifacts"],
                }
            )
    return failures


def _build_same_provider_probe(
    *,
    provider: str,
    samples: Sequence[GoldenCriteriaLiveSample],
    trials: Sequence[BenchmarkTrial],
    comparisons: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    requested_lane_limit = SAME_PROVIDER_PROBE_LANE_LIMITS[provider]
    expected_sample_ids = {sample.sample_id for sample in samples}
    rounds = []
    for trial in trials:
        peak = int(trial.provider_peak_in_flight.get(provider, 0))
        actual_lane_limit = int(trial.lane_limits.get(provider, 0))
        observed_sample_ids = {str(result["sample_id"]) for result in trial.results}
        rounds.append(
            {
                "concurrency": trial.concurrency,
                "repetition": trial.repetition,
                "requested_lane_limit": requested_lane_limit,
                "actual_lane_limit": actual_lane_limit,
                "peak_in_flight": peak,
                "overlap_observed": peak >= 2,
                "result_count": len(trial.results),
                "all_samples_present": observed_sample_ids == expected_sample_ids,
                "all_workers_timed": bool(trial.results)
                and all(
                    isinstance(result.get("worker_started_at"), (int, float))
                    and not isinstance(result.get("worker_started_at"), bool)
                    and isinstance(result.get("worker_finished_at"), (int, float))
                    and not isinstance(result.get("worker_finished_at"), bool)
                    and result["worker_finished_at"] >= result["worker_started_at"]
                    for result in trial.results
                ),
                "all_acceptance_complete": bool(trial.results)
                and all(
                    result.get("acceptance") == "complete" for result in trial.results
                ),
                "all_routes_accepted": bool(trial.results)
                and all(bool(result.get("route_accepted")) for result in trial.results),
            }
        )

    control_rounds = [item for item in rounds if item["concurrency"] == 1]
    parallel_rounds = [item for item in rounds if item["concurrency"] == 2]
    control_valid = len(control_rounds) == SAME_PROVIDER_PROBE_REPETITIONS and all(
        item["actual_lane_limit"] == 1 and item["peak_in_flight"] == 1
        for item in control_rounds
    )
    overlap_observed = len(parallel_rounds) == SAME_PROVIDER_PROBE_REPETITIONS and all(
        item["actual_lane_limit"] == 2 and item["peak_in_flight"] == 2
        for item in parallel_rounds
    )
    results_complete = all(
        item["all_samples_present"]
        and item["all_workers_timed"]
        and item["all_acceptance_complete"]
        and item["all_routes_accepted"]
        for item in rounds
    )
    blockers = [
        dict(item)
        for item in failures
        if item.get("route") in {"browser_preflight", "benchmark_trial"}
        or item.get("stage") in {"provider_status", "trial_runner"}
        or item.get("code") is not None
        or item.get("http_status") is not None
        or item.get("error_category") is not None
        or item.get("retryable") is not None
    ]
    result_failures = [dict(item) for item in failures if item not in blockers]
    results_stable = not comparisons
    if blockers:
        verdict = "blocked"
        parallel_capable: bool | None = None
    elif result_failures or not results_complete:
        verdict = "results_incomplete"
        parallel_capable = False
    elif not results_stable:
        verdict = "unstable"
        parallel_capable = False
    elif control_valid and overlap_observed:
        verdict = "capable"
        parallel_capable = True
    else:
        verdict = "overlap_not_observed"
        parallel_capable = False
    return {
        "provider": provider,
        "samples": [
            {
                "sample_id": sample.sample_id,
                "doi": sample.doi,
            }
            for sample in samples
        ],
        "catalog_lane_limit": provider_batch_concurrency(provider),
        "requested_lane_limit": requested_lane_limit,
        "allowed_concurrencies": list(SAME_PROVIDER_PROBE_CONCURRENCIES),
        "repetitions": SAME_PROVIDER_PROBE_REPETITIONS,
        "rounds": rounds,
        "control_valid": control_valid,
        "overlap_observed": overlap_observed,
        "results_complete": results_complete,
        "results_stable": results_stable,
        "speedup_is_success_criterion": False,
        "parallel_capable": parallel_capable,
        "verdict": verdict,
        "blockers": blockers,
        "result_failures": result_failures,
    }


def run_parallel_live_benchmark(
    *,
    benchmark_catalog: Mapping[str, Any],
    manifest_path: Path | None = None,
    output_dir: Path | None = None,
    providers: Sequence[str] | None = None,
    sample_ids: Sequence[str] | None = None,
    concurrencies: Sequence[int] | None = None,
    repetitions: int | None = None,
    same_provider_probe: str | None = None,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
    transport_factory: TransportFactory = no_cache_transport,
    preflight_fn: PreflightFn = preflight_browser_provider,
    provider_status_fn: Callable[..., dict[str, Any]] = provider_status_payload,
    golden_runner_fn: GoldenRunnerFn = run_golden_criteria_live_review,
    clock: Callable[[], float] = time.monotonic,
) -> ParallelLiveBenchmarkReport:
    probe_provider = normalize_text(same_provider_probe).lower() or None
    if probe_provider is not None:
        if probe_provider not in SAME_PROVIDER_PROBE_SAMPLES:
            raise ValueError(
                "same_provider_probe must be one of: "
                + ", ".join(sorted(SAME_PROVIDER_PROBE_SAMPLES))
            )
        conflicting = [
            name
            for name, value in (
                ("providers", providers),
                ("sample_ids", sample_ids),
                ("concurrencies", concurrencies),
                ("repetitions", repetitions),
            )
            if value is not None
        ]
        if conflicting:
            raise ValueError(
                "same_provider_probe cannot be combined with: " + ", ".join(conflicting)
            )
        sample_ids = SAME_PROVIDER_PROBE_SAMPLES[probe_provider]
        concurrencies = SAME_PROVIDER_PROBE_CONCURRENCIES
        repetitions = SAME_PROVIDER_PROBE_REPETITIONS
    concurrency_values = _validate_positive_values(
        DEFAULT_CONCURRENCIES if concurrencies is None else concurrencies,
        name="concurrencies",
    )
    active_repetitions = repetitions if repetitions is not None else DEFAULT_REPETITIONS
    if (
        isinstance(active_repetitions, bool)
        or not isinstance(active_repetitions, int)
        or active_repetitions < 1
    ):
        raise ValueError("repetitions must be a positive integer")
    runtime_env = build_runtime_env(env)
    ensure_live_opt_in(runtime_env)
    manifest = load_manifest(manifest_path)
    expectations = expectations_from_catalog(benchmark_catalog)
    samples = select_benchmark_samples(
        manifest,
        expectations,
        providers=providers,
        sample_ids=sample_ids,
    )
    if not samples:
        raise ValueError("benchmark sample selection must not be empty")

    active_now = now or datetime.now(UTC)
    output_root = (
        output_dir or timestamped_benchmark_output_dir(now=active_now)
    ).resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"benchmark output directory is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    status_transport = no_cache_transport()
    try:
        status_payload = provider_status_fn(
            env=runtime_env,
            transport=status_transport,
        )
    finally:
        status_transport.close()
    status_by_provider = _provider_status_index(status_payload)

    preflight: dict[str, dict[str, Any]] = {}
    for provider in dict.fromkeys(sample.provider for sample in samples):
        if not _requires_browser_runtime(provider):
            continue
        status = status_by_provider.get(provider, {})
        if status and not bool(status.get("available")):
            preflight[provider] = {
                "provider": provider,
                "status": normalize_text(status.get("status")).lower() or "error",
                "reason_code": "provider_status_unavailable",
                "stage": "provider_status",
                "message": next(iter(status.get("notes") or []), None),
            }
            continue
        sample = next(item for item in samples if item.provider == provider)
        try:
            result = preflight_fn(
                provider,
                env=runtime_env,
                target_url=sample.landing_url or sample.doi,
                save_storage_state=True,
                download_dir=output_root / "preflight" / provider,
                artifact_mode="all",
            )
            preflight[provider] = _preflight_payload(result)
        except Exception as exc:  # pragma: no cover - defensive live boundary
            preflight[provider] = {
                "provider": provider,
                "status": "runtime_error",
                "reason_code": exc.__class__.__name__,
                "stage": "browser_preflight",
                "message": str(exc),
            }

    effective_status_payload = _apply_preflight_status(status_payload, preflight)
    trials: list[BenchmarkTrial] = []
    expectation_by_doi = {
        normalize_doi(expectation.doi): expectation
        for expectation in expectations.values()
    }
    expectation_by_provider = {
        expectation.provider: expectation for expectation in expectations.values()
    }
    selected_ids = [sample.sample_id for sample in samples]
    eligible_providers = {
        sample.provider
        for sample in samples
        if bool(
            _provider_status_index(effective_status_payload)
            .get(sample.provider, {})
            .get("available", True)
        )
    }
    attempted_count = sum(
        1 for sample in samples if sample.provider in eligible_providers
    )

    for concurrency in concurrency_values:
        for repetition in range(1, active_repetitions + 1):
            trial_root = (
                output_root
                / "runs"
                / f"concurrency-{concurrency}"
                / f"repeat-{repetition}"
            )
            transport = transport_factory()
            started_at = clock()
            trial_report: GoldenCriteriaLiveReport | None = None
            trial_error: dict[str, Any] = {}
            try:
                trial_report = golden_runner_fn(
                    manifest_path=manifest_path,
                    output_dir=trial_root,
                    sample_ids=selected_ids,
                    env=runtime_env,
                    transport=transport,
                    provider_status_fn=lambda **_kwargs: effective_status_payload,
                    now=active_now,
                    concurrency=concurrency,
                    **(
                        {"lane_limit_overrides": SAME_PROVIDER_PROBE_LANE_LIMITS}
                        if probe_provider is not None
                        else {}
                    ),
                )
            except Exception as exc:  # pragma: no cover - defensive live boundary
                trial_error = {
                    "code": exc.__class__.__name__,
                    "message": str(exc),
                    "error_category": "trial_runner_error",
                }
            finally:
                wall_seconds = round(clock() - started_at, 3)
                transport.close()
            result_payloads = (
                [
                    _trial_result_payload(
                        result,
                        expectation_by_doi.get(normalize_doi(result.doi))
                        or expectation_by_provider.get(result.provider),
                    )
                    for result in trial_report.results
                ]
                if trial_report is not None
                else []
            )
            status_counts = Counter(result["status"] for result in result_payloads)
            acceptance_counts = Counter(
                result["acceptance"] for result in result_payloads
            )
            trials.append(
                BenchmarkTrial(
                    concurrency=concurrency,
                    repetition=repetition,
                    wall_seconds=wall_seconds,
                    attempted_count=(
                        attempted_count if trial_report is not None else 0
                    ),
                    papers_per_second=(
                        round(attempted_count / wall_seconds, 3)
                        if wall_seconds > 0 and trial_report is not None
                        else 0.0
                    ),
                    status_counts=dict(sorted(status_counts.items())),
                    acceptance_counts=dict(sorted(acceptance_counts.items())),
                    completion_order=(
                        list(trial_report.completion_order)
                        if trial_report is not None
                        else []
                    ),
                    lane_limits=(
                        dict(trial_report.lane_limits)
                        if trial_report is not None
                        else {}
                    ),
                    provider_peak_in_flight=(
                        dict(trial_report.provider_peak_in_flight)
                        if trial_report is not None
                        else {}
                    ),
                    report_json=str(trial_root / "report.json"),
                    report_markdown=str(trial_root / "report.md"),
                    results=result_payloads,
                    error=trial_error,
                )
            )

    summaries = _build_level_summaries(trials, concurrency_values)
    comparisons = _build_comparisons(trials, baseline_concurrency=concurrency_values[0])
    failures = _build_failures(trials, preflight)
    probe_payload = (
        _build_same_provider_probe(
            provider=probe_provider,
            samples=samples,
            trials=trials,
            comparisons=comparisons,
            failures=failures,
        )
        if probe_provider is not None
        else None
    )
    success = not failures and not comparisons
    if probe_payload is not None:
        success = success and probe_payload["parallel_capable"] is True
    final_report = ParallelLiveBenchmarkReport(
        generated_at=active_now.isoformat(),
        output_dir=str(output_root),
        concurrencies=list(concurrency_values),
        repetitions=active_repetitions,
        cache_policy="http_memory_and_disk_disabled_per_trial",
        browser_state_reused=True,
        samples=[
            {
                "sample_id": sample.sample_id,
                "provider": sample.provider,
                "doi": sample.doi,
                "access_path": (
                    "browser"
                    if _requires_browser_runtime(sample.provider)
                    else "direct"
                ),
            }
            for sample in samples
        ],
        provider_status=status_payload,
        preflight=preflight,
        trials=trials,
        summary_by_concurrency=summaries,
        comparisons=comparisons,
        failures=failures,
        same_provider_probe=probe_payload,
        success=success,
    )
    final_report.write_json(output_root / "benchmark.json")
    final_report.write_markdown(output_root / "benchmark.md")
    return final_report


__all__ = [
    "BENCHMARK_ROOT_NAME",
    "DEFAULT_BENCHMARK_PROVIDERS",
    "DEFAULT_CONCURRENCIES",
    "DEFAULT_REPETITIONS",
    "SAME_PROVIDER_PROBE_CONCURRENCIES",
    "SAME_PROVIDER_PROBE_LANE_LIMITS",
    "SAME_PROVIDER_PROBE_REPETITIONS",
    "SAME_PROVIDER_PROBE_SAMPLES",
    "BenchmarkExpectation",
    "BenchmarkLevelSummary",
    "BenchmarkTrial",
    "ParallelLiveBenchmarkReport",
    "expectations_from_catalog",
    "no_cache_transport",
    "run_parallel_live_benchmark",
    "select_benchmark_samples",
    "timestamped_benchmark_output_dir",
]
