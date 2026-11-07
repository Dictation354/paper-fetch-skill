"""Best-effort DOI enrichment after Elsevier XML acceptance.

The XML bibliography remains authoritative for membership, text and order.
All matching evidence is internal; conversion to ArticleModel performs no I/O.
"""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, replace
import re
import unicodedata
from typing import Any
from collections.abc import Mapping, Sequence

from ..http import HttpRequestPolicy, RequestCancelledError
from ..http.transport import request_cancel_check
from ..publisher_identity import normalize_doi
from ..tracing import TraceEvent
from ._article_markdown_common import (
    first_child,
    first_descendant,
    child_text,
    xml_local_name,
)
from ._article_markdown_elsevier_document import _extract_reference_title
from ._reference_doi import reference_doi


def _normalized(value: Any) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKC", str(value or "")).casefold()
        if c.isalnum()
    )


def _author(value: str) -> str:
    # Publisher citations use initials followed by the surname. Crossref's
    # reference author may instead use 'Surname, initials'.
    value = value.split(",", 1)[0].strip()
    value = re.sub(r"^(?:[^\W\d_]\.(?:\s*|(?=[^\W\d_])))+", "", value)
    return _normalized(value)


def _text(node, name):
    found = first_descendant(node, name)
    return " ".join("".join(found.itertext()).split()) if found is not None else ""


@dataclass(frozen=True)
class Citation:
    keys: tuple[str, ...] = ()
    title: str = ""
    first_author: str = ""
    year: str = ""
    volume: str = ""
    first_page: str = ""
    doi: str = ""

    @property
    def searchable(self):
        return bool(self.title and self.first_author and self.year)


def xml_citations(root) -> list[Citation]:
    result = []
    for node in root.iter():
        if xml_local_name(node.tag) != "bib-reference":
            continue
        reference = first_child(node, "reference")
        contribution = first_child(reference, "contribution")
        host = first_child(reference, "host")
        author = first_descendant(contribution, "author")
        result.append(
            Citation(
                keys=tuple(
                    value
                    for value in (
                        node.get("id"),
                        reference.get("id") if reference is not None else "",
                    )
                    if value
                ),
                title=_extract_reference_title(contribution),
                first_author=child_text(author, "surname"),
                year=_text(host, "date"),
                volume=_text(host, "volume-nr"),
                first_page=_text(host, "first-page") or _text(host, "article-number"),
                doi=reference_doi(_text(reference, "doi"))
                or reference_doi(_text(node, "source-text"))
                or "",
            )
        )
    return result


def metadata_citation(record: Mapping[str, Any], *, work=False) -> Citation:
    extra = record.get("_bibliography") or {}
    first_author = str(extra.get("first_author") or record.get("author") or "")
    if not first_author and record.get("authors"):
        first_author = str(record["authors"][0]).split()[-1]
    return Citation(
        keys=tuple(
            extra.get("keys") or ([str(record["key"])] if record.get("key") else [])
        ),
        title=str(record.get("title") or record.get("article-title") or ""),
        first_author=first_author,
        year=str(record.get("published") or "")[:4]
        if work
        else str(record.get("year") or ""),
        volume=str(extra.get("volume") or record.get("volume") or ""),
        first_page=str(extra.get("first_page") or record.get("first-page") or ""),
        doi=reference_doi(str(record.get("doi") or record.get("DOI") or "")) or "",
    )


def _key(value: str, parent_doi: str) -> str:
    prefix = parent_doi.casefold() + "_"
    return value[len(prefix) :] if value.casefold().startswith(prefix) else value


