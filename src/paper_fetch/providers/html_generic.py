"""Generic HTML fallback provider for AI-friendly article extraction."""

from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent
from ..html_lookup import is_usable_html_lookup_title
from ..http import HttpTransport, RequestFailure
from ..models import AssetProfile, article_from_markdown, normalize_text
from ..publisher_identity import extract_doi, normalize_doi
from ..utils import dedupe_authors
from . import html_assets as _html_assets
from . import html_noise as _html_noise
from .base import ProviderFailure, map_request_failure
from .html_nature import clean_nature_text_fragment, is_nature_like_url

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    NavigableString = None
    Tag = None

trafilatura = _html_noise.trafilatura
clean_html_for_extraction = _html_noise.clean_html_for_extraction
clean_markdown = _html_noise.clean_markdown
count_words = _html_noise.count_words
decode_html = _html_noise.decode_html
body_character_count = _html_noise.body_character_count
body_metrics = _html_noise.body_metrics
has_sufficient_article_body = _html_noise.has_sufficient_article_body
download_figure_assets = _html_assets.download_figure_assets
extract_figure_assets = _html_assets.extract_figure_assets
extract_full_size_figure_image_url = _html_assets.extract_full_size_figure_image_url
extract_html_assets = _html_assets.extract_html_assets
extract_supplementary_assets = _html_assets.extract_supplementary_assets
figure_download_candidates = _html_assets.figure_download_candidates
html_asset_identity_key = _html_assets.html_asset_identity_key
promote_springer_media_url_to_full_size = _html_assets.promote_springer_media_url_to_full_size
resolve_figure_download_url = _html_assets.resolve_figure_download_url

INPUT_TAG_PATTERN = re.compile(r"<input\b[^>]*>", flags=re.IGNORECASE)
HTML_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*("([^"]*)"|\'([^\']*)\')')
HTML_REFRESH_URL_PATTERN = re.compile(r"url\s*=\s*(?P<quote>['\"]?)(?P<url>[^'\";>]+)(?P=quote)", flags=re.IGNORECASE)
HTML_SCRIPT_ARTICLE_NAME_PATTERN = re.compile(r"\barticleName\s*:\s*(['\"])(?P<value>.*?)(?<!\\)\1", flags=re.IGNORECASE | re.DOTALL)
HTML_SCRIPT_IDENTIFIER_PATTERN = re.compile(r"\bidentifierValue\s*:\s*(['\"])(?P<value>.*?)(?<!\\)\1", flags=re.IGNORECASE | re.DOTALL)


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


def extract_article_markdown(html_text: str, source_url: str) -> str:
    return _html_noise.extract_article_markdown(
        html_text,
        source_url,
        trafilatura_backend=trafilatura,
    )


def parse_html_metadata(html_text: str, source_url: str) -> dict[str, Any]:
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

    authors = dedupe_authors([normalize_text(value) for value in parser.meta.get("citation_author", []) if normalize_text(value)])
    doi = extract_doi_from_meta(parser.meta) or extract_doi_from_text(parser.canonical_url or "")
    html_title = normalize_text("".join(parser.title)) or None
    if not is_usable_html_lookup_title(html_title):
        html_title = lookup_hints.get("lookup_title")
    title = first("citation_title", "dc.title", "og:title") or html_title or None
    abstract = first("citation_abstract", "description", "dc.description", "og:description")
    if abstract and is_nature_like_url(source_url):
        abstract = clean_nature_text_fragment(abstract)
    journal_title = first("citation_journal_title", "prism.publicationname", "dc.source")
    published = first("citation_publication_date", "citation_online_date", "dc.date", "prism.publicationdate")
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
        "published": published,
        "landing_page_url": parser.canonical_url or source_url,
        "doi": doi,
        "keywords": list(dict.fromkeys(keywords)),
        "raw_meta": parser.meta,
        "lookup_title": lookup_hints.get("lookup_title"),
        "lookup_redirect_url": lookup_hints.get("redirect_url"),
        "identifier_value": lookup_hints.get("identifier_value"),
    }


def extract_html_lookup_hints(
    html_text: str,
    source_url: str,
    *,
    meta: Mapping[str, list[str]] | None = None,
) -> dict[str, str | None]:
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


