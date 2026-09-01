"""arXiv identifier normalization helpers."""

from __future__ import annotations

import re
import urllib.parse

from .utils import normalize_text

ARXIV_DOI_PREFIX = "10.48550/arxiv."
NEW_STYLE_ARXIV_ID_PATTERN = r"\d{4}\.\d{4,5}"
OLD_STYLE_ARXIV_ID_PATTERN = r"[a-z-]+(?:\.[A-Z]{2})?/\d{7}"
ARXIV_ID_BODY_PATTERN = (
    rf"(?:{NEW_STYLE_ARXIV_ID_PATTERN}|{OLD_STYLE_ARXIV_ID_PATTERN})(?:v\d+)?"
)
ARXIV_ID_RE = re.compile(rf"^{ARXIV_ID_BODY_PATTERN}$", flags=re.IGNORECASE)


def normalize_arxiv_id(value: str | None) -> str:
    candidate = normalize_text(value)
    if not candidate:
        return ""
    candidate = re.sub(r"^arxiv:\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(
        r"^https?://(?:www\.)?arxiv\.org/(?:abs|html|pdf)/",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"^10\.48550/arxiv\.", "", candidate, flags=re.IGNORECASE)
    candidate = candidate.split("?", 1)[0].split("#", 1)[0].strip()
    candidate = re.sub(r"\.pdf$", "", candidate, flags=re.IGNORECASE)
    if not ARXIV_ID_RE.fullmatch(candidate):
        return ""
    return candidate


def canonical_arxiv_abs_url(arxiv_id: str | None) -> str:
    normalized = normalize_arxiv_id(arxiv_id)
    return f"https://arxiv.org/abs/{normalized}" if normalized else ""


def canonical_arxiv_html_url(arxiv_id: str | None) -> str:
    normalized = normalize_arxiv_id(arxiv_id)
    return f"https://arxiv.org/html/{normalized}" if normalized else ""


def canonical_arxiv_pdf_url(arxiv_id: str | None) -> str:
    normalized = normalize_arxiv_id(arxiv_id)
    return f"https://arxiv.org/pdf/{normalized}" if normalized else ""


def canonical_arxiv_doi(arxiv_id: str | None) -> str:
    normalized = normalize_arxiv_id(arxiv_id)
    return f"{ARXIV_DOI_PREFIX}{normalized}".lower() if normalized else ""


def arxiv_id_from_doi(doi: str | None) -> str:
    candidate = normalize_text(doi)
    if not candidate.lower().startswith(ARXIV_DOI_PREFIX):
        return ""
    return normalize_arxiv_id(candidate)


def arxiv_id_from_url(url: str | None) -> str:
    candidate = normalize_text(url)
    if not candidate:
        return ""
    parsed = urllib.parse.urlparse(candidate)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"arxiv.org", "www.arxiv.org"}:
        return ""
    path = urllib.parse.unquote(parsed.path or "").strip("/")
    parts = path.split("/", 1)
    if len(parts) != 2 or parts[0].lower() not in {"abs", "html", "pdf"}:
        return ""
    return normalize_arxiv_id(parts[1])


def arxiv_id_from_query(value: str | None) -> str:
    candidate = normalize_text(value)
    if not candidate:
        return ""
    return (
        arxiv_id_from_url(candidate)
        or arxiv_id_from_doi(candidate)
        or normalize_arxiv_id(candidate)
    )


__all__ = [
    "ARXIV_DOI_PREFIX",
    "arxiv_id_from_doi",
    "arxiv_id_from_query",
    "arxiv_id_from_url",
    "canonical_arxiv_abs_url",
    "canonical_arxiv_doi",
    "canonical_arxiv_html_url",
    "canonical_arxiv_pdf_url",
    "normalize_arxiv_id",
]
