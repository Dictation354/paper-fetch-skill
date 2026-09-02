"""Envelope rendering and article finalization stage."""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from ..artifacts import ArtifactStore
from ..extraction.html.asset_fields import MARKDOWN_ASSET_REFERENCE_FIELDS
from ..markdown.images import render_markdown_image
from ..models import ArticleModel, FetchEnvelope, OutputMode, RenderOptions
from ..models.markdown import (
    image_reference_basename,
    image_reference_candidates,
    replace_markdown_images,
)
from ..provider_catalog import known_article_source_names
from ..reason_codes import FULLTEXT, METADATA_ONLY
from ..tracing import (
    TraceEvent,
    download_marker,
    fallback_marker,
    project_source_trail_trace,
    source_trail_from_trace,
    trace_from_markers,
)
from ..utils import (
    _extract_year,
    extend_unique,
    format_paper_stem,
    is_http_url,
    normalize_text,
    sanitize_filename,
)
from .types import effective_asset_profile


def finalize_article(
    article: ArticleModel,
    *,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    trace: list[TraceEvent] | None = None,
) -> ArticleModel:
    extend_unique(article.quality.warnings, list(warnings or []))
    if source_trail or trace:
        projected = project_source_trail_trace(
            [*article.quality.source_trail, *list(source_trail or [])],
            trace,
        )
        article.quality.source_trail = source_trail_from_trace(projected)
    return article


def public_source_for_article(article: ArticleModel) -> str:
    if fallback_marker(METADATA_ONLY) in article.quality.source_trail:
        return METADATA_ONLY
    if article.source in known_article_source_names():
        return article.source
    return article.source


def relative_asset_link(value: str | None, *, target_path: Path) -> str | None:
    original = str(value or "").strip()
    if not original or original.startswith(("http://", "https://", "//")):
        return None
    source_path = Path(original).expanduser()
    if not source_path.is_file():
        return None
    source_path = source_path.resolve()
    target_dir = target_path.parent.resolve()
    relative = Path(os.path.relpath(source_path, start=target_dir))
    return urllib.parse.quote(relative.as_posix(), safe="/._-")


def _local_asset_lookup_by_basename(
    article: ArticleModel | None,
    *,
    target_path: Path,
) -> dict[str, tuple[str, Any]]:
    if article is None:
        return {}

    candidates: dict[str, tuple[str, Any]] = {}
    ambiguous: set[str] = set()
    for asset in article.assets:
        relative_path = relative_asset_link(asset.path, target_path=target_path)
        if relative_path is None:
            continue
        basenames = {Path(str(asset.path or "")).name}
        source_url = str(asset.url or "").strip()
        if source_url:
            basenames.add(
                image_reference_basename(
                    urllib.parse.unquote(urllib.parse.urlparse(source_url).path)
                )
            )
        for basename in basenames:
            if not basename:
                continue
            value = (relative_path, asset)
            existing = candidates.get(basename)
            if existing is None:
                candidates[basename] = value
            elif existing[0] != relative_path:
                ambiguous.add(basename)

    return {
        basename: path
        for basename, path in candidates.items()
        if basename not in ambiguous
    }


def _asset_field(asset: Any, field: str) -> str | None:
    if isinstance(asset, Mapping):
        return normalize_text(asset.get(field)) or None
    return normalize_text(getattr(asset, field, None)) or None


def _local_asset_lookups(
    article: ArticleModel | None,
    *,
    target_path: Path,
) -> tuple[dict[str, tuple[str, Any]], dict[str, tuple[str, Any]]]:
    if article is None:
        return {}, {}

    exact: dict[str, tuple[str, Any]] = {}
    exact_ambiguous: set[str] = set()
    basenames: dict[str, tuple[str, Any]] = {}
    basename_ambiguous: set[str] = set()
    for asset in article.assets:
        relative_path = relative_asset_link(
            _asset_field(asset, "path"), target_path=target_path
        )
        if relative_path is None:
            continue
        candidates: set[str] = set()
        for field in MARKDOWN_ASSET_REFERENCE_FIELDS:
            candidates |= image_reference_candidates(_asset_field(asset, field))
        for candidate in candidates:
            value = (relative_path, asset)
            existing = exact.get(candidate)
            if existing is None:
                exact[candidate] = value
            elif existing[0] != relative_path:
                exact_ambiguous.add(candidate)

            basename = image_reference_basename(candidate)
            if not basename:
                continue
            existing_basename = basenames.get(basename)
            if existing_basename is None:
                basenames[basename] = value
            elif existing_basename[0] != relative_path:
                basename_ambiguous.add(basename)

    return (
        {
            candidate: path
            for candidate, path in exact.items()
            if candidate not in exact_ambiguous
        },
        {
            basename: path
            for basename, path in basenames.items()
            if basename not in basename_ambiguous
        },
    )


