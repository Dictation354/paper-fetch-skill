"""IEEE access/block page detection."""

from __future__ import annotations

from ..extraction.html.provider_rules import IEEE_ACCESS_BLOCK_TEXT_TOKENS
from ..runtime import RuntimeContext
from ..utils import normalize_text


def _scan_ieee_block_page_tokens(html_text: str) -> bool:
    lowered = normalize_text(html_text).lower()
    return any(token in lowered for token in IEEE_ACCESS_BLOCK_TEXT_TOKENS)


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
        parser="text-token-scan",
        config={"tokens": IEEE_ACCESS_BLOCK_TEXT_TOKENS},
    )
    return bool(
        context.get_or_set_parse_cache(
            key, lambda: _scan_ieee_block_page_tokens(html_text)
        )
    )
