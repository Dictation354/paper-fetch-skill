"""Envelope rendering and article finalization stage."""

from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

from ..models import ArticleModel, FetchEnvelope, OutputMode, RenderOptions
from ..provider_catalog import known_article_source_names
from ..tracing import merge_trace, source_trail_from_trace, trace_from_markers
from ..utils import extend_unique, normalize_text, sanitize_filename
from .types import effective_asset_profile


def finalize_article(
    article: ArticleModel,
    *,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    extend_unique(article.quality.warnings, list(warnings or []))
    if source_trail:
        article.quality.trace = merge_trace(article.quality.trace, trace_from_markers(list(source_trail)))
        article.quality.source_trail = source_trail_from_trace(article.quality.trace)
    return article


def public_source_for_article(article: ArticleModel) -> str:
    if "fallback:metadata_only" in article.quality.source_trail:
        return "metadata_only"
    if article.source in known_article_source_names():
        return article.source
    return article.source


def relative_asset_link(value: str | None, *, target_path: Path) -> str | None:
    original = str(value or "").strip()
    if not original or original.startswith(("http://", "https://", "//")):
        return None
    source_path = Path(original)
    if not source_path.is_absolute():
        if not source_path.exists():
            return None
        source_path = source_path.resolve()
    target_dir = target_path.parent.resolve()
    relative = Path(os.path.relpath(source_path, start=target_dir))
    return urllib.parse.quote(relative.as_posix(), safe="/._-")


def _local_asset_lookup_by_basename(
    article: ArticleModel | None,
    *,
    target_path: Path,
) -> dict[str, str]:
    if article is None:
        return {}

    candidates: dict[str, str] = {}
    ambiguous: set[str] = set()
    for asset in article.assets:
        relative_path = relative_asset_link(asset.path, target_path=target_path)
        if relative_path is None:
            continue
        basenames = {Path(str(asset.path or "")).name}
        source_url = str(asset.url or "").strip()
        if source_url:
            basenames.add(Path(urllib.parse.unquote(urllib.parse.urlparse(source_url).path)).name)
        for basename in basenames:
            if not basename:
                continue
            existing = candidates.get(basename)
            if existing is None:
                candidates[basename] = relative_path
            elif existing != relative_path:
                ambiguous.add(basename)

    return {basename: path for basename, path in candidates.items() if basename not in ambiguous}


def _remote_asset_basename(destination: str) -> str | None:
    if not destination.startswith(("http://", "https://", "//")):
        return None
    parsed = urllib.parse.urlparse(destination if not destination.startswith("//") else f"https:{destination}")
    basename = Path(urllib.parse.unquote(parsed.path)).name
    return basename or None


def rewrite_markdown_asset_links(
    markdown: str,
    envelope: FetchEnvelope,
    *,
    target_path: Path,
    render: RenderOptions,
) -> str:
    if not markdown or envelope.article is None:
        return markdown

    local_assets_by_basename = _local_asset_lookup_by_basename(envelope.article, target_path=target_path)

    def rewrite_inline_match(match: re.Match[str]) -> str:
        prefix = match.group(1)
        destination = match.group(2)
        relative_path = relative_asset_link(destination, target_path=target_path)
        if relative_path is None and prefix.startswith("!["):
            relative_path = local_assets_by_basename.get(_remote_asset_basename(destination) or "")
        if relative_path is None:
            return match.group(0)
        return f"{prefix}{relative_path}{match.group(3)}"

    return re.sub(
        r"(!?\[[^\]]*\]\()([^)]+)(\))",
        rewrite_inline_match,
        markdown,
    )


def _markdown_filename(envelope: FetchEnvelope, *, markdown_filename: str | None = None) -> str:
    requested = normalize_text(markdown_filename)
    if requested:
        requested_path = Path(requested)
        if requested_path.name != requested:
            raise ValueError("markdown_filename must be a file name, not a path.")
        suffix = requested_path.suffix or ".md"
        stem = requested_path.stem if requested_path.suffix else requested_path.name
        return f"{sanitize_filename(stem or 'article')}{suffix}"

    title = None
    if envelope.article is not None:
        title = envelope.article.metadata.title
    if title is None and envelope.metadata is not None:
        title = envelope.metadata.title
    return f"{sanitize_filename(envelope.doi or title or 'article')}.md"


def _extend_envelope_status(
    envelope: FetchEnvelope,
    *,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> None:
    extend_unique(envelope.warnings, warnings)
    extend_unique(envelope.source_trail, source_trail)
    extend_unique(envelope.quality.warnings, warnings)
    extend_unique(envelope.quality.source_trail, source_trail)
    if envelope.article is not None:
        extend_unique(envelope.article.quality.warnings, warnings)
        extend_unique(envelope.article.quality.source_trail, source_trail)


def save_markdown_to_disk(
    envelope: FetchEnvelope,
    *,
    output_dir: Path,
    render: RenderOptions,
    markdown_filename: str | None = None,
    request_label: str = "save_markdown",
) -> Path | None:
    has_usable_fulltext = bool(envelope.content_kind == "fulltext" and envelope.markdown and envelope.article)
    if not has_usable_fulltext:
        _extend_envelope_status(
            envelope,
            warnings=[
                f"{request_label} was set but full text was not available; nothing written to disk."
            ],
            source_trail=["download:markdown_skipped_no_fulltext"],
        )
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / _markdown_filename(envelope, markdown_filename=markdown_filename)
    target.write_text(
        rewrite_markdown_asset_links(envelope.markdown or "", envelope, target_path=target, render=render),
        encoding="utf-8",
    )
    message = f"Markdown full text was saved to {target}."
    _extend_envelope_status(
        envelope,
        warnings=[message],
        source_trail=["download:markdown_saved"],
    )
    return target


def build_fetch_envelope(
    article: ArticleModel,
    *,
    modes: set[OutputMode],
    render: RenderOptions,
) -> FetchEnvelope:
    resolved_asset_profile = effective_asset_profile(render.asset_profile, source_name=article.source)
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
        content_kind=article.quality.content_kind,
        has_abstract=article.quality.has_abstract,
        warnings=list(article.quality.warnings),
        source_trail=list(article.quality.source_trail),
        trace=list(article.quality.trace),
        token_estimate=article.quality.token_estimate,
        token_estimate_breakdown=article.quality.token_estimate_breakdown,
        quality=article.quality,
        article=article if "article" in modes else None,
        markdown=markdown,
        metadata=metadata,
    )
