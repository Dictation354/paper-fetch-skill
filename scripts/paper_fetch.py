#!/usr/bin/env python3
"""AI-friendly paper fetch entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_model import ArticleModel, metadata_only_article, normalize_text
from fetch_common import (
    HttpTransport,
    ProviderFailure,
    build_output_path,
    build_runtime_env,
    dedupe_authors,
    sanitize_filename,
    save_payload,
)
from provider_clients import build_clients
from providers.html_generic import HtmlGenericClient
from publisher_identity import infer_provider_from_doi, normalize_doi
from resolve_query import ResolvedQuery, resolve_query


class PaperFetchFailure(Exception):
    def __init__(self, status: str, reason: str, *, candidates: list[dict[str, Any]] | None = None) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.candidates = list(candidates or [])


def extend_unique(target: list[str], items: list[str] | None) -> None:
    for item in items or []:
        normalized = normalize_text(item)
        if normalized and normalized not in target:
            target.append(normalized)


def source_trail_for_failure(stage: str, provider_name: str, failure: ProviderFailure) -> str:
    if failure.code == "not_configured":
        suffix = "not_configured"
    elif failure.code == "rate_limited":
        suffix = "rate_limited"
    else:
        suffix = "fail"
    return f"{stage}:{provider_name}_{suffix}"


def finalize_article(article: ArticleModel, *, warnings: list[str] | None = None, source_trail: list[str] | None = None) -> ArticleModel:
    extend_unique(article.quality.warnings, list(warnings or []))
    extend_unique(article.quality.source_trail, list(source_trail or []))
    return article


def merge_metadata(primary: Mapping[str, Any] | None, secondary: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(secondary or {})
    merged.update(primary or {})
    scalar_keys = ("doi", "title", "journal_title", "published", "landing_page_url", "abstract", "publisher")

    def scalarize(value: Any, *, preserve_blank: bool = False) -> str | None:
        if isinstance(value, str):
            normalized = normalize_text(value)
            if normalized:
                return normalized
            return "" if preserve_blank else None
        if isinstance(value, list):
            for item in value:
                scalar = scalarize(item, preserve_blank=preserve_blank)
                if scalar is not None:
                    return scalar
            return "" if preserve_blank and value else None
        if isinstance(value, Mapping):
            for key in ("value", "url", "URL"):
                scalar = scalarize(value.get(key), preserve_blank=preserve_blank)
                if scalar is not None:
                    return scalar
            return "" if preserve_blank and value else None
        if value is None:
            return None
        normalized = normalize_text(str(value))
        if normalized:
            return normalized
        return "" if preserve_blank else None

    for key in scalar_keys:
        primary_has_value = primary is not None and key in primary and primary.get(key) is not None
        if primary_has_value:
            merged[key] = scalarize(primary.get(key), preserve_blank=True)
        else:
            merged[key] = scalarize((secondary or {}).get(key))

    def merged_list(key: str, *, semantic: bool = False) -> list[Any]:
        result: list[Any] = []
        for item in list((primary or {}).get(key) or []) + list((secondary or {}).get(key) or []):
            normalized_item = item
            if isinstance(item, str):
                normalized_item = normalize_text(item)
            if normalized_item and normalized_item not in result:
                result.append(normalized_item)
        if semantic:
            return dedupe_authors([str(item) for item in result])
        return result

    merged["authors"] = merged_list("authors", semantic=True)
    merged["keywords"] = merged_list("keywords")
    merged["license_urls"] = merged_list("license_urls")
    merged["fulltext_links"] = merged_list("fulltext_links")
    merged["references"] = merged_list("references")
    for key in scalar_keys:
        if merged.get(key) == "":
            merged[key] = None
    return merged


def metadata_from_resolution(resolved: ResolvedQuery) -> dict[str, Any]:
    return {
        "doi": resolved.doi,
        "title": resolved.title,
        "journal_title": None,
        "published": None,
        "landing_page_url": resolved.landing_url,
        "authors": [],
        "keywords": [],
        "license_urls": [],
        "references": [],
        "fulltext_links": [],
    }


def fetch_metadata_for_resolved_query(
    resolved: ResolvedQuery,
    *,
    clients: Mapping[str, Any],
) -> tuple[dict[str, Any], str | None, list[str]]:
    provider_name = resolved.provider_hint
    if not provider_name and resolved.doi:
        provider_name = infer_provider_from_doi(resolved.doi)
    provider_name = provider_name or "crossref"

    official_metadata: dict[str, Any] | None = None
    crossref_metadata: dict[str, Any] | None = None
    source_trail: list[str] = []

    if resolved.doi and provider_name != "crossref":
        client = clients.get(provider_name)
        if client is not None:
            try:
                official_metadata = client.fetch_metadata({"doi": resolved.doi})
                if official_metadata:
                    source_trail.append(f"metadata:{provider_name}_ok")
            except ProviderFailure as exc:
                official_metadata = None
                source_trail.append(source_trail_for_failure("metadata", provider_name, exc))

    if resolved.doi:
        try:
            crossref_metadata = clients["crossref"].fetch_metadata({"doi": resolved.doi})
            if crossref_metadata:
                source_trail.append("metadata:crossref_ok")
        except ProviderFailure as exc:
            crossref_metadata = None
            source_trail.append(source_trail_for_failure("metadata", "crossref", exc))

    if official_metadata or crossref_metadata:
        metadata = merge_metadata(official_metadata, crossref_metadata)
        metadata["provider"] = (official_metadata or crossref_metadata or {}).get("provider")
        metadata["official_provider"] = (official_metadata or crossref_metadata or {}).get("official_provider")
        if not metadata.get("landing_page_url"):
            metadata["landing_page_url"] = resolved.landing_url
        return metadata, provider_name, source_trail

    source_trail.append("metadata:resolution_only")
    return metadata_from_resolution(resolved), provider_name, source_trail


def build_metadata_only_result(
    metadata: Mapping[str, Any],
    *,
    resolved: ResolvedQuery,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    return metadata_only_article(
        source="crossref_meta",
        metadata=metadata,
        doi=normalize_doi(str(metadata.get("doi") or resolved.doi or "")) or None,
        warnings=list(warnings or []),
        source_trail=list(source_trail or []),
    )


def maybe_save_provider_payload(
    raw_payload: Any,
    *,
    allow_downloads: bool,
    output_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    if not raw_payload.needs_local_copy:
        return [], []
    provider_slug = normalize_text(str(raw_payload.provider or "provider")).lower().replace(" ", "_") or "provider"
    provider_label = provider_slug.replace("_", " ").title()
    if not allow_downloads:
        return [f"{provider_label} official PDF/binary was not written to disk because --no-download was set."], [
            f"download:{provider_slug}_skipped"
        ]

    effective_output_dir = output_dir or (ROOT_DIR / "live-downloads")
    saved_path = save_payload(
        build_output_path(
            effective_output_dir,
            doi,
            str(metadata.get("title") or ""),
            raw_payload.content_type,
            raw_payload.source_url,
        ),
        raw_payload.body,
    )
    if saved_path:
        return [f"{provider_label} official full text was downloaded as PDF/binary to {saved_path}."], [
            f"download:{provider_slug}_saved"
        ]
    return [f"{provider_label} official full text was available only as PDF/binary and could not be written to disk."], [
        f"download:{provider_slug}_save_failed"
    ]


def fetch_paper_model(
    query: str,
    *,
    allow_html_fallback: bool = True,
    allow_downloads: bool = True,
    output_dir: Path | None = None,
    clients: Mapping[str, Any] | None = None,
    html_client: HtmlGenericClient | None = None,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> ArticleModel:
    active_env = env or build_runtime_env()
    active_transport = transport or HttpTransport()
    client_registry = dict(clients or build_clients(active_transport, active_env))
    resolved = resolve_query(query, transport=active_transport, env=active_env)
    source_trail: list[str] = [f"resolve:{resolved.query_kind}"]
    if resolved.doi:
        source_trail.append("resolve:doi_selected")
    if resolved.candidates and not resolved.doi:
        raise PaperFetchFailure(
            "ambiguous",
            "Query resolution is ambiguous; choose one of the DOI candidates.",
            candidates=resolved.candidates,
        )

    metadata, provider_name, metadata_trail = fetch_metadata_for_resolved_query(resolved, clients=client_registry)
    extend_unique(source_trail, metadata_trail)
    landing_url = normalize_text(str(metadata.get("landing_page_url") or resolved.landing_url or "")) or None
    doi = normalize_doi(str(metadata.get("doi") or resolved.doi or "")) or None
    html_fallback_client = html_client or HtmlGenericClient(active_transport, active_env)
    warnings: list[str] = []

    if doi and provider_name and provider_name != "crossref":
        provider_client = client_registry.get(provider_name)
        if provider_client is not None:
            extend_unique(source_trail, [f"fulltext:{provider_name}_attempt"])
            try:
                raw_payload = provider_client.fetch_raw_fulltext(doi, metadata)
                extend_unique(source_trail, [f"fulltext:{provider_name}_raw_ok"])
                download_warnings, download_trail = maybe_save_provider_payload(
                    raw_payload,
                    allow_downloads=allow_downloads,
                    output_dir=output_dir,
                    doi=doi,
                    metadata=metadata,
                )
                extend_unique(warnings, download_warnings)
                extend_unique(source_trail, download_trail)
                article = provider_client.to_article_model(metadata, raw_payload)
                extend_unique(source_trail, article.quality.source_trail)
                if article.quality.has_fulltext and article.sections:
                    extend_unique(source_trail, [f"fulltext:{provider_name}_article_ok"])
                    return finalize_article(article, warnings=warnings, source_trail=source_trail)
                if article.quality.has_fulltext and not article.sections:
                    warnings.append("Official full text only contained abstract-level content; continuing to HTML fallback.")
                    extend_unique(source_trail, [f"fulltext:{provider_name}_abstract_only"])
                else:
                    extend_unique(source_trail, [f"fulltext:{provider_name}_not_usable"])
                extend_unique(warnings, article.quality.warnings)
            except ProviderFailure as exc:
                warnings.append(exc.message)
                extend_unique(source_trail, [source_trail_for_failure("fulltext", provider_name, exc)])

    if not allow_html_fallback:
        extend_unique(source_trail, ["fallback:html_disabled"])
    if allow_html_fallback and landing_url:
        extend_unique(source_trail, ["fallback:html_attempt"])
        try:
            article = html_fallback_client.fetch_article_model(
                landing_url,
                metadata=metadata,
                expected_doi=doi,
            )
            if article.quality.has_fulltext:
                extend_unique(source_trail, article.quality.source_trail)
                extend_unique(source_trail, ["fallback:html_ok"])
                return finalize_article(article, warnings=warnings, source_trail=source_trail)
            extend_unique(warnings, article.quality.warnings)
            extend_unique(source_trail, article.quality.source_trail)
            extend_unique(source_trail, ["fallback:html_not_usable"])
        except ProviderFailure as exc:
            warnings.append(exc.message)
            extend_unique(source_trail, ["fallback:html_fail"])
    elif allow_html_fallback:
        extend_unique(source_trail, ["fallback:html_unavailable"])

    if metadata:
        warnings.append("Full text was not available; returning metadata and abstract only.")
        extend_unique(source_trail, ["fallback:metadata_only"])
        return build_metadata_only_result(metadata, resolved=resolved, warnings=warnings, source_trail=source_trail)

    raise PaperFetchFailure("error", "Unable to resolve metadata or full text for the requested paper.")


def save_markdown_to_disk(
    article: ArticleModel,
    *,
    output_dir: Path | None,
    include_refs: str,
    max_tokens: int,
) -> None:
    effective_dir = output_dir or (ROOT_DIR / "live-downloads")
    has_usable_fulltext = bool(article.quality.has_fulltext and article.sections)
    if not has_usable_fulltext:
        extend_unique(
            article.quality.warnings,
            ["--save-markdown was set but full text was not available; nothing written to disk."],
        )
        extend_unique(article.quality.source_trail, ["download:markdown_skipped_no_fulltext"])
        return

    effective_dir.mkdir(parents=True, exist_ok=True)
    base = sanitize_filename(article.doi or article.title or "article")
    target = effective_dir / f"{base}.md"
    markdown = article.to_ai_markdown(include_refs=include_refs, max_tokens=max_tokens)
    target.write_text(markdown, encoding="utf-8")
    extend_unique(
        article.quality.warnings,
        [f"Markdown full text was saved to {target}."],
    )
    extend_unique(article.quality.source_trail, ["download:markdown_saved"])


def serialize_article(article: ArticleModel, *, output_format: str, include_refs: str, max_tokens: int) -> str:
    markdown = article.to_ai_markdown(include_refs=include_refs, max_tokens=max_tokens)
    if output_format == "markdown":
        return markdown
    if output_format == "json":
        return article.to_json()
    return json.dumps({"article": article.to_dict(), "markdown": markdown}, ensure_ascii=False, indent=2)


def write_output(serialized: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(serialized)
        if not serialized.endswith("\n"):
            sys.stdout.write("\n")
        return
    Path(output).write_text(serialized, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch AI-friendly full text for a paper by DOI, URL, or title.")
    parser.add_argument("--query", required=True, help="DOI, paper landing URL, or title query")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="markdown")
    parser.add_argument("--output", default="-", help="Output destination. Use - for stdout.")
    parser.add_argument(
        "--output-dir",
        help="Directory for saving raw provider downloads such as Wiley PDFs. Defaults to ./live-downloads for Wiley binary full text.",
    )
    parser.add_argument("--no-download", action="store_true", help="Do not write provider PDF/binary payloads to disk.")
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        help=(
            "Also write the rendered AI Markdown full text to disk (defaults to ./live-downloads, "
            "overridable via --output-dir). Only writes when full text was actually retrieved. "
            "For Wiley the Markdown is produced from PDF text extraction and may be lower fidelity "
            "than Elsevier/Springer XML."
        ),
    )
    parser.add_argument("--include-refs", choices=("none", "top10", "all"), default="top10")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--no-html-fallback", action="store_true")
    args = parser.parse_args()

    try:
        output_dir = Path(args.output_dir) if args.output_dir else None
        article = fetch_paper_model(
            args.query,
            allow_html_fallback=not args.no_html_fallback,
            allow_downloads=not args.no_download,
            output_dir=output_dir,
        )
        if args.save_markdown:
            save_markdown_to_disk(
                article,
                output_dir=output_dir,
                include_refs=args.include_refs,
                max_tokens=args.max_tokens,
            )
        serialized = serialize_article(
            article,
            output_format=args.format,
            include_refs=args.include_refs,
            max_tokens=args.max_tokens,
        )
        write_output(serialized, args.output)
        return 0
    except PaperFetchFailure as exc:
        sys.stderr.write(
            json.dumps(
                {
                    "status": exc.status,
                    "reason": exc.reason,
                    "candidates": exc.candidates or None,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return 2 if exc.status == "ambiguous" else 1
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps({"status": "error", "reason": exc.message}, ensure_ascii=False) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
