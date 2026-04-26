"""Crossref metadata lookup client."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Mapping

from ..config import build_user_agent
from ..errors import ProviderFailure
from ..http import DEFAULT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ..metadata_types import CrossrefMetadata, FulltextLink, ReferenceMetadata
from ..publisher_identity import normalize_doi
from ..utils import (
    date_parts_to_string,
    first_list_item,
    first_non_empty,
    strip_html_tags,
)


def _map_crossref_request_failure(exc: RequestFailure) -> ProviderFailure:
    if exc.status_code in {401, 403}:
        return ProviderFailure("no_access", str(exc))
    if exc.status_code == 404:
        return ProviderFailure("no_result", str(exc))
    if exc.status_code == 429:
        return ProviderFailure("rate_limited", str(exc), retry_after_seconds=exc.retry_after_seconds)
    if exc.status_code in {400, 406, 422}:
        return ProviderFailure("error", str(exc))
    if exc.status_code is None:
        return ProviderFailure("error", str(exc))
    if exc.status_code >= 500:
        return ProviderFailure("error", str(exc))
    return ProviderFailure("error", str(exc))


class CrossrefLookupClient:
    """Low-level Crossref HTTP lookup and metadata normalization client."""

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.user_agent = build_user_agent(env)
        self.mailto = env.get("CROSSREF_MAILTO", "").strip()

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

    def query_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.mailto:
            params["mailto"] = self.mailto
        return params

    def fetch_metadata(self, query: Mapping[str, str | None]) -> CrossrefMetadata:
        doi = normalize_doi(query.get("doi"))
        article_title = (query.get("article_title") or "").strip()
        journal_title = (query.get("journal_title") or "").strip()

        if doi:
            url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    headers=self.headers(),
                    query=self.query_params(),
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
            except RequestFailure as exc:
                raise _map_crossref_request_failure(exc) from exc
            payload = json.loads(response["body"].decode("utf-8"))
            return self.normalize_message(payload["message"], response["url"])

        if not article_title:
            raise ProviderFailure(
                "not_supported",
                "Crossref metadata search requires a DOI or article_title in this implementation.",
            )

        candidates = self.search_bibliographic_candidates(article_title, journal_title=journal_title, rows=5)
        if not candidates:
            raise ProviderFailure("no_result", "Crossref returned no metadata results.")
        return candidates[0]

    def search_bibliographic_candidates(
        self,
        article_title: str,
        *,
        journal_title: str | None = None,
        rows: int = 5,
    ) -> list[CrossrefMetadata]:
        normalized_title = article_title.strip()
        if not normalized_title:
            raise ProviderFailure("not_supported", "Crossref bibliographic search requires a non-empty title query.")

        params = self.query_params()
        params.update(
            {
                "rows": str(rows),
                "query.bibliographic": normalized_title,
            }
        )
        if journal_title and journal_title.strip():
            params["query.container-title"] = journal_title.strip()

        try:
            response = self.transport.request(
                "GET",
                "https://api.crossref.org/works",
                headers=self.headers(),
                query=params,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise _map_crossref_request_failure(exc) from exc

        payload = json.loads(response["body"].decode("utf-8"))
        items = payload.get("message", {}).get("items", [])
        if not items:
            return []
        return [self.normalize_message(item, response["url"]) for item in items if isinstance(item, dict)]

    def normalize_message(self, message: Mapping[str, Any], source_url: str) -> CrossrefMetadata:
        links: list[FulltextLink] = []
        for item in message.get("link", []) or []:
            if not isinstance(item, dict):
                continue
            url = item.get("URL")
            if not url:
                continue
            links.append(
                {
                    "url": url,
                    "content_type": item.get("content-type"),
                    "content_version": item.get("content-version"),
                    "intended_application": item.get("intended-application"),
                }
            )

        licenses = [
            license_record.get("URL")
            for license_record in message.get("license", []) or []
            if isinstance(license_record, dict) and license_record.get("URL")
        ]
        authors = []
        for author in message.get("author", []) or []:
            if not isinstance(author, dict):
                continue
            name = " ".join(
                part
                for part in [
                    str(author.get("given") or "").strip(),
                    str(author.get("family") or "").strip(),
                ]
                if part
            ).strip()
            if not name and author.get("name"):
                name = str(author.get("name")).strip()
            if name:
                authors.append(name)
        references: list[ReferenceMetadata] = []
        for reference in message.get("reference", []) or []:
            if not isinstance(reference, dict):
                continue
            raw = first_non_empty(reference.get("unstructured"), reference.get("article-title"), reference.get("DOI"))
            if not raw:
                continue
            references.append(
                {
                    "raw": strip_html_tags(str(raw)),
                    "doi": reference.get("DOI"),
                    "title": reference.get("article-title"),
                    "year": reference.get("year"),
                }
            )

        keywords: list[str] = []
        seen_keywords: set[str] = set()
        for subject in message.get("subject") or []:
            if isinstance(subject, str):
                text = subject.strip()
                if text and text not in seen_keywords:
                    seen_keywords.add(text)
                    keywords.append(text)

        return {
            "status": "ok",
            "provider": "crossref",
            "official_provider": False,
            "source_url": source_url,
            "doi": message.get("DOI"),
            "title": first_list_item(message.get("title")),
            "journal_title": first_list_item(message.get("container-title")),
            "publisher": message.get("publisher"),
            "authors": authors,
            "keywords": keywords,
            "abstract": strip_html_tags(message.get("abstract")),
            "published": first_non_empty(
                date_parts_to_string(message.get("published-print")),
                date_parts_to_string(message.get("published-online")),
                date_parts_to_string(message.get("issued")),
                date_parts_to_string(message.get("created")),
            ),
            "landing_page_url": first_non_empty(
                message.get("resource", {}).get("primary", {}).get("URL")
                if isinstance(message.get("resource"), dict)
                else None,
                message.get("URL"),
            ),
            "license_urls": licenses,
            "fulltext_links": links,
            "references": references,
        }

    def _normalize_message(self, message: Mapping[str, Any], source_url: str) -> CrossrefMetadata:
        return self.normalize_message(message, source_url)