def extract_refresh_redirect_url(refresh_value: str, source_url: str) -> str | None:
    match = HTML_REFRESH_URL_PATTERN.search(refresh_value or "")
    if not match:
        return None
    return normalize_lookup_url(match.group("url"), source_url)


def normalize_lookup_url(value: str | None, source_url: str) -> str | None:
    raw = html.unescape((value or "").strip())
    if not raw:
        return None
    unquoted = urllib.parse.unquote(raw)
    return urllib.parse.urljoin(source_url, unquoted)


def extract_doi_from_meta(meta: Mapping[str, list[str]]) -> str | None:
    for key in ("citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"):
        for value in meta.get(key, []):
            doi = extract_doi_from_text(value)
            if doi:
                return doi
    return None


def extract_doi_from_text(value: str | None) -> str | None:
    return extract_doi(value)


def merge_html_metadata(base_metadata: Mapping[str, Any] | None, html_metadata: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(base_metadata or {})
    merged = dict(base)
    for key in ("title", "journal_title", "published", "landing_page_url", "doi"):
        merged[key] = normalize_text(str(base.get(key) or html_metadata.get(key) or "")) or None
    merged["abstract"] = normalize_text(str(html_metadata.get("abstract") or base.get("abstract") or "")) or None
    base_authors = [normalize_text(str(item)) for item in (base.get("authors") or []) if normalize_text(str(item))]
    html_authors = [normalize_text(str(item)) for item in (html_metadata.get("authors") or []) if normalize_text(str(item))]
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
    return merged


class HtmlGenericClient:
    name = "html_generic"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.user_agent = build_user_agent(env)

    def fetch_article_model(
        self,
        landing_url: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        expected_doi: str | None = None,
        download_dir: Path | None = None,
        asset_profile: AssetProfile = "none",
    ):
        try:
            response = self.transport.request(
                "GET",
                landing_url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        html_text = decode_html(response["body"])
        html_metadata = parse_html_metadata(html_text, response["url"])
        merged_metadata = merge_html_metadata(metadata, html_metadata)
        if expected_doi and not merged_metadata.get("doi"):
            merged_metadata["doi"] = normalize_doi(expected_doi)

        markdown_text = clean_markdown(extract_article_markdown(html_text, response["url"]))
        if not has_sufficient_article_body(markdown_text, merged_metadata):
            raise ProviderFailure("no_result", "HTML extraction did not produce enough article body text.")

        assets = extract_html_assets(
            html_text,
            response["url"],
            asset_profile=asset_profile,
        )
        warnings: list[str] = []
        source_trail: list[str] = []
        if asset_profile == "none":
            source_trail.append("download:html_assets_skipped_profile_none")
        elif download_dir is None:
            source_trail.append("download:html_assets_skipped_no_download_dir")
        else:
            article_id = (
                normalize_doi(str(merged_metadata.get("doi") or expected_doi or ""))
                or normalize_text(str(merged_metadata.get("title") or ""))
                or response["url"]
            )
            asset_results = download_figure_assets(
                self.transport,
                article_id=article_id,
                assets=assets,
                output_dir=download_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
            )
            downloaded_assets = list(asset_results.get("assets") or [])
            downloaded_by_identity = {html_asset_identity_key(item): item for item in downloaded_assets if html_asset_identity_key(item)}
            assets = [
                {
                    **asset,
                    "path": downloaded_by_identity.get(html_asset_identity_key(asset), {}).get("path"),
                }
                for asset in assets
            ]
            if downloaded_assets:
                source_trail.append(f"download:html_assets_saved_profile_{asset_profile}")
            failures = list(asset_results.get("asset_failures") or [])
            if failures:
                warnings.append(f"HTML related assets were only partially downloaded ({len(failures)} failed).")
                source_trail.append("download:html_asset_failures")

        return article_from_markdown(
            source="html_generic",
            metadata=merged_metadata,
            doi=normalize_doi(str(merged_metadata.get("doi") or expected_doi or "")) or None,
            markdown_text=markdown_text,
            assets=assets,
            warnings=warnings,
            source_trail=source_trail,
        )
