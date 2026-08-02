"""IEEE access/block page detection."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..extraction.html.html_tags import HTML_DROP_TAGS
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import IEEE_ACCESS_BLOCK_TEXT_TOKENS
from ..runtime import RuntimeContext
from ..utils import normalize_text

IEEE_BLOCK_PAGE_SCANNER_VERSION = "visible-text-v2"


def _contains_ieee_block_page_token(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return any(token in lowered for token in IEEE_ACCESS_BLOCK_TEXT_TOKENS)


def _scan_ieee_block_page_tokens(html_text: str) -> bool:
    if not _contains_ieee_block_page_token(html_text):
        return False

    html_for_parse = re.sub(r"^\s*<\?xml[^>]*>\s*", "", html_text)
    soup = BeautifulSoup(html_for_parse, choose_parser())
    for node in list(soup.find_all(HTML_DROP_TAGS)):
        node.decompose()
    return _contains_ieee_block_page_token(soup.get_text(" ", strip=True))


def _looks_like_ieee_block_page(
    html_text: str,
    *,
    context: RuntimeContext | None = None,
    source_url: str | None = None,
) -> bool:
    if not isinstance(context, RuntimeContext):
        return _scan_ieee_block_page_tokens(html_text)
    key = context.build_parse_cache_key(
        provider="ieee",
        role="access_block_page",
        source=source_url,
        body=html_text,
        parser=f"BeautifulSoup:{choose_parser()}",
        config={
            "scanner_version": IEEE_BLOCK_PAGE_SCANNER_VERSION,
            "tokens": IEEE_ACCESS_BLOCK_TEXT_TOKENS,
            "drop_tags": HTML_DROP_TAGS,
        },
    )
    return bool(
        context.get_or_set_parse_cache(
            key, lambda: _scan_ieee_block_page_tokens(html_text)
        )
    )
