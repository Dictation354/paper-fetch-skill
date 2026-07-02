"""Shared section-heading vocabularies without extraction/runtime imports."""

from __future__ import annotations

MARKDOWN_ABSTRACT_HEADINGS = frozenset(
    {
        "abstract",
        "structured abstract",
        "summary",
        "resumo",
        "resumen",
        "resume",
        "résumé",
        "zusammenfassung",
    }
)
SIGNIFICANCE_ABSTRACT_HEADINGS = frozenset({"significance", "significance statement"})
PRIMARY_ABSTRACT_HEADINGS = MARKDOWN_ABSTRACT_HEADINGS & {
    "abstract",
    "structured abstract",
    "summary",
}


__all__ = [
    "MARKDOWN_ABSTRACT_HEADINGS",
    "PRIMARY_ABSTRACT_HEADINGS",
    "SIGNIFICANCE_ABSTRACT_HEADINGS",
]
