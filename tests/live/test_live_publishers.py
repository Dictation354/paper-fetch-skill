from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import warnings

import pytest

from paper_fetch.http import (
    HttpTransport,
    redact_text_for_diagnostics,
)
from paper_fetch.logging_utils import redact_log_value
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
from tests.support.live_acceptance import (
    catalog_acceptance_report,
    fetch_browser_diagnostics,
    _asset_performance_summary,
    preserve_terminal_record,
)
from tests.live._runtime_env import (
    build_isolated_live_env,
    require_local_browser_or_skip,
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
def catalog_live_artifact_root() -> Path:
    configured = os.environ.get("PAPER_FETCH_LIVE_ARTIFACT_DIR", "").strip()
    root = (
        Path(configured)
        if configured
        else Path(".paper-fetch-runs/live-publisher-acceptance")
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="module")
def catalog_live_report(catalog_live_artifact_root: Path):
    records: list[dict[str, object]] = []
    yield records
    payload = catalog_acceptance_report(records)
    (catalog_live_artifact_root / "live-acceptance.json").write_text(
        json.dumps(redact_log_value(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "sample,backend",
    [
        (sample, backend)
        for sample in iter_provider_benchmark_samples()
        for backend in (
            ("camoufox", "byparr") if sample.provider == "pnas" else ("auto",)
        )
    ],
    ids=[
        f"{sample.provider}-{backend}"
        for sample in iter_provider_benchmark_samples()
        for backend in (
            ("camoufox", "byparr") if sample.provider == "pnas" else ("auto",)
        )
    ],
)
def test_catalog_provider_sample_live_body_acceptance(
    sample,
    backend,
    catalog_live_env,
    catalog_live_artifact_root,
    catalog_live_report,
    record_property,
) -> None:
    from paper_fetch.providers.browser_runtime.selection import selected_backend

    catalog_live_env = type(catalog_live_env)(catalog_live_env)
    catalog_live_env[f"PAPER_FETCH_{sample.provider.upper()}_BROWSER_BACKEND"] = backend
    active_backend = (
        selected_backend(catalog_live_env, provider=sample.provider)
        if provider_has_browser_route(sample.provider)
        else "http"
    )
    catalog_live_artifact_root = catalog_live_artifact_root / active_backend
    catalog_live_artifact_root.mkdir(parents=True, exist_ok=True)
    provider_output_dir = (
        catalog_live_artifact_root
        / "providers"
        / (sample.provider if backend == "auto" else f"{sample.provider}-{backend}")
    )
    record_property("browser_backend", active_backend)
    sample_started_at = time.monotonic()
    preflight_seconds = 0.0
    terminal_record: dict[str, object] = {
        "provider": sample.provider,
        "backend": active_backend,
        "requested_backend": backend,
        "doi": normalize_doi(sample.doi),
        "terminal": {
            "status": "failed",
            "reason_code": "terminated_before_acceptance",
        },
        "preflight": None,
        "source": None,
        "source_trail": [],
        "acceptance": {
            "overall": "failed",
            "reason_code": "terminated_before_acceptance",
        },
        "performance": {"total_seconds": 0.0, "preflight_seconds": 0},
        "output_dir": str(provider_output_dir),
        "asset_paths": [],
    }
    catalog_live_report.append(terminal_record)
    with preserve_terminal_record(
        terminal_record,
        catalog_live_report,
        catalog_live_artifact_root,
        sample_started_at,
        record_property,
    ):
        missing = [
            key
            for key in sample.required_env
            if not catalog_live_env.get(key, "").strip()
        ]
        if missing:
            terminal_record["terminal"] = {
                "status": "skipped",
                "reason_code": "missing_required_environment",
                "missing_names": sorted(missing),
            }
            terminal_record["acceptance"] = {
                "overall": "failed",
                "reason_code": "missing_required_environment",
            }
            terminal_record["performance"] = {
                "total_seconds": round(time.monotonic() - sample_started_at, 3),
                "preflight_seconds": 0,
            }
            pytest.skip(
                "Missing required environment variables for live test: "
                + ", ".join(missing)
            )
        if provider_has_browser_route(sample.provider):
            require_local_browser_or_skip(
                _PytestSkipper(), catalog_live_env, provider=sample.provider
            )
        record_property("preflight_seconds", 0)
        record_property("preflight_navigation_count", 0)

        fetch_telemetry: dict[str, object] = {}
        try:
            envelope = fetch_envelope(
                sample.doi,
                transport=HttpTransport(),
                env=catalog_live_env,
                download_dir=provider_output_dir,
                artifact_mode="all",
                preferred_provider=sample.provider,
                asset_profile="body",
                telemetry=fetch_telemetry,
            )
        except PaperFetchFailure as exc:
            terminal_record["terminal"] = {
                "status": "failed",
                "reason_code": exc.status,
                "stage": exc.stage,
                "message": redact_text_for_diagnostics(exc.reason)[:1000],
            }
            terminal_record["performance"] = {
                "preflight_seconds": preflight_seconds,
                "fetch_wall_seconds": fetch_telemetry["fetch_wall_seconds"],
                "total_seconds": round(time.monotonic() - sample_started_at, 3),
            }
            terminal_record["source_trail"] = list(exc.source_trail or [])
            terminal_record["failure_details"] = exc.details
            terminal_record["fetch_diagnostics"] = fetch_browser_diagnostics(
                provider_output_dir,
                provider=sample.provider,
                doi=sample.doi,
            )
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
        total_seconds = round(time.monotonic() - sample_started_at, 3)
        fetch_diagnostics = fetch_browser_diagnostics(
            provider_output_dir,
            provider=sample.provider,
            doi=sample.doi,
        )
        performance_warning = None
        if (
            sample.provider == "pnas"
            and float(fetch_telemetry["fetch_wall_seconds"]) > 45
        ):
            performance_warning = (
                "PNAS fetch exceeded the observational 45 second target: "
                f"{fetch_telemetry['fetch_wall_seconds']:.3f}s"
            )
            warnings.warn(performance_warning, RuntimeWarning, stacklevel=1)
        record_property("fetch_wall_seconds", fetch_telemetry["fetch_wall_seconds"])
        record_property(
            "browser_navigation_count",
            fetch_diagnostics["browser_navigation_count"],
        )
        record_property(
            "dom_readiness_result", fetch_diagnostics.get("dom_readiness_result") or ""
        )
        record_property(
            "dom_readiness_seconds", fetch_diagnostics.get("dom_readiness_seconds") or 0
        )
        record_property("sample_total_seconds", total_seconds)
        record_property("performance_warning", performance_warning or "")
        success_record = {
            "provider": sample.provider,
            "backend": active_backend,
            "requested_backend": backend,
            "doi": normalize_doi(sample.doi),
            "terminal": {"status": "failed", "reason_code": "validation_pending"},
            "preflight": None,
            "fetch_diagnostics": fetch_diagnostics,
            "source": article.source,
            "source_trail": list(article.quality.source_trail),
            "acceptance": acceptance.model_dump(mode="json"),
            "performance": {
                "preflight_seconds": preflight_seconds,
                "fetch_wall_seconds": fetch_telemetry["fetch_wall_seconds"],
                "total_seconds": total_seconds,
                "preflight_navigation_count": 0,
                "browser_navigation_count": fetch_diagnostics[
                    "browser_navigation_count"
                ],
                "navigation_seconds": fetch_diagnostics["navigation_seconds"],
                "dom_readiness_result": fetch_diagnostics.get("dom_readiness_result"),
                "dom_readiness_seconds": fetch_diagnostics.get("dom_readiness_seconds"),
                "downloaded_asset_count": sum(
                    bool(asset.path) for asset in article.assets
                ),
                "assets": _asset_performance_summary(article),
                "warning": performance_warning,
            },
            "output_dir": str(provider_output_dir),
            "asset_paths": [str(asset.path) for asset in article.assets if asset.path],
        }
        terminal_record.clear()
        terminal_record.update(success_record)

        # Preserve the complete rendered body beside the original provider payload
        # and assets, so performance observations can be audited without refetching.
        markdown_path = provider_output_dir / "article.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(
            article.to_ai_markdown(
                include_refs="all", asset_profile="body", max_tokens="full_text"
            ),
            encoding="utf-8",
        )
        success_record["markdown_path"] = str(markdown_path)
        article_path = markdown_path.with_suffix(".json")
        article_path.write_text(
            json.dumps(
                redact_log_value(article.to_dict()), ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        success_record["article_path"] = str(article_path)

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
        assert acceptance.overall == OverallAcceptanceStatus.COMPLETE, (
            acceptance.to_json()
        )
        if sample.provider == "pnas":
            assert len(article.assets) == 4
            assert all(
                asset.path and asset.download_tier == "full_size"
                for asset in article.assets
            )
        terminal_record["terminal"] = {"status": "complete", "reason_code": "accepted"}


def test_aip_cold_start_stability_uses_html_for_five_fresh_profiles(
    catalog_live_env,
    catalog_live_artifact_root,
) -> None:
    if not RUN_AIP_COLD_STABILITY:
        pytest.skip(
            "Set PAPER_FETCH_RUN_AIP_COLD_STABILITY=1 to run repeated AIP cold starts."
        )

    require_local_browser_or_skip(_PytestSkipper(), catalog_live_env, provider="aip")

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

    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest(
                "Set PAPER_FETCH_RUN_LIVE=1 to run live publisher acceptance tests."
            )
        cls.env, cls.runtime_env_tempdir = build_isolated_live_env()

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
        try:
            article = fetch_article(
                "10.1016/0304-4165(96)00054-2",
                transport=HttpTransport(),
                env=self.env,
            )
        except PaperFetchFailure as exc:
            _skip_legal_access_boundary("elsevier", exc)
            raise

        self.assertEqual(article.doi, "10.1016/0304-4165(96)00054-2")
        self.assertEqual(article.source, "elsevier_pdf")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        acquisition = article.acquisition
        self.assertIsNotNone(acquisition)
        self.assertEqual(acquisition.provider, "elsevier")
        self.assertEqual(acquisition.representation, "pdf")
        self.assertIn(acquisition.route, {"pdf_api", "browser_pdf"})
        if acquisition.route == "pdf_api":
            self.assertEqual(acquisition.transport, "api")
            self.assertIn("fulltext:elsevier_pdf_api_ok", article.quality.source_trail)
            self.assertIn(
                "fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail
            )
        else:
            self.assertEqual(acquisition.transport, "browser")
            self.assertIn(
                "fulltext:elsevier_browser_pdf_ok", article.quality.source_trail
            )
        self.assertNotIn("fulltext:elsevier_html_ok", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
