from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import warnings
from collections import Counter
from collections.abc import Mapping

import pytest

from paper_fetch.http import HttpTransport
from paper_fetch.provider_catalog import provider_has_browser_route
from paper_fetch.publisher_identity import normalize_doi
from paper_fetch.reason_codes import NO_ACCESS
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper
from paper_fetch.workflow.types import PaperFetchFailure
from paper_fetch.workflow.acceptance import (
    AssetAcceptanceStatus,
    ContentAcceptanceStatus,
    FetchAcceptanceStatus,
    IdentityAcceptanceStatus,
    OverallAcceptanceStatus,
    OutputAcceptanceStatus,
    evaluate_fetch_acceptance,
)
from tests.live._runtime_env import (
    build_isolated_live_env,
    preflight_selected_browser_or_skip,
)
from tests.provider_benchmark_samples import (
    iter_provider_benchmark_samples,
    provider_benchmark_sample,
)


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
RUN_AIP_COLD_STABILITY = os.environ.get("PAPER_FETCH_RUN_AIP_COLD_STABILITY") == "1"
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
AIP_SAMPLE = provider_benchmark_sample("aip")
AIP_COLD_START_ATTEMPTS = 5


class _PytestSkipper:
    @staticmethod
    def skipTest(message: str) -> None:
        pytest.skip(message)

    @staticmethod
    def fail(message: str) -> None:
        pytest.fail(message)


def _skip_legal_access_boundary(provider: str, exc: PaperFetchFailure) -> None:
    if exc.status == NO_ACCESS:
        pytest.skip(
            f"{provider} live route reached a legal access boundary; "
            f"configure entitlement/authentication before retrying ({exc.status})."
        )


def fetch_envelope(
    query: str,
    *,
    transport: HttpTransport,
    env: dict[str, str],
    download_dir: Path | None = None,
    artifact_mode: str = "none",
    preferred_provider: str | None = None,
    asset_profile: str | None = None,
    telemetry: dict[str, object] | None = None,
):
    started_at = time.monotonic()
    context = RuntimeContext(
        env=env,
        transport=transport,
        download_dir=download_dir,
        artifact_mode=artifact_mode,
    )
    try:
        envelope = fetch_paper(
            query,
            modes={"article"},
            strategy=FetchStrategy(
                allow_metadata_only_fallback=False,
                preferred_providers=(
                    [preferred_provider] if preferred_provider is not None else None
                ),
                asset_profile=asset_profile,
            ),
            context=context,
        )
    finally:
        if telemetry is not None:
            telemetry["stage_timings"] = dict(context.stage_timings)
            telemetry["fetch_wall_seconds"] = round(time.monotonic() - started_at, 3)
        context.close()
    return envelope


def fetch_article(query: str, *, transport: HttpTransport, env: dict[str, str]):
    envelope = fetch_envelope(query, transport=transport, env=env)
    assert envelope.article is not None
    return envelope.article


@pytest.fixture(scope="module")
def catalog_live_env():
    if not RUN_LIVE:
        pytest.skip(
            "Set PAPER_FETCH_RUN_LIVE=1 to run live publisher acceptance tests."
        )
    env, tempdir = build_isolated_live_env()
    try:
        yield env
    finally:
        tempdir.cleanup()


@pytest.fixture(scope="module")
def catalog_live_preflight_cache():
    return {}


