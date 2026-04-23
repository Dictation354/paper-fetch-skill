"""Compatibility facade over provider-neutral HTML runtime helpers."""

from __future__ import annotations

from ..extraction.html._runtime import (
    HTML_BLOCK_TAGS,
    HTML_DROP_TAGS,
    body_metrics,
    clean_markdown,
    count_words,
    extract_article_markdown,
    has_sufficient_article_body,
    should_drop_html_element,
)

__all__ = [
    "HTML_BLOCK_TAGS",
    "HTML_DROP_TAGS",
    "body_metrics",
    "clean_markdown",
    "count_words",
    "extract_article_markdown",
    "has_sufficient_article_body",
    "should_drop_html_element",
]
