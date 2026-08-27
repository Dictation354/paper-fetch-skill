"""Live review artifact generation for the golden criteria fixture catalog."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, UTC
import json
import logging
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.parse
from typing import Any
from collections.abc import Callable, Mapping, Sequence

import yaml

from paper_fetch.config import build_runtime_env, resolve_repo_root
from paper_fetch.http import HttpTransport
from paper_fetch.logging_utils import emit_structured_log
from paper_fetch.models import Asset, FetchEnvelope, RenderOptions
from paper_fetch.provider_catalog import (
    official_provider_names,
    provider_has_browser_route,
)
from paper_fetch.providers.registry import build_clients
from paper_fetch.quality.issues import is_authorless_briefing_like
from paper_fetch.quality.reason_codes import FULLTEXT, INSUFFICIENT_BODY
from paper_fetch.reason_codes import (
    ABSTRACT_ONLY,
    ERROR,
    METADATA_ONLY,
    NO_RESULT,
    NOT_CONFIGURED,
    OK,
    RATE_LIMITED,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, PaperFetchFailure, fetch_paper
from paper_fetch.tracing import nearest_rank_percentile
from paper_fetch.utils import normalize_text, sanitize_filename
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.workflow.batch_routing import provider_lane_limit
from paper_fetch.workflow.batch_runner import (
    BatchFailure,
    run_batch,
)
from paper_fetch.workflow.rendering import rewrite_markdown_asset_links

logger = logging.getLogger("paper_fetch_devtools.golden_criteria.live")

SUPPORTED_PROVIDERS = official_provider_names()
UNSUPPORTED_PROVIDER_STATUS = "skipped_unsupported_provider"
DEFAULT_REVIEW_ROOT_NAME = "golden-criteria-review"
RUN_LIVE_ENV_VAR = "PAPER_FETCH_RUN_LIVE"
REVIEW_STATUS_VALUES = ("ok", "issue", "blocked", "skipped")
ISSUE_CATEGORIES = (
    "content_missing",
    "noise_leak",
    "section_structure",
    "reference_loss",
    "figure_table_loss",
    "asset_download_failure",
    "asset_fidelity_degraded",
    "asset_placeholder_suspected",
    "asset_remote_only",
    "math_loss",
    "metadata_loss",
    "route_source_mismatch",
    "live_fetch_blocked",
    "unsupported_provider",
)
QUALITY_FLAG_CATEGORY_MAP = {
    INSUFFICIENT_BODY: "content_missing",
    "weak_body_structure": "section_structure",
    "table_fallback_present": "figure_table_loss",
    "table_semantic_loss": "figure_table_loss",
    "formula_fallback_present": "math_loss",
    "formula_missing_present": "math_loss",
}
MARKDOWN_IMAGE_URL_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
MARKDOWN_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+")
REFERENCES_HEADING_PATTERN = re.compile(
    r"^\s{0,3}#{1,6}\s+references(?:\s|\(|$)", flags=re.IGNORECASE
)
NUMBERED_REFERENCE_ITEM_PATTERN = re.compile(r"^\s*(?:\d{1,4}[.)]|\[\d{1,4}\])\s+\S")
BULLET_REFERENCE_ITEM_PATTERN = re.compile(r"^\s*[-*+]\s+\S")
IEEE_MEDIASTORE_HOST = "ieeexplore.ieee.org"
IEEE_MEDIASTORE_PATH_TOKEN = "/mediastore/ieee/content/media/"
SOLUTION_BY_CATEGORY = {
    "live_fetch_blocked": (
        "Stabilize live provider setup and fallback handling.",
        "Check provider_status, runtime env, rate-limit state, and the provider fetch waterfall for affected samples.",
    ),
    "unsupported_provider": (
        "Add provider support or keep the sample explicitly out of live review runs.",
        "Implement a provider route for the publisher, or document why the fixture is reference-only.",
    ),
    "asset_download_failure": (
        "Improve body asset extraction and download resilience.",
        "Inspect figure/table candidates, full-size fallbacks, and download failure diagnostics for affected samples.",
    ),
    "asset_fidelity_degraded": (
        "Improve archived asset fidelity.",
        "Inspect fallback previews or conversion losses without treating successful local downloads as failures.",
    ),
    "asset_placeholder_suspected": (
        "Replace suspected placeholder assets.",
        "Inspect tiny, invalid, or duplicate archived payloads and recover the real publisher asset.",
    ),
    "asset_remote_only": (
        "Complete requested asset archiving.",
        "Inspect requested assets that retained only remote links despite archive being enabled.",
    ),
    "content_missing": (
        "Recover missing article body content.",
        "Compare generated Markdown against original fixture HTML/XML and update provider extraction selectors or XML traversal.",
    ),
    "section_structure": (
        "Normalize section detection and heading order.",
        "Add regression coverage for malformed or missing headings in the affected provider path.",
    ),
    "reference_loss": (
        "Preserve reference sections in rendered Markdown and ArticleModel references.",
        "Add provider-specific reference extraction tests using affected samples.",
    ),
    "figure_table_loss": (
        "Preserve declared figures and tables even when rendering is partial.",
        "Track declared versus rendered assets and add visible Markdown placeholders for dropped tables or figures.",
    ),
    "math_loss": (
        "Improve formula extraction and fallback visibility.",
        "Add tests around MathML/TeX examples from affected samples and surface degraded conversion notes.",
    ),
    "metadata_loss": (
        "Recover missing title, author, DOI, or publication metadata.",
        "Compare provider metadata extraction against fixture metadata and Crossref fallback merge behavior.",
    ),
    "route_source_mismatch": (
        "Keep live provider results on the expected route source.",
        "Compare the sample purpose with provider_manifest.route_sources and fix silent fallback to the wrong fulltext source.",
    ),
    "noise_leak": (
        "Tighten provider noise filtering.",
        "Add negative assertions for leaked navigation, access prompts, related articles, and publisher chrome.",
    ),
}


@dataclass(frozen=True)
class GoldenCriteriaLiveSample:
    sample_id: str
    doi: str
    provider: str
    title: str
    source_url: str
    landing_url: str
    assets: dict[str, str] = field(default_factory=dict)
    expected_live_status: str | None = None
    expected_review_status: str | None = None
    out_of_scope_reason: str | None = None
    purpose: str | None = None
    route_kind: str | None = None
    fixture_purposes: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.provider in SUPPORTED_PROVIDERS


@dataclass(frozen=True)
class ReviewSummary:
    review_status: str
    issue_categories: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GoldenCriteriaLiveResult:
    sample_id: str
    provider: str
    doi: str
    title: str
    status: str
    content_kind: str | None
    source: str | None
    has_fulltext: bool
    warnings: list[str]
    source_trail: list[str]
    asset_count: int
    sample_output_dir: str
    review_status: str
    issue_categories: list[str]
    elapsed_seconds: float
    stage_timings: dict[str, float] = field(default_factory=dict)
    http_cache_stats: dict[str, int] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    expected_outcome: bool = False
    out_of_scope_reason: str | None = None
    asset_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    acceptance: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    failure_diagnostics: dict[str, Any] = field(default_factory=dict)
    diagnostic_artifacts: list[dict[str, Any]] = field(default_factory=list)
    worker_started_at: float | None = None
    worker_finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderReviewSummary:
    provider: str
    attempted: int
    status_counts: dict[str, int]
    fulltext: int
    blocked: int
    skipped: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IssueReviewSummary:
    issue_category: str
    count: int
    sample_ids: list[str]
    dois: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SolutionRecommendation:
    priority: int
    issue_category: str
    title: str
    recommendation: str
    affected_count: int
    sample_ids: list[str]
    suggested_test: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerformanceStageSummary:
    provider: str
    route: str
    stage: str
    sample_count: int
    observed_seconds: float | None = None
    p50_seconds: float | None = None
    p95_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GoldenCriteriaLiveReport:
    generated_at: str
    output_dir: str
    total_samples: int
    supported_samples: int
    skipped_samples: int
    provider_status: dict[str, Any]
    results: list[GoldenCriteriaLiveResult]
    summary_by_provider: list[ProviderReviewSummary]
    summary_by_issue: list[IssueReviewSummary]
    performance_by_provider_route_stage: list[PerformanceStageSummary]
    solution_recommendations: list[SolutionRecommendation]
    concurrency: int = 1
    completion_order: list[str] = field(default_factory=list)
    lane_limits: dict[str, int] = field(default_factory=dict)
    provider_peak_in_flight: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "output_dir": self.output_dir,
            "total_samples": self.total_samples,
            "supported_samples": self.supported_samples,
            "skipped_samples": self.skipped_samples,
            "provider_status": self.provider_status,
            "results": [item.to_dict() for item in self.results],
            "summary_by_provider": [
                item.to_dict() for item in self.summary_by_provider
            ],
            "summary_by_issue": [item.to_dict() for item in self.summary_by_issue],
            "performance_by_provider_route_stage": [
                item.to_dict() for item in self.performance_by_provider_route_stage
            ],
            "solution_recommendations": [
                item.to_dict() for item in self.solution_recommendations
            ],
            "concurrency": self.concurrency,
            "completion_order": list(self.completion_order),
            "lane_limits": dict(self.lane_limits),
            "provider_peak_in_flight": dict(self.provider_peak_in_flight),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n", encoding="utf-8")

    def to_markdown(self) -> str:
        lines = [
            "# Golden Criteria Live Review",
            "",
            "## Coverage Overview",
            "",
            f"- Generated: `{self.generated_at}`",
            f"- Output directory: `{self.output_dir}`",
            f"- Total golden samples: `{self.total_samples}`",
            f"- Supported live samples: `{self.supported_samples}`",
            f"- Skipped unsupported samples: `{self.skipped_samples}`",
            f"- Concurrency: `{self.concurrency}`",
            f"- Lane limits: `{json.dumps(self.lane_limits, sort_keys=True)}`",
            "- Provider peak in-flight: "
            f"`{json.dumps(self.provider_peak_in_flight, sort_keys=True)}`",
            "",
            "## Provider Summary",
            "",
            "| Provider | Attempted | Fulltext | Blocked | Skipped | Status Counts |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
        for summary in self.summary_by_provider:
            counts = ", ".join(
                f"{key}={value}"
                for key, value in sorted(summary.status_counts.items())
                if value
            )
            lines.append(
                f"| `{summary.provider}` | {summary.attempted} | {summary.fulltext} | "
                f"{summary.blocked} | {summary.skipped} | {counts or '-'} |"
            )

        lines.extend(
            [
                "",
                "## Sample Results",
                "",
                "| Sample | Provider | DOI | Status | Content | Source | Assets | Seconds | Resolve | Metadata | Fulltext | Browser | DOM Ready | HTTP | Retry | Asset | Formula | Render | Fetch | Materialize | Review | Issues |",
                "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for result in self.results:
            issues = ", ".join(f"`{item}`" for item in result.issue_categories) or "-"
            sample_link = (
                f"[{result.sample_id}]({Path(result.sample_output_dir).name}/review.md)"
            )
            resolve_seconds = result.stage_timings.get("resolve_seconds", 0.0)
            metadata_seconds = result.stage_timings.get("metadata_seconds", 0.0)
            fulltext_seconds = result.stage_timings.get("fulltext_seconds", 0.0)
            browser_seconds = result.stage_timings.get("browser_seconds", 0.0)
            dom_readiness_seconds = result.stage_timings.get(
                "dom_readiness_seconds", 0.0
            )
            http_seconds = result.stage_timings.get("http_seconds", 0.0)
            retry_seconds = result.stage_timings.get("retry_seconds", 0.0)
            asset_seconds = result.stage_timings.get("asset_seconds", 0.0)
            formula_seconds = result.stage_timings.get("formula_seconds", 0.0)
            render_seconds = result.stage_timings.get("render_seconds", 0.0)
            fetch_seconds = result.stage_timings.get("fetch_seconds", 0.0)
            materialize_seconds = result.stage_timings.get("materialize_seconds", 0.0)
            lines.append(
                f"| {sample_link} | `{result.provider}` | `{result.doi}` | `{result.status}` | "
                f"`{result.content_kind or '-'}` | `{result.source or '-'}` | {result.asset_count} | "
                f"{result.elapsed_seconds:.3f} | {resolve_seconds:.3f} | {metadata_seconds:.3f} | "
                f"{fulltext_seconds:.3f} | {browser_seconds:.3f} | "
                f"{dom_readiness_seconds:.3f} | {http_seconds:.3f} | "
                f"{retry_seconds:.3f} | {asset_seconds:.3f} | {formula_seconds:.3f} | "
                f"{render_seconds:.3f} | {fetch_seconds:.3f} | {materialize_seconds:.3f} | "
                f"`{result.review_status}` | {issues} |"
            )

        lines.extend(
            [
                "",
                "## Provider Route Performance",
                "",
                "| Provider | Route | Stage | Samples | Observed | p50 | p95 |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for performance_summary in self.performance_by_provider_route_stage:
            observed = (
                f"{performance_summary.observed_seconds:.3f}"
                if performance_summary.observed_seconds is not None
                else "-"
            )
            p50 = (
                f"{performance_summary.p50_seconds:.3f}"
                if performance_summary.p50_seconds is not None
                else "-"
            )
            p95 = (
                f"{performance_summary.p95_seconds:.3f}"
                if performance_summary.p95_seconds is not None
                else "-"
            )
            lines.append(
                f"| `{performance_summary.provider}` | `{performance_summary.route}` | "
                f"`{performance_summary.stage}` | {performance_summary.sample_count} | "
                f"{observed} | {p50} | {p95} |"
            )

        lines.extend(
            [
                "",
                "## Recurring Issue Groups",
                "",
                "| Issue Category | Count | Sample IDs |",
                "| --- | ---: | --- |",
            ]
        )
        if self.summary_by_issue:
            for issue_summary in self.summary_by_issue:
                sample_ids = (
                    ", ".join(f"`{item}`" for item in issue_summary.sample_ids) or "-"
                )
                lines.append(
                    f"| `{issue_summary.issue_category}` | {issue_summary.count} | {sample_ids} |"
                )
        else:
            lines.append("| `none` | 0 | - |")

        lines.extend(
            [
                "",
                "## Prioritized Solutions",
                "",
            ]
        )
        if self.solution_recommendations:
            for item in self.solution_recommendations:
                sample_ids = (
                    ", ".join(f"`{sample_id}`" for sample_id in item.sample_ids) or "-"
                )
                lines.extend(
                    [
                        f"{item.priority}. **{item.title}**",
                        f"   Issue: `{item.issue_category}`; affected samples: {item.affected_count}; examples: {sample_ids}.",
                        f"   Recommendation: {item.recommendation}",
                        f"   Suggested test: {item.suggested_test}",
                        "",
                    ]
                )
        else:
            lines.append("No recurring issues have been recorded yet.")
        return "\n".join(lines).rstrip() + "\n"

    def write_markdown(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")


FetchPaperFn = Callable[..., FetchEnvelope]
ProviderStatusFn = Callable[..., dict[str, Any]]


def default_manifest_path() -> Path:
    return (
        resolve_repo_root() / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    )


def provider_manifest_path(provider: str) -> Path:
    return resolve_repo_root() / "onboarding" / "manifests" / f"{provider}.yml"


def timestamped_review_output_dir(*, now: datetime | None = None) -> Path:
    active_now = now or datetime.now(UTC)
    timestamp = active_now.strftime("%Y%m%d-%H%M%S")
    return resolve_repo_root() / "live-downloads" / DEFAULT_REVIEW_ROOT_NAME / timestamp


def ensure_live_opt_in(env: Mapping[str, str]) -> None:
    if normalize_text(env.get(RUN_LIVE_ENV_VAR)) != "1":
        raise RuntimeError(
            f"Set {RUN_LIVE_ENV_VAR}=1 to run the golden criteria live review pipeline."
        )


def load_manifest(manifest_path: Path | None = None) -> dict[str, Any]:
    path = manifest_path or default_manifest_path()
    return json.loads(path.read_text(encoding="utf-8"))


def load_provider_manifest(provider: str) -> dict[str, Any] | None:
    path = provider_manifest_path(provider)
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def iter_golden_criteria_samples(
    manifest: Mapping[str, Any],
) -> list[GoldenCriteriaLiveSample]:
    samples: list[GoldenCriteriaLiveSample] = []
    for sample_id, raw_sample in (manifest.get("samples") or {}).items():
        if not isinstance(raw_sample, Mapping):
            continue
        if str(raw_sample.get("fixture_family") or "golden") != "golden":
            continue
        doi = normalize_text(raw_sample.get("doi")) or str(sample_id)
        provider = normalize_text(raw_sample.get("publisher")).lower()
        source_url = normalize_text(raw_sample.get("source_url"))
        landing_url = normalize_text(raw_sample.get("landing_url")) or source_url
        title = normalize_text(raw_sample.get("title")) or doi
        assets = {
            str(name): str(path)
            for name, path in (raw_sample.get("assets") or {}).items()
            if isinstance(name, str) and isinstance(path, str)
        }
        samples.append(
            GoldenCriteriaLiveSample(
                sample_id=str(sample_id),
                doi=doi,
                provider=provider,
                title=title,
                source_url=source_url,
                landing_url=landing_url,
                assets=assets,
                expected_live_status=normalize_text(
                    raw_sample.get("expected_live_status")
                )
                or None,
                expected_review_status=normalize_text(
                    raw_sample.get("expected_review_status")
                ).lower()
                or None,
                out_of_scope_reason=normalize_text(
                    raw_sample.get("out_of_scope_reason")
                )
                or None,
                purpose=normalize_text(raw_sample.get("purpose")) or None,
                route_kind=normalize_text(raw_sample.get("route_kind")) or None,
                fixture_purposes=tuple(
                    normalize_text(item)
                    for item in (raw_sample.get("fixture_purposes") or [])
                    if normalize_text(item)
                ),
            )
        )
    return samples


def select_samples(
    samples: Sequence[GoldenCriteriaLiveSample],
    *,
    providers: Sequence[str] | None = None,
    sample_ids: Sequence[str] | None = None,
) -> list[GoldenCriteriaLiveSample]:
    provider_filter = {
        normalize_text(item).lower()
        for item in (providers or [])
        if normalize_text(item)
    }
    sample_filter = {
        normalize_text(item) for item in (sample_ids or []) if normalize_text(item)
    }
    selected = []
    for sample in samples:
        if provider_filter and sample.provider not in provider_filter:
            continue
        if (
            sample_filter
            and sample.sample_id not in sample_filter
            and sample.doi not in sample_filter
        ):
            continue
        selected.append(sample)
    return selected


def schedule_supported_samples(
    samples: Sequence[GoldenCriteriaLiveSample],
) -> list[GoldenCriteriaLiveSample]:
    grouped: dict[str, list[GoldenCriteriaLiveSample]] = defaultdict(list)
    for sample in samples:
        if sample.supported:
            grouped[sample.provider].append(sample)

    scheduled: list[GoldenCriteriaLiveSample] = []
    max_count = max(
        (len(grouped.get(provider, [])) for provider in SUPPORTED_PROVIDERS), default=0
    )
    for index in range(max_count):
        for provider in SUPPORTED_PROVIDERS:
            provider_samples = grouped.get(provider, [])
            if index < len(provider_samples):
                scheduled.append(provider_samples[index])
    return scheduled


def provider_status_payload(
    *,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    runtime_env = build_runtime_env(env)
    active_transport = transport or HttpTransport()
    clients = build_clients(active_transport, runtime_env)
    providers: list[dict[str, Any]] = []
    for provider_name in SUPPORTED_PROVIDERS:
        client = clients.get(provider_name)
        if client is None:
            providers.append(
                {
                    "provider": provider_name,
                    "status": ERROR,
                    "available": False,
                    "official_provider": True,
                    "missing_env": [],
                    "notes": [f"{provider_name} is not registered."],
                    "checks": [],
                }
            )
            continue
        try:
            providers.append(client.probe_status().to_dict())
        except Exception as exc:  # pragma: no cover - defensive live diagnostics
            providers.append(
                {
                    "provider": provider_name,
                    "status": ERROR,
                    "available": False,
                    "official_provider": bool(
                        getattr(client, "official_provider", True)
                    ),
                    "missing_env": [],
                    "notes": [f"Provider diagnostics failed unexpectedly: {exc}"],
                    "checks": [],
                }
            )
    return {"providers": providers}


def sample_output_dir(output_root: Path, sample: GoldenCriteriaLiveSample) -> Path:
    return output_root / sanitize_filename(sample.sample_id)


def classify_envelope_status(
    sample: GoldenCriteriaLiveSample, envelope: FetchEnvelope
) -> tuple[str, str | None, str | None]:
    if envelope.content_kind == FULLTEXT:
        return FULLTEXT, None, None

    source_trail = set(envelope.source_trail)
    for status in (NOT_CONFIGURED, RATE_LIMITED):
        if f"fulltext:{sample.provider}_{status}" in source_trail:
            return status, status, _first_non_generic_warning(envelope.warnings)
    if (
        f"fulltext:{sample.provider}_fail" in source_trail
        or f"fulltext:{sample.provider}_not_usable" in source_trail
    ):
        return (
            "blocked_live_fetch",
            NO_RESULT,
            _first_non_generic_warning(envelope.warnings),
        )
    if envelope.content_kind in {ABSTRACT_ONLY, METADATA_ONLY}:
        return METADATA_ONLY, None, _first_non_generic_warning(envelope.warnings)
    return (
        "blocked_live_fetch",
        "blocked_live_fetch",
        _first_non_generic_warning(envelope.warnings),
    )


def _first_non_generic_warning(warnings: Sequence[str]) -> str | None:
    for warning in warnings:
        text = normalize_text(warning)
        if (
            text
            and text
            != "Full text was not available; returning metadata and abstract only."
        ):
            return text
    return normalize_text(warnings[0]) if warnings else None


def issue_categories_for_result(
    *,
    status: str,
    envelope: FetchEnvelope | None = None,
    unsupported_provider: bool = False,
) -> list[str]:
    categories: list[str] = []
    if unsupported_provider:
        categories.append("unsupported_provider")
    elif status != FULLTEXT:
        categories.append("live_fetch_blocked")

    if envelope is not None:
        asset_issue_codes = {
            normalize_text(code).lower()
            for code in envelope.quality.asset_summary.issue_codes
            if normalize_text(code)
        }
        categories.extend(
            code
            for code in (
                "asset_download_failure",
                "asset_fidelity_degraded",
                "asset_placeholder_suspected",
                "asset_remote_only",
            )
            if code in asset_issue_codes
        )
        if _markdown_references_block_mixes_numbered_and_bullet_items(
            envelope.markdown
        ):
            categories.append("reference_loss")
        for flag in envelope.quality.flags:
            category = QUALITY_FLAG_CATEGORY_MAP.get(normalize_text(flag).lower())
            if category:
                categories.append(category)
        if (
            envelope.article is not None
            and not envelope.article.metadata.authors
            and not is_authorless_briefing_like(envelope.article)
        ):
            categories.append("metadata_loss")
    return [category for category in ISSUE_CATEGORIES if category in set(categories)]


def _sample_purposes(sample: GoldenCriteriaLiveSample) -> tuple[str, ...]:
    purposes = [
        purpose for purpose in (sample.purpose, *sample.fixture_purposes) if purpose
    ]
    return tuple(dict.fromkeys(purposes))


def _expected_source_for_sample(
    sample: GoldenCriteriaLiveSample,
    provider_manifest: Mapping[str, Any] | None,
) -> str | None:
    if not provider_manifest:
        return None
    route_sources = provider_manifest.get("route_sources")
    if not isinstance(route_sources, Mapping):
        return None
    route_kind = normalize_text(sample.route_kind).lower()
    purposes = set(_sample_purposes(sample))
    if "pdf_fallback" in purposes or route_kind == "pdf_fallback":
        return normalize_text(route_sources.get("pdf_fallback")) or None
    main_path = provider_manifest.get("main_path")
    if isinstance(main_path, Sequence) and not isinstance(main_path, (str, bytes)):
        for step in main_path:
            step_name = normalize_text(step)
            if step_name in {"landing_html", "article_html", "xml"}:
                expected = normalize_text(route_sources.get(step_name))
                if expected:
                    return expected
    return None


def route_source_issue_categories(
    sample: GoldenCriteriaLiveSample,
    *,
    source: str | None,
    status: str,
    provider_manifest: Mapping[str, Any] | None,
) -> list[str]:
    if status != FULLTEXT:
        return []
    expected_source = _expected_source_for_sample(sample, provider_manifest)
    if not expected_source:
        return []
    if normalize_text(source) == expected_source:
        return []
    return ["route_source_mismatch"]


def _markdown_contract_for_sample(
    sample: GoldenCriteriaLiveSample,
    provider_manifest: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if not provider_manifest:
        return None
    purposes = _sample_purposes(sample)
    markdown_contract = provider_manifest.get("markdown_contract")
    if isinstance(markdown_contract, Mapping):
        for purpose in purposes:
            contract = markdown_contract.get(purpose)
            if (
                isinstance(contract, Mapping)
                and normalize_text(contract.get("doi")) == sample.doi
            ):
                return contract
    for extra_fixture in provider_manifest.get("extra_fixtures") or []:
        if not isinstance(extra_fixture, Mapping):
            continue
        if normalize_text(extra_fixture.get("doi")) != sample.doi:
            continue
        contract = extra_fixture.get("markdown_contract")
        if isinstance(contract, Mapping):
            return contract
    return None


def markdown_contract_issue_categories(
    sample: GoldenCriteriaLiveSample,
    *,
    markdown: str | None,
    provider_manifest: Mapping[str, Any] | None,
) -> list[str]:
    contract = _markdown_contract_for_sample(sample, provider_manifest)
    if not contract:
        return []
    text = markdown or ""
    categories: set[str] = set()
    for value in contract.get("must_include") or []:
        if str(value) not in text:
            categories.add("content_missing")
    for value in contract.get("must_not_include") or []:
        if str(value) in text:
            categories.add("noise_leak")
    for pattern in contract.get("must_match") or []:
        try:
            matched = re.search(str(pattern), text) is not None
        except re.error:
            matched = False
        if not matched:
            categories.add("content_missing")
    count_equals = contract.get("count_equals")
    if isinstance(count_equals, Mapping):
        for value, expected_count in count_equals.items():
            try:
                expected_int = int(expected_count)
            except (TypeError, ValueError):
                continue
            if text.count(str(value)) != expected_int:
                categories.add("content_missing")
    return [category for category in ISSUE_CATEGORIES if category in categories]


def _dedupe_issue_categories(categories: Sequence[str]) -> list[str]:
    category_set = set(categories)
    return [category for category in ISSUE_CATEGORIES if category in category_set]


def _markdown_image_urls(markdown: str | None) -> list[str]:
    return [
        normalize_text(match.group(1)).strip("<>")
        for match in MARKDOWN_IMAGE_URL_PATTERN.finditer(markdown or "")
    ]


def _markdown_references_block_mixes_numbered_and_bullet_items(
    markdown: str | None,
) -> bool:
    in_references = False
    has_numbered_item = False
    has_bullet_item = False
    for line in (markdown or "").splitlines():
        if REFERENCES_HEADING_PATTERN.match(line):
            in_references = True
            has_numbered_item = False
            has_bullet_item = False
            continue
        if not in_references:
            continue
        if MARKDOWN_HEADING_PATTERN.match(line):
            if has_numbered_item and has_bullet_item:
                return True
            in_references = False
            continue
        if NUMBERED_REFERENCE_ITEM_PATTERN.match(line):
            has_numbered_item = True
        elif BULLET_REFERENCE_ITEM_PATTERN.match(line):
            has_bullet_item = True
        if has_numbered_item and has_bullet_item:
            return True
    return has_numbered_item and has_bullet_item


def _is_ieee_mediastore_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(
        normalize_text(url) if not url.startswith("//") else f"https:{url}"
    )
    return (
        normalize_text(parsed.netloc).lower().endswith(IEEE_MEDIASTORE_HOST)
        and IEEE_MEDIASTORE_PATH_TOKEN in normalize_text(parsed.path).lower()
    )


def _reference_candidates(value: str | None) -> set[str]:
    normalized = normalize_text(value).strip("<>")
    if not normalized:
        return set()
    parsed = urllib.parse.urlsplit(normalized)
    path = parsed.path or normalized
    raw_candidates = {
        normalized,
        path,
        urllib.parse.unquote(normalized),
        urllib.parse.unquote(path),
    }
    candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        candidate = (
            re.sub(r"/+", "/", normalize_text(raw_candidate).replace("\\", "/"))
            .strip()
            .removeprefix("./")
        )
        if candidate:
            candidates.add(candidate)
            candidates.add(candidate.lstrip("/"))
    return candidates


def _reference_basename(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _references_match(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    left_basenames = {
        _reference_basename(item) for item in left if _reference_basename(item)
    }
    right_basenames = {
        _reference_basename(item) for item in right if _reference_basename(item)
    }
    return bool(left_basenames & right_basenames)


def _asset_reference_candidates(asset: Any) -> set[str]:
    candidates: set[str] = set()
    for attribute_name in (
        "path",
        "url",
        "original_url",
        "download_url",
        "source_url",
        "preview_url",
        "full_size_url",
        "link",
    ):
        candidates |= _reference_candidates(getattr(asset, attribute_name, None))
    return candidates


def _markdown_has_unlocalized_downloaded_ieee_mediastore_asset(
    envelope: FetchEnvelope,
) -> bool:
    if envelope.article is None:
        return False
    remote_urls = [
        url
        for url in _markdown_image_urls(envelope.markdown)
        if _is_ieee_mediastore_url(url)
    ]
    if not remote_urls:
        return False
    remote_candidate_sets = [_reference_candidates(url) for url in remote_urls]
    for asset in list(envelope.article.assets or []):
        if local_existing_asset_path(asset) is None:
            continue
        asset_candidates = _asset_reference_candidates(asset)
        if asset_candidates and any(
            _references_match(asset_candidates, remote_candidates)
            for remote_candidates in remote_candidate_sets
        ):
            return True
    return False


def review_status_for(status: str, issue_categories: Sequence[str]) -> str:
    if status == UNSUPPORTED_PROVIDER_STATUS:
        return "skipped"
    if status != FULLTEXT:
        return "blocked"
    return "issue" if issue_categories else "ok"


def sample_expected_outcome_applies(
    sample: GoldenCriteriaLiveSample, status: str
) -> bool:
    expected_live_status = normalize_text(sample.expected_live_status).lower()
    normalized_status = normalize_text(status).lower()
    status_matches = expected_live_status == normalized_status
    if (
        expected_live_status == METADATA_ONLY
        and normalized_status == "blocked_live_fetch"
    ):
        status_matches = True
    if expected_live_status and not status_matches:
        return False
    return bool(sample.expected_review_status or sample.out_of_scope_reason)


def apply_expected_outcome(
    sample: GoldenCriteriaLiveSample,
    result: GoldenCriteriaLiveResult,
) -> GoldenCriteriaLiveResult:
    if not sample_expected_outcome_applies(sample, result.status):
        return result
    expected_review_status = normalize_text(sample.expected_review_status).lower()
    review_status = (
        expected_review_status
        if expected_review_status in REVIEW_STATUS_VALUES
        else result.review_status
    )
    return replace(
        result,
        review_status=review_status,
        issue_categories=[],
        expected_outcome=True,
        out_of_scope_reason=sample.out_of_scope_reason,
    )


def normalize_body_assets(article: Any, sample_dir: Path) -> int:
    if article is None:
        return 0
    assets = list(getattr(article, "assets", []) or [])
    body_asset_dir = sample_dir / "body_assets"
    body_asset_dir.mkdir(parents=True, exist_ok=True)

    used_names: set[str] = set()
    copied_count = 0
    for asset in assets:
        source_path = local_existing_asset_path(asset)
        if source_path is None:
            continue
        source_resolved = source_path.resolve()
        body_asset_resolved = body_asset_dir.resolve()
        if source_resolved.parent == body_asset_resolved:
            destination = source_path
            used_names.add(source_path.name)
        else:
            filename = unique_asset_filename(source_path, used_names)
            destination = body_asset_dir / filename
            shutil.copy2(source_path, destination)
        if isinstance(asset, Asset):
            asset.path = str(destination)
        elif hasattr(asset, "path"):
            asset.path = str(destination)
        copied_count += 1
    return copied_count


def local_existing_asset_path(asset: Any) -> Path | None:
    raw_path = normalize_text(getattr(asset, "path", None))
    if not raw_path or raw_path.startswith(("http://", "https://", "//")):
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = path.resolve()
    return path if path.exists() and path.is_file() else None


def unique_asset_filename(source_path: Path, used_names: set[str]) -> str:
    stem = sanitize_filename(source_path.stem or "asset")
    suffix = source_path.suffix or ".bin"
    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate in used_names:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    used_names.add(candidate)
    return candidate


def materialize_fetch_artifacts(
    *,
    envelope: FetchEnvelope,
    sample_dir: Path,
    render: RenderOptions,
) -> int:
    sample_dir.mkdir(parents=True, exist_ok=True)
    asset_count = normalize_body_assets(envelope.article, sample_dir)
    markdown = envelope.markdown
    if envelope.article is not None:
        markdown = envelope.article.to_ai_markdown(
            include_refs=render.include_refs,
            asset_profile=render.asset_profile or "body",
            max_tokens=render.max_tokens,
        )
    if markdown is not None:
        target_path = sample_dir / "extracted.md"
        envelope.markdown = rewrite_markdown_asset_links(
            markdown, envelope, target_path=target_path, render=render
        )
        target_path.write_text(envelope.markdown, encoding="utf-8")
    if envelope.article is not None:
        (sample_dir / "article.json").write_text(
            envelope.article.to_json() + "\n", encoding="utf-8"
        )
    (sample_dir / "fetch-envelope.json").write_text(
        envelope.to_json() + "\n", encoding="utf-8"
    )
    return asset_count


def collect_asset_diagnostics(article: Any) -> list[dict[str, Any]]:
    if article is None:
        return []
    diagnostics: list[dict[str, Any]] = []
    for asset in list(getattr(article, "assets", []) or []):
        entry = {
            "kind": normalize_text(getattr(asset, "kind", None)),
            "heading": normalize_text(getattr(asset, "heading", None)),
            "section": normalize_text(getattr(asset, "section", None)),
            "render_state": normalize_text(getattr(asset, "render_state", None)),
            "download_tier": normalize_text(getattr(asset, "download_tier", None)),
            "download_url": normalize_text(getattr(asset, "download_url", None)),
            "original_url": normalize_text(getattr(asset, "original_url", None)),
            "path": normalize_text(getattr(asset, "path", None)),
            "content_type": normalize_text(getattr(asset, "content_type", None)),
            "downloaded_bytes": getattr(asset, "downloaded_bytes", None),
            "width": getattr(asset, "width", None),
            "height": getattr(asset, "height", None),
        }
        compact = {
            key: value for key, value in entry.items() if value not in ("", None)
        }
        if compact:
            diagnostics.append(compact)
    return diagnostics


def _stage_timings(
    *,
    fetch_seconds: float = 0.0,
    materialize_seconds: float = 0.0,
    total_seconds: float = 0.0,
    runtime_stage_timings: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    timings = {
        "fetch_seconds": round(max(0.0, fetch_seconds), 3),
        "materialize_seconds": round(max(0.0, materialize_seconds), 3),
        "total_seconds": round(max(0.0, total_seconds), 3),
    }
    for key in (
        "resolve_seconds",
        "metadata_seconds",
        "fulltext_seconds",
        "browser_seconds",
        "dom_readiness_seconds",
        "http_seconds",
        "retry_seconds",
        "asset_seconds",
        "formula_seconds",
        "asset_browser_prepare_seconds",
        "asset_browser_release_seconds",
        "render_seconds",
    ):
        try:
            value = float((runtime_stage_timings or {}).get(key, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        timings[key] = round(max(0.0, value), 3)
    return timings


def _transport_cache_stats(transport: HttpTransport) -> dict[str, int]:
    snapshot = getattr(transport, "cache_stats_snapshot", None)
    if not callable(snapshot):
        return {}
    return snapshot()


def _cache_stats_delta(
    before: Mapping[str, Any] | None, after: Mapping[str, Any] | None
) -> dict[str, int]:
    keys = sorted(set((before or {}).keys()) | set((after or {}).keys()))
    delta: dict[str, int] = {}
    for key in keys:
        try:
            before_value = int((before or {}).get(key, 0))
        except (TypeError, ValueError):
            before_value = 0
        try:
            after_value = int((after or {}).get(key, 0))
        except (TypeError, ValueError):
            after_value = 0
        delta[str(key)] = max(0, after_value - before_value)
    return delta


def _trace_payload(trace: Sequence[Any] | None) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for event in trace or []:
        if isinstance(event, Mapping):
            payload.append(dict(event))
        elif hasattr(event, "__dataclass_fields__"):
            payload.append(asdict(event))
    return payload


def _failure_diagnostics_payload(error: Exception) -> dict[str, Any]:
    payload = {
        "provider": getattr(error, "provider", None),
        "route": getattr(error, "route", None),
        "stage": getattr(error, "stage", None),
        "http_status": getattr(error, "http_status", None),
        "error_category": getattr(error, "error_category", None),
        "retryable": getattr(error, "retryable", None),
        "retry_after_seconds": getattr(error, "retry_after_seconds", None),
        "details": dict(getattr(error, "details", None) or {}),
    }
    return {key: value for key, value in payload.items() if value not in (None, {}, [])}


def _acceptance_payload(
    sample: GoldenCriteriaLiveSample,
    *,
    envelope: FetchEnvelope | None = None,
    failure_code: str | None = None,
) -> dict[str, Any]:
    return evaluate_fetch_acceptance(
        envelope,
        asset_profile="body",
        requested_outputs=("article", "markdown"),
        failure_code=failure_code,
        expected_doi=sample.doi,
        doi=envelope.doi if envelope is not None else sample.doi,
        title=sample.title,
        source=envelope.source if envelope is not None else None,
    ).to_dict()


def _emit_sample_result_log(result: GoldenCriteriaLiveResult) -> None:
    emit_structured_log(
        logger,
        logging.DEBUG,
        "golden_criteria_live_sample_result",
        sample_id=result.sample_id,
        provider=result.provider,
        doi=result.doi,
        status=result.status,
        review_status=result.review_status,
        elapsed_seconds=result.elapsed_seconds,
        stage_timings=dict(result.stage_timings),
        http_cache_stats=dict(result.http_cache_stats),
    )


def _emit_sample_start_log(sample: GoldenCriteriaLiveSample) -> None:
    emit_structured_log(
        logger,
        logging.DEBUG,
        "golden_criteria_live_sample_start",
        sample_id=sample.sample_id,
        provider=sample.provider,
        doi=sample.doi,
        title=sample.title,
    )


def render_asset_diagnostics(asset_diagnostics: Sequence[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for asset in asset_diagnostics:
        heading = (
            normalize_text(asset.get("heading"))
            or normalize_text(asset.get("kind"))
            or "asset"
        )
        tier = normalize_text(asset.get("download_tier")) or "-"
        width = asset.get("width")
        height = asset.get("height")
        dimensions = f"{width}x{height}" if width and height else "-"
        content_type = normalize_text(asset.get("content_type")) or "-"
        rows.append(
            f"- {heading}: tier={tier}, dimensions={dimensions}, content_type={content_type}"
        )
    return "\n".join(rows) if rows else "No downloaded asset diagnostics recorded."


def _science_preview_tier_is_accepted(result: GoldenCriteriaLiveResult) -> bool:
    if normalize_text(result.provider).lower() != "science":
        return False
    trail = {normalize_text(marker).lower() for marker in result.source_trail}
    return (
        "download:science_assets_preview_accepted" in trail
        and "download:science_assets_preview_fallback" not in trail
        and "download:science_asset_failures" not in trail
    )


def render_review_template(result: GoldenCriteriaLiveResult) -> str:
    issue_categories = ", ".join(result.issue_categories)
    if result.expected_outcome:
        reason = (
            normalize_text(result.out_of_scope_reason)
            or "This sample is documented as an expected live-review outcome."
        )
        what_is_wrong = f"No provider defect is recorded. Expected outcome: {reason}"
        proposed_fix = "No fix proposed; keep this sample as an explicit expected/out-of-scope case."
    elif result.review_status == "ok":
        if _science_preview_tier_is_accepted(result):
            what_is_wrong = (
                "No issue recorded. For this Science sample, `download_tier=preview` is an accepted diagnostic label: "
                "the downloaded figure dimensions met the acceptance threshold, and the live page exposes the same "
                "article figures through `/assets/graphic/...jpeg`. Do not classify this tier label alone as "
                "`asset_download_failure`."
            )
            proposed_fix = (
                "No fix proposed for the accepted `preview` tier label. Reopen only if assets are missing, dimensions "
                "fall below the threshold, or `download:science_assets_preview_fallback` / `download:science_asset_failures` appears."
            )
        else:
            what_is_wrong = "No issue recorded yet. Read extracted.md and update this file if a problem is found."
            proposed_fix = "No fix proposed yet."
    elif result.review_status == "skipped":
        what_is_wrong = f"Sample was skipped because provider `{result.provider}` is not supported by this live review pipeline."
        proposed_fix = "Add provider support or keep this sample documented as unsupported for live review."
    elif result.review_status == "blocked":
        what_is_wrong = (
            f"Live fetch did not produce fulltext. Status: `{result.status}`."
        )
        proposed_fix = "Fix provider configuration, rate limiting, access handling, or provider waterfall before content review."
    else:
        what_is_wrong = "Automated review heuristics detected a possible issue. Confirm by reading extracted.md."
        proposed_fix = (
            "Inspect the affected provider path and add a focused regression test."
        )

    return (
        f"# Review: {result.sample_id}\n\n"
        f"- status: {result.review_status}\n"
        f"- issue_categories: [{issue_categories}]\n"
        f"- doi: {result.doi}\n"
        f"- provider: {result.provider}\n"
        f"- live_status: {result.status}\n"
        f"- content_kind: {result.content_kind or '-'}\n"
        f"- source: {result.source or '-'}\n"
        f"- asset_count: {result.asset_count}\n\n"
        f"- elapsed_seconds: {result.elapsed_seconds:.3f}\n"
        f"- stage_timings: {json.dumps(result.stage_timings, ensure_ascii=False, sort_keys=True)}\n\n"
        f"- http_cache_stats: {json.dumps(result.http_cache_stats, ensure_ascii=False, sort_keys=True)}\n\n"
        f"- expected_outcome: {str(result.expected_outcome).lower()}\n"
        f"- out_of_scope_reason: {result.out_of_scope_reason or '-'}\n\n"
        "## what_is_wrong\n\n"
        f"{what_is_wrong}\n\n"
        "## evidence\n\n"
        "TODO: Add concrete excerpts, missing sections, leaked noise, or asset observations after manual reading.\n\n"
        "### asset_diagnostics\n\n"
        f"{render_asset_diagnostics(result.asset_diagnostics)}\n\n"
        "## proposed_fix\n\n"
        f"{proposed_fix}\n\n"
        "## likely_code_area\n\n"
        "TODO: Add provider module, renderer, asset downloader, or metadata merge area.\n\n"
        "## suggested_test\n\n"
        "TODO: Add or update the smallest regression test that would catch this issue.\n"
    )


def parse_review_summary(text: str) -> ReviewSummary:
    status = "ok"
    categories: list[str] = []
    for line in text.splitlines():
        status_match = re.match(r"^\s*-\s*status:\s*(.+?)\s*$", line)
        if status_match:
            candidate = normalize_text(status_match.group(1)).lower()
            if candidate in REVIEW_STATUS_VALUES:
                status = candidate
            continue
        categories_match = re.match(r"^\s*-\s*issue_categories:\s*(.+?)\s*$", line)
        if categories_match:
            categories = parse_issue_categories(categories_match.group(1))
    return ReviewSummary(review_status=status, issue_categories=categories)


def parse_issue_categories(value: str) -> list[str]:
    normalized = normalize_text(value).strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    categories = [
        normalize_text(item).strip("`'\" ").lower()
        for item in re.split(r"[,;]", normalized)
        if normalize_text(item).strip("`'\" ")
    ]
    return [category for category in ISSUE_CATEGORIES if category in set(categories)]


def ensure_review_file(
    result: GoldenCriteriaLiveResult, sample_dir: Path
) -> ReviewSummary:
    review_path = sample_dir / "review.md"
    if review_path.exists():
        return parse_review_summary(review_path.read_text(encoding="utf-8"))
    review_path.write_text(render_review_template(result), encoding="utf-8")
    return ReviewSummary(
        review_status=result.review_status,
        issue_categories=list(result.issue_categories),
    )


def result_with_review_summary(
    result: GoldenCriteriaLiveResult,
    review: ReviewSummary,
) -> GoldenCriteriaLiveResult:
    if result.expected_outcome:
        review = ReviewSummary(review_status=result.review_status, issue_categories=[])
    return GoldenCriteriaLiveResult(
        sample_id=result.sample_id,
        provider=result.provider,
        doi=result.doi,
        title=result.title,
        status=result.status,
        content_kind=result.content_kind,
        source=result.source,
        has_fulltext=result.has_fulltext,
        warnings=list(result.warnings),
        source_trail=list(result.source_trail),
        asset_count=result.asset_count,
        sample_output_dir=result.sample_output_dir,
        review_status=review.review_status,
        issue_categories=list(review.issue_categories),
        elapsed_seconds=result.elapsed_seconds,
        stage_timings=dict(result.stage_timings),
        http_cache_stats=dict(result.http_cache_stats),
        error_code=result.error_code,
        error_message=result.error_message,
        expected_outcome=result.expected_outcome,
        out_of_scope_reason=result.out_of_scope_reason,
        asset_diagnostics=list(result.asset_diagnostics),
        acceptance=dict(result.acceptance),
        trace=[dict(item) for item in result.trace],
        failure_diagnostics=dict(result.failure_diagnostics),
        diagnostic_artifacts=[dict(item) for item in result.diagnostic_artifacts],
        worker_started_at=result.worker_started_at,
        worker_finished_at=result.worker_finished_at,
    )


def skipped_result(
    sample: GoldenCriteriaLiveSample, sample_dir: Path
) -> GoldenCriteriaLiveResult:
    categories = issue_categories_for_result(
        status=UNSUPPORTED_PROVIDER_STATUS,
        unsupported_provider=True,
    )
    return GoldenCriteriaLiveResult(
        sample_id=sample.sample_id,
        provider=sample.provider,
        doi=sample.doi,
        title=sample.title,
        status=UNSUPPORTED_PROVIDER_STATUS,
        content_kind=None,
        source=None,
        has_fulltext=False,
        warnings=[
            f"Provider {sample.provider!r} is not supported by the live review pipeline."
        ],
        source_trail=[],
        asset_count=0,
        sample_output_dir=str(sample_dir),
        review_status=review_status_for(UNSUPPORTED_PROVIDER_STATUS, categories),
        issue_categories=categories,
        elapsed_seconds=0.0,
        stage_timings=_stage_timings(),
        error_code=UNSUPPORTED_PROVIDER_STATUS,
        error_message=f"Unsupported provider: {sample.provider}",
        acceptance=_acceptance_payload(
            sample, failure_code=UNSUPPORTED_PROVIDER_STATUS
        ),
    )


def precheck_blocked_result(
    sample: GoldenCriteriaLiveSample,
    sample_dir: Path,
    *,
    provider_status_entry: Mapping[str, Any],
) -> GoldenCriteriaLiveResult:
    status = (
        normalize_text(provider_status_entry.get("status")).lower() or NOT_CONFIGURED
    )
    message = provider_status_message(provider_status_entry)
    categories = issue_categories_for_result(status=status)
    return GoldenCriteriaLiveResult(
        sample_id=sample.sample_id,
        provider=sample.provider,
        doi=sample.doi,
        title=sample.title,
        status=status
        if status in {NOT_CONFIGURED, RATE_LIMITED, ERROR}
        else "blocked_live_fetch",
        content_kind=None,
        source=None,
        has_fulltext=False,
        warnings=[message] if message else [],
        source_trail=[],
        asset_count=0,
        sample_output_dir=str(sample_dir),
        review_status=review_status_for(status, categories),
        issue_categories=categories,
        elapsed_seconds=0.0,
        stage_timings=_stage_timings(),
        error_code=status,
        error_message=message,
        acceptance=_acceptance_payload(sample, failure_code=status),
        failure_diagnostics={
            "provider": sample.provider,
            "stage": "provider_status",
            "error_category": status,
        },
    )


def provider_status_message(provider_status_entry: Mapping[str, Any]) -> str | None:
    for note in provider_status_entry.get("notes") or []:
        text = normalize_text(note)
        if text:
            return text
    for check in provider_status_entry.get("checks") or []:
        if not isinstance(check, Mapping):
            continue
        if normalize_text(check.get("status")).lower() == OK:
            continue
        text = normalize_text(check.get("message"))
        if text:
            return text
    return None


def fetch_sample_result(
    sample: GoldenCriteriaLiveSample,
    *,
    sample_dir: Path,
    fetch_paper_fn: FetchPaperFn,
    render: RenderOptions,
    env: Mapping[str, str],
    transport: HttpTransport,
    clients: Mapping[str, Any],
    provider_manifest: Mapping[str, Any] | None = None,
    runtime_context: RuntimeContext | None = None,
) -> GoldenCriteriaLiveResult:
    _emit_sample_start_log(sample)
    started_at = time.monotonic()
    cache_stats_before = _transport_cache_stats(transport)
    fetch_seconds = 0.0
    materialize_seconds = 0.0
    runtime_context = runtime_context or RuntimeContext(
        env=env,
        transport=transport,
        clients=clients,
        download_dir=sample_dir,
    )
    try:
        fetch_started_at = time.monotonic()
        fetch_kwargs: dict[str, Any] = {
            "modes": {"article", "markdown"},
            "strategy": FetchStrategy(
                allow_metadata_only_fallback=True,
                asset_profile="body",
            ),
            "render": render,
            "context": runtime_context,
        }
        envelope = fetch_paper_fn(sample.doi, **fetch_kwargs)
        fetch_seconds = time.monotonic() - fetch_started_at
        materialize_started_at = time.monotonic()
        asset_count = materialize_fetch_artifacts(
            envelope=envelope, sample_dir=sample_dir, render=render
        )
        materialize_seconds = time.monotonic() - materialize_started_at
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        timings = _stage_timings(
            fetch_seconds=fetch_seconds,
            materialize_seconds=materialize_seconds,
            total_seconds=elapsed_seconds,
            runtime_stage_timings=runtime_context.stage_timings,
        )
        asset_diagnostics = collect_asset_diagnostics(envelope.article)
        status, error_code, error_message = classify_envelope_status(sample, envelope)
        categories = issue_categories_for_result(status=status, envelope=envelope)
        categories = _dedupe_issue_categories(
            [
                *categories,
                *route_source_issue_categories(
                    sample,
                    source=envelope.source,
                    status=status,
                    provider_manifest=provider_manifest,
                ),
                *markdown_contract_issue_categories(
                    sample,
                    markdown=envelope.markdown,
                    provider_manifest=provider_manifest,
                ),
            ]
        )
        http_cache_stats = _cache_stats_delta(
            cache_stats_before, _transport_cache_stats(transport)
        )
        result = GoldenCriteriaLiveResult(
            sample_id=sample.sample_id,
            provider=sample.provider,
            doi=sample.doi,
            title=sample.title,
            status=status,
            content_kind=envelope.content_kind,
            source=envelope.source,
            has_fulltext=envelope.has_fulltext,
            warnings=list(envelope.warnings),
            source_trail=list(envelope.source_trail),
            asset_count=asset_count,
            sample_output_dir=str(sample_dir),
            review_status=review_status_for(status, categories),
            issue_categories=categories,
            elapsed_seconds=elapsed_seconds,
            stage_timings=timings,
            http_cache_stats=http_cache_stats,
            error_code=error_code,
            error_message=error_message,
            asset_diagnostics=asset_diagnostics,
            acceptance=_acceptance_payload(sample, envelope=envelope),
            trace=_trace_payload(envelope.trace),
            diagnostic_artifacts=[dict(item) for item in envelope.diagnostic_artifacts],
        )
        _emit_sample_result_log(result)
        return result
    except PaperFetchFailure as exc:
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        timings = _stage_timings(
            fetch_seconds=fetch_seconds or elapsed_seconds,
            materialize_seconds=materialize_seconds,
            total_seconds=elapsed_seconds,
            runtime_stage_timings=runtime_context.stage_timings,
        )
        status = (
            exc.status
            if exc.status in {NOT_CONFIGURED, RATE_LIMITED}
            else "blocked_live_fetch"
        )
        categories = issue_categories_for_result(status=status)
        http_cache_stats = _cache_stats_delta(
            cache_stats_before, _transport_cache_stats(transport)
        )
        result = GoldenCriteriaLiveResult(
            sample_id=sample.sample_id,
            provider=sample.provider,
            doi=sample.doi,
            title=sample.title,
            status=status,
            content_kind=None,
            source=None,
            has_fulltext=False,
            warnings=[],
            source_trail=[],
            asset_count=0,
            sample_output_dir=str(sample_dir),
            review_status=review_status_for(status, categories),
            issue_categories=categories,
            elapsed_seconds=elapsed_seconds,
            stage_timings=timings,
            http_cache_stats=http_cache_stats,
            error_code=exc.status,
            error_message=exc.reason,
            acceptance=_acceptance_payload(sample, failure_code=exc.status),
            trace=_trace_payload(exc.trace or runtime_context.fetch_trace),
            failure_diagnostics=_failure_diagnostics_payload(exc),
            diagnostic_artifacts=[
                dict(item) for item in runtime_context.diagnostic_artifacts
            ],
        )
        _emit_sample_result_log(result)
        return result
    except Exception as exc:  # pragma: no cover - defensive live path
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        timings = _stage_timings(
            fetch_seconds=fetch_seconds or elapsed_seconds,
            materialize_seconds=materialize_seconds,
            total_seconds=elapsed_seconds,
            runtime_stage_timings=runtime_context.stage_timings,
        )
        categories = issue_categories_for_result(status="blocked_live_fetch")
        http_cache_stats = _cache_stats_delta(
            cache_stats_before, _transport_cache_stats(transport)
        )
        result = GoldenCriteriaLiveResult(
            sample_id=sample.sample_id,
            provider=sample.provider,
            doi=sample.doi,
            title=sample.title,
            status=ERROR,
            content_kind=None,
            source=None,
            has_fulltext=False,
            warnings=[],
            source_trail=[],
            asset_count=0,
            sample_output_dir=str(sample_dir),
            review_status="blocked",
            issue_categories=categories,
            elapsed_seconds=elapsed_seconds,
            stage_timings=timings,
            http_cache_stats=http_cache_stats,
            error_code=exc.__class__.__name__,
            error_message=str(exc),
            acceptance=_acceptance_payload(sample, failure_code=ERROR),
            trace=_trace_payload(runtime_context.fetch_trace),
            failure_diagnostics={
                "provider": sample.provider,
                "stage": "live_fetch",
                "error_category": exc.__class__.__name__,
            },
            diagnostic_artifacts=[
                dict(item) for item in runtime_context.diagnostic_artifacts
            ],
        )
        _emit_sample_result_log(result)
        return result
    finally:
        runtime_context.close()


def build_provider_summaries(
    results: Sequence[GoldenCriteriaLiveResult],
) -> list[ProviderReviewSummary]:
    providers = sorted({result.provider for result in results})
    summaries: list[ProviderReviewSummary] = []
    for provider in providers:
        provider_results = [result for result in results if result.provider == provider]
        counts = Counter(result.status for result in provider_results)
        summaries.append(
            ProviderReviewSummary(
                provider=provider,
                attempted=len(provider_results),
                status_counts=dict(sorted(counts.items())),
                fulltext=counts.get(FULLTEXT, 0),
                blocked=sum(
                    1
                    for result in provider_results
                    if result.review_status == "blocked"
                ),
                skipped=sum(
                    1
                    for result in provider_results
                    if result.review_status == "skipped"
                ),
            )
        )
    return summaries


def build_issue_summaries(
    results: Sequence[GoldenCriteriaLiveResult],
) -> list[IssueReviewSummary]:
    grouped: dict[str, list[GoldenCriteriaLiveResult]] = defaultdict(list)
    for result in results:
        for category in result.issue_categories:
            grouped[category].append(result)
    return [
        IssueReviewSummary(
            issue_category=category,
            count=len(items),
            sample_ids=[item.sample_id for item in items[:10]],
            dois=[item.doi for item in items[:10]],
        )
        for category, items in sorted(grouped.items())
    ]


_PERFORMANCE_STAGE_KEYS = (
    "browser_seconds",
    "dom_readiness_seconds",
    "http_seconds",
    "retry_seconds",
    "asset_seconds",
    "render_seconds",
    "total_seconds",
)


def build_performance_summaries(
    results: Sequence[GoldenCriteriaLiveResult],
) -> list[PerformanceStageSummary]:
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for result in results:
        route = normalize_text(result.source).lower() or "unavailable"
        for stage in _PERFORMANCE_STAGE_KEYS:
            try:
                value = max(0.0, float(result.stage_timings.get(stage, 0.0)))
            except (TypeError, ValueError):
                value = 0.0
            grouped[(result.provider, route, stage)].append(value)

    summaries: list[PerformanceStageSummary] = []
    for (provider, route, stage), values in sorted(grouped.items()):
        sample_count = len(values)
        summaries.append(
            PerformanceStageSummary(
                provider=provider,
                route=route,
                stage=stage,
                sample_count=sample_count,
                observed_seconds=(round(values[0], 3) if sample_count == 1 else None),
                p50_seconds=(
                    nearest_rank_percentile(values, 0.50) if sample_count >= 2 else None
                ),
                p95_seconds=(
                    nearest_rank_percentile(values, 0.95) if sample_count >= 2 else None
                ),
            )
        )
    return summaries


def build_solution_recommendations(
    results: Sequence[GoldenCriteriaLiveResult],
) -> list[SolutionRecommendation]:
    grouped: dict[str, list[GoldenCriteriaLiveResult]] = defaultdict(list)
    for result in results:
        for category in result.issue_categories:
            grouped[category].append(result)
    recommendations: list[SolutionRecommendation] = []
    priority = 1
    for category in ISSUE_CATEGORIES:
        items = grouped.get(category, [])
        if not items:
            continue
        title, recommendation = SOLUTION_BY_CATEGORY[category]
        recommendations.append(
            SolutionRecommendation(
                priority=priority,
                issue_category=category,
                title=title,
                recommendation=recommendation,
                affected_count=len(items),
                sample_ids=[item.sample_id for item in items[:10]],
                suggested_test=f"Add or update a focused regression test for `{category}` using one affected golden sample.",
            )
        )
        priority += 1
    return recommendations


def build_report(
    *,
    generated_at: str,
    output_dir: Path,
    provider_status: dict[str, Any],
    results: Sequence[GoldenCriteriaLiveResult],
    concurrency: int = 1,
    completion_order: Sequence[str] = (),
    lane_limits: Mapping[str, int] | None = None,
    provider_peak_in_flight: Mapping[str, int] | None = None,
) -> GoldenCriteriaLiveReport:
    result_list = list(results)
    return GoldenCriteriaLiveReport(
        generated_at=generated_at,
        output_dir=str(output_dir),
        total_samples=len(result_list),
        supported_samples=sum(
            1 for result in result_list if result.provider in SUPPORTED_PROVIDERS
        ),
        skipped_samples=sum(
            1 for result in result_list if result.status == UNSUPPORTED_PROVIDER_STATUS
        ),
        provider_status=provider_status,
        results=result_list,
        summary_by_provider=build_provider_summaries(result_list),
        summary_by_issue=build_issue_summaries(result_list),
        performance_by_provider_route_stage=build_performance_summaries(result_list),
        solution_recommendations=build_solution_recommendations(result_list),
        concurrency=concurrency,
        completion_order=list(completion_order),
        lane_limits=dict(lane_limits or {}),
        provider_peak_in_flight=dict(provider_peak_in_flight or {}),
    )


def _validated_lane_limit_overrides(
    lane_limit_overrides: Mapping[str, int] | None,
) -> dict[str, int]:
    """Validate development-only provider lane overrides.

    Browser-backed overrides are deliberately capped at two. Production CLI/MCP
    callers never pass this parameter and continue to use provider catalog limits.
    """

    normalized: dict[str, int] = {}
    for provider, value in (lane_limit_overrides or {}).items():
        provider_key = normalize_text(provider).lower()
        if not provider_key or provider_key not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unknown lane limit override provider: {provider!r}")
        if provider_key in normalized:
            raise ValueError(
                "lane_limit_overrides must not contain duplicate providers"
            )
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8:
            raise ValueError("lane_limit_overrides values must be integers from 1 to 8")
        if provider_has_browser_route(provider_key) and value > 2:
            raise ValueError("browser-provider lane_limit_overrides must not exceed 2")
        normalized[provider_key] = value
    return normalized


def run_golden_criteria_live_review(
    *,
    manifest_path: Path | None = None,
    output_dir: Path | None = None,
    providers: Sequence[str] | None = None,
    sample_ids: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    fetch_paper_fn: FetchPaperFn = fetch_paper,
    provider_status_fn: ProviderStatusFn = provider_status_payload,
    now: datetime | None = None,
    concurrency: int = 1,
    lane_limit_overrides: Mapping[str, int] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> GoldenCriteriaLiveReport:
    if isinstance(concurrency, bool) or not 1 <= concurrency <= 8:
        raise ValueError("concurrency must be an integer from 1 to 8")
    resolved_lane_overrides = _validated_lane_limit_overrides(lane_limit_overrides)
    manifest = load_manifest(manifest_path)
    all_samples = iter_golden_criteria_samples(manifest)
    selected_samples = select_samples(
        all_samples, providers=providers, sample_ids=sample_ids
    )
    output_root = (output_dir or timestamped_review_output_dir(now=now)).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = (now or datetime.now(UTC)).isoformat()
    runtime_env = build_runtime_env(env)
    ensure_live_opt_in(runtime_env)
    active_transport = transport or HttpTransport()
    clients = build_clients(active_transport, runtime_env)
    batch_context = RuntimeContext(env=runtime_env, transport=active_transport)
    render = RenderOptions(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    status_payload = provider_status_fn(env=runtime_env, transport=active_transport)
    provider_status_by_provider = {
        normalize_text(entry.get("provider")).lower(): dict(entry)
        for entry in (status_payload.get("providers") or [])
        if isinstance(entry, Mapping) and normalize_text(entry.get("provider"))
    }
    ai_provider_manifests: dict[str, dict[str, Any]] = {}
    for provider in {sample.provider for sample in selected_samples}:
        provider_manifest = load_provider_manifest(provider)
        if provider_manifest is not None:
            ai_provider_manifests[provider] = provider_manifest

    (output_root / "manifest-snapshot.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "provider-status.json").write_text(
        json.dumps(status_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    results_by_sample_id: dict[str, GoldenCriteriaLiveResult] = {}
    for sample in selected_samples:
        sample_dir = sample_output_dir(output_root, sample)
        sample_dir.mkdir(parents=True, exist_ok=True)
        if not sample.supported:
            _emit_sample_start_log(sample)
            result = skipped_result(sample, sample_dir)
            result = apply_expected_outcome(sample, result)
            review = ensure_review_file(result, sample_dir)
            reviewed_result = result_with_review_summary(result, review)
            _emit_sample_result_log(reviewed_result)
            results_by_sample_id[sample.sample_id] = reviewed_result

    def execute_supported_sample(
        sample: GoldenCriteriaLiveSample,
    ) -> GoldenCriteriaLiveResult:
        sample_dir = sample_output_dir(output_root, sample)
        sample_dir.mkdir(parents=True, exist_ok=True)
        provider_status_entry = provider_status_by_provider.get(sample.provider, {})
        if provider_status_entry and not bool(provider_status_entry.get("available")):
            _emit_sample_start_log(sample)
            result = precheck_blocked_result(
                sample,
                sample_dir,
                provider_status_entry=provider_status_entry,
            )
            result = apply_expected_outcome(sample, result)
            review = ensure_review_file(result, sample_dir)
            reviewed_result = result_with_review_summary(result, review)
            _emit_sample_result_log(reviewed_result)
            return reviewed_result
        item_context = batch_context.new_request_context(
            download_dir=sample_dir,
            asset_profile="body",
        )
        result = fetch_sample_result(
            sample,
            sample_dir=sample_dir,
            fetch_paper_fn=fetch_paper_fn,
            render=render,
            env=runtime_env,
            transport=active_transport,
            clients=clients,
            provider_manifest=ai_provider_manifests.get(sample.provider),
            runtime_context=item_context,
        )
        result = apply_expected_outcome(sample, result)
        review = ensure_review_file(result, sample_dir)
        return result_with_review_summary(result, review)

    activity_lock = threading.Lock()
    provider_in_flight: Counter[str] = Counter()
    provider_peak_in_flight: Counter[str] = Counter()
    worker_timings: dict[str, tuple[float, float]] = {}

    def run_supported_sample(
        sample: GoldenCriteriaLiveSample,
    ) -> GoldenCriteriaLiveResult:
        worker_started_at = clock()
        with activity_lock:
            provider_in_flight[sample.provider] += 1
            provider_peak_in_flight[sample.provider] = max(
                provider_peak_in_flight[sample.provider],
                provider_in_flight[sample.provider],
            )
        try:
            result = execute_supported_sample(sample)
        finally:
            worker_finished_at = clock()
            with activity_lock:
                provider_in_flight[sample.provider] -= 1
                worker_timings[sample.sample_id] = (
                    worker_started_at,
                    worker_finished_at,
                )
        return replace(
            result,
            worker_started_at=worker_started_at,
            worker_finished_at=worker_finished_at,
        )

    def classify_live_result(result: GoldenCriteriaLiveResult) -> BatchFailure | None:
        if result.status == RATE_LIMITED:
            retry_after = result.failure_diagnostics.get("retry_after_seconds")
            return BatchFailure(
                reason_code=result.error_code or RATE_LIMITED,
                message=result.error_message or "Provider rate limit is active.",
                retry_after_seconds=(
                    float(retry_after)
                    if isinstance(retry_after, (int, float))
                    and not isinstance(retry_after, bool)
                    else None
                ),
                rate_limited=True,
                details=dict(result.failure_diagnostics),
            )
        if result.status in {ERROR, "blocked_live_fetch"}:
            return BatchFailure(
                reason_code=result.error_code or result.status,
                message=result.error_message or "Live fetch failed.",
                details=dict(result.failure_diagnostics),
            )
        return None

    scheduled_samples = schedule_supported_samples(selected_samples)
    effective_lane_limits = {
        provider: min(
            concurrency,
            resolved_lane_overrides.get(
                provider,
                provider_lane_limit(provider, global_limit=concurrency),
            ),
        )
        for provider in dict.fromkeys(sample.provider for sample in scheduled_samples)
    }
    try:
        batch_result = run_batch(
            scheduled_samples,
            run_supported_sample,
            max_workers=concurrency,
            lane_key=lambda sample: sample.provider,
            lane_limits=effective_lane_limits,
            result_classifier=classify_live_result,
        )
    finally:
        batch_context.close()
    for item_result in batch_result.results:
        if item_result.value is None:
            error = item_result.error or RuntimeError("live benchmark worker failed")
            sample = item_result.item
            sample_dir = sample_output_dir(output_root, sample)
            result = GoldenCriteriaLiveResult(
                sample_id=sample.sample_id,
                provider=sample.provider,
                doi=sample.doi,
                title=sample.title,
                status=ERROR,
                content_kind=None,
                source=None,
                has_fulltext=False,
                warnings=[],
                source_trail=[],
                asset_count=0,
                sample_output_dir=str(sample_dir),
                review_status="blocked",
                issue_categories=issue_categories_for_result(
                    status="blocked_live_fetch"
                ),
                elapsed_seconds=0.0,
                stage_timings=_stage_timings(),
                error_code=error.__class__.__name__,
                error_message=str(error),
                acceptance=_acceptance_payload(sample, failure_code=ERROR),
                failure_diagnostics=_failure_diagnostics_payload(error),
                worker_started_at=(
                    worker_timings.get(sample.sample_id, (None, None))[0]
                ),
                worker_finished_at=(
                    worker_timings.get(sample.sample_id, (None, None))[1]
                ),
            )
            review = ensure_review_file(result, sample_dir)
            results_by_sample_id[sample.sample_id] = result_with_review_summary(
                result, review
            )
            continue
        results_by_sample_id[item_result.item.sample_id] = item_result.value

    completion_order = [
        event.result.item.sample_id for event in batch_result.completion_events
    ]

    ordered_results = [
        results_by_sample_id[sample.sample_id]
        for sample in selected_samples
        if sample.sample_id in results_by_sample_id
    ]
    report = build_report(
        generated_at=generated_at,
        output_dir=output_root,
        provider_status=status_payload,
        results=ordered_results,
        concurrency=concurrency,
        completion_order=completion_order,
        lane_limits=effective_lane_limits,
        provider_peak_in_flight=dict(provider_peak_in_flight),
    )
    report.write_json(output_root / "report.json")
    report.write_markdown(output_root / "report.md")
    emit_structured_log(
        logger,
        logging.INFO,
        "golden_criteria_live_review_result",
        output_dir=str(output_root),
        total_samples=report.total_samples,
        supported_samples=report.supported_samples,
        skipped_samples=report.skipped_samples,
        http_cache_stats=_transport_cache_stats(active_transport),
    )
    return report