def _remote_asset_basename(destination: str) -> str | None:
    if not destination.startswith(("http://", "https://", "//")):
        return None
    parsed = urllib.parse.urlparse(
        destination if not destination.startswith("//") else f"https:{destination}"
    )
    basename = Path(urllib.parse.unquote(parsed.path)).name
    return basename or None


def _publisher_root_relative_asset_link(
    value: str | None,
    *,
    article: ArticleModel | None,
) -> str | None:
    original = str(value or "").strip()
    if not original.lower().startswith("/cms/") or article is None:
        return None
    landing_page_url = normalize_text(article.metadata.landing_page_url)
    if not is_http_url(landing_page_url):
        return None
    return urllib.parse.urljoin(landing_page_url, original)


def _render_asset_markdown_image(
    asset: Any,
    *,
    fallback_alt: str,
    relative_path: str,
    title: str = "",
) -> str:
    kind = _asset_field(asset, "kind") or ""
    heading = _asset_field(asset, "heading") or fallback_alt
    destination = f'{relative_path} "{title}"' if title else relative_path
    return render_markdown_image(kind, heading, destination)


def rewrite_markdown_asset_links(
    markdown: str,
    envelope: FetchEnvelope,
    *,
    target_path: Path,
    render: RenderOptions,
) -> str:
    if not markdown or envelope.article is None:
        return markdown

    local_assets_by_basename = _local_asset_lookup_by_basename(
        envelope.article, target_path=target_path
    )
    local_assets_by_reference, local_assets_by_candidate_basename = (
        _local_asset_lookups(
            envelope.article,
            target_path=target_path,
        )
    )

    def rewrite_inline_match(match: re.Match[str]) -> str:
        prefix = match.group(1)
        destination = match.group(2)
        relative_path = relative_asset_link(destination, target_path=target_path)
        if relative_path is None and prefix.startswith("!["):
            destination_candidates = image_reference_candidates(destination)
            for candidate in destination_candidates:
                match_value = local_assets_by_reference.get(candidate)
                if match_value is not None:
                    relative_path = match_value[0]
                    break
            if relative_path is None:
                for candidate in destination_candidates:
                    match_value = local_assets_by_candidate_basename.get(
                        image_reference_basename(candidate)
                    )
                    if match_value is not None:
                        relative_path = match_value[0]
                        break
            if relative_path is None:
                match_value = local_assets_by_basename.get(
                    _remote_asset_basename(destination) or ""
                )
                if match_value is not None:
                    relative_path = match_value[0]
        if relative_path is None:
            remote_path = _publisher_root_relative_asset_link(
                destination,
                article=envelope.article,
            )
            if remote_path is None:
                return match.group(0)
            return f"{prefix}{remote_path}{match.group(3)}"
        return f"{prefix}{relative_path}{match.group(3)}"

    def rewrite_image(image: Any) -> str:
        destination = normalize_text(image.url).strip("<>")
        destination_candidates = image_reference_candidates(destination)
        relative_path: str | None = None
        matched_asset: Any | None = None
        for candidate in destination_candidates:
            match_value = local_assets_by_reference.get(candidate)
            if match_value is not None:
                relative_path, matched_asset = match_value
                break
        if relative_path is None:
            for candidate in destination_candidates:
                match_value = local_assets_by_candidate_basename.get(
                    image_reference_basename(candidate)
                )
                if match_value is not None:
                    relative_path, matched_asset = match_value
                    break
        if relative_path is None:
            match_value = local_assets_by_basename.get(
                _remote_asset_basename(destination) or ""
            )
            if match_value is not None:
                relative_path, matched_asset = match_value
        if relative_path is None:
            relative_path = relative_asset_link(destination, target_path=target_path)
        if relative_path is None:
            remote_path = _publisher_root_relative_asset_link(
                destination,
                article=envelope.article,
            )
            if remote_path is not None:
                return image.text.replace(destination, remote_path, 1)
            return image.text
        if matched_asset is None:
            return image.text.replace(destination, relative_path, 1)
        return _render_asset_markdown_image(
            matched_asset,
            fallback_alt=image.alt,
            relative_path=relative_path,
            title=image.title,
        )

    markdown = replace_markdown_images(markdown, rewrite_image)
    return re.sub(
        r"((?<!!)\[[^\]]*\]\()([^)]+)(\))",
        rewrite_inline_match,
        markdown,
    )


