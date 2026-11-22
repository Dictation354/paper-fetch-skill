"""Article URL identities for the two RSC journal platforms."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

_LEGACY_ARTICLE = re.compile(
    r"/(?:[a-z]{2}/)?content/article(?P<kind>html|landing|pdf)/"
    r"\d{4}/[a-z0-9]+/(?P<code>[a-z][a-z0-9]*)/?",
    re.IGNORECASE,
)
_SILVERCHAIR_ARTICLE = re.compile(r"/[a-z0-9-]+/article(?:-abstract)?/.+", re.I)
_SILVERCHAIR_PDF = re.compile(r"/[a-z0-9-]+/article-pdf/.+", re.I)


def is_rsc_journal_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "pubs.rsc.org"
    )


def rsc_legacy_doi(url: str) -> str | None:
    if is_rsc_journal_url(url) and (
        match := _LEGACY_ARTICLE.fullmatch(urlsplit(url).path)
    ):
        return f"10.1039/{match['code'].lower()}"
    return None


def is_rsc_silverchair_article(url: str) -> bool:
    return is_rsc_journal_url(url) and bool(
        _SILVERCHAIR_ARTICLE.fullmatch(urlsplit(url).path)
    )


def is_rsc_main_pdf(url: str, doi: str) -> bool:
    parsed = urlsplit(url)
    if parsed.netloc.lower() == "rscj.silverchair-cdn.com":
        code = doi.removeprefix("10.1039/")
        return (
            parsed.scheme in {"http", "https"}
            and parsed.path.lower().startswith("/rscj/content_public/journal/")
            and f"/10.1039_{code}/" in parsed.path.lower()
            and parsed.path.lower().endswith(f"/{code}.pdf")
        )
    if not is_rsc_journal_url(url):
        return False
    if match := _LEGACY_ARTICLE.fullmatch(parsed.path):
        return match["kind"].lower() == "pdf" and rsc_legacy_doi(url) == doi
    path = parsed.path.lower()
    return bool(
        _SILVERCHAIR_PDF.fullmatch(path)
        and not any(marker in path for marker in ("supplem", "_suppl", "-suppl"))
    )


def rsc_legacy_article_url(url: str, doi: str, *, pdf: bool = False) -> str | None:
    if rsc_legacy_doi(url) != doi:
        return None
    parsed = urlsplit(url)
    path = re.sub(
        r"/article(?:html|landing|pdf)/",
        "/articlepdf/" if pdf else "/articlehtml/",
        parsed.path,
        flags=re.IGNORECASE,
    )
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
