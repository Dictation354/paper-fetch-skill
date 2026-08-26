"""arXiv Atom API client and parsers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Sequence
import re
import xml.etree.ElementTree as ET

from ..arxiv_id import arxiv_id_from_query, normalize_arxiv_id
from ..http import (
    HttpTransport,
    RequestFailure,
    is_pdf_content_type,
)
from ..http.provider_policy import provider_request_policy
from ..provider_catalog import compile_route_execution_policy
from ..utils import normalize_text
from ..xml_security import XmlParseFailure, parse_xml
from ._arxiv_metadata import _dedupe_strings

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_API_ACCEPT = "application/atom+xml,application/xml,text/xml,*/*;q=0.8"
ARXIV_API_TIMEOUT_SECONDS = 60
ARXIV_API_DELAY_SECONDS = 3.0
ARXIV_API_NUM_RETRIES = 2
_ARXIV_ATOM_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


@dataclass(frozen=True)
class ArxivSearch:
    id_list: Sequence[str]
    max_results: int = 1


@dataclass(frozen=True)
class ArxivApiAuthor:
    name: str


@dataclass(frozen=True)
class ArxivApiResult:
    entry_id: str
    updated: datetime | None
    published: datetime | None
    title: str
    authors: tuple[ArxivApiAuthor, ...]
    summary: str
    comment: str | None = None
    journal_ref: str | None = None
    doi: str | None = None
    primary_category: str | None = None
    categories: tuple[str, ...] = ()
    pdf_url: str | None = None
    short_id: str = ""

    def get_short_id(self) -> str:
        return self.short_id or arxiv_id_from_query(self.entry_id)


def _parse_arxiv_atom_datetime(value: str | None) -> datetime | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def _atom_text(entry: ET.Element, path: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        normalize_text(
            entry.findtext(path, default="", namespaces=_ARXIV_ATOM_NAMESPACES)
        ),
    ).strip()


def _atom_attr(entry: ET.Element, path: str, attribute: str) -> str:
    node = entry.find(path, _ARXIV_ATOM_NAMESPACES)
    if node is None:
        return ""
    return normalize_text(node.get(attribute))


def _atom_pdf_url(entry: ET.Element) -> str:
    for link in entry.findall("atom:link", _ARXIV_ATOM_NAMESPACES):
        href = normalize_text(link.get("href"))
        if not href:
            continue
        title = normalize_text(link.get("title")).lower()
        content_type = normalize_text(link.get("type")).lower()
        if title == "pdf" or is_pdf_content_type(content_type) or "/pdf/" in href:
            return href
    return ""


def _parse_arxiv_atom_result(
    entry: ET.Element, *, requested_ids: Sequence[str]
) -> ArxivApiResult:
    entry_id = _atom_text(entry, "atom:id")
    short_id = arxiv_id_from_query(entry_id)
    if not short_id and len(requested_ids) == 1:
        short_id = requested_ids[0]
    authors = tuple(
        ArxivApiAuthor(name=name)
        for name in _dedupe_strings(
            [
                _atom_text(author, "atom:name")
                for author in entry.findall("atom:author", _ARXIV_ATOM_NAMESPACES)
            ]
        )
    )
    categories = tuple(
        _dedupe_strings(
            [
                category.get("term")
                for category in entry.findall("atom:category", _ARXIV_ATOM_NAMESPACES)
            ]
        )
    )
    primary_category = _atom_attr(entry, "arxiv:primary_category", "term")
    if not primary_category and categories:
        primary_category = categories[0]
    return ArxivApiResult(
        entry_id=entry_id,
        updated=_parse_arxiv_atom_datetime(_atom_text(entry, "atom:updated")),
        published=_parse_arxiv_atom_datetime(_atom_text(entry, "atom:published")),
        title=_atom_text(entry, "atom:title"),
        authors=authors,
        summary=_atom_text(entry, "atom:summary"),
        comment=_atom_text(entry, "arxiv:comment") or None,
        journal_ref=_atom_text(entry, "arxiv:journal_ref") or None,
        doi=_atom_text(entry, "arxiv:doi") or None,
        primary_category=primary_category or None,
        categories=categories,
        pdf_url=_atom_pdf_url(entry) or None,
        short_id=short_id,
    )


def _parse_arxiv_atom_results(
    body: bytes, *, requested_ids: Sequence[str]
) -> list[ArxivApiResult]:
    try:
        root = parse_xml(body, source="arXiv API Atom XML")
    except XmlParseFailure as exc:
        raise ValueError(f"Invalid arXiv API Atom XML: {exc}") from exc
    return [
        _parse_arxiv_atom_result(entry, requested_ids=requested_ids)
        for entry in root.findall("atom:entry", _ARXIV_ATOM_NAMESPACES)
    ]


class InternalArxivApiClient:
    def __init__(self, transport: HttpTransport, user_agent: str) -> None:
        self.transport = transport
        self.user_agent = user_agent

    def results(self, search: ArxivSearch) -> list[ArxivApiResult]:
        requested_ids = [
            normalized
            for raw_id in getattr(search, "id_list", [])
            if (normalized := normalize_arxiv_id(str(raw_id)))
        ]
        if not requested_ids:
            return []
        max_results = max(1, int(getattr(search, "max_results", 1) or 1))
        execution_policy = compile_route_execution_policy("arxiv", "atom_metadata")
        response = self.transport.request(
            "GET",
            ARXIV_API_URL,
            headers={
                "Accept": ARXIV_API_ACCEPT,
                "User-Agent": self.user_agent,
            },
            query={
                "id_list": ",".join(requested_ids),
                "max_results": str(max_results),
            },
            timeout=execution_policy.timeout_seconds,
            retry_on_rate_limit=execution_policy.retry_on_rate_limit,
            rate_limit_retries=execution_policy.rate_limit_retries,
            max_rate_limit_wait_seconds=int(
                execution_policy.rate_limit_wait_budget_seconds
            ),
            retry_on_transient=execution_policy.retry_on_transient,
            transient_retries=execution_policy.transient_retries,
            request_policy=provider_request_policy("arxiv", "atom_metadata"),
        )
        status_code = int(response.get("status_code") or 0)
        if status_code >= 400:
            raise RequestFailure(
                status_code,
                f"HTTP {status_code} for {ARXIV_API_URL}",
                body=bytes(response.get("body") or b""),
                headers=response.get("headers"),
                url=normalize_text(response.get("url")) or ARXIV_API_URL,
            )
        body = response.get("body") or b""
        if not isinstance(body, bytes):
            body = str(body).encode("utf-8")
        return _parse_arxiv_atom_results(body, requested_ids=requested_ids)
