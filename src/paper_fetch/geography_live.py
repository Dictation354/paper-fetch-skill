"""Live-only geography publisher report helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping, Sequence

from .config import build_runtime_env, resolve_repo_root
from .http import HttpTransport
from .models import FetchEnvelope, TokenEstimateBreakdown, filtered_body_sections
from .providers.html_generic import HtmlGenericClient
from .providers.registry import build_clients
from .publisher_identity import normalize_doi
from .service import FetchStrategy, PaperFetchFailure, fetch_paper
from .utils import normalize_text

GEOGRAPHY_PROVIDER_ORDER = ("elsevier", "springer", "wiley", "science", "pnas")
GEOGRAPHY_RESULT_STATUSES = (
    "fulltext",
    "metadata_only",
    "not_configured",
    "rate_limited",
    "no_result",
    "error",
)
EXPECTED_FULLTEXT_SOURCES_BY_PROVIDER = {
    "elsevier": frozenset({"elsevier_xml", "elsevier_browser"}),
    "springer": frozenset({"springer_html"}),
    "wiley": frozenset({"wiley_browser"}),
    "science": frozenset({"science"}),
    "pnas": frozenset({"pnas"}),
}
REPORT_RESULT_WARNING = "Full text was not available; returning metadata and abstract only."
ASCII_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[!-~]+$")
RESEARCH_BRIEFING_HEADING_SIGNATURE = (
    "the question",
    "the discovery",
    "the implications",
    "expert opinion",
    "behind the paper",
    "from the editor",
)
ABSTRACT_INFLATED_TOKEN_THRESHOLD = 900
ABSTRACT_INFLATED_CHAR_THRESHOLD = 3500
ABSTRACT_INFLATED_WITH_OVERLAP_TOKEN_THRESHOLD = 600
ABSTRACT_INFLATED_WITH_OVERLAP_CHAR_THRESHOLD = 2600
OVERLAP_SINGLE_CHUNK_MIN_CHARS = 240
OVERLAP_MULTI_CHUNK_MIN_CHARS = 160
OVERLAP_MULTI_CHUNK_MATCHES = 2


@dataclass(frozen=True)
class GeographySample:
    provider: str
    doi: str
    title: str
    landing_url: str
    topic_tags: tuple[str, ...]
    year: int
    seed_level: int = 1


@dataclass(frozen=True)
class GeographyReportResult:
    provider: str
    doi: str
    title: str
    status: str
    source: str | None
    content_kind: str | None
    has_fulltext: bool
    warnings: list[str]
    source_trail: list[str]
    token_estimate_breakdown: TokenEstimateBreakdown
    elapsed_seconds: float
    error_code: str | None
    error_message: str | None
    issue_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeographyProviderSummary:
    provider: str
    attempted: int
    status_counts: dict[str, int]
    success_sources: list[str]
    success_source_trails: list[str]
    sample_dois: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeographyIssueSummary:
    issue_flag: str
    count: int
    sample_dois: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeographyAnalysisNote:
    key: str
    summary: str
    sample_dois: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeographyLiveReport:
    generated_at: str
    providers: list[str]
    per_provider_limit: int
    total_attempts: int
    results: list[GeographyReportResult]
    summary_by_provider: list[GeographyProviderSummary]
    summary_by_issue: list[GeographyIssueSummary]
    analysis_notes: list[GeographyAnalysisNote]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "providers": list(self.providers),
            "per_provider_limit": self.per_provider_limit,
            "total_attempts": self.total_attempts,
            "results": [item.to_dict() for item in self.results],
            "summary_by_provider": [item.to_dict() for item in self.summary_by_provider],
            "summary_by_issue": [item.to_dict() for item in self.summary_by_issue],
            "analysis_notes": [item.to_dict() for item in self.analysis_notes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    def to_markdown(self) -> str:
        lines = [
            "# Geography Live Report",
            "",
            f"- Generated: `{self.generated_at}`",
            f"- Providers: `{', '.join(self.providers)}`",
            f"- Attempts per provider: `{self.per_provider_limit}`",
            f"- Total attempts: `{self.total_attempts}`",
            "",
            "## Provider Summary",
            "",
            "| Provider | Attempted | Fulltext | Metadata | Not Configured | Rate Limited | No Result | Error |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for summary in self.summary_by_provider:
            counts = summary.status_counts
            lines.append(
                "| {provider} | {attempted} | {fulltext} | {metadata_only} | {not_configured} | {rate_limited} | {no_result} | {error} |".format(
                    provider=summary.provider,
                    attempted=summary.attempted,
                    fulltext=counts.get("fulltext", 0),
                    metadata_only=counts.get("metadata_only", 0),
                    not_configured=counts.get("not_configured", 0),
                    rate_limited=counts.get("rate_limited", 0),
                    no_result=counts.get("no_result", 0),
                    error=counts.get("error", 0),
                )
            )

        lines.extend(
            [
                "",
                "## Issue Summary",
                "",
                "| Issue Flag | Count | Sample DOIs |",
                "| --- | ---: | --- |",
            ]
        )
        if self.summary_by_issue:
            for summary in self.summary_by_issue:
                lines.append(
                    f"| `{summary.issue_flag}` | {summary.count} | {', '.join(summary.sample_dois) or '-'} |"
                )
        else:
            lines.append("| `none` | 0 | - |")

        lines.extend(["", "## Analysis Notes", ""])
        for note in self.analysis_notes:
            if note.sample_dois:
                lines.append(f"- `{note.key}`: {note.summary} Examples: {', '.join(note.sample_dois)}")
            else:
                lines.append(f"- `{note.key}`: {note.summary}")

        lines.extend(["", "## Attempts", ""])
        for provider in self.providers:
            lines.append(f"### {provider}")
            for result in self.results:
                if result.provider != provider:
                    continue
                flags = f" [{', '.join(result.issue_flags)}]" if result.issue_flags else ""
                lines.append(
                    f"- `{result.doi}` | `{result.status}` | source=`{result.source or '-'}`"
                    f" | content_kind=`{result.content_kind or '-'}`"
                    f" | elapsed=`{result.elapsed_seconds:.3f}s`{flags}"
                )
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def write_markdown(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")


def default_report_paths() -> tuple[Path, Path]:
    output_dir = resolve_repo_root() / "live-downloads" / "reports"
    return output_dir / "geography-live-report.json", output_dir / "geography-live-report.md"


def select_geography_samples(
    samples: Sequence[GeographySample],
    *,
    per_provider: int = 10,
    providers: Sequence[str] | None = None,
) -> list[GeographySample]:
    provider_order = [item for item in GEOGRAPHY_PROVIDER_ORDER if providers is None or item in providers]
    grouped: dict[str, list[GeographySample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.provider].append(sample)

    selected: list[GeographySample] = []
    for provider in provider_order:
        provider_samples = grouped.get(provider, [])
        if len(provider_samples) < per_provider:
            raise ValueError(
                f"Provider {provider!r} only has {len(provider_samples)} geography samples, expected at least {per_provider}."
            )
        selected.extend(provider_samples[:per_provider])
    return selected


def schedule_geography_samples(
    samples: Sequence[GeographySample],
    *,
    providers: Sequence[str],
) -> list[GeographySample]:
    grouped: dict[str, list[GeographySample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.provider].append(sample)

    scheduled: list[GeographySample] = []
    max_samples = max((len(grouped.get(provider, [])) for provider in providers), default=0)
    for sample_index in range(max_samples):
        for provider in providers:
            provider_samples = grouped.get(provider, [])
            if sample_index < len(provider_samples):
                scheduled.append(provider_samples[sample_index])
    return scheduled


def run_geography_live_report(
    samples: Sequence[GeographySample],
    *,
    per_provider: int = 10,
    providers: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> GeographyLiveReport:
    selected_samples = select_geography_samples(samples, per_provider=per_provider, providers=providers)
    scheduled_samples = schedule_geography_samples(
        selected_samples,
        providers=[item for item in GEOGRAPHY_PROVIDER_ORDER if providers is None or item in providers],
    )
    active_env = build_runtime_env(env)
    active_transport = transport if transport is not None else HttpTransport()
    client_registry = build_clients(active_transport, active_env)
    html_client = HtmlGenericClient(active_transport, active_env)
    results: list[GeographyReportResult] = []

    for sample in scheduled_samples:
        started_at = time.monotonic()
        try:
            envelope = fetch_paper(
                sample.doi,
                modes={"article", "markdown"},
                strategy=FetchStrategy(
                    allow_html_fallback=False,
                    allow_metadata_only_fallback=True,
                ),
                download_dir=None,
                clients=client_registry,
                html_client=html_client,
                transport=active_transport,
                env=active_env,
            )
            elapsed_seconds = round(time.monotonic() - started_at, 3)
            results.append(build_report_result(sample, envelope, elapsed_seconds=elapsed_seconds))
        except PaperFetchFailure as exc:
            results.append(
                GeographyReportResult(
                    provider=sample.provider,
                    doi=sample.doi,
                    title=sample.title,
                    status="error",
                    source=None,
                    content_kind=None,
                    has_fulltext=False,
                    warnings=[],
                    source_trail=[],
                    token_estimate_breakdown=TokenEstimateBreakdown(),
                    elapsed_seconds=round(time.monotonic() - started_at, 3),
                    error_code=exc.status,
                    error_message=exc.reason,
                    issue_flags=[],
                )
            )
        except Exception as exc:  # pragma: no cover - defensive live-only path
            results.append(
                GeographyReportResult(
                    provider=sample.provider,
                    doi=sample.doi,
                    title=sample.title,
                    status="error",
                    source=None,
                    content_kind=None,
                    has_fulltext=False,
                    warnings=[],
                    source_trail=[],
                    token_estimate_breakdown=TokenEstimateBreakdown(),
                    elapsed_seconds=round(time.monotonic() - started_at, 3),
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    issue_flags=[],
                )
            )

    report_providers = [item for item in GEOGRAPHY_PROVIDER_ORDER if any(result.provider == item for result in results)]
    return GeographyLiveReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        providers=report_providers,
        per_provider_limit=per_provider,
        total_attempts=len(results),
        results=results,
        summary_by_provider=build_provider_summaries(results, providers=report_providers),
        summary_by_issue=build_issue_summaries(results),
        analysis_notes=build_analysis_notes(results, providers=report_providers),
    )


def build_report_result(
    sample: GeographySample,
    envelope: FetchEnvelope,
    *,
    elapsed_seconds: float,
) -> GeographyReportResult:
    status, error_code = classify_result_status(sample.provider, envelope)
    return GeographyReportResult(
        provider=sample.provider,
        doi=sample.doi,
        title=sample.title,
        status=status,
        source=envelope.source,
        content_kind=envelope.content_kind,
        has_fulltext=envelope.has_fulltext,
        warnings=list(envelope.warnings),
        source_trail=list(envelope.source_trail),
        token_estimate_breakdown=envelope.token_estimate_breakdown,
        elapsed_seconds=elapsed_seconds,
        error_code=error_code,
        error_message=detect_error_message(status, envelope),
        issue_flags=collect_issue_flags(sample.provider, envelope, status=status),
    )


def classify_result_status(provider: str, envelope: FetchEnvelope) -> tuple[str, str | None]:
    if envelope.content_kind == "fulltext":
        return "fulltext", None

    source_trail = set(envelope.source_trail)
    if f"fulltext:{provider}_not_configured" in source_trail:
        return "not_configured", "not_configured"
    if f"fulltext:{provider}_rate_limited" in source_trail:
        return "rate_limited", "rate_limited"
    if (
        f"fulltext:{provider}_fail" in source_trail
        or f"fulltext:{provider}_not_usable" in source_trail
        or "fallback:html_fail" in source_trail
    ):
        return "no_result", "no_result"
    return "metadata_only", None


def detect_error_message(status: str, envelope: FetchEnvelope) -> str | None:
    if status in {"fulltext", "metadata_only"}:
        return None
    for warning in envelope.warnings:
        if warning != REPORT_RESULT_WARNING:
            return warning
    if envelope.warnings:
        return envelope.warnings[0]
    return None


def collect_issue_flags(provider: str, envelope: FetchEnvelope, *, status: str) -> list[str]:
    issue_flags: list[str] = []
    article = envelope.article
    metadata = getattr(article, "metadata", None)
    raw_abstract_text = getattr(metadata, "abstract", None)
    abstract_text = normalize_text(raw_abstract_text)
    body_sections = filtered_body_sections(getattr(article, "sections", []) or []) if article is not None else []
    body_text = "\n\n".join(normalize_text(section.text) for section in body_sections if normalize_text(section.text))

    if abstract_text and status == "fulltext":
        abstract_tokens = int(getattr(envelope.token_estimate_breakdown, "abstract", 0) or 0)
        overlap_detected = bool(body_text) and has_abstract_body_overlap(raw_abstract_text or abstract_text, body_text)
        if has_inflated_abstract(
            abstract_text,
            abstract_tokens=abstract_tokens,
            body_text=body_text,
            overlap_detected=overlap_detected,
        ):
            issue_flags.append("abstract_inflated")
        if overlap_detected:
            issue_flags.append("abstract_body_overlap")

    if article is not None and any(reference_doi_requires_normalization(item.doi) for item in article.references):
        issue_flags.append("refs_doi_not_normalized")
    if status == "fulltext" and envelope.source not in EXPECTED_FULLTEXT_SOURCES_BY_PROVIDER.get(provider, frozenset()):
        issue_flags.append("unexpected_source_path")
    if article is not None and not getattr(metadata, "authors", []) and not is_authorless_briefing_like(article):
        issue_flags.append("empty_authors")
    if len(envelope.warnings) >= 3:
        issue_flags.append("high_warning_count")
    return sorted(set(issue_flags))


def build_provider_summaries(
    results: Sequence[GeographyReportResult],
    *,
    providers: Sequence[str],
) -> list[GeographyProviderSummary]:
    summaries: list[GeographyProviderSummary] = []
    for provider in providers:
        provider_results = [item for item in results if item.provider == provider]
        counts = Counter(item.status for item in provider_results)
        summaries.append(
            GeographyProviderSummary(
                provider=provider,
                attempted=len(provider_results),
                status_counts={status: counts.get(status, 0) for status in GEOGRAPHY_RESULT_STATUSES},
                success_sources=sorted({item.source for item in provider_results if item.status == "fulltext" and item.source}),
                success_source_trails=sorted(
                    {
                        success_path_signature(item.source_trail)
                        for item in provider_results
                        if item.status == "fulltext"
                    }
                ),
                sample_dois=[item.doi for item in provider_results[:3]],
            )
        )
    return summaries


def build_issue_summaries(results: Sequence[GeographyReportResult]) -> list[GeographyIssueSummary]:
    grouped: dict[str, list[GeographyReportResult]] = defaultdict(list)
    for result in results:
        for issue_flag in result.issue_flags:
            grouped[issue_flag].append(result)
    summaries = [
        GeographyIssueSummary(
            issue_flag=issue_flag,
            count=len(items),
            sample_dois=[item.doi for item in items[:5]],
        )
        for issue_flag, items in sorted(grouped.items())
    ]
    return summaries


def build_analysis_notes(
    results: Sequence[GeographyReportResult],
    *,
    providers: Sequence[str],
) -> list[GeographyAnalysisNote]:
    notes: list[GeographyAnalysisNote] = []
    precheck_results = [item for item in results if item.status in {"not_configured", "rate_limited", "no_result"}]
    notes.append(
        GeographyAnalysisNote(
            key="precheck_gap",
            summary=(
                f"{len(precheck_results)} attempts produced analyzable provider-managed failures. "
                "This report records them per sample instead of letting provider-level prechecks skip the whole publisher."
            ),
            sample_dois=[item.doi for item in precheck_results[:5]],
        )
    )

    pnas_issues = [
        item
        for item in results
        if item.provider == "pnas" and any(flag in item.issue_flags for flag in ("abstract_inflated", "abstract_body_overlap"))
    ]
    notes.append(
        GeographyAnalysisNote(
            key="pnas_abstract_quality",
            summary=(
                f"{len(pnas_issues)} PNAS attempts were flagged for oversized or body-overlapping abstracts."
                if pnas_issues
                else "No PNAS attempts were flagged for oversized or body-overlapping abstracts in this run."
            ),
            sample_dois=[item.doi for item in pnas_issues[:5]],
        )
    )

    wiley_issues = [item for item in results if item.provider == "wiley" and "refs_doi_not_normalized" in item.issue_flags]
    notes.append(
        GeographyAnalysisNote(
            key="wiley_reference_doi_normalization",
            summary=(
                f"{len(wiley_issues)} Wiley attempts contained reference DOIs that still need ASCII/spacing normalization."
                if wiley_issues
                else "No Wiley attempts were flagged for reference DOI normalization in this run."
            ),
            sample_dois=[item.doi for item in wiley_issues[:5]],
        )
    )

    stability_parts: list[str] = []
    for provider in providers:
        provider_results = [item for item in results if item.provider == provider and item.status == "fulltext"]
        signatures = sorted({success_path_signature(item.source_trail) for item in provider_results})
        if not signatures:
            stability_parts.append(f"{provider}: no fulltext successes")
            continue
        descriptor = "stable" if len(signatures) == 1 else f"mixed ({len(signatures)})"
        stability_parts.append(f"{provider}: {descriptor}")
    notes.append(
        GeographyAnalysisNote(
            key="source_trail_stability",
            summary="; ".join(stability_parts),
            sample_dois=[item.doi for item in results if item.status == "fulltext"][:5],
        )
    )
    return notes


def has_abstract_body_overlap(abstract_text: str, body_text: str) -> bool:
    normalized_body = normalize_overlap_text(body_text)
    if not normalized_body:
        return False
    matched_chunks = 0
    for chunk in overlap_chunks(abstract_text):
        if chunk in normalized_body:
            if len(chunk) >= OVERLAP_SINGLE_CHUNK_MIN_CHARS:
                return True
            matched_chunks += 1
            if matched_chunks >= OVERLAP_MULTI_CHUNK_MATCHES:
                return True
    return False


def has_inflated_abstract(
    abstract_text: str,
    *,
    abstract_tokens: int,
    body_text: str,
    overlap_detected: bool | None = None,
) -> bool:
    if abstract_tokens >= ABSTRACT_INFLATED_TOKEN_THRESHOLD or len(abstract_text) >= ABSTRACT_INFLATED_CHAR_THRESHOLD:
        return True
    if overlap_detected is None:
        overlap_detected = bool(body_text) and has_abstract_body_overlap(abstract_text, body_text)
    if overlap_detected and (
        abstract_tokens >= ABSTRACT_INFLATED_WITH_OVERLAP_TOKEN_THRESHOLD
        or len(abstract_text) >= ABSTRACT_INFLATED_WITH_OVERLAP_CHAR_THRESHOLD
    ):
        return True
    return False


def is_authorless_briefing_like(article: Any) -> bool:
    headings = [
        normalize_text(getattr(section, "heading", "")).lower()
        for section in filtered_body_sections(getattr(article, "sections", []) or [])
        if normalize_text(getattr(section, "heading", ""))
    ]
    if not headings:
        return False
    heading_set = set(headings)
    return all(item in heading_set for item in RESEARCH_BRIEFING_HEADING_SIGNATURE)


def overlap_chunks(text: str) -> list[str]:
    chunks = [
        normalize_overlap_text(item)
        for item in re.split(r"\n\s*\n", text)
        if len(normalize_overlap_text(item)) >= OVERLAP_MULTI_CHUNK_MIN_CHARS
    ]
    if not chunks:
        return []
    if len(chunks) == 1:
        return chunks
    return chunks


def normalize_overlap_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip().lower()


def reference_doi_requires_normalization(doi: str | None) -> bool:
    normalized = normalize_text(doi)
    if not normalized:
        return False
    ascii_normalized = normalized.encode("ascii", errors="ignore").decode("ascii")
    lowered = normalized.lower()
    if ascii_normalized != normalized:
        return True
    if normalized.startswith(("http://", "https://", "doi:")):
        return True
    if any(character.isspace() for character in normalized):
        return True
    return not ASCII_DOI_PATTERN.match(lowered)


def success_path_signature(source_trail: Sequence[str]) -> str:
    markers = [item for item in source_trail if item.startswith("fulltext:") and ("_ok" in item or "_article_ok" in item)]
    return " -> ".join(markers) if markers else "none"