def match_citation(
    target: Citation,
    candidates: Sequence[Citation],
    *,
    parent_doi: str,
    allow_keys=True,
):
    """A unique record, never the first result or a positional association."""
    keyed = [
        candidate
        for candidate in candidates
        if allow_keys
        and {_key(k, parent_doi) for k in target.keys}
        & {_key(k, parent_doi) for k in candidate.keys}
    ]
    pool = keyed if keyed else candidates
    matches = []
    for candidate in pool:
        if not candidate.doi:
            continue
        fields = (
            (target.title, candidate.title, _normalized),
            (target.first_author, candidate.first_author, _author),
            (target.year, candidate.year, _normalized),
            (target.volume, candidate.volume, _normalized),
            (target.first_page, candidate.first_page, _normalized),
        )
        if any(a and b and normalize(a) != normalize(b) for a, b, normalize in fields):
            continue
        if not keyed and not (target.searchable and candidate.searchable):
            continue
        matches.append(candidate)
    # Multiple records are ambiguous even if they happen to name the same DOI.
    if len(matches) != 1:
        return None
    return matches[0], "reference_key" if keyed else "title_author_year_volume_pages"


class _ReferenceDeadlineExceeded(Exception):
    """An enrichment deadline is not a retryable HTTP socket timeout."""


class _RequestTransport:
    """Reuse HTTP caching/limits while bounding enrichment to this request."""

    def __init__(self, transport, context):
        self.transport, self.context = transport, context

    def request(self, method, url, **kwargs):
        context = self.context
        remaining = context.remaining_seconds(30)
        if remaining < 1:
            raise TimeoutError("Reference completion deadline exceeded.")
        policy = kwargs.get("request_policy") or HttpRequestPolicy()
        kwargs["timeout"] = min(int(remaining), policy.timeout_seconds or 30)

        def check():
            context.raise_if_cancelled()
            if context.remaining_seconds() <= 0:
                raise _ReferenceDeadlineExceeded(
                    "Reference completion deadline exceeded."
                )
            return False

        previous = request_cancel_check.get()

        def combined_check():
            return check() or bool(previous and previous())

        token = request_cancel_check.set(combined_check)
        try:
            return self.transport.request(method, url, **kwargs)
        finally:
            request_cancel_check.reset(token)


def _crossref_client(context):
    crossref = context.get_clients().get("crossref")
    if crossref is None:
        return None
    if getattr(crossref, "lookup", None) is not None:
        # Copy the lightweight client, never mutate the shared client's transport.
        crossref = copy(crossref)
        crossref.lookup = copy(crossref.lookup)
        crossref.lookup.transport = _RequestTransport(
            crossref.lookup.transport, context
        )
    return crossref


def _web_references(client, doi, metadata, context):
    from . import _elsevier_html
    from .browser_runtime import BrowserHtmlReadiness
    from .browser_runtime.types import BrowserHtmlFetchOptions
    from ..extraction.html._metadata import parse_html_metadata
    from ..extraction.html.parsing import choose_parser
    from bs4 import BeautifulSoup

    runtime = client.deps.load_runtime_config(client.env, provider="elsevier", doi=doi)
    if runtime.backend != "byparr":
        return []
    client.deps.ensure_runtime_ready(runtime)
    # The provider's normal context manager reuses its request-local profile lease.
    result = client.deps.fetch_html_with_browser(
        client.html_candidates(doi, metadata),
        publisher="elsevier",
        config=runtime,
        max_timeout_ms=context.remaining_timeout_ms(runtime.timeout_ms),
        runtime_context=context,
        wait_seconds=0,
        readiness=BrowserHtmlReadiness(selector="#references", require_selector=True),
        options=BrowserHtmlFetchOptions(reuse_runtime_page=True),
    )
    context.raise_if_cancelled()
    observed = normalize_doi(
        parse_html_metadata(result.html, result.final_url).get("doi")
    )
    if not observed or observed != normalize_doi(doi):
        return []
    soup = BeautifulSoup(result.html, choose_parser())
    for node in list(soup.select(_elsevier_html.NOISE_SELECTOR)):
        node.decompose()
    return _elsevier_html._references(soup)


