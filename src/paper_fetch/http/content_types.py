"""Shared MIME type constants and content-type helpers."""

from __future__ import annotations

PDF_MIME_TYPE = "application/pdf"
PDF_ACCEPT_HEADER = f"{PDF_MIME_TYPE},*/*;q=0.8"
STRUCTURED_TEXT_MIME_TYPES = (
    "application/json",
    "application/xml",
    "application/jats+xml",
)
TEXTUAL_CONTENT_TYPES = (
    "text/",
    *STRUCTURED_TEXT_MIME_TYPES,
    "text/xml",
)


def content_type_base(value: str | None) -> str:
    return str(value or "").split(";", 1)[0].strip().lower()


def is_pdf_content_type(value: str | None) -> bool:
    return content_type_base(value) == PDF_MIME_TYPE


def is_xml_content_type(content_type: str | None) -> bool:
    normalized = content_type_base(content_type)
    return normalized in {
        "application/xml",
        "text/xml",
        "application/jats+xml",
    } or normalized.endswith("+xml")


def is_textual_content_type(content_type: str | None) -> bool:
    normalized = content_type_base(content_type)
    if not normalized:
        return False
    return (
        any(
            normalized.startswith(prefix) or normalized == prefix
            for prefix in TEXTUAL_CONTENT_TYPES
        )
        or normalized.endswith("+xml")
        or normalized.endswith("+json")
    )


__all__ = [
    "PDF_ACCEPT_HEADER",
    "PDF_MIME_TYPE",
    "STRUCTURED_TEXT_MIME_TYPES",
    "TEXTUAL_CONTENT_TYPES",
    "content_type_base",
    "is_pdf_content_type",
    "is_textual_content_type",
    "is_xml_content_type",
]
