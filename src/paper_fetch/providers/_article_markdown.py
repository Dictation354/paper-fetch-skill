"""Facade for XML-to-Markdown helpers shared by provider implementations."""

from __future__ import annotations

from ._article_markdown_document import (
    ArticleStructure,
    build_article_structure,
    build_markdown_document,
    write_article_markdown,
)
from ._article_markdown_math import (
    render_display_formula,
    render_external_mathml_expression,
    render_inline_formula,
    render_mathml_expression,
    render_tex_math,
)

__all__ = [
    "ArticleStructure",
    "build_article_structure",
    "build_markdown_document",
    "render_display_formula",
    "render_external_mathml_expression",
    "render_inline_formula",
    "render_mathml_expression",
    "render_tex_math",
    "write_article_markdown",
]
