"""MDPI article URL helpers."""

from __future__ import annotations

import re
import urllib.parse

from .publisher_identity import normalize_doi
from .utils import normalize_text


MDPI_HOSTS = {"mdpi.com", "www.mdpi.com"}
MDPI_ISSN_JOURNAL_CODES = {
    "1424-8220": "s",
    "1660-4601": "ijerph",
    "1996-1073": "en",
    "2071-1050": "su",
    "2072-4292": "rs",
    "2073-4441": "w",
    "2077-0375": "membranes",
    "2227-7390": "math",
    "2304-8158": "foods",
}
MDPI_JOURNAL_CODE_ISSNS = {
    journal_code: issn for issn, journal_code in MDPI_ISSN_JOURNAL_CODES.items()
}
MDPI_ISSN_PATTERN = re.compile(r"\d{4}-\d{3}[\dXx]")


def is_mdpi_url(url: str | None) -> bool:
    candidate = normalize_text(url)
    if not candidate:
        return False
    parsed = urllib.parse.urlparse(candidate)
    host = normalize_text(parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and host in MDPI_HOSTS


def mdpi_doi_from_landing_url(url: str | None) -> str | None:
    """Derive the canonical MDPI DOI from numeric article URLs when known.

    Classic MDPI URLs encode the journal ISSN plus volume, issue, and article
    number, while the DOI suffix uses the journal system code. We only derive a
    DOI when the ISSN is in the provider-owned mapping.
    """

    candidate = normalize_text(url)
    if not is_mdpi_url(candidate):
        return None

    parsed = urllib.parse.urlparse(candidate)
    parts = [
        urllib.parse.unquote(part).strip()
        for part in parsed.path.split("/")
        if part.strip()
    ]
    if len(parts) < 4:
        return None
    issn, volume, issue, article_number = parts[:4]
    if (
        not MDPI_ISSN_PATTERN.fullmatch(issn)
        or not volume.isdigit()
        or not issue.isdigit()
        or not article_number.isdigit()
    ):
        return None

    journal_code = MDPI_ISSN_JOURNAL_CODES.get(issn.lower())
    if not journal_code:
        return None

    return normalize_doi(
        f"10.3390/{journal_code}{volume}{issue.zfill(2)}{article_number.zfill(4)}"
    )


def mdpi_landing_url_from_doi(doi: str | None) -> str | None:
    normalized = normalize_doi(doi)
    if not normalized.startswith("10.3390/"):
        return None
    suffix = normalized.split("/", 1)[1]
    for journal_code in sorted(MDPI_JOURNAL_CODE_ISSNS, key=len, reverse=True):
        if not suffix.startswith(journal_code):
            continue
        encoded = suffix[len(journal_code) :]
        if len(encoded) < 7 or not encoded.isdigit():
            continue
        volume = encoded[:-6]
        issue = encoded[-6:-4]
        article_number = encoded[-4:]
        if not volume:
            continue
        return (
            f"https://www.mdpi.com/{MDPI_JOURNAL_CODE_ISSNS[journal_code]}/"
            f"{int(volume)}/{int(issue)}/{int(article_number)}"
        )
    return None
