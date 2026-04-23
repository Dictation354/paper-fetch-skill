"""Export problematic geography live-report samples into a dedicated folder."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from .config import build_runtime_env, resolve_repo_root
from .geography_live import GeographySample, build_report_result
from .http import HttpTransport
from .models import RenderOptions
from .service import FetchStrategy, PaperFetchFailure, fetch_paper
from .utils import normalize_text, sanitize_filename


@dataclass(frozen=True)
class GeographyIssueExportEntry:
    provider: str
    doi: str
    title: str
    issue_flags: list[str]
    output_dir: str
    export_status: str
    elapsed_seconds: float
    exported_files: list[str]
    current_status: str | None = None
    current_source: str | None = None
    current_content_kind: str | None = None
    current_issue_flags: list[str] | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_issue_artifact_output_dir() -> Path:
    return resolve_repo_root() / "live-downloads" / "geography-issue-artifacts"


def load_report_payload(report_json_path: Path) -> dict[str, Any]:
    return json.loads(report_json_path.read_text(encoding="utf-8"))


def collect_issue_rows(
    report_payload: Mapping[str, Any],
    *,
    issue_flags: Sequence[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    wanted_flags = {normalize_text(item) for item in (issue_flags or []) if normalize_text(item)}
    rows: list[dict[str, Any]] = []
    for raw_row in report_payload.get("results", []):
        row = dict(raw_row)
        row_flags = [normalize_text(item) for item in row.get("issue_flags", []) if normalize_text(item)]
        if not row_flags:
            continue
        if wanted_flags and not wanted_flags.intersection(row_flags):
            continue
        row["issue_flags"] = row_flags
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def schedule_issue_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    providers: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    provider_order = list(providers or [])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw_row in rows:
        row = dict(raw_row)
        provider = normalize_text(row.get("provider"))
        if not provider:
            continue
        grouped[provider].append(row)
        if provider not in provider_order:
            provider_order.append(provider)

    scheduled: list[dict[str, Any]] = []
    max_rows = max((len(grouped.get(provider, [])) for provider in provider_order), default=0)
    for row_index in range(max_rows):
        for provider in provider_order:
            provider_rows = grouped.get(provider, [])
            if row_index < len(provider_rows):
                scheduled.append(provider_rows[row_index])
    return scheduled


def export_geography_issue_artifacts(
    *,
    report_json_path: Path,
    output_dir: Path | None = None,
    issue_flags: Sequence[str] | None = None,
    limit: int | None = None,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    report_payload = load_report_payload(report_json_path)
    selected_rows = collect_issue_rows(report_payload, issue_flags=issue_flags, limit=limit)
    providers = [normalize_text(item) for item in report_payload.get("providers", []) if normalize_text(item)]
    scheduled_rows = schedule_issue_rows(selected_rows, providers=providers)
    export_root = Path(output_dir or default_issue_artifact_output_dir())
    export_root.mkdir(parents=True, exist_ok=True)

    active_env = build_runtime_env(env)
    active_transport = transport if transport is not None else HttpTransport()

    entries: list[GeographyIssueExportEntry] = []
    started_at = time.monotonic()

    for row in scheduled_rows:
        entry = export_issue_row(row=row, output_root=export_root, env=active_env, transport=active_transport)
        entries.append(entry)

    summary = {
        "generated_from_report": str(report_json_path),
        "output_dir": str(export_root),
        "selected_issue_flags": sorted({flag for row in scheduled_rows for flag in row.get("issue_flags", [])}),
        "requested_issue_flags": [normalize_text(item) for item in (issue_flags or []) if normalize_text(item)],
        "total_selected": len(scheduled_rows),
        "exported": sum(1 for entry in entries if entry.export_status == "exported"),
        "failed": sum(1 for entry in entries if entry.export_status != "exported"),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "entries": [entry.to_dict() for entry in entries],
    }
    (export_root / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def export_issue_row(
    *,
    row: Mapping[str, Any],
    output_root: Path,
    env: Mapping[str, str],
    transport: HttpTransport,
) -> GeographyIssueExportEntry:
    doi = normalize_text(row.get("doi")) or "unknown-doi"
    provider = normalize_text(row.get("provider")) or "unknown-provider"
    title = normalize_text(row.get("title")) or doi
    flags = [normalize_text(item) for item in row.get("issue_flags", []) if normalize_text(item)]
    entry_dir = output_root / sanitize_filename(doi)
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / "original-issue-row.json").write_text(json.dumps(dict(row), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    started_at = time.monotonic()
    try:
        envelope = fetch_paper(
            doi,
            modes={"article", "markdown"},
            strategy=FetchStrategy(
                allow_metadata_only_fallback=True,
            ),
            render=RenderOptions(include_refs="all", asset_profile="none", max_tokens="full_text"),
            download_dir=entry_dir,
            transport=transport,
            env=env,
        )
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        sample = GeographySample(
            provider=provider,
            doi=doi,
            title=title,
            landing_url="",
            topic_tags=tuple(),
            year=0,
            seed_level=0,
        )
        current_result = build_report_result(sample, envelope, elapsed_seconds=elapsed_seconds)
        (entry_dir / "fetch-envelope.json").write_text(envelope.to_json() + "\n", encoding="utf-8")
        if envelope.article is not None:
            (entry_dir / "article.json").write_text(envelope.article.to_json() + "\n", encoding="utf-8")
        if envelope.markdown is not None:
            (entry_dir / "extracted.md").write_text(envelope.markdown, encoding="utf-8")
        (entry_dir / "current-issue-row.json").write_text(json.dumps(current_result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        return GeographyIssueExportEntry(
            provider=provider,
            doi=doi,
            title=title,
            issue_flags=flags,
            output_dir=str(entry_dir),
            export_status="exported",
            elapsed_seconds=elapsed_seconds,
            exported_files=list_exported_files(entry_dir),
            current_status=current_result.status,
            current_source=current_result.source,
            current_content_kind=current_result.content_kind,
            current_issue_flags=current_result.issue_flags,
        )
    except PaperFetchFailure as exc:
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        error_payload = {
            "provider": provider,
            "doi": doi,
            "title": title,
            "issue_flags": flags,
            "error_code": exc.status,
            "error_message": exc.reason,
        }
        (entry_dir / "export-error.json").write_text(json.dumps(error_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return GeographyIssueExportEntry(
            provider=provider,
            doi=doi,
            title=title,
            issue_flags=flags,
            output_dir=str(entry_dir),
            export_status="error",
            elapsed_seconds=elapsed_seconds,
            exported_files=list_exported_files(entry_dir),
            error_code=exc.status,
            error_message=exc.reason,
        )
    except Exception as exc:  # pragma: no cover - defensive export path
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        error_payload = {
            "provider": provider,
            "doi": doi,
            "title": title,
            "issue_flags": flags,
            "error_code": exc.__class__.__name__,
            "error_message": str(exc),
        }
        (entry_dir / "export-error.json").write_text(json.dumps(error_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return GeographyIssueExportEntry(
            provider=provider,
            doi=doi,
            title=title,
            issue_flags=flags,
            output_dir=str(entry_dir),
            export_status="error",
            elapsed_seconds=elapsed_seconds,
            exported_files=list_exported_files(entry_dir),
            error_code=exc.__class__.__name__,
            error_message=str(exc),
        )


def list_exported_files(entry_dir: Path) -> list[str]:
    return sorted(
        str(path.relative_to(entry_dir))
        for path in entry_dir.rglob("*")
        if path.is_file()
    )


def effective_issue_flags(entry: Mapping[str, Any]) -> list[str]:
    if "current_issue_flags" in entry:
        return [
            normalize_text(item)
            for item in entry.get("current_issue_flags", [])
            if normalize_text(item)
        ]
    return [normalize_text(item) for item in entry.get("issue_flags", []) if normalize_text(item)]


def materialize_issue_type_view(
    *,
    artifact_root: Path,
    clean: bool = True,
) -> dict[str, Any]:
    index_payload = load_report_payload(artifact_root / "index.json")
    export_dir_names = {
        Path(entry["output_dir"]).name
        for entry in index_payload.get("entries", [])
        if normalize_text(entry.get("output_dir"))
    }
    issue_dirs = sorted(
        {
            flag
            for entry in index_payload.get("entries", [])
            for flag in effective_issue_flags(entry)
            if normalize_text(flag)
        }
    )

    if clean:
        stale_issue_dirs = [
            path
            for path in artifact_root.iterdir()
            if path.is_dir() and path.name not in export_dir_names and path.name not in issue_dirs
        ]
        for stale_dir in stale_issue_dirs:
            for child in sorted(stale_dir.iterdir()):
                if child.is_symlink() or child.is_file():
                    child.unlink()
                elif child.is_dir():
                    for nested in sorted(child.rglob("*"), reverse=True):
                        if nested.is_symlink() or nested.is_file():
                            nested.unlink()
                        elif nested.is_dir():
                            nested.rmdir()
                    child.rmdir()
            stale_dir.rmdir()
        for issue_flag in issue_dirs:
            issue_dir = artifact_root / issue_flag
            if issue_dir.exists():
                for child in sorted(issue_dir.iterdir()):
                    if child.is_symlink() or child.is_file():
                        child.unlink()
                    elif child.is_dir():
                        for nested in sorted(child.rglob("*"), reverse=True):
                            if nested.is_symlink() or nested.is_file():
                                nested.unlink()
                            elif nested.is_dir():
                                nested.rmdir()
                        child.rmdir()
                issue_dir.rmdir()

    summary_entries: list[dict[str, Any]] = []
    for issue_flag in issue_dirs:
        issue_dir = artifact_root / issue_flag
        issue_dir.mkdir(parents=True, exist_ok=True)
        linked: list[str] = []
        for entry in index_payload.get("entries", []):
            entry_flags = effective_issue_flags(entry)
            if issue_flag not in entry_flags:
                continue
            entry_dir = Path(entry["output_dir"])
            link_path = issue_dir / entry_dir.name
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(entry_dir.resolve(), target_is_directory=True)
            linked.append(entry["doi"])

        summary = {
            "issue_flag": issue_flag,
            "count": len(linked),
            "dois": linked,
        }
        (issue_dir / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_entries.append(summary)

    view_summary = {
        "artifact_root": str(artifact_root),
        "issue_dirs": summary_entries,
    }
    (artifact_root / "issue-view-index.json").write_text(json.dumps(view_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return view_summary
