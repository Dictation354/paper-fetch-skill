"""Token estimation and budget helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Mapping

from ..utils import normalize_text
from .markdown import normalize_markdown_text, strip_markdown_images
from .schema import MaxTokensMode, Reference, Section, TokenEstimateBreakdown, TRUNCATION_WARNING
from .sections import BODY_SECTION_EXCLUDED_KINDS, combine_abstract_text

def estimate_tokens(text: str) -> int:
    normalized = normalize_markdown_text(text)
    return estimate_normalized_tokens(normalized)


def estimate_normalized_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def truncate_text_to_tokens(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""
    normalized = normalize_markdown_text(text)
    if estimate_normalized_tokens(normalized) <= token_budget:
        return normalized
    max_chars = max(32, token_budget * 4)
    truncated = normalized[:max_chars].rstrip(" ,;:\n")
    if len(truncated) < len(normalized):
        truncated += "..."
    return truncated


def normalize_token_budget(max_tokens: MaxTokensMode) -> tuple[float, bool]:
    if max_tokens == "full_text":
        return math.inf, True
    return float(max_tokens), False


def coerce_token_estimate_breakdown(
    value: TokenEstimateBreakdown | Mapping[str, Any] | None,
) -> TokenEstimateBreakdown:
    if isinstance(value, TokenEstimateBreakdown):
        return value
    if isinstance(value, Mapping):
        return TokenEstimateBreakdown(
            abstract=int(value.get("abstract") or 0),
            body=int(value.get("body") or 0),
            refs=int(value.get("refs") or 0),
        )
    return TokenEstimateBreakdown()


def build_token_estimate_breakdown(
    *,
    abstract_text: str | None,
    sections: Sequence["Section"],
    references: Sequence["Reference"],
) -> TokenEstimateBreakdown:
    abstract = estimate_tokens(combine_abstract_text(abstract_text=abstract_text, sections=sections) or "")
    body = estimate_tokens(
        "\n\n".join(
            strip_markdown_images(section.text)
            for section in sections
            if section.kind not in BODY_SECTION_EXCLUDED_KINDS and strip_markdown_images(section.text)
        )
    )
    refs = estimate_tokens("\n".join(normalize_text(reference.raw) for reference in references if normalize_text(reference.raw)))
    return TokenEstimateBreakdown(abstract=abstract, body=body, refs=refs)


__all__ = [
    "TRUNCATION_WARNING",
    "estimate_tokens",
    "estimate_normalized_tokens",
    "truncate_text_to_tokens",
    "normalize_token_budget",
    "coerce_token_estimate_breakdown",
    "build_token_estimate_breakdown",
]
