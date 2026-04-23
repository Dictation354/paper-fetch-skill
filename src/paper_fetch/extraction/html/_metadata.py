"""Provider-neutral HTML metadata parsing helpers."""

from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser
from typing import Mapping

from ...html_lookup import is_usable_html_lookup_title
from ...metadata_types import HtmlLookupHints, HtmlMetadata, ProviderMetadata
from ...utils import dedupe_authors
from ...models import normalize_text
from ...publisher_identity import normalize_doi
from ...publisher_identity import extract_doi as extract_doi_from_text

INPUT_TAG_PATTERN = re.compile(r"<input\b[^>]*>", flags=re.IGNORECASE)
HTML_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*("([^"]*)"|\'([^\']*)\')')
HTML_REFRESH_URL_PATTERN = re.compile(r"url\s*=\s*(?P<quote>['\"]?)(?P<url>[^'\";>]+)(?P=quote)", flags=re.IGNORECASE)
HTML_SCRIPT_ARTICLE_NAME_PATTERN = re.compile(
    r"\barticleName\s*:\s*(['\"])(?P<value>.*?)(?<!\\)\1",
    flags=re.IGNORECASE | re.DOTALL,
)
HTML_SCRIPT_IDENTIFIER_PATTERN = re.compile(
    r"\bidentifierValue\s*:\s*(['\"])(?P<value>.*?)(?<!\\)\1",
    flags=re.IGNORECASE | re.DOTALL,
)
EXPLICIT_ABSTRACT_META_KEYS = (
    "citation_abstract",
    "dc.abstract",
    "dc.description.abstract",
    "eprints.abstract",
    "prism.abstract",
    "article:abstract",
    "og:article:abstract",
)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.title: list[str] = []
        self.canonical_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "meta":
            key = attributes.get("name") or attributes.get("property") or attributes.get("http-equiv")
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta.setdefault(key.lower(), []).append(content)
        elif lowered_tag == "link":
            rel = attributes.get("rel", "").lower()
            href = attributes.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical_url = href
        elif lowered_tag == "title":
            self.title = []

    def handle_data(self, data: str) -> None:
        if data and self.lasttag == "title":
            self.title.append(data)