def complete_reference_dois(client, doi, metadata, payload, context):
    """Enrich accepted XML, retaining it on lookup, browser or matching failure."""
    from .elsevier import elsevier_xml_root_from_payload
    from ..workflow.session_cache import CROSSREF_METADATA_KEY

    context.raise_if_cancelled()
    root = elsevier_xml_root_from_payload(
        payload.body, context=context, source_url=payload.source_url
    )
    if root is None:
        return payload
    citations = xml_citations(root)
    pending = {i: ref for i, ref in enumerate(citations) if not ref.doi}
    if not pending:
        return payload
    diagnostics: dict[str, list[dict[str, Any]]] = {"matches": [], "attempts": []}

    def attempt(source, operation):
        context.raise_if_cancelled()
        try:
            if context.remaining_seconds() <= 0:
                raise TimeoutError("Reference completion deadline exceeded.")
            result = operation()
            context.raise_if_cancelled()
        except RequestCancelledError:
            raise
        except Exception as exc:  # Enrichment must never discard accepted XML.
            context.raise_if_cancelled()
            diagnostics["attempts"].append(
                {
                    "source": source,
                    "outcome": "unavailable",
                    "reason": type(exc).__name__,
                }
            )
            return None
        diagnostics["attempts"].append({"source": source, "outcome": "ok"})
        return result

    def fill(records, source, *, work=False, keys=True):
        candidates = [
            metadata_citation(record, work=work)
            for record in records
            if isinstance(record, Mapping)
        ]
        for index, target in list(pending.items()):
            matched = match_citation(
                target, candidates, parent_doi=doi, allow_keys=keys
            )
            if matched is None:
                continue
            candidate, basis = matched
            diagnostics["matches"].append(
                {
                    "index": index,
                    "reference_keys": list(target.keys),
                    "doi": candidate.doi,
                    "source": source,
                    "basis": basis,
                    "evidence": {
                        "title": candidate.title,
                        "first_author": candidate.first_author,
                        "year": candidate.year,
                        "volume": candidate.volume,
                        "first_page": candidate.first_page,
                    },
                }
            )
            del pending[index]

    crossref = attempt("crossref_client", lambda: _crossref_client(context))
    parent_key = CROSSREF_METADATA_KEY.materialize(normalize_doi(doi))
    parent = context.get_session_cache(parent_key)
    if parent is None and crossref is not None:
        parent = attempt(
            "crossref_parent", lambda: crossref.fetch_metadata({"doi": doi})
        )
        if parent is not None:
            context.set_session_cache(parent_key, parent)
    if isinstance(parent, Mapping) and normalize_doi(
        parent.get("doi")
    ) == normalize_doi(doi):
        fill(
            parent.get("_reference_records") or parent.get("references") or [],
            "crossref_parent",
        )

    if crossref is not None:
        for index, target in list(pending.items()):
            if index not in pending:
                continue
            if not target.searchable:
                continue
            key = ("elsevier_reference_search", _normalized(target.title))
            records = context.get_session_cache(key)
            if records is None:
                records = attempt(
                    "crossref_search",
                    lambda title=target.title: crossref.search_bibliographic_candidates(
                        title, rows=5
                    ),
                )
                context.set_session_cache(key, records or [])
            fill(records or [], "crossref_search", work=True, keys=False)

    if pending:
        key = ("elsevier_reference_html", normalize_doi(doi))
        records = context.get_session_cache(key)
        if records is None:
            records = attempt(
                "elsevier_html", lambda: _web_references(client, doi, metadata, context)
            )
            context.set_session_cache(key, records or [])
        fill(records or [], "elsevier_html")
    payload.content = replace(
        payload.content,
        diagnostics={
            **payload.content.diagnostics,
            "reference_doi_completion": diagnostics,
        },
    )
    payload.trace.extend(
        TraceEvent(
            stage="references",
            component="elsevier_doi_completion",
            outcome="ok",
            provider="elsevier",
            target=match["doi"],
            message=f"Reference {match['index'] + 1}: {match['doi']}; source={match['source']}; basis={match['basis']}.",
        )
        for match in diagnostics["matches"]
    )
    payload.trace.append(
        TraceEvent(
            stage="references",
            component="elsevier_doi_completion",
            outcome="ok" if diagnostics["matches"] else "unavailable",
            message=f"Filled {len(diagnostics['matches'])} XML reference DOIs; evidence in reference_doi_completion diagnostics.",
        )
    )
    return payload