def _markdown_filename(
    envelope: FetchEnvelope, *, markdown_filename: str | None = None
) -> str:
    requested = normalize_text(markdown_filename)
    if requested:
        requested_path = Path(requested)
        if requested_path.name != requested:
            raise ValueError("markdown_filename must be a file name, not a path.")
        suffix = requested_path.suffix or ".md"
        stem = requested_path.stem if requested_path.suffix else requested_path.name
        return f"{sanitize_filename(stem or 'article')}{suffix}"

    meta = (
        envelope.article.metadata if envelope.article is not None else envelope.metadata
    )
    authors = list(meta.authors) if meta and meta.authors else None
    year = _extract_year(meta.published if meta else None)
    title = meta.title if meta else None
    return f"{format_paper_stem(authors, year, title, doi=envelope.doi)}.md"


def _extend_envelope_status(
    envelope: FetchEnvelope,
    *,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> None:
    extend_unique(envelope.quality.warnings, warnings)
    extend_unique(envelope.quality.source_trail, source_trail)


def save_markdown_to_disk(
    envelope: FetchEnvelope,
    *,
    output_dir: Path,
    render: RenderOptions,
    markdown_filename: str | None = None,
    request_label: str = "save_markdown",
    overwrite: bool = True,
    commit_guard: Callable[[], None] | None = None,
) -> Path | None:
    has_usable_fulltext = bool(
        envelope.content_kind == FULLTEXT and envelope.markdown and envelope.article
    )
    if not has_usable_fulltext:
        _extend_envelope_status(
            envelope,
            warnings=[
                f"{request_label} was set but full text was not available; nothing written to disk."
            ],
            source_trail=[download_marker("markdown_skipped_no_fulltext")],
        )
        return None

    target = output_dir / _markdown_filename(
        envelope, markdown_filename=markdown_filename
    )
    ArtifactStore.from_download_dir(output_dir).write_text_file(
        target,
        rewrite_markdown_asset_links(
            envelope.markdown or "", envelope, target_path=target, render=render
        ),
        encoding="utf-8",
        overwrite=overwrite,
        commit_guard=commit_guard,
    )
    message = f"Markdown full text was saved to {target}."
    _extend_envelope_status(
        envelope,
        warnings=[message],
        source_trail=[download_marker("markdown", "saved")],
    )
    return target


def build_fetch_envelope(
    article: ArticleModel,
    *,
    modes: set[OutputMode],
    render: RenderOptions,
    trace: list[TraceEvent] | None = None,
    diagnostic_artifacts: list[dict[str, Any]] | None = None,
) -> FetchEnvelope:
    resolved_asset_profile = effective_asset_profile(
        render.asset_profile, source_name=article.source
    )
    markdown = (
        article.to_ai_markdown(
            include_refs=render.include_refs,
            asset_profile=resolved_asset_profile,
            max_tokens=render.max_tokens,
        )
        if "markdown" in modes
        else None
    )
    metadata = article.metadata if "metadata" in modes else None
    return FetchEnvelope(
        doi=article.doi,
        source=public_source_for_article(article),
        has_fulltext=article.quality.has_fulltext,
        acquisition=article.acquisition,
        source_trail=list(article.quality.source_trail),
        trace=list(trace or trace_from_markers(article.quality.source_trail)),
        quality=article.quality,
        article=article if "article" in modes else None,
        markdown=markdown,
        metadata=metadata,
        diagnostic_artifacts=[dict(item) for item in (diagnostic_artifacts or [])],
    )
