"""Public markdown extraction entrypoints for Science/PNAS browser workflows."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from ...metadata_types import ProviderMetadata
from ...extraction.html.parsing import choose_parser
from ...extraction.html.semantics import collect_html_section_hints
from ...extraction.html.signals import SciencePnasHtmlFailure
from ...quality.html_availability import (
    HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
    assess_html_fulltext_availability,
    availability_failure_message,
    clean_container,
    select_best_container,
)
from ...utils import normalize_text
from .._science_pnas_profiles import publisher_profile as _publisher_profile
from .normalization import (
    _drop_front_matter_teaser_figures,
    _drop_table_blocks,
    _normalize_abstract_blocks,
    _normalize_special_blocks,
)
from .postprocess import (
    _abstract_block_texts_from_payloads,
    _abstract_section_payloads,
    _ensure_body_markdown_heading,
    _inject_inline_table_blocks,
    _missing_abstract_markdown,
    _postprocess_browser_workflow_markdown,
)
from .profile import (
    clean_markdown,
    extract_article_markdown,
    extract_page_title,
    _container_selection_policy,
    _content_fragment_html,
    _drop_abstract_sections_from_body_container,
    _node_language_hint,
    _noise_profile_for_publisher,
)

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None

def extract_browser_workflow_markdown(
    html_text: str,
    source_url: str,
    publisher: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    if BeautifulSoup is None:
        raise SciencePnasHtmlFailure("missing_bs4", "BeautifulSoup is required for browser-workflow HTML extraction.")

    soup = BeautifulSoup(html_text, choose_parser())
    title = extract_page_title(soup)
    container = select_best_container(soup, publisher, policy=_container_selection_policy(publisher))
    if container is None:
        raise SciencePnasHtmlFailure(
            "article_container_not_found",
            "Could not identify the main article container in publisher HTML.",
        )

    clean_container(container, publisher, drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW)
    from ...extraction.html.assets import extract_figure_assets

    asset_container = copy.deepcopy(container)
    _normalize_abstract_blocks(asset_container)
    _drop_front_matter_teaser_figures(asset_container, publisher)
    _drop_table_blocks(asset_container)
    figure_assets = extract_figure_assets(_content_fragment_html(asset_container, publisher=publisher), source_url)

    table_entries = _normalize_special_blocks(container, publisher)
    abstract_sections = _abstract_section_payloads(container)
    abstract_block_texts = _abstract_block_texts_from_payloads(abstract_sections)
    body_container = copy.deepcopy(container)
    _drop_abstract_sections_from_body_container(body_container, publisher)
    section_hints = collect_html_section_hints(
        body_container,
        title=title,
        language_hint_resolver=_node_language_hint,
    )
    container_html = _content_fragment_html(body_container, publisher=publisher)
    noise_profile = _noise_profile_for_publisher(publisher)
    markdown = clean_markdown(
        extract_article_markdown(
            container_html,
            source_url,
            trafilatura_backend=None,
            noise_profile=noise_profile,
        ),
        noise_profile=noise_profile,
    )
    if abstract_sections:
        markdown = _ensure_body_markdown_heading(markdown, title=title)
    abstract_markdown = _missing_abstract_markdown(container, markdown, publisher=publisher)
    if abstract_markdown:
        markdown = clean_markdown(f"{abstract_markdown}\n\n{markdown}", noise_profile=noise_profile)
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip() + "\n"
    markdown = _inject_inline_table_blocks(markdown, table_entries=table_entries, publisher=publisher)
    markdown = _postprocess_browser_workflow_markdown(
        markdown,
        title=title,
        publisher=publisher,
        figure_assets=figure_assets,
        table_entries=table_entries,
        abstract_block_texts=abstract_block_texts,
    )

    quality_metadata = dict(metadata or {})
    if title and not quality_metadata.get("title"):
        quality_metadata["title"] = title
    diagnostics = assess_html_fulltext_availability(
        markdown,
        quality_metadata,
        provider=publisher,
        html_text=html_text,
        title=title,
        final_url=source_url,
        container_tag=container.name,
        container_text_length=len(" ".join(container.stripped_strings)),
        section_hints=section_hints,
    )
    if not diagnostics.accepted:
        raise SciencePnasHtmlFailure(diagnostics.reason, availability_failure_message(diagnostics))

    extraction_payload = {
        "title": title,
        "abstract_text": normalize_text(abstract_sections[0]["text"]) if abstract_sections else ("\n\n".join(abstract_block_texts) if abstract_block_texts else None),
        "abstract_sections": abstract_sections,
        "section_hints": section_hints,
        "container_tag": container.name,
        "container_text_length": len(" ".join(container.stripped_strings)),
        "availability_diagnostics": diagnostics.to_dict(),
    }
    profile = _publisher_profile(publisher)
    if profile.finalize_extraction is not None:
        markdown, extraction_payload = profile.finalize_extraction(
            html_text,
            source_url,
            markdown,
            extraction_payload,
            metadata=metadata,
        )
    return markdown, extraction_payload


def extract_science_pnas_markdown(
    html_text: str,
    source_url: str,
    publisher: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    return extract_browser_workflow_markdown(
        html_text,
        source_url,
        publisher,
        metadata=metadata,
    )


__all__ = [
    "extract_browser_workflow_markdown",
    "extract_science_pnas_markdown",
]
