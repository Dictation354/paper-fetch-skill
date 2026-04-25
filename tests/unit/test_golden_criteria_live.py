from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from paper_fetch import golden_criteria_live_cli
from paper_fetch.golden_criteria_live import (
    GoldenCriteriaLiveResult,
    GoldenCriteriaLiveSample,
    ISSUE_CATEGORIES,
    SUPPORTED_PROVIDERS,
    apply_expected_outcome,
    iter_golden_criteria_samples,
    issue_categories_for_result,
    load_manifest,
    materialize_fetch_artifacts,
    parse_review_summary,
    render_review_template,
    run_golden_criteria_live_review,
)
from paper_fetch.models import Asset, FetchEnvelope, Metadata, Quality, RenderOptions, Section
from paper_fetch.service import PaperFetchFailure

from ._paper_fetch_support import build_envelope, sample_article


def _provider_status_payload(**kwargs):
    return {
        "providers": [
            {
                "provider": "elsevier",
                "status": "ready",
                "available": True,
                "official_provider": True,
                "missing_env": [],
                "notes": [],
                "checks": [],
            },
            {
                "provider": "springer",
                "status": "ready",
                "available": True,
                "official_provider": True,
                "missing_env": [],
                "notes": [],
                "checks": [],
            },
            {
                "provider": "wiley",
                "status": "not_configured",
                "available": False,
                "official_provider": True,
                "missing_env": ["FLARESOLVERR_ENV_FILE"],
                "notes": [],
                "checks": [
                    {
                        "name": "runtime_env",
                        "status": "not_configured",
                        "message": "Wiley runtime is not configured.",
                        "missing_env": ["FLARESOLVERR_ENV_FILE"],
                        "details": {},
                    }
                ],
            },
            {
                "provider": "science",
                "status": "ready",
                "available": True,
                "official_provider": True,
                "missing_env": [],
                "notes": [],
                "checks": [],
            },
            {
                "provider": "pnas",
                "status": "ready",
                "available": True,
                "official_provider": True,
                "missing_env": [],
                "notes": [],
                "checks": [],
            },
        ]
    }


def _mini_manifest(tmpdir: Path) -> Path:
    manifest = {
        "samples": {
            "elsevier_fulltext": {
                "doi": "10.1016/fulltext",
                "publisher": "elsevier",
                "source_url": "https://example.test/elsevier",
                "fixture_family": "golden",
                "assets": {"original.xml": "fixtures/elsevier.xml"},
            },
            "elsevier_blocked_404": {
                "doi": "10.1016/S1575-1813(18)30261-4",
                "publisher": "elsevier",
                "source_url": "https://example.test/elsevier-404",
                "fixture_family": "golden",
                "assets": {"bilingual.xml": "fixtures/elsevier-bilingual.xml"},
                "expected_live_status": "metadata_only",
                "expected_review_status": "skipped",
                "out_of_scope_reason": "Intentional invalid DOI.",
            },
            "springer_metadata": {
                "doi": "10.1038/metadata",
                "publisher": "springer",
                "source_url": "https://example.test/springer",
                "fixture_family": "golden",
                "assets": {"original.html": "fixtures/springer.html"},
            },
            "wiley_not_configured": {
                "doi": "10.1111/notconfigured",
                "publisher": "wiley",
                "source_url": "https://example.test/wiley",
                "fixture_family": "golden",
                "assets": {"original.html": "fixtures/wiley.html"},
            },
            "science_rate_limited": {
                "doi": "10.1126/ratelimited",
                "publisher": "science",
                "source_url": "https://example.test/science",
                "fixture_family": "golden",
                "assets": {"original.html": "fixtures/science.html"},
            },
            "pnas_error": {
                "doi": "10.1073/error",
                "publisher": "pnas",
                "source_url": "https://example.test/pnas",
                "fixture_family": "golden",
                "assets": {"original.html": "fixtures/pnas.html"},
            },
            "tandf_skip": {
                "doi": "10.1080/skip",
                "publisher": "tandf",
                "source_url": "https://example.test/tandf",
                "fixture_family": "golden",
                "assets": {"bilingual.html": "fixtures/tandf.html"},
                "expected_live_status": "skipped_unsupported_provider",
                "expected_review_status": "skipped",
                "out_of_scope_reason": "Unsupported provider is intentional.",
            },
            "block_ignored": {
                "doi": "10.1000/block",
                "publisher": "springer",
                "source_url": "https://example.test/block",
                "fixture_family": "block",
                "assets": {"raw.html": "fixtures/block.html"},
            },
        }
    }
    manifest_path = tmpdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _metadata_only_envelope(doi: str) -> FetchEnvelope:
    return FetchEnvelope(
        doi=doi,
        source="metadata_only",
        has_fulltext=False,
        content_kind="metadata_only",
        has_abstract=True,
        warnings=["Full text was not available; returning metadata and abstract only."],
        source_trail=["fallback:metadata_only"],
        quality=Quality(has_fulltext=False, content_kind="metadata_only", has_abstract=True),
        article=None,
        markdown="# Metadata only\n",
        metadata=Metadata(title="Metadata Only", abstract="Abstract"),
    )