@pytest.fixture(scope="module")
def catalog_live_artifact_root() -> Path:
    configured = os.environ.get("PAPER_FETCH_LIVE_ARTIFACT_DIR", "").strip()
    root = (
        Path(configured)
        if configured
        else Path(".paper-fetch-runs/live-publisher-acceptance")
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _catalog_acceptance_report(
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
    all_recorded_complete = bool(records) and set(overall) == {"complete"}
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


def _browser_runtime_trace(
    diagnostics: Mapping[str, object] | None,
) -> dict[str, object]:
    trace = (diagnostics or {}).get("browser_runtime_trace")
    return dict(trace) if isinstance(trace, Mapping) else {}


def _last_browser_candidate(trace: Mapping[str, object]) -> dict[str, object]:
    candidates = trace.get("candidates")
    if not isinstance(candidates, list):
        return {}
    for candidate in reversed(candidates):
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return {}


@pytest.fixture(scope="module")
def catalog_live_report(catalog_live_artifact_root: Path):
    records: list[dict[str, object]] = []
    yield records
    payload = _catalog_acceptance_report(records)
    (catalog_live_artifact_root / "live-acceptance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "sample",
    iter_provider_benchmark_samples(),
    ids=lambda sample: sample.provider,
)
def test_catalog_provider_sample_live_body_acceptance(
    sample,
    catalog_live_env,
    catalog_live_preflight_cache,
    catalog_live_artifact_root,
    catalog_live_report,
    record_property,
) -> None:
    sample_started_at = time.monotonic()
    preflight_seconds = 0.0
    preflight_trace: dict[str, object] = {}
    missing = [
        key for key in sample.required_env if not catalog_live_env.get(key, "").strip()
    ]
    if missing:
        pytest.skip(
            "Missing required environment variables for live test: "
            + ", ".join(missing)
        )
    if provider_has_browser_route(sample.provider):
        preflight_started_at = time.monotonic()
        preflight = preflight_selected_browser_or_skip(
            _PytestSkipper(),
            provider=sample.provider,
            env=catalog_live_env,
            cache=catalog_live_preflight_cache,
            artifact_root=catalog_live_artifact_root / "preflight",
        )
        preflight_seconds = round(time.monotonic() - preflight_started_at, 3)
        preflight_trace = _browser_runtime_trace(preflight.diagnostics)
        record_property("preflight_status", preflight.status)
        record_property("preflight_reason_code", preflight.reason_code)
        record_property("preflight_stage", preflight.stage or "")
        record_property("preflight_final_url", preflight.final_url or "")
        record_property(
            "preflight_storage_state_path",
            str(preflight.storage_state_path or ""),
        )
        diagnostic_path = str(
            (preflight.diagnostics or {}).get("diagnostic_path") or ""
        )
        record_property("preflight_diagnostic_path", diagnostic_path)
        record_property("preflight_seconds", preflight_seconds)
        record_property(
            "preflight_navigation_count",
            int(preflight_trace.get("navigation_count") or 0),
        )

    fetch_telemetry: dict[str, object] = {}
    try:
        envelope = fetch_envelope(
            sample.doi,
            transport=HttpTransport(),
            env=catalog_live_env,
            download_dir=catalog_live_artifact_root / "providers" / sample.provider,
            artifact_mode="all",
            preferred_provider=sample.provider,
            asset_profile="body",
            telemetry=fetch_telemetry,
        )
    except PaperFetchFailure as exc:
        _skip_legal_access_boundary(sample.provider, exc)
        raise
    assert envelope.article is not None
    article = envelope.article
    acceptance = evaluate_fetch_acceptance(
        envelope,
        asset_profile="body",
        requested_outputs={"article"},
        expected_doi=sample.doi,
    )
    record_property("fetch_source", article.source)
    record_property(
        "fetch_source_trail",
        json.dumps(article.quality.source_trail, ensure_ascii=False),
    )
    record_property("fetch_acceptance", acceptance.to_json())
    stage_timings = dict(fetch_telemetry.get("stage_timings") or {})
    total_seconds = round(time.monotonic() - sample_started_at, 3)
    preflight_reuse_hit = "browser:preflight_reuse_hit" in set(
        article.quality.source_trail
    )
    readiness = _last_browser_candidate(preflight_trace)
    performance_warning = None
    if sample.provider == "pnas" and total_seconds > 45:
        performance_warning = (
            "PNAS preflight+fetch exceeded the observational 45 second target: "
            f"{total_seconds:.3f}s"
        )
        warnings.warn(performance_warning, RuntimeWarning, stacklevel=1)
    record_property(
        "fetch_stage_timings",
        json.dumps(stage_timings, ensure_ascii=False, sort_keys=True),
    )
    record_property("fetch_wall_seconds", fetch_telemetry["fetch_wall_seconds"])
    record_property("preflight_reuse_hit", str(preflight_reuse_hit).lower())
    record_property(
        "browser_navigation_count", int(preflight_trace.get("navigation_count") or 0)
    )
    record_property("dom_readiness_result", readiness.get("dom_readiness_result") or "")
    record_property(
        "dom_readiness_seconds", readiness.get("dom_readiness_seconds") or 0
    )
    record_property("sample_total_seconds", total_seconds)
    record_property("performance_warning", performance_warning or "")
    preflight_payload = None
    if provider_has_browser_route(sample.provider):
        preflight_payload = {
            "status": preflight.status,
            "reason_code": preflight.reason_code,
            "stage": preflight.stage,
            "final_url": preflight.final_url,
            "storage_state_path": str(preflight.storage_state_path or "") or None,
            "diagnostic_path": str(
                (preflight.diagnostics or {}).get("diagnostic_path") or ""
            )
            or None,
            "browser_runtime_trace": preflight_trace,
        }
    catalog_live_report.append(
        {
            "provider": sample.provider,
            "doi": normalize_doi(sample.doi),
            "preflight": preflight_payload,
            "source": article.source,
            "source_trail": list(article.quality.source_trail),
            "acceptance": acceptance.model_dump(mode="json"),
            "performance": {
                "preflight_seconds": preflight_seconds,
                "fetch_wall_seconds": fetch_telemetry["fetch_wall_seconds"],
                "total_seconds": total_seconds,
                "stage_timings": stage_timings,
                "preflight_reuse_hit": preflight_reuse_hit,
                "preflight_navigation_count": int(
                    preflight_trace.get("navigation_count") or 0
                ),
                "fetch_html_navigation_count": 0 if preflight_reuse_hit else None,
                "dom_readiness_result": readiness.get("dom_readiness_result"),
                "dom_readiness_seconds": readiness.get("dom_readiness_seconds"),
                "downloaded_asset_count": sum(
                    bool(asset.path) for asset in article.assets
                ),
                "warning": performance_warning,
            },
            "output_dir": str(
                catalog_live_artifact_root / "providers" / sample.provider
            ),
            "asset_paths": [str(asset.path) for asset in article.assets if asset.path],
        }
    )

    assert normalize_doi(article.doi or "") == normalize_doi(sample.doi)
    assert article.quality.has_fulltext
    assert article.sections
    assert sample.accepts_live_result(
        source=article.source,
        source_trail=article.quality.source_trail,
    ), article.quality.source_trail
    assert acceptance.identity.status == IdentityAcceptanceStatus.RESOLVED
    assert acceptance.fetch.status == FetchAcceptanceStatus.OK
    assert acceptance.content.status == ContentAcceptanceStatus.FULLTEXT
    assert acceptance.asset.status in {
        AssetAcceptanceStatus.COMPLETE,
        AssetAcceptanceStatus.NOT_APPLICABLE,
    }
    assert acceptance.output.status == OutputAcceptanceStatus.COMPLETE
    assert acceptance.overall == OverallAcceptanceStatus.COMPLETE, acceptance.to_json()
    if sample.provider == "pnas":
        assert "browser:preflight_reuse_hit" in article.quality.source_trail
        assert "fulltext:pnas_html_ok" in article.quality.source_trail
        assert "fulltext:pnas_pdf_fallback_ok" not in article.quality.source_trail
        assert int(preflight_trace.get("navigation_count") or 0) == 1
        assert acceptance.asset.status == AssetAcceptanceStatus.COMPLETE


def test_aip_cold_start_stability_uses_html_for_five_fresh_profiles(
    catalog_live_env,
    catalog_live_preflight_cache,
    catalog_live_artifact_root,
) -> None:
    if not RUN_AIP_COLD_STABILITY:
        pytest.skip(
            "Set PAPER_FETCH_RUN_AIP_COLD_STABILITY=1 to run repeated AIP cold starts."
        )

    preflight_selected_browser_or_skip(
        _PytestSkipper(),
        provider="aip",
        env=catalog_live_env,
        cache=catalog_live_preflight_cache,
        artifact_root=catalog_live_artifact_root / "preflight",
    )

    artifact_tempdir: tempfile.TemporaryDirectory | None = None
    artifact_root_value = os.environ.get("PAPER_FETCH_LIVE_ARTIFACT_DIR")
    if artifact_root_value:
        artifact_root = Path(artifact_root_value)
    else:
        artifact_tempdir = tempfile.TemporaryDirectory(
            prefix="paper-fetch-aip-cold-live-"
        )
        artifact_root = Path(artifact_tempdir.name)
    failures: list[dict[str, object]] = []
    for attempt in range(1, AIP_COLD_START_ATTEMPTS + 1):
        env, tempdir = build_isolated_live_env()
        context = RuntimeContext(
            env=env,
            transport=HttpTransport(),
            download_dir=artifact_root / f"attempt-{attempt}",
            artifact_mode="all",
        )
        try:
            envelope = fetch_paper(
                AIP_SAMPLE.doi,
                modes={"article"},
                strategy=FetchStrategy(
                    allow_metadata_only_fallback=False,
                    preferred_providers=["aip"],
                    asset_profile="none",
                ),
                context=context,
            )
            acceptance = evaluate_fetch_acceptance(
                envelope,
                asset_profile="none",
                requested_outputs={"article"},
                expected_doi=AIP_SAMPLE.doi,
            )
            article = envelope.article
            source = article.source if article is not None else None
            source_trail = list(
                article.quality.source_trail if article is not None else []
            )
            if not (
                source == "aip_html"
                and "fulltext:aip_html_ok" in source_trail
                and "fulltext:aip_pdf_fallback_ok" not in source_trail
                and acceptance.overall == OverallAcceptanceStatus.COMPLETE
                and acceptance.identity.status == IdentityAcceptanceStatus.RESOLVED
                and acceptance.fetch.status == FetchAcceptanceStatus.OK
                and acceptance.content.status == ContentAcceptanceStatus.FULLTEXT
                and acceptance.output.status == OutputAcceptanceStatus.COMPLETE
            ):
                failures.append(
                    {
                        "attempt": attempt,
                        "source": source,
                        "source_trail": source_trail,
                        "acceptance": acceptance.model_dump(mode="json"),
                    }
                )
        except Exception as exc:  # noqa: BLE001 - collect all independent trials.
            failures.append(
                {
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        finally:
            context.close()
            tempdir.cleanup()

    if artifact_tempdir is not None:
        artifact_tempdir.cleanup()
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=2)


class LivePublisherTests(unittest.TestCase):
    runtime_env_tempdir: tempfile.TemporaryDirectory | None = None
    preflight_cache: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest(
                "Set PAPER_FETCH_RUN_LIVE=1 to run live publisher acceptance tests."
            )
        cls.env, cls.runtime_env_tempdir = build_isolated_live_env()
        cls.preflight_cache = {}

    @classmethod
    def tearDownClass(cls) -> None:
        runtime_env_tempdir = getattr(cls, "runtime_env_tempdir", None)
        if runtime_env_tempdir is not None:
            runtime_env_tempdir.cleanup()

    def _require_env(self, *keys: str) -> None:
        missing = [key for key in keys if not self.env.get(key, "").strip()]
        if missing:
            self.skipTest(
                f"Missing required environment variables for live test: {', '.join(missing)}"
            )

    def _assert_matches_sample(self, article, sample) -> None:
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertTrue(
            sample.accepts_live_result(
                source=article.source,
                source_trail=article.quality.source_trail,
            ),
            article.quality.source_trail,
        )

    def test_elsevier_url_live_recovers_doi_and_uses_official_fulltext(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            ELSEVIER_SAMPLE.resolve_url,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.doi, ELSEVIER_SAMPLE.doi)
        self._assert_matches_sample(article, ELSEVIER_SAMPLE)
        self.assertIn("resolve:url", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)

    def test_elsevier_old_doi_live_uses_official_pdf_fallback(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            "10.1016/0304-4165(96)00054-2",
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "elsevier_pdf")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_fail", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
