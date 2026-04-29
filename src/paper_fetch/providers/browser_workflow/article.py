"""Article assembly helpers for provider browser workflows."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Callable, Mapping

from ...extraction.html.signals import SciencePnasHtmlFailure
from ...metadata_types import ProviderMetadata
from ...models import (
    article_from_markdown,
    coerce_asset_failure_diagnostics,
    metadata_only_article,
)
from ...publisher_identity import normalize_doi
from ...runtime import RuntimeContext
from ...tracing import merge_trace, source_trail_from_trace, trace_from_markers
from ...utils import dedupe_authors, extend_unique, normalize_text
from .._browser_workflow_html_extraction import (
    _cached_browser_workflow_markdown,
    rewrite_inline_figure_links,
)
from ..base import RawFulltextPayload

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient


def _leading_body_after_abstract(
    metadata_abstract: str | None,
    extracted_abstract: str | None,
) -> str | None:
    normalized_metadata = normalize_text(metadata_abstract)
    normalized_abstract = normalize_text(extracted_abstract)
    if (
        not normalized_metadata
        or not normalized_abstract
        or normalized_metadata == normalized_abstract
    ):
        return None
    if not normalized_metadata.startswith(normalized_abstract):
        return None
    remainder = normalized_metadata[len(normalized_abstract) :].strip()
    return remainder or None


def _prepend_leading_body_markdown(markdown_text: str, lead_body: str | None) -> str:
    normalized_lead_body = normalize_text(lead_body)
    if not normalized_lead_body:
        return markdown_text
    if normalized_lead_body in normalize_text(markdown_text):
        return markdown_text

    main_text_block = f"## Main Text\n\n{normalized_lead_body}"
    stripped_markdown = markdown_text.strip()
    if not stripped_markdown:
        return main_text_block
    if stripped_markdown.startswith("# "):
        parts = stripped_markdown.split("\n\n", 1)
        if len(parts) == 2:
            return f"{parts[0]}\n\n{main_text_block}\n\n{parts[1]}".strip()
    return f"{main_text_block}\n\n{stripped_markdown}".strip()


def _normalized_authors(values: Any) -> list[str]:
    return [
        normalize_text(str(item))
        for item in (values or [])
        if normalize_text(str(item))
    ]


def merge_provider_owned_authors(
    metadata: Mapping[str, Any],
    raw_payload: RawFulltextPayload,
    *,
    fallback_extractor: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    article_metadata = dict(metadata)
    content = getattr(raw_payload, "content", None)
    extraction = content.diagnostics.get("extraction") if content is not None else None
    extracted_authors = _normalized_authors(
        extraction.get("extracted_authors") if isinstance(extraction, Mapping) else []
    )
    if (
        not extracted_authors
        and fallback_extractor is not None
        and "html" in normalize_text(raw_payload.content_type).lower()
    ):
        html_text = bytes(raw_payload.body or b"").decode("utf-8", errors="replace")
        extracted_authors = _normalized_authors(fallback_extractor(html_text))
    if not extracted_authors:
        return article_metadata

    existing_authors = _normalized_authors(article_metadata.get("authors") or [])
    article_metadata["authors"] = dedupe_authors(
        [*extracted_authors, *existing_authors]
    )
    return article_metadata


def browser_workflow_article_from_payload(
    client: "BrowserWorkflowClient",
    metadata: ProviderMetadata,
    raw_payload: RawFulltextPayload,
    *,
    downloaded_assets: list[Mapping[str, Any]] | None = None,
    asset_failures: list[Mapping[str, Any]] | None = None,
    context: RuntimeContext | None = None,
):
    context = client._runtime_context(context)
    content = raw_payload.content
    markdown_text = str(
        (content.markdown_text if content is not None else "") or ""
    ).strip()
    warnings = list(raw_payload.warnings)
    trace = list(raw_payload.trace)
    doi = normalize_doi(metadata.get("doi"))
    source = client.article_source()
    assets = list(downloaded_assets or [])
    content_type = str(raw_payload.content_type or "").lower()

    if not markdown_text and "html" in content_type:
        html_text = (
            bytes(raw_payload.body or b"").decode("utf-8", errors="replace").strip()
        )
        if html_text:
            try:
                markdown_text, extraction = _cached_browser_workflow_markdown(
                    client,
                    html_text,
                    raw_payload.source_url
                    or str(metadata.get("landing_page_url") or ""),
                    metadata=metadata,
                    context=context,
                )
            except SciencePnasHtmlFailure as exc:
                warnings.append(
                    f"{client.name} HTML content was not usable ({exc.message})."
                )
            else:
                diagnostics_payload = (
                    dict(content.diagnostics) if content is not None else {}
                )
                diagnostics_payload["extraction"] = extraction
                diagnostics = extraction.get("availability_diagnostics")
                if diagnostics is not None:
                    diagnostics_payload["availability_diagnostics"] = diagnostics
                if content is not None:
                    raw_payload.content = replace(
                        content,
                        markdown_text=markdown_text,
                        diagnostics=diagnostics_payload,
                    )
                    content = raw_payload.content

    if not markdown_text:
        warnings.append(f"{client.name} retrieval did not produce usable markdown.")
        return metadata_only_article(
            source=source,
            metadata=metadata,
            doi=doi or None,
            warnings=warnings,
            trace=[*trace, *trace_from_markers([f"fulltext:{client.name}_parse_fail"])],
        )
    if asset_failures:
        warnings.append(
            f"{client.name} related assets were only partially downloaded ({len(asset_failures)} failed)."
        )
    if assets and markdown_text:
        markdown_text = rewrite_inline_figure_links(
            markdown_text,
            figure_assets=assets,
            publisher=client.name,
        )

    article_metadata = dict(metadata)
    extraction_payload = (
        content.diagnostics.get("extraction") if content is not None else None
    )
    extracted_abstract = normalize_text(
        extraction_payload.get("abstract_text")
        if isinstance(extraction_payload, Mapping)
        else ""
    )
    extracted_references = (
        list(extraction_payload.get("references") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    abstract_sections = (
        list(extraction_payload.get("abstract_sections") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    section_hints = (
        list(extraction_payload.get("section_hints") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    if extracted_references:
        article_metadata["references"] = extracted_references
    if extracted_abstract:
        lead_body = _leading_body_after_abstract(
            article_metadata.get("abstract"), extracted_abstract
        )
        article_metadata["abstract"] = extracted_abstract
        markdown_text = _prepend_leading_body_markdown(markdown_text, lead_body)
    availability_diagnostics = (
        dict(content.diagnostics.get("availability_diagnostics") or {})
        if content is not None
        and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
        else None
    )

    article = article_from_markdown(
        source=source,
        metadata=article_metadata,
        doi=doi or None,
        markdown_text=markdown_text,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        assets=assets,
        warnings=warnings,
        trace=trace,
        availability_diagnostics=availability_diagnostics,
        allow_downgrade_from_diagnostics=True,
    )
    article.quality.asset_failures = coerce_asset_failure_diagnostics(asset_failures)
    return article


def _finalize_abstract_only_provider_article(
    provider_name: str,
    article,
    *,
    warnings: list[str] | None = None,
):
    marker = f"fulltext:{provider_name}_abstract_only"
    article.quality.trace = merge_trace(
        article.quality.trace, trace_from_markers([marker])
    )
    article.quality.source_trail = source_trail_from_trace(article.quality.trace)
    extend_unique(article.quality.warnings, list(warnings or []))
    return article
