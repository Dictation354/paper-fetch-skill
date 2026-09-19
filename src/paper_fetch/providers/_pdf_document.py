"""Document-role evidence for full-paper PDF acquisition, not PDF formatting."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit


def non_article_pdf_reason(url: str, *, label: str = "") -> str | None:
    path = unquote(urlsplit(url).path).casefold()
    if re.search(r"/(?:previewpdf|pdfpreview)(?:/|$)", path):
        return "pdf_preview_only"
    if (
        re.search(r"/(?:suppl_file|supplementary|supplements?)(?:/|$)", path)
        or re.search(r"(?:_moesm\d*_|_esm\.pdf$)", path)
        or re.search(
            r"\b(?:supplementary|supplemental|supporting)\s+(?:information|material|data|file)",
            label,
            re.IGNORECASE,
        )
    ):
        return "pdf_supplement_only"
    return None
