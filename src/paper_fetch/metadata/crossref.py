"""Crossref metadata lookup client."""

from __future__ import annotations

import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..config import build_user_agent
from ..errors import ProviderFailure
from ..http import (
    HttpTransport,
    RequestFailure,
    decode_json_object_response,
    provider_request_policy,
)
from ..metadata.types import CrossrefMetadata, FulltextLink, ReferenceMetadata
from ..publisher_identity import normalize_doi
from ..providers.base import map_request_failure
from ..reason_codes import IDENTITY_MISMATCH, NO_RESULT, NOT_SUPPORTED
from ..utils import (
    date_parts_to_string,
    first_list_item,
    first_non_empty,
    strip_html_tags,
)


def _map_crossref_request_failure(exc: RequestFailure) -> ProviderFailure:
    return map_request_failure(exc)


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
                    request_policy=provider_request_policy("crossref", "metadata"),
                )
            except RequestFailure as exc:
                raise _map_crossref_request_failure(exc) from exc
            try:
                payload = decode_json_object_response(
                    response, label="Crossref", required_keys=("message",)
                )
                message = payload["message"]
                if not isinstance(message, Mapping):
                    raise RequestFailure(
                        int(response.get("status_code") or 200),
                        "Crossref message must be an object.",
                        url=str(response.get("url") or ""),
                        error_category="response_schema_mismatch",
                    )
            except RequestFailure as exc:
                raise _map_crossref_request_failure(exc) from exc
            observed_doi = normalize_doi(str(message.get("DOI") or ""))
            if observed_doi and observed_doi != doi:
                raise ProviderFailure(
                    IDENTITY_MISMATCH,
                    "Crossref response DOI does not match the endpoint DOI.",
                )
            return self.normalize_message(message, response["url"])

        if not article_title:
            raise ProviderFailure(
                NOT_SUPPORTED,
                "Crossref metadata search requires a DOI or article_title in this implementation.",
            )

        candidates = self.search_bibliographic_candidates(
            article_title, journal_title=journal_title, rows=5
        )
        if not candidates:
            raise ProviderFailure(NO_RESULT, "Crossref returned no metadata results.")
        return candidates[0]

    def search_bibliographic_candidates(
        self,
        article_title: str,
        *,
        journal_title: str | None = None,
        doi_prefix: str | None = None,
        rows: int = 5,
    ) -> list[CrossrefMetadata]:
        normalized_title = article_title.strip()
        if not normalized_title:
            raise ProviderFailure(
                NOT_SUPPORTED,
                "Crossref bibliographic search requires a non-empty title query.",
            )

        params = self.query_params()
        params.update(
            {
                "rows": str(rows),
                "query.bibliographic": normalized_title,
            }
        )
        if journal_title and journal_title.strip():
            params["query.container-title"] = journal_title.strip()
        if doi_prefix and doi_prefix.strip():
            params["filter"] = f"prefix:{doi_prefix.strip().rstrip('/')}"

        try:
            response = self.transport.request(
                "GET",
                "https://api.crossref.org/works",
                headers=self.headers(),
                query=params,
                request_policy=provider_request_policy("crossref", "metadata"),
            )
        except RequestFailure as exc:
            raise _map_crossref_request_failure(exc) from exc

        try:
            payload = decode_json_object_response(
                response, label="Crossref", required_keys=("message",)
            )
            message = payload["message"]
            if not isinstance(message, Mapping):
                raise RequestFailure(
                    int(response.get("status_code") or 200),
                    "Crossref message must be an object.",
                    url=str(response.get("url") or ""),
                    error_category="response_schema_mismatch",
                )
        except RequestFailure as exc:
            raise _map_crossref_request_failure(exc) from exc
        items = message.get("items", [])
        if not items:
            return []
        return [
            self.normalize_message(item, response["url"])
            for item in items
            if isinstance(item, dict)
        ]

    def normalize_message(
        self, message: Mapping[str, Any], source_url: str
    ) -> CrossrefMetadata:
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
            str(license_record.get("URL"))
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
            raw = first_non_empty(
                reference.get("unstructured"),
                reference.get("article-title"),
                reference.get("DOI"),
            )
            if not raw:
                continue
            references.append(
                {
                    "raw": strip_html_tags(str(raw)) or "",
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
