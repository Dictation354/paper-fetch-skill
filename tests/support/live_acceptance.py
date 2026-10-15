"""Privacy-safe live report persistence, including assertion and skip outcomes."""

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