class GoldenCriteriaLiveTests(unittest.TestCase):
    def test_manifest_loader_selects_63_golden_samples_and_classifies_provider_support(self) -> None:
        samples = iter_golden_criteria_samples(load_manifest())

        self.assertEqual(len(samples), 63)
        supported = [sample for sample in samples if sample.supported]
        unsupported = [sample for sample in samples if not sample.supported]

        self.assertEqual(len(supported), 61)
        self.assertEqual({sample.provider for sample in unsupported}, {"sage", "tandf"})
        self.assertTrue(all(sample.provider in SUPPORTED_PROVIDERS for sample in supported))

    def test_runner_writes_reports_and_covers_live_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_path = _mini_manifest(root)
            asset_source = root / "figure-source.png"
            asset_source.write_bytes(b"figure")

            def fake_fetch(query, **kwargs):
                if query == "10.1016/fulltext":
                    article = sample_article()
                    article.doi = query
                    article.assets = [
                        Asset(
                            kind="figure",
                            heading="Figure 1",
                            caption="Example figure.",
                            path=str(asset_source),
                            section="body",
                        )
                    ]
                    return build_envelope(article)
                if query == "10.1016/S1575-1813(18)30261-4":
                    return _metadata_only_envelope(query)
                if query == "10.1038/metadata":
                    return _metadata_only_envelope(query)
                if query == "10.1126/ratelimited":
                    raise PaperFetchFailure("rate_limited", "Science rate limit is active.")
                if query == "10.1073/error":
                    raise RuntimeError("PNAS exploded")
                raise AssertionError(f"unexpected query {query}")

            report = run_golden_criteria_live_review(
                manifest_path=manifest_path,
                output_dir=root / "review",
                env={"PAPER_FETCH_RUN_LIVE": "1"},
                fetch_paper_fn=fake_fetch,
                provider_status_fn=_provider_status_payload,
                now=datetime(2026, 4, 23, tzinfo=timezone.utc),
            )

            statuses = {result.sample_id: result.status for result in report.results}
            self.assertEqual(statuses["elsevier_fulltext"], "fulltext")
            self.assertEqual(statuses["elsevier_blocked_404"], "metadata_only")
            self.assertEqual(statuses["springer_metadata"], "metadata_only")
            self.assertEqual(statuses["wiley_not_configured"], "not_configured")
            self.assertEqual(statuses["science_rate_limited"], "rate_limited")
            self.assertEqual(statuses["pnas_error"], "error")
            self.assertEqual(statuses["tandf_skip"], "skipped_unsupported_provider")

            output_root = Path(report.output_dir)
            self.assertTrue((output_root / "report.json").exists())
            self.assertTrue((output_root / "report.md").exists())
            self.assertTrue((output_root / "provider-status.json").exists())
            self.assertTrue((output_root / "manifest-snapshot.json").exists())

            sample_dir = output_root / "elsevier_fulltext"
            self.assertTrue((sample_dir / "fetch-envelope.json").exists())
            self.assertTrue((sample_dir / "article.json").exists())
            self.assertTrue((sample_dir / "extracted.md").exists())
            self.assertTrue((sample_dir / "body_assets" / "figure-source.png").exists())
            rendered = (sample_dir / "extracted.md").read_text(encoding="utf-8")
            self.assertIn("](body_assets/figure-source.png)", rendered)
            self.assertTrue((output_root / "wiley_not_configured" / "review.md").exists())
            reviews = {result.sample_id: result.review_status for result in report.results}
            self.assertEqual(reviews["elsevier_blocked_404"], "skipped")
            self.assertEqual(reviews["tandf_skip"], "skipped")
            issues = {result.sample_id: result.issue_categories for result in report.results}
            self.assertEqual(issues["elsevier_blocked_404"], [])
            self.assertEqual(issues["tandf_skip"], [])

            report_markdown = (output_root / "report.md").read_text(encoding="utf-8")
            self.assertIn("## Coverage Overview", report_markdown)
            self.assertIn("## Recurring Issue Groups", report_markdown)
            self.assertIn("## Prioritized Solutions", report_markdown)

    def test_materialize_fetch_artifacts_normalizes_body_assets_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_asset_dir = root / "downloads"
            source_asset_dir.mkdir()
            source_asset = source_asset_dir / "figure one.png"
            source_asset.write_bytes(b"figure")

            article = sample_article()
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="A figure.", path=str(source_asset), section="body")
            ]
            envelope = build_envelope(article)
            sample_dir = root / "sample"

            count = materialize_fetch_artifacts(
                envelope=envelope,
                sample_dir=sample_dir,
                render=RenderOptions(include_refs="all", asset_profile="body", max_tokens="full_text"),
            )

            self.assertEqual(count, 1)
            self.assertTrue((sample_dir / "body_assets" / "figure_one.png").exists())
            rendered = (sample_dir / "extracted.md").read_text(encoding="utf-8")
            self.assertIn("](body_assets/figure_one.png)", rendered)

    def test_review_template_and_parser_cover_all_review_statuses(self) -> None:
        for status, review_status, categories in [
            ("fulltext", "ok", []),
            ("fulltext", "issue", ["asset_download_failure"]),
            ("metadata_only", "blocked", ["live_fetch_blocked"]),
            ("skipped_unsupported_provider", "skipped", ["unsupported_provider"]),
        ]:
            with self.subTest(review_status=review_status):
                result = _result(status=status, review_status=review_status, categories=categories)
                rendered = render_review_template(result)
                parsed = parse_review_summary(rendered)
                self.assertEqual(parsed.review_status, review_status)
                self.assertEqual(parsed.issue_categories, categories)
                self.assertTrue(set(parsed.issue_categories).issubset(set(ISSUE_CATEGORIES)))

    def test_science_preview_accepted_is_not_an_asset_issue(self) -> None:
        article = sample_article()
        envelope = build_envelope(article)
        envelope.source_trail = [
            "download:science_assets_saved_profile_body",
            "download:science_assets_preview_accepted",
        ]
        envelope.warnings = [
            "Science figure downloads used preview images for 4 asset(s), but their saved dimensions met the acceptance threshold."
        ]

        categories = issue_categories_for_result(status="fulltext", envelope=envelope)

        self.assertNotIn("asset_download_failure", categories)

    def test_formula_only_preview_fallback_is_not_an_asset_issue(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(
                kind="formula",
                heading="Formula 1",
                path="/tmp/formula-1.png",
                download_tier="preview",
            )
        ]
        envelope = build_envelope(article)
        envelope.source_trail = [
            "download:wiley_assets_saved_profile_body",
            "download:wiley_assets_preview_fallback",
        ]
        envelope.warnings = [
            "Wiley figure downloads fell back to preview images for 1 asset(s) because full-size/original downloads were unavailable."
        ]

        categories = issue_categories_for_result(status="fulltext", envelope=envelope)

        self.assertNotIn("asset_download_failure", categories)

    def test_non_formula_preview_fallback_remains_an_asset_issue(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(
                kind="figure",
                heading="Figure 1",
                path="/tmp/figure-1.png",
                download_tier="preview",
            )
        ]
        envelope = build_envelope(article)
        envelope.source_trail = [
            "download:wiley_assets_saved_profile_body",
            "download:wiley_assets_preview_fallback",
        ]
        envelope.warnings = [
            "Wiley figure downloads fell back to preview images for 1 asset(s) because full-size/original downloads were unavailable."
        ]

        categories = issue_categories_for_result(status="fulltext", envelope=envelope)

        self.assertIn("asset_download_failure", categories)

    def test_review_template_marks_accepted_science_preview_as_non_issue(self) -> None:
        result = GoldenCriteriaLiveResult(
            sample_id="10.1126_science.accepted_preview",
            provider="science",
            doi="10.1126/science.accepted_preview",
            title="Science accepted preview",
            status="fulltext",
            content_kind="fulltext",
            source="science",
            has_fulltext=True,
            warnings=[
                "Science figure downloads used preview images for 4 asset(s), but their saved dimensions met the acceptance threshold."
            ],
            source_trail=[
                "download:science_assets_saved_profile_body",
                "download:science_assets_preview_accepted",
            ],
            asset_count=4,
            sample_output_dir="/tmp/sample",
            review_status="ok",
            issue_categories=[],
            elapsed_seconds=0.0,
        )

        rendered = render_review_template(result)
        parsed = parse_review_summary(rendered)

        self.assertEqual(parsed.review_status, "ok")
        self.assertEqual(parsed.issue_categories, [])
        self.assertIn("accepted diagnostic label", rendered)
        self.assertIn("Do not classify this tier label alone as `asset_download_failure`", rendered)
        self.assertNotIn("No issue recorded yet. Read extracted.md", rendered)

    def test_authorless_briefing_does_not_trigger_metadata_loss(self) -> None:
        article = sample_article()
        article.metadata.authors = []
        article.sections = [
            Section(heading="The question", level=2, kind="body", text="Question text " * 10),
            Section(heading="The discovery", level=2, kind="body", text="Discovery text " * 10),
            Section(heading="The implications", level=2, kind="body", text="Implications text " * 10),
            Section(heading="Expert opinion", level=2, kind="body", text="Expert text " * 10),
            Section(heading="Behind the paper", level=2, kind="body", text="Behind text " * 10),
            Section(heading="From the editor", level=2, kind="body", text="Editor text " * 10),
        ]
        envelope = build_envelope(article)

        categories = issue_categories_for_result(status="fulltext", envelope=envelope)

        self.assertNotIn("metadata_loss", categories)

    def test_authorless_regular_article_still_triggers_metadata_loss(self) -> None:
        article = sample_article()
        article.metadata.authors = []
        envelope = build_envelope(article)

        categories = issue_categories_for_result(status="fulltext", envelope=envelope)

        self.assertIn("metadata_loss", categories)

    def test_expected_metadata_only_outcome_applies_to_blocked_live_fetch_status(self) -> None:
        sample = GoldenCriteriaLiveSample(
            sample_id="elsevier_invalid",
            doi="10.1016/S1575-1813(18)30261-4",
            provider="elsevier",
            title="Invalid DOI",
            source_url="https://example.test/article",
            landing_url="https://example.test/article",
            expected_live_status="metadata_only",
            expected_review_status="skipped",
            out_of_scope_reason="Intentional invalid DOI.",
        )
        result = GoldenCriteriaLiveResult(
            sample_id=sample.sample_id,
            provider=sample.provider,
            doi=sample.doi,
            title=sample.title,
            status="blocked_live_fetch",
            content_kind="metadata_only",
            source="metadata_only",
            has_fulltext=False,
            warnings=[],
            source_trail=[],
            asset_count=0,
            sample_output_dir="/tmp/sample",
            review_status="blocked",
            issue_categories=["live_fetch_blocked"],
            elapsed_seconds=0.0,
        )

        applied = apply_expected_outcome(sample, result)

        self.assertTrue(applied.expected_outcome)
        self.assertEqual(applied.review_status, "skipped")
        self.assertEqual(applied.issue_categories, [])

    def test_script_main_invokes_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "review"
            report = type(
                "StubReport",
                (),
                {
                    "output_dir": str(output_dir),
                    "total_samples": 3,
                },
            )()
            captured: dict[str, object] = {}
            original_loader = golden_criteria_live_cli._load_live_review_exports
            golden_criteria_live_cli._load_live_review_exports = lambda: (
                SUPPORTED_PROVIDERS,
                ["elsevier", "springer"],
                lambda **kwargs: captured.update(kwargs) or report,
                lambda: output_dir,
            )
            try:
                exit_code = golden_criteria_live_cli.main(["--output-dir", str(output_dir)])
            finally:
                golden_criteria_live_cli._load_live_review_exports = original_loader

            self.assertEqual(exit_code, 0)
            self.assertEqual(captured["output_dir"], output_dir)


def _result(*, status: str, review_status: str, categories: list[str]):
    from paper_fetch.golden_criteria_live import GoldenCriteriaLiveResult

    return GoldenCriteriaLiveResult(
        sample_id=f"sample_{review_status}",
        provider="elsevier",
        doi="10.1000/example",
        title="Example",
        status=status,
        content_kind="fulltext" if status == "fulltext" else None,
        source="elsevier_xml" if status == "fulltext" else None,
        has_fulltext=status == "fulltext",
        warnings=[],
        source_trail=[],
        asset_count=0,
        sample_output_dir="/tmp/sample",
        review_status=review_status,
        issue_categories=categories,
        elapsed_seconds=0.0,
    )
