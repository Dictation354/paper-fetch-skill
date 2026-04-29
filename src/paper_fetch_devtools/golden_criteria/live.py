"""Live review artifact generation for the golden criteria fixture catalog."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import inspect
import json
import logging
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable, Mapping, Sequence

from paper_fetch.config import build_runtime_env, resolve_repo_root
from paper_fetch.http import HttpTransport
from paper_fetch.logging_utils import emit_structured_log
from paper_fetch.models import Asset, FetchEnvelope, RenderOptions
from paper_fetch.providers.registry import build_clients
from paper_fetch.quality.issues import is_authorless_briefing_like
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, PaperFetchFailure, fetch_paper
from paper_fetch.utils import normalize_text, sanitize_filename
from paper_fetch.workflow.rendering import rewrite_markdown_asset_links

logger = logging.getLogger("paper_fetch_devtools.golden_criteria.live")

SUPPORTED_PROVIDERS = ("elsevier", "springer", "wiley", "science", "pnas")
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
    "math_loss",
    "metadata_loss",
    "live_fetch_blocked",
    "unsupported_provider",
)
QUALITY_FLAG_CATEGORY_MAP = {
    "insufficient_body": "content_missing",
    "weak_body_structure": "section_structure",
    "table_fallback_present": "figure_table_loss",
    "table_semantic_loss": "figure_table_loss",
    "formula_fallback_present": "math_loss",
    "formula_missing_present": "math_loss",
}
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
    solution_recommendations: list[SolutionRecommendation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "output_dir": self.output_dir,
            "total_samples": self.total_samples,
            "supported_samples": self.supported_samples,
            "skipped_samples": self.skipped_samples,
            "provider_status": self.provider_status,
            "results": [item.to_dict() for item in self.results],
            "summary_by_provider": [item.to_dict() for item in self.summary_by_provider],
            "summary_by_issue": [item.to_dict() for item in self.summary_by_issue],
            "solution_recommendations": [item.to_dict() for item in self.solution_recommendations],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

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
            "",
            "## Provider Summary",
            "",
            "| Provider | Attempted | Fulltext | Blocked | Skipped | Status Counts |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
        for summary in self.summary_by_provider:
            counts = ", ".join(f"{key}={value}" for key, value in sorted(summary.status_counts.items()) if value)
            lines.append(
                f"| `{summary.provider}` | {summary.attempted} | {summary.fulltext} | "
                f"{summary.blocked} | {summary.skipped} | {counts or '-'} |"
            )

        lines.extend(
            [
                "",
                "## Sample Results",
                "",
                "| Sample | Provider | DOI | Status | Content | Source | Assets | Seconds | Resolve | Metadata | Fulltext | Asset | Formula | Render | Fetch | Materialize | Review | Issues |",
                "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for result in self.results:
            issues = ", ".join(f"`{item}`" for item in result.issue_categories) or "-"
            sample_link = f"[{result.sample_id}]({Path(result.sample_output_dir).name}/review.md)"
            resolve_seconds = result.stage_timings.get("resolve_seconds", 0.0)
            metadata_seconds = result.stage_timings.get("metadata_seconds", 0.0)
            fulltext_seconds = result.stage_timings.get("fulltext_seconds", 0.0)
            asset_seconds = result.stage_timings.get("asset_seconds", 0.0)
            formula_seconds = result.stage_timings.get("formula_seconds", 0.0)
            render_seconds = result.stage_timings.get("render_seconds", 0.0)
            fetch_seconds = result.stage_timings.get("fetch_seconds", 0.0)
            materialize_seconds = result.stage_timings.get("materialize_seconds", 0.0)
            lines.append(
                f"| {sample_link} | `{result.provider}` | `{result.doi}` | `{result.status}` | "
                f"`{result.content_kind or '-'}` | `{result.source or '-'}` | {result.asset_count} | "
                f"{result.elapsed_seconds:.3f} | {resolve_seconds:.3f} | {metadata_seconds:.3f} | "
                f"{fulltext_seconds:.3f} | {asset_seconds:.3f} | {formula_seconds:.3f} | "
                f"{render_seconds:.3f} | {fetch_seconds:.3f} | {materialize_seconds:.3f} | "
                f"`{result.review_status}` | {issues} |"
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
            for summary in self.summary_by_issue:
                sample_ids = ", ".join(f"`{item}`" for item in summary.sample_ids) or "-"
                lines.append(f"| `{summary.issue_category}` | {summary.count} | {sample_ids} |")
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
                sample_ids = ", ".join(f"`{sample_id}`" for sample_id in item.sample_ids) or "-"
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
    return resolve_repo_root() / "tests" / "fixtures" / "golden_criteria" / "manifest.json"


def timestamped_review_output_dir(*, now: datetime | None = None) -> Path:
    active_now = now or datetime.now(timezone.utc)
    timestamp = active_now.strftime("%Y%m%d-%H%M%S")
    return resolve_repo_root() / "live-downloads" / DEFAULT_REVIEW_ROOT_NAME / timestamp


def ensure_live_opt_in(env: Mapping[str, str]) -> None:
    if normalize_text(env.get(RUN_LIVE_ENV_VAR)) != "1":
        raise RuntimeError(f"Set {RUN_LIVE_ENV_VAR}=1 to run the golden criteria live review pipeline.")


def load_manifest(manifest_path: Path | None = None) -> dict[str, Any]:
    path = manifest_path or default_manifest_path()
    return json.loads(path.read_text(encoding="utf-8"))


def iter_golden_criteria_samples(manifest: Mapping[str, Any]) -> list[GoldenCriteriaLiveSample]:
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
                expected_live_status=normalize_text(raw_sample.get("expected_live_status")) or None,
                expected_review_status=normalize_text(raw_sample.get("expected_review_status")).lower() or None,
                out_of_scope_reason=normalize_text(raw_sample.get("out_of_scope_reason")) or None,
            )
        )
    return samples


def select_samples(
    samples: Sequence[GoldenCriteriaLiveSample],
    *,
    providers: Sequence[str] | None = None,
    sample_ids: Sequence[str] | None = None,
) -> list[GoldenCriteriaLiveSample]:
    provider_filter = {normalize_text(item).lower() for item in (providers or []) if normalize_text(item)}
    sample_filter = {normalize_text(item) for item in (sample_ids or []) if normalize_text(item)}
    selected = []
    for sample in samples:
        if provider_filter and sample.provider not in provider_filter:
            continue
        if sample_filter and sample.sample_id not in sample_filter and sample.doi not in sample_filter:
            continue
        selected.append(sample)
    return selected


def schedule_supported_samples(samples: Sequence[GoldenCriteriaLiveSample]) -> list[GoldenCriteriaLiveSample]:
    grouped: dict[str, list[GoldenCriteriaLiveSample]] = defaultdict(list)
    for sample in samples:
        if sample.supported:
            grouped[sample.provider].append(sample)

    scheduled: list[GoldenCriteriaLiveSample] = []
    max_count = max((len(grouped.get(provider, [])) for provider in SUPPORTED_PROVIDERS), default=0)
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
                    "status": "error",
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
                    "status": "error",
                    "available": False,
                    "official_provider": bool(getattr(client, "official_provider", True)),
                    "missing_env": [],
                    "notes": [f"Provider diagnostics failed unexpectedly: {exc}"],
                    "checks": [],
                }
            )
    return {"providers": providers}


def sample_output_dir(output_root: Path, sample: GoldenCriteriaLiveSample) -> Path:
    return output_root / sanitize_filename(sample.sample_id)


def classify_envelope_status(sample: GoldenCriteriaLiveSample, envelope: FetchEnvelope) -> tuple[str, str | None, str | None]:
    if envelope.content_kind == "fulltext":
        return "fulltext", None, None

    source_trail = set(envelope.source_trail)
    for status in ("not_configured", "rate_limited"):
        if f"fulltext:{sample.provider}_{status}" in source_trail:
            return status, status, _first_non_generic_warning(envelope.warnings)
    if (
        f"fulltext:{sample.provider}_fail" in source_trail
        or f"fulltext:{sample.provider}_not_usable" in source_trail
    ):
        return "blocked_live_fetch", "no_result", _first_non_generic_warning(envelope.warnings)
    if envelope.content_kind in {"abstract_only", "metadata_only"}:
        return "metadata_only", None, _first_non_generic_warning(envelope.warnings)
    return "blocked_live_fetch", "blocked_live_fetch", _first_non_generic_warning(envelope.warnings)


def _first_non_generic_warning(warnings: Sequence[str]) -> str | None:
    for warning in warnings:
        text = normalize_text(warning)
        if text and text != "Full text was not available; returning metadata and abstract only.":
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
    elif status != "fulltext":
        categories.append("live_fetch_blocked")

    if envelope is not None:
        trail_blob = " ".join(envelope.source_trail).lower()
        warning_blob = " ".join(envelope.warnings).lower()
        preview_fallback_assets = [
            asset
            for asset in list((envelope.article.assets if envelope.article is not None else []) or [])
            if normalize_text(getattr(asset, "download_tier", None)).lower() == "preview"
        ]
        preview_fallback_has_non_formula_asset = any(
            normalize_text(getattr(asset, "kind", None)).lower() != "formula"
            for asset in preview_fallback_assets
        )
        if (
            "asset_failures" in trail_blob
            or "partially downloaded" in warning_blob
            or ("assets_preview_fallback" in trail_blob and (not preview_fallback_assets or preview_fallback_has_non_formula_asset))
        ):
            categories.append("asset_download_failure")
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


def review_status_for(status: str, issue_categories: Sequence[str]) -> str:
    if status == UNSUPPORTED_PROVIDER_STATUS:
        return "skipped"
    if status != "fulltext":
        return "blocked"
    return "issue" if issue_categories else "ok"


def sample_expected_outcome_applies(sample: GoldenCriteriaLiveSample, status: str) -> bool:
    expected_live_status = normalize_text(sample.expected_live_status).lower()
    normalized_status = normalize_text(status).lower()
    status_matches = expected_live_status == normalized_status
    if expected_live_status == "metadata_only" and normalized_status == "blocked_live_fetch":
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
    review_status = expected_review_status if expected_review_status in REVIEW_STATUS_VALUES else result.review_status
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
    if body_asset_dir.exists():
        shutil.rmtree(body_asset_dir)
    body_asset_dir.mkdir(parents=True, exist_ok=True)

    used_names: set[str] = set()
    copied_count = 0
    for asset in assets:
        source_path = local_existing_asset_path(asset)
        if source_path is None:
            continue
        filename = unique_asset_filename(source_path, used_names)
        destination = body_asset_dir / filename
        if source_path.resolve() != destination.resolve():
            shutil.copy2(source_path, destination)
        if isinstance(asset, Asset):
            asset.path = str(destination)
        elif hasattr(asset, "path"):
            setattr(asset, "path", str(destination))
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
        envelope.markdown = rewrite_markdown_asset_links(markdown, envelope, target_path=target_path, render=render)
        target_path.write_text(envelope.markdown, encoding="utf-8")
    if envelope.article is not None:
        (sample_dir / "article.json").write_text(envelope.article.to_json() + "\n", encoding="utf-8")
    (sample_dir / "fetch-envelope.json").write_text(envelope.to_json() + "\n", encoding="utf-8")
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
            "content_type": normalize_text(getattr(asset, "content_type", None)),
            "downloaded_bytes": getattr(asset, "downloaded_bytes", None),
            "width": getattr(asset, "width", None),
            "height": getattr(asset, "height", None),
        }
        compact = {key: value for key, value in entry.items() if value not in ("", None)}
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
        "asset_seconds",
        "formula_seconds",
        "render_seconds",
    ):
        try:
            value = float((runtime_stage_timings or {}).get(key, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        timings[key] = round(max(0.0, value), 3)
    return timings


def _callable_accepts_keyword(function: Callable[..., Any], keyword: str) -> bool:
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False
    return keyword in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def _transport_cache_stats(transport: HttpTransport) -> dict[str, int]:
    snapshot = getattr(transport, "cache_stats_snapshot", None)
    if not callable(snapshot):
        return {}
    return snapshot()


def _cache_stats_delta(before: Mapping[str, Any] | None, after: Mapping[str, Any] | None) -> dict[str, int]:
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


def render_asset_diagnostics(asset_diagnostics: Sequence[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for asset in asset_diagnostics:
        heading = normalize_text(asset.get("heading")) or normalize_text(asset.get("kind")) or "asset"
        tier = normalize_text(asset.get("download_tier")) or "-"
        width = asset.get("width")
        height = asset.get("height")
        dimensions = f"{width}x{height}" if width and height else "-"
        content_type = normalize_text(asset.get("content_type")) or "-"
        rows.append(f"- {heading}: tier={tier}, dimensions={dimensions}, content_type={content_type}")
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
        reason = normalize_text(result.out_of_scope_reason) or "This sample is documented as an expected live-review outcome."
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
        what_is_wrong = f"Live fetch did not produce fulltext. Status: `{result.status}`."
        proposed_fix = "Fix provider configuration, rate limiting, access handling, or provider waterfall before content review."
    else:
        what_is_wrong = "Automated review heuristics detected a possible issue. Confirm by reading extracted.md."
        proposed_fix = "Inspect the affected provider path and add a focused regression test."

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


def ensure_review_file(result: GoldenCriteriaLiveResult, sample_dir: Path) -> ReviewSummary:
    review_path = sample_dir / "review.md"
    if review_path.exists():
        return parse_review_summary(review_path.read_text(encoding="utf-8"))
    review_path.write_text(render_review_template(result), encoding="utf-8")
    return ReviewSummary(review_status=result.review_status, issue_categories=list(result.issue_categories))


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
    )


def skipped_result(sample: GoldenCriteriaLiveSample, sample_dir: Path) -> GoldenCriteriaLiveResult:
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
        warnings=[f"Provider {sample.provider!r} is not supported by the live review pipeline."],
        source_trail=[],
        asset_count=0,
        sample_output_dir=str(sample_dir),
        review_status=review_status_for(UNSUPPORTED_PROVIDER_STATUS, categories),
        issue_categories=categories,
        elapsed_seconds=0.0,
        stage_timings=_stage_timings(),
        error_code=UNSUPPORTED_PROVIDER_STATUS,
        error_message=f"Unsupported provider: {sample.provider}",
    )


def precheck_blocked_result(
    sample: GoldenCriteriaLiveSample,
    sample_dir: Path,
    *,
    provider_status_entry: Mapping[str, Any],
) -> GoldenCriteriaLiveResult:
    status = normalize_text(provider_status_entry.get("status")).lower() or "not_configured"
    message = provider_status_message(provider_status_entry)
    categories = issue_categories_for_result(status=status)
    return GoldenCriteriaLiveResult(
        sample_id=sample.sample_id,
        provider=sample.provider,
        doi=sample.doi,
        title=sample.title,
        status=status if status in {"not_configured", "rate_limited", "error"} else "blocked_live_fetch",
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
    )


def provider_status_message(provider_status_entry: Mapping[str, Any]) -> str | None:
    for note in provider_status_entry.get("notes") or []:
        text = normalize_text(note)
        if text:
            return text
    for check in provider_status_entry.get("checks") or []:
        if not isinstance(check, Mapping):
            continue
        if normalize_text(check.get("status")).lower() == "ok":
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
) -> GoldenCriteriaLiveResult:
    started_at = time.monotonic()
    cache_stats_before = _transport_cache_stats(transport)
    fetch_seconds = 0.0
    materialize_seconds = 0.0
    runtime_context = RuntimeContext(
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
        }
        if _callable_accepts_keyword(fetch_paper_fn, "context"):
            fetch_kwargs["context"] = runtime_context
        else:
            fetch_kwargs.update(
                {
                    "download_dir": sample_dir,
                    "clients": clients,
                    "transport": transport,
                    "env": env,
                }
            )
        envelope = fetch_paper_fn(sample.doi, **fetch_kwargs)
        fetch_seconds = time.monotonic() - fetch_started_at
        materialize_started_at = time.monotonic()
        asset_count = materialize_fetch_artifacts(envelope=envelope, sample_dir=sample_dir, render=render)
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
        http_cache_stats = _cache_stats_delta(cache_stats_before, _transport_cache_stats(transport))
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
        status = exc.status if exc.status in {"not_configured", "rate_limited"} else "blocked_live_fetch"
        categories = issue_categories_for_result(status=status)
        http_cache_stats = _cache_stats_delta(cache_stats_before, _transport_cache_stats(transport))
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
        http_cache_stats = _cache_stats_delta(cache_stats_before, _transport_cache_stats(transport))
        result = GoldenCriteriaLiveResult(
            sample_id=sample.sample_id,
            provider=sample.provider,
            doi=sample.doi,
            title=sample.title,
            status="error",
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
        )
        _emit_sample_result_log(result)
        return result
    finally:
        runtime_context.close()


def build_provider_summaries(results: Sequence[GoldenCriteriaLiveResult]) -> list[ProviderReviewSummary]:
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
                fulltext=counts.get("fulltext", 0),
                blocked=sum(1 for result in provider_results if result.review_status == "blocked"),
                skipped=sum(1 for result in provider_results if result.review_status == "skipped"),
            )
        )
    return summaries


def build_issue_summaries(results: Sequence[GoldenCriteriaLiveResult]) -> list[IssueReviewSummary]:
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


def build_solution_recommendations(results: Sequence[GoldenCriteriaLiveResult]) -> list[SolutionRecommendation]:
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
) -> GoldenCriteriaLiveReport:
    result_list = list(results)
    return GoldenCriteriaLiveReport(
        generated_at=generated_at,
        output_dir=str(output_dir),
        total_samples=len(result_list),
        supported_samples=sum(1 for result in result_list if result.provider in SUPPORTED_PROVIDERS),
        skipped_samples=sum(1 for result in result_list if result.status == UNSUPPORTED_PROVIDER_STATUS),
        provider_status=provider_status,
        results=result_list,
        summary_by_provider=build_provider_summaries(result_list),
        summary_by_issue=build_issue_summaries(result_list),
        solution_recommendations=build_solution_recommendations(result_list),
    )


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
) -> GoldenCriteriaLiveReport:
    manifest = load_manifest(manifest_path)
    all_samples = iter_golden_criteria_samples(manifest)
    selected_samples = select_samples(all_samples, providers=providers, sample_ids=sample_ids)
    output_root = (output_dir or timestamped_review_output_dir(now=now)).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = (now or datetime.now(timezone.utc)).isoformat()
    runtime_env = build_runtime_env(env)
    ensure_live_opt_in(runtime_env)
    active_transport = transport or HttpTransport()
    clients = build_clients(active_transport, runtime_env)
    render = RenderOptions(include_refs="all", asset_profile="body", max_tokens="full_text")
    status_payload = provider_status_fn(env=runtime_env, transport=active_transport)
    provider_status_by_provider = {
        normalize_text(entry.get("provider")).lower(): dict(entry)
        for entry in (status_payload.get("providers") or [])
        if isinstance(entry, Mapping) and normalize_text(entry.get("provider"))
    }

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
            result = skipped_result(sample, sample_dir)
            result = apply_expected_outcome(sample, result)
            review = ensure_review_file(result, sample_dir)
            results_by_sample_id[sample.sample_id] = result_with_review_summary(result, review)

    for sample in schedule_supported_samples(selected_samples):
        sample_dir = sample_output_dir(output_root, sample)
        sample_dir.mkdir(parents=True, exist_ok=True)
        provider_status_entry = provider_status_by_provider.get(sample.provider, {})
        if provider_status_entry and not bool(provider_status_entry.get("available")):
            result = precheck_blocked_result(
                sample,
                sample_dir,
                provider_status_entry=provider_status_entry,
            )
            result = apply_expected_outcome(sample, result)
            review = ensure_review_file(result, sample_dir)
            results_by_sample_id[sample.sample_id] = result_with_review_summary(result, review)
            continue
        result = fetch_sample_result(
            sample,
            sample_dir=sample_dir,
            fetch_paper_fn=fetch_paper_fn,
            render=render,
            env=runtime_env,
            transport=active_transport,
            clients=clients,
        )
        result = apply_expected_outcome(sample, result)
        review = ensure_review_file(result, sample_dir)
        results_by_sample_id[sample.sample_id] = result_with_review_summary(result, review)

    ordered_results = [results_by_sample_id[sample.sample_id] for sample in selected_samples if sample.sample_id in results_by_sample_id]
    report = build_report(
        generated_at=generated_at,
        output_dir=output_root,
        provider_status=status_payload,
        results=ordered_results,
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