def extract_html_input_values(html_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in INPUT_TAG_PATTERN.finditer(html_text):
        attributes: dict[str, str] = {}
        for name, _, double_quoted, single_quoted in HTML_ATTRIBUTE_PATTERN.findall(match.group(0)):
            attributes[name.lower()] = html.unescape(double_quoted or single_quoted or "")
        key = normalize_text(attributes.get("name") or "").lower()
        if key:
            values[key] = attributes.get("value", "")
    return values


def extract_script_value(pattern: re.Pattern[str], html_text: str) -> str | None:
    match = pattern.search(html_text)
    if not match:
        return None
    return normalize_text(html.unescape(match.group("value")))


def normalize_lookup_url(value: str | None, source_url: str) -> str | None:
    raw = html.unescape((value or "").strip())
    if not raw:
        return None
    unquoted = urllib.parse.unquote(raw)
    return urllib.parse.urljoin(source_url, unquoted)


def extract_refresh_redirect_url(refresh_value: str, source_url: str) -> str | None:
    match = HTML_REFRESH_URL_PATTERN.search(refresh_value or "")
    if not match:
        return None
    return normalize_lookup_url(match.group("url"), source_url)


def extract_doi_from_meta(meta: Mapping[str, list[str]]) -> str | None:
    for key in ("citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"):
        for value in meta.get(key, []):
            doi = extract_doi_from_text(value)
            if doi:
                return doi
    return None


def extract_html_lookup_hints(
    html_text: str,
    source_url: str,
    *,
    meta: Mapping[str, list[str]] | None = None,
) -> HtmlLookupHints:
    input_values = extract_html_input_values(html_text)
    hidden_redirect = normalize_lookup_url(input_values.get("redirecturl"), source_url)
    refresh_redirect = None
    for refresh_value in (meta or {}).get("refresh", []):
        refresh_redirect = extract_refresh_redirect_url(refresh_value, source_url)
        if refresh_redirect:
            break

    lookup_title = (
        extract_script_value(HTML_SCRIPT_ARTICLE_NAME_PATTERN, html_text)
        or normalize_text(input_values.get("articletitle") or "")
        or None
    )
    identifier_value = (
        extract_script_value(HTML_SCRIPT_IDENTIFIER_PATTERN, html_text)
        or normalize_text(input_values.get("id") or "")
        or None
    )

    return {
        "lookup_title": lookup_title if is_usable_html_lookup_title(lookup_title) else None,
        "redirect_url": hidden_redirect or refresh_redirect,
        "identifier_value": identifier_value,
    }


def parse_html_metadata(html_text: str, source_url: str) -> HtmlMetadata:
    parser = _MetaParser()
    parser.feed(html_text)
    parser.close()
    lookup_hints = extract_html_lookup_hints(html_text, source_url, meta=parser.meta)

    def first(*keys: str) -> str | None:
        for key in keys:
            values = parser.meta.get(key.lower())
            if values:
                value = normalize_text(values[0])
                if value:
                    return html.unescape(value)
        return None

    authors = dedupe_authors(
        [normalize_text(value) for value in parser.meta.get("citation_author", []) if normalize_text(value)]
    )
    doi = extract_doi_from_meta(parser.meta) or extract_doi_from_text(parser.canonical_url or "")
    html_title = normalize_text("".join(parser.title)) or None
    if not is_usable_html_lookup_title(html_title):
        html_title = lookup_hints.get("lookup_title")
    title = first("citation_title", "dc.title", "og:title") or html_title or None
    abstract = first(*EXPLICIT_ABSTRACT_META_KEYS)
    journal_title = first("citation_journal_title", "prism.publicationname", "dc.source")
    article_type = first("citation_article_type", "dc.type", "prism.section", "article:section")
    published = first("citation_publication_date", "citation_online_date", "dc.date", "prism.publicationdate")
    citation_fulltext_html_url = normalize_lookup_url(first("citation_fulltext_html_url"), source_url)
    citation_abstract_html_url = normalize_lookup_url(first("citation_abstract_html_url"), source_url)
    keywords = [
        normalize_text(item)
        for item in parser.meta.get("citation_keywords", []) + parser.meta.get("keywords", [])
        if normalize_text(item)
    ]

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "journal_title": journal_title,
        "article_type": article_type,
        "published": published,
        "landing_page_url": parser.canonical_url or source_url,
        "citation_fulltext_html_url": citation_fulltext_html_url,
        "citation_abstract_html_url": citation_abstract_html_url,
        "doi": doi,
        "keywords": list(dict.fromkeys(keywords)),
        "raw_meta": parser.meta,
        "lookup_title": lookup_hints.get("lookup_title"),
        "lookup_redirect_url": lookup_hints.get("redirect_url"),
        "identifier_value": lookup_hints.get("identifier_value"),
    }


def merge_html_metadata(base_metadata: ProviderMetadata | None, html_metadata: HtmlMetadata) -> HtmlMetadata:
    base = dict(base_metadata or {})
    merged = dict(base)
    for key in (
        "title",
        "journal_title",
        "published",
        "landing_page_url",
        "doi",
        "article_type",
        "citation_fulltext_html_url",
        "citation_abstract_html_url",
    ):
        merged[key] = normalize_text(str(base.get(key) or html_metadata.get(key) or "")) or None
    merged["abstract"] = normalize_text(str(html_metadata.get("abstract") or base.get("abstract") or "")) or None
    base_authors = [normalize_text(str(item)) for item in (base.get("authors") or []) if normalize_text(str(item))]
    html_authors = [
        normalize_text(str(item)) for item in (html_metadata.get("authors") or []) if normalize_text(str(item))
    ]
    merged["authors"] = dedupe_authors(base_authors + html_authors)
    merged["keywords"] = list(
        dict.fromkeys(
            normalize_text(str(item))
            for item in (base.get("keywords") or []) + (html_metadata.get("keywords") or [])
            if normalize_text(str(item))
        )
    )
    merged["license_urls"] = list(base.get("license_urls") or [])
    merged["fulltext_links"] = list(base.get("fulltext_links") or [])
    merged["raw_meta"] = html_metadata.get("raw_meta", {})
    if html_metadata.get("lookup_title"):
        merged["lookup_title"] = html_metadata.get("lookup_title")
    if html_metadata.get("lookup_redirect_url"):
        merged["lookup_redirect_url"] = html_metadata.get("lookup_redirect_url")
    if html_metadata.get("identifier_value"):
        merged["identifier_value"] = html_metadata.get("identifier_value")
    if not merged.get("doi"):
        merged["doi"] = normalize_doi(str(html_metadata.get("doi") or ""))
    return merged
