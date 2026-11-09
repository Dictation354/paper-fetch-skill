"""Privacy-safe live report persistence, including assertion and skip outcomes."""

from pathlib import Path
from collections.abc import Mapping
from statistics import median

from paper_fetch.publisher_identity import normalize_doi

from collections import Counter
from contextlib import contextmanager
import json
import time

import pytest
from paper_fetch.http import redact_text_for_diagnostics
from paper_fetch.logging_utils import redact_log_value
from tests.provider_benchmark_samples import iter_provider_benchmark_samples


def catalog_acceptance_report(
    records: list[dict[str, object]],
) -> dict[str, object]:
    overall = Counter(str(record["acceptance"]["overall"]) for record in records)
    catalog_providers = [
        sample.provider for sample in iter_provider_benchmark_samples()
    ]
    recorded_providers = {str(record["provider"]) for record in records}
    unrecorded_providers = [
        provider for provider in catalog_providers if provider not in recorded_providers
    ]
    all_recorded_complete = (
        bool(records)
        and set(overall) == {"complete"}
        and all(
            record.get("terminal", {}).get("status") == "complete" for record in records
        )
    )
    return {
        "schema_version": 2,
        "task": "catalog_body_asset_acceptance",
        "requested_asset_profile": "body",
        "summary": {
            "catalog_provider_count": len(catalog_providers),
            "recorded_provider_count": len(records),
            "unrecorded_provider_count": len(unrecorded_providers),
            "unrecorded_providers": unrecorded_providers,
            "overall": dict(sorted(overall.items())),
            "all_recorded_complete": all_recorded_complete,
            "all_catalog_providers_complete": (
                all_recorded_complete and not unrecorded_providers
            ),
        },
        "providers": records,
    }


@contextmanager
def preserve_terminal_record(
    terminal_record, records, root, started_at, record_property
):
    try:
        yield
    except BaseException as exc:
        terminal = dict(terminal_record["terminal"])
        terminal["status"] = (
            "skipped" if isinstance(exc, pytest.skip.Exception) else "failed"
        )
        if terminal.get("reason_code") in {
            "validation_pending",
            "terminated_before_acceptance",
        }:
            terminal["reason_code"] = (
                "assertion_failed"
                if isinstance(exc, AssertionError)
                else type(exc).__name__
            )
        terminal["message"] = redact_text_for_diagnostics(str(exc))[:1000]
        terminal_record["terminal"] = terminal
        raise
    finally:
        performance = dict(terminal_record.get("performance") or {})
        performance["total_seconds"] = round(time.monotonic() - started_at, 3)
        terminal_record["performance"] = performance
        record_property("sample_total_seconds", performance["total_seconds"])
        (root / "live-acceptance.json").write_text(
            json.dumps(
                redact_log_value(catalog_acceptance_report(records)),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _asset_performance_summary(article) -> dict[str, object]:
    rows = [
        timing
        for timing in (
            *(
                asset.asset_timing
                for asset in article.assets
                if isinstance(asset.asset_timing, Mapping)
            ),
            *(
                failure.get("asset_timing")
                for failure in article.quality.asset_failures
                if isinstance(failure, Mapping)
            ),
        )
        if isinstance(timing, Mapping) and timing
    ]
    phase_names = (
        "queue_ms",
        "candidate_resolution_ms",
        "dns_policy_validation_ms",
        "connect_to_headers_ttfb_ms",
        "body_stream_ms",
        "browser_recovery_ms",
        "retry_wait_ms",
        "conversion_ms",
        "save_ms",
        "total_ms",
    )
    totals = {
        name: round(sum(float(row.get(name) or 0.0) for row in rows), 3)
        for name in phase_names
    }
    quality_reasons = Counter(
        reason
        for asset in article.assets
        for reason in asset.provenance
        if reason
        in {
            "official_full_size_access_restricted",
            "official_full_size_not_exposed",
        }
    )
    return {
        "asset_count": len(rows),
        "download_tiers": dict(
            sorted(
                Counter(
                    asset.download_tier or "unknown" for asset in article.assets
                ).items()
            )
        ),
        "quality_reasons": dict(sorted(quality_reasons.items())),
        "status": dict(
            sorted(Counter(str(row.get("status") or "unknown") for row in rows).items())
        ),
        "totals_ms": totals,
        "median_total_ms": round(
            median(float(row.get("total_ms") or 0.0) for row in rows), 3
        )
        if rows
        else 0.0,
    }


def fetch_browser_diagnostics(
    root: Path, *, provider: str, doi: str
) -> dict[str, object]:
    """Read only this fetch's saved runtime diagnostics, including failed fetches."""
    records = []
    for path in sorted((root / "diagnostics" / provider).rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        payload_doi = normalize_doi(str(payload.get("doi") or ""))
        if payload_doi and payload_doi != normalize_doi(doi):
            continue
        if not payload_doi and path.parent.parent.name != doi.replace("/", "_"):
            continue
        diagnostics = payload.get("diagnostics") or {}
        trace = diagnostics.get("browser_runtime_trace") or (
            payload.get("page") or {}
        ).get("browser_runtime")
        if isinstance(trace, Mapping):
            records.append({"path": str(path), "browser_runtime_trace": dict(trace)})
    # A completed runtime snapshot takes precedence over extraction failure summaries.
    runtime = next(
        (row for row in records if Path(row["path"]).name == "byparr.json"), None
    )
    trace = (runtime or records[-1])["browser_runtime_trace"] if records else {}
    candidates = trace.get("candidates") or []
    last = next(
        (dict(row) for row in reversed(candidates) if isinstance(row, Mapping)), {}
    )
    return {
        "diagnostics": records,
        "browser_runtime_trace": trace,
        "browser_navigation_count": int(
            trace.get("navigation_count") or len(candidates)
        ),
        "navigation_seconds": round(
            sum(
                float(row.get("navigation_seconds") or 0)
                for row in candidates
                if isinstance(row, Mapping)
            ),
            3,
        ),
        "dom_readiness_result": last.get("dom_readiness_result")
        or (
            "ready"
            if last.get("dom_readiness_ready")
            else "timeout"
            if last.get("dom_readiness_attempted")
            else None
        ),
        "dom_readiness_seconds": last.get("dom_readiness_seconds"),
    }
