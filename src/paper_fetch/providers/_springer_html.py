"""Static compatibility facade for Springer provider HTML helpers."""

from __future__ import annotations

from ._springer_authors import (
    extract_authors as extract_authors,
    normalize_display_authors as normalize_display_authors,
)

from ._springer_assets import (
    SPRINGER_SUPPLEMENTARY_SECTION_TITLES as SPRINGER_SUPPLEMENTARY_SECTION_TITLES,
    extract_asset_html_scopes as extract_asset_html_scopes,
    extract_source_data_html_scope as extract_source_data_html_scope,
    extract_springer_table_image_url as extract_springer_table_image_url,
    extract_html_assets as extract_html_assets,
    extract_scoped_html_assets as extract_scoped_html_assets,
    download_assets_for_springer as download_assets_for_springer,
)

from ._springer_markdown import (
    clean_markdown as clean_markdown,
    _remove_springer_ai_alt_disclaimers as _remove_springer_ai_alt_disclaimers,
    extract_article_markdown as extract_article_markdown,
    extract_html_payload as extract_html_payload,
)

from ._springer_dom import (
    decode_html as decode_html,
    parse_html_metadata as parse_html_metadata,
    merge_html_metadata as merge_html_metadata,
)


__all__ = [
    "SPRINGER_SUPPLEMENTARY_SECTION_TITLES",
    "_remove_springer_ai_alt_disclaimers",
    "clean_markdown",
    "decode_html",
    "download_assets_for_springer",
    "extract_article_markdown",
    "extract_asset_html_scopes",
    "extract_authors",
    "extract_html_assets",
    "extract_html_payload",
    "extract_scoped_html_assets",
    "extract_source_data_html_scope",
    "extract_springer_table_image_url",
    "merge_html_metadata",
    "normalize_display_authors",
    "parse_html_metadata",
]
