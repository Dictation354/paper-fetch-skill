"""Privacy-safe page diagnostics for reached-but-unusable HTML routes."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .extraction.html.parsing import choose_parser
from .http import (
    diagnostic_url_payload,
    redact_text_for_diagnostics,
    redact_url_for_diagnostics,
)
from .publisher_identity import normalize_doi
from .runtime import RuntimeContext
from .utils import normalize_text, sanitize_filename

PAGE_DIAGNOSTIC_SCHEMA_VERSION = 2
SANITIZED_HTML_MAX_BYTES = 2 * 1024 * 1024
EMPTY_ARTICLE_SHELL_MAX_BYTES = 4096
_DROP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "form",
        "input",
        "textarea",
        "select",
        "button",
        "iframe",
        "object",
        "embed",
    }
)
_STRUCTURE_ATTRIBUTES = frozenset(
    {"id", "class", "role", "itemprop", "property", "typeof", "data-extent"}
)
_URL_ATTRIBUTES = frozenset({"href", "src"})
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "hr", "img", "link", "meta", "source", "wbr"}
)
_EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])"
)
_TRUNCATED_MARKER = "<!-- paper-fetch diagnostic truncated -->"


@dataclass(frozen=True)
class PageDiagnosticRequest:
    provider: str
    route: str
    attempt: int
    failure_code: str
    stage: str
    html_text: str | None
    doi: str | None = None
    target_url: str | None = None
    final_url: str | None = None
    backend: str | None = None
    response_status: int | None = None
    title: str | None = None
    summary: str | None = None
    details: Mapping[str, Any] | None = None


def _redact_page_text(value: str) -> str:
    return _EMAIL_PATTERN.sub(
        "[redacted-email]",
        redact_text_for_diagnostics(str(value or "")),
    )


def _sanitize_dom(html_text: str) -> BeautifulSoup:
    soup = BeautifulSoup(html_text, choose_parser())
    for node in list(soup.find_all(string=lambda item: isinstance(item, Comment))):
        node.extract()
    for tag in list(soup.find_all(_DROP_TAGS)):
        tag.decompose()
    for tag in soup.find_all(True):
        attrs: dict[str, Any] = {}
        for raw_name, raw_value in list(tag.attrs.items()):
            name = normalize_text(str(raw_name)).lower()
            if name.startswith("on"):
                continue
            if name in _STRUCTURE_ATTRIBUTES:
                if isinstance(raw_value, list):
                    value = " ".join(_redact_page_text(str(item)) for item in raw_value)
                else:
                    value = _redact_page_text(str(raw_value or ""))
                if value:
                    attrs[name] = value
            elif name in _URL_ATTRIBUTES:
                value = redact_url_for_diagnostics(str(raw_value or ""))
                if value:
                    attrs[name] = value
        tag.attrs = attrs
    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        redacted = _redact_page_text(str(node))
        if redacted != str(node):
            node.replace_with(redacted)
    return soup


class _BoundedHtmlSerializer:
    def __init__(self, maximum_bytes: int) -> None:
        self.maximum_bytes = max(1, int(maximum_bytes))
        self.parts: list[str] = []
        self.byte_count = 0
        self.truncated = False
        self.reserved_closing_bytes = 0
        self.marker_written = False

    def _append(self, value: str, *, is_marker: bool = False) -> bool:
        encoded_size = len(value.encode("utf-8"))
        marker_reserve = (
            0
            if self.marker_written or is_marker
            else len(_TRUNCATED_MARKER.encode("utf-8"))
        )
        if (
            self.byte_count
            + encoded_size
            + self.reserved_closing_bytes
            + marker_reserve
            > self.maximum_bytes
        ):
            self.truncated = True
            return False
        self.parts.append(value)
        self.byte_count += encoded_size
        return True

    def _attributes(self, tag: Tag) -> str:
        rendered: list[str] = []
        for name, raw_value in sorted(tag.attrs.items()):
            value = (
                " ".join(str(item) for item in raw_value)
                if isinstance(raw_value, list)
                else str(raw_value)
            )
            rendered.append(f' {name}="{html.escape(value, quote=True)}"')
        return "".join(rendered)

    def node(self, node: Any) -> bool:
        if isinstance(node, NavigableString):
            return self._append(html.escape(str(node), quote=False))
        if not isinstance(node, Tag):
            return True
        name = normalize_text(node.name).lower()
        if not name:
            return True
        opening = f"<{name}{self._attributes(node)}>"
        if name in _VOID_TAGS:
            return self._append(opening)
        closing = f"</{name}>"
        closing_bytes = len(closing.encode("utf-8"))
        self.reserved_closing_bytes += closing_bytes
        if not self._append(opening):
            self.reserved_closing_bytes -= closing_bytes
            return False
        for child in list(node.children):
            if not self.node(child):
                break
        if self.truncated and not self.marker_written:
            if self._append(_TRUNCATED_MARKER, is_marker=True):
                self.marker_written = True
        self.reserved_closing_bytes -= closing_bytes
        return self._append(closing)

    def finish(self) -> tuple[str, bool]:
        return "".join(self.parts), self.truncated


def sanitize_page_html(
    html_text: str,
    *,
    maximum_bytes: int = SANITIZED_HTML_MAX_BYTES,
) -> tuple[str, bool]:
    soup = _sanitize_dom(html_text)
    serializer = _BoundedHtmlSerializer(maximum_bytes)
    for child in list(soup.contents):
        if not serializer.node(child):
            break
    return serializer.finish()


def _page_identity(doi: str | None, target_url: str | None) -> str:
    normalized_doi = normalize_doi(doi or "")
    if normalized_doi:
        return sanitize_filename(normalized_doi)
    return hashlib.sha256(str(target_url or "").encode("utf-8")).hexdigest()


def page_shape_diagnostics(html_text: str) -> dict[str, Any]:
    """Summarize DOM shape without retaining publisher text or attributes."""

    raw_bytes = html_text.encode("utf-8")
    soup = BeautifulSoup(html_text, choose_parser())
    body = soup.find("body")
    body_text = normalize_text(body.get_text(" ", strip=True)) if body else ""
    return {
        "byte_count": len(raw_bytes),
        "has_html": soup.find("html") is not None,
        "has_head": soup.find("head") is not None,
        "has_body": body is not None,
        "body_text_length": len(body_text),
        "body_element_count": len(body.find_all(True)) if body else 0,
        "article_container_count": len(soup.select("article, main, [role='main']")),
    }


def is_empty_article_shell(
    html_text: str,
    *,
    response_status: int | None,
) -> bool:
    """Conservatively identify the observed HTTP-200 head-only publisher shell."""

    shape = page_shape_diagnostics(html_text)
    return bool(
        response_status == 200
        and shape["byte_count"] <= EMPTY_ARTICLE_SHELL_MAX_BYTES
        and not shape["has_body"]
    )


def _selected_browser_runtime_trace(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    trace = {
        key: value[key]
        for key in (
            "backend",
            "media_blocking",
            "timeout_budget_ms",
            "browser_connect_seconds",
            "duration_seconds",
            "remaining_ms",
            "deadline_exhausted",
            "browser_context_seed",
            "storage_state_save",
        )
        if key in value
    }
    candidates = value.get("candidates")
    if isinstance(candidates, list):
        safe_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            safe_candidates.append(
                {
                    key: candidate[key]
                    for key in (
                        "url",
                        "url_sha256",
                        "final_url",
                        "final_url_sha256",
                        "status",
                        "navigation_seconds",
                        "dom_readiness_seconds",
                        "dom_readiness_attempted",
                        "dom_readiness_ready",
                        "dom_readiness_selector",
                        "dom_readiness_text_length",
                        "dom_readiness_paragraph_count",
                        "dom_readiness_heading_count",
                        "selector_readiness_attempted",
                        "selector_readiness_ready",
                        "selector_readiness_required",
                        "selector_readiness_expected_text",
                        "selector_readiness_seconds",
                        "duration_seconds",
                        "result",
                        "block_reason",
                        "error",
                    )
                    if key in candidate
                }
            )
        trace["candidates"] = safe_candidates
    return trace


def _selected_page_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(details or {})
    selected: dict[str, Any] = {
        key: payload[key]
        for key in (
            "readiness",
            "candidates",
            "candidate_count",
            "candidate_diagnostics",
            "selectors",
            "selector",
            "body_metrics",
            "availability_diagnostics",
        )
        if key in payload
    }
    browser_runtime = _selected_browser_runtime_trace(
        payload.get("browser_runtime_trace")
    )
    if browser_runtime is not None:
        selected["browser_runtime"] = browser_runtime
    return selected


def capture_page_diagnostic(
    context: RuntimeContext,
    request: PageDiagnosticRequest,
) -> dict[str, Any]:
    """Return an in-memory summary and optionally persist sanitized artifacts."""

    has_page = request.html_text is not None
    html_text = request.html_text or ""
    raw_bytes = html_text.encode("utf-8")
    diagnostic: dict[str, Any] = {
        "schema_version": PAGE_DIAGNOSTIC_SCHEMA_VERSION,
        "provider": normalize_text(request.provider).lower(),
        "route": normalize_text(request.route).lower(),
        "failure_code": normalize_text(request.failure_code).lower(),
        "stage": normalize_text(request.stage).lower(),
        "backend": normalize_text(request.backend).lower() or None,
        "attempt": max(1, int(request.attempt)),
        "target": diagnostic_url_payload(str(request.target_url or "")),
        "final": diagnostic_url_payload(str(request.final_url or "")),
        "response_status": request.response_status,
        "title_summary": _redact_page_text(str(request.title or ""))[:500] or None,
        "page_summary": _redact_page_text(str(request.summary or ""))[:1000] or None,
        "page": {
            **_selected_page_details(request.details),
            "html_shape": page_shape_diagnostics(html_text) if has_page else None,
        },
        "raw_html": (
            {
                "byte_count": len(raw_bytes),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            }
            if has_page
            else None
        ),
        "sanitized_html": None,
    }
    store = context.artifact_store
    if store is None or not store.allows_auxiliary_artifacts:
        return diagnostic
    root = store.download_dir
    if root is None:
        return diagnostic
    directory = (
        root
        / "diagnostics"
        / sanitize_filename(normalize_text(request.provider).lower() or "provider")
        / _page_identity(request.doi, request.target_url)
        / (
            f"{sanitize_filename(normalize_text(request.route).lower() or 'html')}-"
            f"{max(1, int(request.attempt))}"
        )
    )
    sanitized_path = None
    if has_page:
        sanitized, truncated = sanitize_page_html(html_text)
        sanitized_path = store.write_text_file(
            directory / "page-sanitized.html",
            sanitized,
            encoding="utf-8",
            overwrite=True,
        )
        sanitized_bytes = sanitized.encode("utf-8")
        diagnostic["sanitized_html"] = {
            "path": str(sanitized_path),
            "byte_count": len(sanitized_bytes),
            "sha256": hashlib.sha256(sanitized_bytes).hexdigest(),
            "truncated": truncated,
        }
    diagnostic_path = directory / "diagnostic.json"
    diagnostic["diagnostic_path"] = str(diagnostic_path)
    store.write_json_file(diagnostic_path, diagnostic, overwrite=True)
    artifact_records = [
        {
            "path": str(diagnostic_path),
            "kind": "diagnostic",
            "route": diagnostic["route"],
            "failure_code": diagnostic["failure_code"],
        },
    ]
    if sanitized_path is not None:
        artifact_records.append(
            {
                "path": str(sanitized_path),
                "kind": "diagnostic",
                "route": diagnostic["route"],
                "failure_code": diagnostic["failure_code"],
            }
        )
    for record in artifact_records:
        if record not in context.diagnostic_artifacts:
            context.diagnostic_artifacts.append(record)
    return diagnostic


__all__ = [
    "EMPTY_ARTICLE_SHELL_MAX_BYTES",
    "PAGE_DIAGNOSTIC_SCHEMA_VERSION",
    "SANITIZED_HTML_MAX_BYTES",
    "PageDiagnosticRequest",
    "capture_page_diagnostic",
    "is_empty_article_shell",
    "page_shape_diagnostics",
    "sanitize_page_html",
]
