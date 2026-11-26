"""Best-effort DOI enrichment after Elsevier XML acceptance.

The XML bibliography remains authoritative for membership, text and order.
All matching evidence is internal; conversion to ArticleModel performs no I/O.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from copy import copy
from dataclasses import dataclass, replace
from typing import Any

from ..errors import ProviderFailure
from ..http import HttpRequestPolicy, RequestCancelledError
from ..http.transport import request_cancel_check, request_timeout_limit
from ..publication_dates import citation_date
from ..publisher_identity import normalize_doi
from ..reason_codes import NO_RESULT
from ..tracing import TraceEvent
from ._article_markdown_common import (
    child_text,
    first_child,
    first_descendant,
    xml_local_name,
)
from ._article_markdown_elsevier_document import (
    _extract_reference_title,
    _xml_reference_source,
)
from ._reference_doi import reference_doi

DEFAULT_REFERENCE_ENRICHMENT_BUDGET_SECONDS = 15.0


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
    is_journal_host: bool = True

    @property
    def searchable(self):
        return bool(self.title and self.first_author and self.year)


def _host_fields(host):
    return (
        _text(host, "date"),
        _text(host, "volume-nr"),
        _text(host, "first-page") or _text(host, "article-number"),
    )


def _journal_host(host, *, volume: str, first_page: str) -> bool:
    if (
        first_descendant(host, "book") is not None
        or first_descendant(host, "edited-book") is not None
    ):
        return False
    issue = first_descendant(host, "issue")
    if issue is not None:
        return first_descendant(issue, "conference") is None
    return first_descendant(host, "e-host") is None and bool(
        _text(host, "issn") or volume or first_page or _text(host, "maintitle")
    )


def xml_citations(root) -> list[Citation]:
    result = []
    for node in root.iter():
        if xml_local_name(node.tag) != "bib-reference":
            continue
        reference, _, _, doi = _xml_reference_source(node)
        contribution = first_child(reference, "contribution")
        hosts = [
            child
            for child in (() if reference is None else reference)
            if isinstance(child.tag, str) and xml_local_name(child.tag) == "host"
        ]
        author = first_descendant(contribution, "author")
        fields = [_host_fields(host) for host in hosts]
        journal_fields = [
            values
            for host, values in zip(hosts, fields, strict=True)
            if _journal_host(host, volume=values[1], first_page=values[2])
        ]
        year, volume, first_page = (journal_fields or fields or [("", "", "")])[0]
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
                year=year,
                volume=volume,
                first_page=first_page,
                doi=doi,
                is_journal_host=bool(journal_fields)
                and first_descendant(node, "other-ref") is None,
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
        year=str(citation_date(record.get("publication_dates")) or "")[:4]
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


class _ReferenceBudget:
    def __init__(self, context):
        self.context = context
        self.deadline = time.monotonic() + DEFAULT_REFERENCE_ENRICHMENT_BUDGET_SECONDS

    def effective_deadline(self) -> float:
        deadline = self.context.deadline_monotonic
        return self.deadline if deadline is None else min(self.deadline, deadline)

    def remaining(self) -> float:
        self.context.raise_if_cancelled()
        remaining = self.effective_deadline() - time.monotonic()
        if remaining <= 0:
            raise _ReferenceDeadlineExceeded("Reference completion deadline exceeded.")
        return remaining


class _RequestTransport:
    """Reuse HTTP caching/limits while bounding enrichment to this request."""

    def __init__(self, transport, context, *, budget=None):
        self.transport = transport
        self.budget = budget if budget is not None else _ReferenceBudget(context)

    def request(self, method, url, **kwargs):
        policy = kwargs.get("request_policy") or HttpRequestPolicy()
        kwargs["timeout"] = min(
            self.budget.remaining(),
            5.0,
            kwargs.get("timeout") or policy.timeout_seconds or 5.0,
        )
        previous = request_cancel_check.get()

        def combined_check():
            self.budget.remaining()
            return bool(previous and previous())

        cancel_token = request_cancel_check.set(combined_check)
        timeout_token = request_timeout_limit.set(self.budget.remaining)
        try:
            try:
                response = self.transport.request(method, url, **kwargs)
            except RequestCancelledError:
                raise
            except Exception:
                self.budget.remaining()
                raise
            self.budget.remaining()
            return response
        finally:
            request_timeout_limit.reset(timeout_token)
            request_cancel_check.reset(cancel_token)


def _crossref_client(context, budget):
    crossref = context.get_clients().get("crossref")
    if crossref is None:
        return None
    if getattr(crossref, "lookup", None) is not None:
        # Copy the lightweight client, never mutate the shared client's transport.
        crossref = copy(crossref)
        crossref.lookup = copy(crossref.lookup)
        crossref.lookup.transport = _RequestTransport(
            crossref.lookup.transport, context, budget=budget
        )
    return crossref


def complete_reference_dois(doi, payload, context):
    """Fill missing DOIs in accepted XML using Crossref bibliographic evidence."""
    from ..workflow.session_cache import CROSSREF_METADATA_KEY
    from .elsevier import elsevier_xml_root_from_payload

    started = time.perf_counter()
    budget = _ReferenceBudget(context)
    diagnostics: dict[str, list[dict[str, Any]]] = {"matches": [], "attempts": []}

    def attempt(operation, *args, **kwargs):
        budget.remaining()
        try:
            result = operation(*args, **kwargs)
        except (RequestCancelledError, _ReferenceDeadlineExceeded):
            raise
        except ProviderFailure as exc:
            budget.remaining()
            outcome = "info" if exc.code == NO_RESULT else "unavailable"
            return None, {"outcome": outcome, "reason": exc.code}
        except Exception as exc:  # Enrichment must never discard accepted XML.
            budget.remaining()
            return None, {"outcome": "unavailable", "reason": type(exc).__name__}
        budget.remaining()
        return result, {"outcome": "ok"}

    def record_attempt(source, result):
        result, details = result
        diagnostics["attempts"].append({"source": source, **details})
        return result

    def fill(records, source, targets, *, work=False, keys=True):
        candidates = [
            metadata_citation(record, work=work)
            for record in records
            if isinstance(record, Mapping)
        ]
        for index in targets:
            target = pending[index]
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

    def search(crossref):
        titles: dict[str, list[int]] = {}
        for index, target in pending.items():
            if target.is_journal_host and target.searchable:
                titles.setdefault(_normalized(target.title), []).append(index)
        if not titles:
            return
        keys = {title: ("elsevier_reference_search", title) for title in titles}
        cached = {title: context.get_session_cache(key) for title, key in keys.items()}
        completed_results: dict[str, tuple[Any, dict[str, Any]]] = {}

        def collect(done):
            deadline_error = None
            for future in done:
                try:
                    completed_results[futures[future]] = future.result()
                except _ReferenceDeadlineExceeded as exc:
                    deadline_error = exc
            return deadline_error

        def apply_completed():
            for title in titles:
                records = cached[title]
                if title in completed_results:
                    records = record_attempt(
                        "crossref_search", completed_results[title]
                    )
                    if records is not None:
                        context.set_session_cache(keys[title], records)
                if records:
                    fill(
                        records, "crossref_search", titles[title], work=True, keys=False
                    )

        executor = ThreadPoolExecutor(max_workers=min(3, len(titles)))
        try:
            futures: dict[Future[tuple[Any, dict[str, Any]]], str] = {
                executor.submit(
                    copy_context().run,
                    attempt,
                    crossref.search_bibliographic_candidates,
                    pending[indices[0]].title,
                    rows=5,
                ): title
                for title, indices in titles.items()
                if cached[title] is None
            }
            unfinished = set(futures)
            try:
                while unfinished:
                    done, unfinished = wait(
                        unfinished,
                        timeout=min(0.1, budget.remaining()),
                        return_when=FIRST_COMPLETED,
                    )
                    if deadline_error := collect(done):
                        raise deadline_error
            except _ReferenceDeadlineExceeded:
                collect(future for future in unfinished if future.done())
                apply_completed()
                raise
            apply_completed()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    source = "xml_citations"
    try:
        budget.remaining()
        root = elsevier_xml_root_from_payload(
            payload.content.body, context=context, source_url=payload.content.source_url
        )
        if root is None:
            return payload
        pending = {i: ref for i, ref in enumerate(xml_citations(root)) if not ref.doi}
        if not pending:
            return payload

        source = "crossref_client"
        crossref = record_attempt(source, attempt(_crossref_client, context, budget))
        source = "crossref_parent"
        parent_key = CROSSREF_METADATA_KEY.materialize(normalize_doi(doi))
        parent = context.get_session_cache(parent_key)
        if parent is None and crossref is not None:
            parent = record_attempt(
                source, attempt(crossref.fetch_metadata, {"doi": doi})
            )
            if parent is not None:
                context.set_session_cache(parent_key, parent)
        if isinstance(parent, Mapping) and normalize_doi(
            parent.get("doi")
        ) == normalize_doi(doi):
            fill(
                parent.get("_reference_records") or parent.get("references") or [],
                source,
                list(pending),
            )

        source = "crossref_search"
        if crossref is not None and pending:
            search(crossref)

        budget.remaining()
    except RequestCancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        context.raise_if_cancelled()
        diagnostics["attempts"].append(
            {"source": source, "outcome": "unavailable", "reason": type(exc).__name__}
        )
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
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
            duration_ms=duration_ms,
            target=match["doi"],
            message=f"Reference {match['index'] + 1}: {match['doi']}; source={match['source']}; basis={match['basis']}.",
        )
        for match in diagnostics["matches"]
    )
    outcome = "info"
    if diagnostics["matches"]:
        outcome = "ok"
    elif any(item["outcome"] == "unavailable" for item in diagnostics["attempts"]):
        outcome = "unavailable"
    payload.trace.append(
        TraceEvent(
            stage="references",
            component="elsevier_doi_completion",
            outcome=outcome,
            duration_ms=duration_ms,
            message=f"Filled {len(diagnostics['matches'])} XML reference DOIs; evidence in reference_doi_completion diagnostics.",
        )
    )
    return payload
