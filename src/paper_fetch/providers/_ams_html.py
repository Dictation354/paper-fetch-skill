"""Compatibility facade for AMS provider HTML helpers."""

from __future__ import annotations

from typing import Any

from . import _ams_dom as _impl

from ._ams_authors import (
    _AUTHOR_PIPELINE as _AUTHOR_PIPELINE,
    extract_authors as extract_authors,
)

from ._ams_references import (
    extract_references as extract_references,
    blocking_fallback_signals as blocking_fallback_signals,
)

from ._ams_assets import (
    extract_asset_html_scopes as extract_asset_html_scopes,
    scoped_asset_extractor as scoped_asset_extractor,
)

from ._ams_markdown import (
    _normalize_ams_markdown_text as _normalize_ams_markdown_text,
    ams_normalize_markdown as ams_normalize_markdown,
    ams_classify_heading as ams_classify_heading,
    ams_keep_unknown_abstract_block as ams_keep_unknown_abstract_block,
    normalize_article_model as normalize_article_model,
    finalize_extraction as finalize_extraction,
)

from ._ams_dom import (
    ams_before_block_normalization as ams_before_block_normalization,
    ams_after_block_normalization as ams_after_block_normalization,
    ams_body_container as ams_body_container,
    ams_asset_body_container as ams_asset_body_container,
    ams_asset_figure_extraction as ams_asset_figure_extraction,
    refine_selected_container as refine_selected_container,
    select_content_nodes as select_content_nodes,
)


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)

__all__ = [
    "_AUTHOR_PIPELINE",
    "_normalize_ams_markdown_text",
    "ams_after_block_normalization",
    "ams_asset_body_container",
    "ams_asset_figure_extraction",
    "ams_before_block_normalization",
    "ams_body_container",
    "ams_classify_heading",
    "ams_keep_unknown_abstract_block",
    "ams_normalize_markdown",
    "blocking_fallback_signals",
    "extract_asset_html_scopes",
    "extract_authors",
    "extract_references",
    "finalize_extraction",
    "normalize_article_model",
    "refine_selected_container",
    "scoped_asset_extractor",
    "select_content_nodes",
]
