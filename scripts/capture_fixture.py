#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
from datetime import datetime, UTC
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SRC_PATH = REPO_ROOT / "src"
if SRC_PATH.is_dir() and str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _structured_errors import ToolError, emit_error, error_payload  # noqa: E402
from paper_fetch.config import build_publisher_user_agent  # noqa: E402
from paper_fetch.extraction.html.parsing import choose_parser  # noqa: E402
from paper_fetch.extraction.html.signals import (
    CHALLENGE_PATTERNS,
    contains_access_gate_text,
    summarize_html,
)  # noqa: E402
from paper_fetch.http import (  # noqa: E402
    HttpTransport,
    RequestFailure,
    build_network_error_detail,
    classify_network_error,
)  # noqa: E402
from paper_fetch.publisher_identity import infer_provider_from_doi, normalize_doi  # noqa: E402
from paper_fetch.utils import normalize_text  # noqa: E402

from bs4 import BeautifulSoup  # noqa: E402


HTTP_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MAX_HTTP_CAPTURE_REDIRECTS = 8
GOLDEN_PURPOSES = {
    "structure",
    "table",
    "formula",
    "figure",
    "supplementary",
    "references",
    "pdf_fallback",
}
BLOCK_PURPOSES = {"abstract_only", "access_gate", "empty_shell"}
PURPOSES = sorted(GOLDEN_PURPOSES | BLOCK_PURPOSES)
PURPOSE_ALIASES = {
    "abstract-only": "abstract_only",
    "access-gate": "access_gate",
    "empty-shell": "empty_shell",
    "pdf-fallback": "pdf_fallback",
}
CLI_PURPOSES = sorted(set(PURPOSES) | set(PURPOSE_ALIASES))
RETRY_VIA_ERROR_CODES = {"HTTP_FORBIDDEN", "HTTP_RATE_LIMITED", "CHALLENGE_DETECTED"}
ACCESS_REVIEW_DIR = REPO_ROOT / "onboarding" / "access-reviews"
FULLTEXT_CONTAINER_SELECTORS = (
    "#itemFullTextId",
    "#html_fulltext",
    ".articleSection",
    "article",
    "main",
)
MIN_FULLTEXT_CONTAINER_TEXT_CHARS = 1200


class CaptureArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_error(
            error_payload(
                "UNSUITABLE_DOI_SAMPLE",
                message,
                provider=None,
                manifest=None,
                task_id="capture-fixtures-parse-args",
                retryable=False,
                details={"reason": message},
            )
        )
        raise SystemExit(2)


class ManifestContext:
    def __init__(
        self,
        *,
        path: Path,
        data: dict[str, Any],
        provider: str | None,
        routing: dict[str, Any],
        sample: dict[str, Any] | None,
        sample_path: str | None = None,
    ) -> None:
        self.path = path
        self.data = data
        self.provider = provider
        self.routing = routing
        self.sample = sample
        self.sample_path = sample_path


class CaptureFixtureError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        route: str | None = None,
        previous_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.route = route
        self.previous_code = previous_code

    def to_payload(
        self,
        *,
        provider: str | None = None,
        manifest: str | None = None,
        purpose: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {}
        extras: dict[str, Any] = {}
        if provider:
            extras["provider"] = provider
        if manifest:
            extras["manifest"] = manifest
        if purpose:
            details["purpose"] = purpose
            extras["purpose"] = purpose
        if self.status_code is not None:
            details["status_code"] = self.status_code
            extras["status_code"] = self.status_code
        if self.route:
            details["route"] = self.route
            extras["route"] = self.route
        if self.previous_code:
            details["previous_code"] = self.previous_code
            extras["previous_code"] = self.previous_code
        return error_payload(
            self.code,
            self.message,
            provider=provider,
            manifest=manifest,
            task_id=task_id,
            retryable=self.retryable,
            details=details,
            extras=extras,
        )


def _repo_root() -> Path:
    return REPO_ROOT


def doi_slug(doi: str) -> str:
    return normalize_doi(doi).replace("/", "_")


def normalize_purpose(value: str) -> str:
    return PURPOSE_ALIASES.get(value, value)


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"samples": {}}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest root must be an object: {path}")
    samples = manifest.setdefault("samples", {})
    if not isinstance(samples, dict):
        raise ValueError(f"manifest samples must be an object: {path}")
    return manifest


def _load_provider_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ToolError(
            "MANIFEST_NOT_FOUND",
            "Provider manifest was not found.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="capture-fixtures-validate-manifest",
            details={"path": path.as_posix()},
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest YAML is invalid.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="capture-fixtures-validate-manifest",
            details={"reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest root must be an object.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="capture-fixtures-validate-manifest",
            details={"path": path.as_posix()},
        )
    return data


def _manifest_context(
    path_value: str | None, purpose: str | None
) -> ManifestContext | None:
    if not path_value:
        return None
    path = Path(path_value)
    data = _load_provider_manifest(path)
    fixtures = data.get("fixtures") if isinstance(data.get("fixtures"), dict) else {}
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    sample = doi_samples.get(purpose) if purpose else None
    if purpose and sample is not None and not isinstance(sample, dict):
        raise CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            f"fixtures.doi_samples.{purpose} must be an object",
            retryable=False,
        )
    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
    provider = data.get("name")
    return ManifestContext(
        path=path,
        data=data,
        provider=str(provider) if provider else None,
        routing=dict(routing),
        sample=sample if isinstance(sample, dict) else None,
        sample_path=f"fixtures.doi_samples.{purpose}" if purpose else None,
    )


def _manifest_context_for_sample(
    *,
    path: Path,
    data: dict[str, Any],
    sample: dict[str, Any],
    sample_path: str,
) -> ManifestContext:
    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
    provider = data.get("name")
    return ManifestContext(
        path=path,
        data=data,
        provider=str(provider) if provider else None,
        routing=dict(routing),
        sample=sample,
        sample_path=sample_path,
    )


def _load_access_review(provider: str | None) -> dict[str, Any] | None:
    if not provider:
        return None
    path = ACCESS_REVIEW_DIR / f"{provider}.yml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _allowed_runtimes(manifest: ManifestContext | None) -> set[str]:
    review = _load_access_review(manifest.provider if manifest else None)
    runtimes = review.get("allowed_runtimes") if isinstance(review, dict) else None
    if isinstance(runtimes, list):
        return {str(value) for value in runtimes}
    return set()


def _probe_requires_browser(manifest: ManifestContext | None) -> bool:
    if manifest is None:
        return False
    probe = (
        manifest.data.get("probe")
        if isinstance(manifest.data.get("probe"), dict)
        else {}
    )
    return bool(
        probe.get("requires_browser_runtime") or probe.get("requires_playwright")
    )


def _sample_prefers_browser_pdf_fallback(
    manifest: ManifestContext | None, purpose: str | None
) -> bool:
    if (
        purpose != "pdf_fallback"
        or manifest is None
        or not isinstance(manifest.sample, dict)
    ):
        return False
    observed_signals = {
        normalize_text(str(signal)).lower()
        for signal in manifest.sample.get("observed_signals") or []
    }
    if observed_signals & {"browser_pdf", "browser_public_pdf", "browser_pdf_fallback"}:
        return True
    return "http_403" in observed_signals and "pdf_link" in observed_signals


def _select_capture_route(
    args: argparse.Namespace,
    *,
    manifest: ManifestContext | None,
    purpose: str | None = None,
) -> str:
    if not getattr(args, "auto_via", False):
        return str(args.via)
    allowed = _allowed_runtimes(manifest)
    requires_browser = _probe_requires_browser(manifest)
    if requires_browser:
        if "browser" in allowed:
            return "browser"
        raise CaptureFixtureError(
            "BROWSER_RUNTIME_REQUIRED",
            "manifest probe requires browser capture, but access review does not allow browser runtime",
            retryable=False,
            route="browser",
        )
    if _sample_prefers_browser_pdf_fallback(manifest, purpose) and "browser" in allowed:
        return "browser"
    if allowed and "http" not in allowed and "browser" in allowed:
        return "browser"
    return "http"


def _auto_retry_via(
    args: argparse.Namespace,
    *,
    manifest: ManifestContext | None,
    selected_route: str,
) -> str | None:
    retry_via = getattr(args, "retry_via", None)
    if retry_via:
        return str(retry_via)
    if not getattr(args, "auto_via", False) or selected_route != "http":
        return None
    if "browser" in _allowed_runtimes(manifest):
        return "browser"
    return None


def _iter_manifest_capture_contexts(path_value: str) -> list[ManifestContext]:
    path = Path(path_value)
    data = _load_provider_manifest(path)
    fixtures = data.get("fixtures") if isinstance(data.get("fixtures"), dict) else {}
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    contexts: list[ManifestContext] = []
    for purpose in PURPOSES:
        sample = doi_samples.get(purpose)
        if sample is None:
            continue
        if not isinstance(sample, dict):
            raise CaptureFixtureError(
                "UNSUITABLE_DOI_SAMPLE",
                f"fixtures.doi_samples.{purpose} must be an object",
                retryable=False,
            )
        contexts.append(
            _manifest_context_for_sample(
                path=path,
                data=data,
                sample=sample,
                sample_path=f"fixtures.doi_samples.{purpose}",
            )
        )
    extra_fixtures = data.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict):
                raise CaptureFixtureError(
                    "UNSUITABLE_DOI_SAMPLE",
                    f"extra_fixtures[{index}] must be an object",
                    retryable=False,
                )
            contexts.append(
                _manifest_context_for_sample(
                    path=path,
                    data=data,
                    sample=sample,
                    sample_path=f"extra_fixtures[{index}]",
                )
            )
    return contexts


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def _content_type(response: dict[str, Any]) -> str:
    headers = (
        response.get("headers") if isinstance(response.get("headers"), dict) else {}
    )
    return str(
        headers.get("content-type") or headers.get("Content-Type") or "text/html"
    )


def _header_value(headers: dict[str, Any] | None, key: str) -> str:
    if not headers:
        return ""
    target = key.lower()
    for header_key, value in headers.items():
        if str(header_key).lower() == target:
            return str(value or "")
    return ""


def _response_url(response: dict[str, Any], request_url: str) -> str:
    raw_url = str(response.get("url") or "").strip()
    return urljoin(request_url, raw_url) if raw_url else request_url


def _body_bytes(response: dict[str, Any]) -> bytes:
    body = response.get("body", b"")
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    raise TypeError("HttpTransport response body must be bytes or str")


def _extension_for(content_type: str, purpose: str) -> str:
    normalized = content_type.lower()
    if purpose == "pdf_fallback" or "application/pdf" in normalized:
        return "pdf"
    if "xml" in normalized:
        return "xml"
    return "html"


def _fixture_family(purpose: str) -> str:
    return "block" if purpose in BLOCK_PURPOSES else "golden"


def _fixture_path(root: Path, slug: str, purpose: str, content_type: str) -> Path:
    family = _fixture_family(purpose)
    if family == "block":
        return root / "tests" / "fixtures" / "block" / slug / "original.html"
    filename = f"original.{_extension_for(content_type, purpose)}"
    return root / "tests" / "fixtures" / "golden_criteria" / slug / filename


def _fixture_path_from_entry(
    root: Path,
    entry: dict[str, Any],
    *,
    purpose: str | None = None,
    content_type: str | None = None,
) -> Path | None:
    assets = entry.get("assets") if isinstance(entry.get("assets"), dict) else {}
    if purpose is not None and content_type is not None:
        expected_name = f"original.{_extension_for(content_type, purpose)}"
        value = assets.get(expected_name)
        if isinstance(value, str) and value:
            path = root / value
            if path.exists():
                return path
    for name in (
        "original.pdf",
        "original.xml",
        "original.html",
        "raw.html",
        "article.html",
    ):
        value = assets.get(name)
        if isinstance(value, str) and value:
            path = root / value
            if path.exists():
                return path
    for value in assets.values():
        if isinstance(value, str) and value:
            path = root / value
            if path.exists():
                return path
    return None


def _entry_matches_capture_plan(
    entry: dict[str, Any], *, purpose: str, content_type: str
) -> bool:
    route_kind = normalize_text(str(entry.get("route_kind") or "")).lower()
    entry_content_type = normalize_text(str(entry.get("content_type") or "")).lower()
    expected_extension = _extension_for(content_type, purpose)
    if purpose == "pdf_fallback":
        return route_kind == "pdf_fallback" and (
            "application/pdf" in entry_content_type or expected_extension == "pdf"
        )
    if route_kind == "pdf_fallback":
        return False
    if expected_extension == "xml":
        return route_kind in {"xml", "jats_xml"} or "xml" in entry_content_type
    return route_kind in {"", "html"} and "pdf" not in entry_content_type


def _planned_content_type_from_manifest(
    purpose: str, sample: dict[str, Any] | None
) -> str:
    if purpose == "pdf_fallback":
        return "application/pdf"
    if not sample:
        return "text/html"
    evidence_url = normalize_text(str(sample.get("evidence_url") or "")).lower()
    observed_signals = {
        normalize_text(str(signal)).lower()
        for signal in sample.get("observed_signals") or []
    }
    if (
        "jats_xml" in observed_signals
        or "xml_body_sections" in observed_signals
        or "type=manuscript" in evidence_url
        or evidence_url.endswith(".xml")
    ):
        return "application/xml"
    if "pdf_fallback" in observed_signals or "type=printable" in evidence_url:
        return "application/pdf"
    return "text/html"


def _manifest_entry(
    *,
    doi: str,
    provider: str,
    source_url: str,
    fetched_at: str,
    purpose: str,
    fixture_path: Path,
    root: Path,
    content_type: str,
) -> dict[str, Any]:
    family = _fixture_family(purpose)
    route_kind = (
        "pdf_fallback"
        if purpose == "pdf_fallback"
        else ("block" if family == "block" else _extension_for(content_type, purpose))
    )
    asset_name = fixture_path.name
    return {
        "doi": doi,
        "publisher": provider,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "purpose": purpose,
        "expected_outcome": "pending",
        "fixture_family": family,
        "content_type": content_type,
        "route_kind": route_kind,
        "origin_kind": "real_replay",
        "usage_kind": "content",
        "assets": {
            asset_name: fixture_path.relative_to(root).as_posix(),
        },
    }


def _redact_transient_url(url: str) -> str:
    parts = urlsplit(url)
    if "token=" not in parts.query.lower():
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _capture_http(url: str) -> dict[str, Any]:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
        "User-Agent": build_publisher_user_agent({}),
    }
    transport = HttpTransport()
    current_url = url
    for redirect_count in range(MAX_HTTP_CAPTURE_REDIRECTS + 1):
        response = transport.request(
            "GET",
            current_url,
            headers=headers,
            retry_on_transient=True,
        )
        response["url"] = _response_url(response, current_url)
        status_code = int(response.get("status_code") or 200)
        location = _header_value(
            response.get("headers")
            if isinstance(response.get("headers"), dict)
            else {},
            "location",
        )
        if status_code in HTTP_REDIRECT_STATUS_CODES and location:
            if redirect_count >= MAX_HTTP_CAPTURE_REDIRECTS:
                raise RequestFailure(
                    status_code,
                    f"Exceeded HTTP redirect limit while capturing fixture for {url}",
                    headers=response.get("headers")
                    if isinstance(response.get("headers"), dict)
                    else {},
                    url=response["url"],
                )
            current_url = urljoin(response["url"], location)
            continue
        return response
    raise RequestFailure(
        None,
        f"Exceeded HTTP redirect limit while capturing fixture for {url}",
        url=current_url,
    )


def _is_pdf_response(content_type: str, body: bytes) -> bool:
    return "application/pdf" in content_type.lower() or body.lstrip().startswith(
        b"%PDF"
    )


def _is_html_response(content_type: str, body: bytes) -> bool:
    return (
        "html" in content_type.lower()
        or body.lstrip().lower().startswith(b"<!doctype html")
        or b"<html" in body[:512].lower()
    )


def _decode_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _contains_challenge(text: str) -> bool:
    lowered = text.lower()
    return (
        any(pattern in lowered for pattern in CHALLENGE_PATTERNS)
        or "captcha" in lowered
    )


def _looks_empty_article_shell(content_type: str, body: bytes) -> bool:
    if not _is_html_response(content_type, body):
        return False
    if not body.strip():
        return True
    html = _decode_body(body)
    text = summarize_html(html, limit=200).strip()
    return not text and "<html" in html.lower()


def _has_populated_fulltext_container(html: str) -> bool:
    try:
        soup = BeautifulSoup(html, choose_parser())
    except Exception:
        return False
    for selector in FULLTEXT_CONTAINER_SELECTORS:
        for node in soup.select(selector):
            if (
                len(normalize_text(node.get_text(" ", strip=True)))
                >= MIN_FULLTEXT_CONTAINER_TEXT_CHARS
            ):
                return True
    return False


def _validate_capture_response(
    *,
    response: dict[str, Any],
    purpose: str,
    route: str,
) -> tuple[str, bytes, str]:
    content_type = _content_type(response)
    body = _body_bytes(response)
    final_url = str(response.get("url") or "")
    status_code = int(response.get("status_code") or 200)
    body_text = _decode_body(body) if _is_html_response(content_type, body) else ""

    if status_code == 403:
        raise CaptureFixtureError(
            "HTTP_FORBIDDEN",
            "publisher returned HTTP 403 while capturing fixture",
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if status_code == 429:
        raise CaptureFixtureError(
            "HTTP_RATE_LIMITED",
            "publisher returned HTTP 429 while capturing fixture",
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if status_code >= 500:
        raise CaptureFixtureError(
            "NETWORK_TRANSIENT",
            f"publisher returned transient HTTP {status_code} while capturing fixture",
            retryable=True,
            status_code=status_code,
            route=route,
        )
    visible_body_text = summarize_html(body_text, limit=1000) if body_text else ""
    if _is_html_response(content_type, body) and _contains_challenge(visible_body_text):
        raise CaptureFixtureError(
            "CHALLENGE_DETECTED",
            "publisher returned a challenge or CAPTCHA page while capturing fixture",
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if purpose == "pdf_fallback" and not _is_pdf_response(content_type, body):
        raise CaptureFixtureError(
            "NON_PDF_FALLBACK_CONTENT",
            "pdf_fallback sample did not return PDF content",
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if (
        purpose != "access_gate"
        and _is_html_response(content_type, body)
        and contains_access_gate_text(body_text)
        and not _has_populated_fulltext_container(body_text)
    ):
        raise CaptureFixtureError(
            "ACCESS_GATE_CAPTURED",
            "captured HTML is an access gate instead of the requested fixture purpose",
            retryable=False,
            status_code=status_code,
            route=route,
        )
    if purpose != "empty_shell" and _looks_empty_article_shell(content_type, body):
        raise CaptureFixtureError(
            "EMPTY_ARTICLE_SHELL",
            "captured HTML has no article text",
            retryable=False,
            status_code=status_code,
            route=route,
        )
    return content_type, body, final_url


def _map_request_failure(exc: RequestFailure, *, route: str) -> CaptureFixtureError:
    status_code = exc.status_code
    if status_code == 403:
        return CaptureFixtureError(
            "HTTP_FORBIDDEN",
            str(exc),
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if status_code == 429:
        return CaptureFixtureError(
            "HTTP_RATE_LIMITED",
            str(exc),
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if status_code is not None and status_code >= 500:
        return CaptureFixtureError(
            "NETWORK_TRANSIENT",
            str(exc),
            retryable=True,
            status_code=status_code,
            route=route,
        )
    if exc.body:
        content_type = _content_type({"headers": exc.headers})
        body_text = (
            _decode_body(exc.body) if _is_html_response(content_type, exc.body) else ""
        )
        if _contains_challenge(body_text):
            return CaptureFixtureError(
                "CHALLENGE_DETECTED",
                str(exc),
                retryable=True,
                status_code=status_code,
                route=route,
            )
    return CaptureFixtureError(
        "NETWORK_TRANSIENT",
        str(exc),
        retryable=True,
        status_code=status_code,
        route=route,
    )


def _browser_capture_error(
    exc: Exception,
    *,
    route: str,
) -> CaptureFixtureError:
    reason = (
        getattr(exc, "reason", None)
        or getattr(exc, "kind", None)
        or getattr(exc, "code", None)
        or ""
    )
    message = getattr(exc, "message", None) or str(exc)
    normalized_reason = str(reason or "").strip()
    if normalized_reason in {
        "browser_runtime_unavailable",
        "cloakbrowser_launch_failed",
        "missing_browser_runtime",
        "not_configured",
    }:
        return CaptureFixtureError(
            "BROWSER_RUNTIME_REQUIRED",
            message or "browser fixture capture requires a configured browser runtime",
            retryable=False,
            route=route,
        )
    if normalized_reason in {"cloudflare_challenge", "publisher_access_challenge"}:
        return CaptureFixtureError(
            "CHALLENGE_DETECTED",
            message or "publisher returned a challenge page while capturing fixture",
            retryable=True,
            route=route,
        )
    if normalized_reason in {
        "downloaded_file_not_pdf",
        "pdf_download_not_triggered",
    }:
        return CaptureFixtureError(
            "NON_PDF_FALLBACK_CONTENT",
            message or "pdf_fallback sample did not return PDF content",
            retryable=True,
            route=route,
        )
    if normalized_reason in {
        "publisher_not_found",
        "article_container_not_found",
        "empty_html_attempts",
        "empty_html_response",
    }:
        return CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            message or "browser capture could not resolve a usable publisher article",
            retryable=False,
            route=route,
        )
    return CaptureFixtureError(
        "NETWORK_TRANSIENT",
        message or "browser fixture capture failed",
        retryable=True,
        route=route,
    )


def _pdf_seed_url(url: str) -> str | None:
    parsed = urlsplit(url)
    path = parsed.path
    if "/doi/pdf/" in path:
        seed_path = path.replace("/doi/pdf/", "/doi/", 1)
    elif "/doi/epdf/" in path:
        seed_path = path.replace("/doi/epdf/", "/doi/", 1)
    elif path.rstrip("/").endswith("/pdf"):
        seed_path = path.rstrip("/")[: -len("/pdf")]
    else:
        return None
    if not seed_path:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, seed_path, "", ""))


def _capture_browser(
    doi: str,
    *,
    url: str,
    provider: str | None,
    purpose: str,
    root: Path,
    route: str,
) -> dict[str, Any]:
    if purpose == "pdf_fallback":
        from paper_fetch.providers._pdf_fallback import (
            PdfFallbackFailure,
            fetch_pdf_with_browser,
        )

        artifact_dir = (
            root / ".paper-fetch-runs" / "fixture-capture" / doi_slug(doi) / purpose
        )
        seed_url = _pdf_seed_url(url)
        try:
            result = fetch_pdf_with_browser(
                [url],
                artifact_dir=artifact_dir,
                seed_urls=[seed_url] if seed_url else None,
            )
        except PdfFallbackFailure as exc:
            raise _browser_capture_error(exc, route=route) from exc
        return {
            "headers": {"content-type": "application/pdf"},
            "body": result.pdf_bytes,
            "url": result.final_url,
            "status_code": 200,
        }

    from paper_fetch.config import build_browser_user_agent
    from paper_fetch.extraction.html.signals import HtmlExtractionFailure
    from paper_fetch.providers.browser_workflow.html_extraction import (
        fetch_html_with_fast_browser,
    )

    try:
        result = fetch_html_with_fast_browser(
            [url],
            publisher=provider or "unknown",
            user_agent=build_browser_user_agent({}),
        )
    except HtmlExtractionFailure as exc:
        raise _browser_capture_error(exc, route=route) from exc
    except Exception as exc:
        raise _browser_capture_error(exc, route=route) from exc
    headers = {
        str(key).lower(): str(value)
        for key, value in (result.response_headers or {}).items()
    }
    headers.setdefault("content-type", "text/html")
    return {
        "headers": headers,
        "body": result.html.encode("utf-8"),
        "url": result.final_url or url,
        "status_code": result.response_status or 200,
    }


def _capture_route(
    doi: str,
    *,
    route: str,
    source_url: str,
    provider: str | None,
    purpose: str,
    root: Path,
) -> dict[str, Any]:
    if route == "http":
        try:
            return _capture_http(source_url)
        except RequestFailure as exc:
            raise _map_request_failure(exc, route=route) from exc
        except Exception as exc:
            category = classify_network_error(exc)
            detail = build_network_error_detail(exc)
            message = f"network transient during fixture capture: {category.value}"
            if detail:
                message = f"{message}: {detail}"
            raise CaptureFixtureError(
                "NETWORK_TRANSIENT",
                message,
                retryable=True,
                route=route,
            ) from exc
    if route in {"playwright", "browser"}:
        return _capture_browser(
            doi,
            url=source_url,
            provider=provider,
            purpose=purpose,
            root=root,
            route=route,
        )
    raise CaptureFixtureError(
        "UNSUITABLE_DOI_SAMPLE",
        f"unsupported fixture capture route: {route}",
        retryable=False,
        route=route,
    )


def _should_retry_via(
    error: CaptureFixtureError,
    *,
    retry_via: str | None,
    manifest: ManifestContext | None,
) -> bool:
    if retry_via != "browser":
        return False
    return error.code in RETRY_VIA_ERROR_CODES


def _manifest_evidence(sample: dict[str, Any] | None) -> dict[str, Any]:
    if not sample:
        return {}
    return {
        "evidence_url": sample.get("evidence_url"),
        "evidence_reason": sample.get("evidence_reason"),
        "observed_signals": sample.get("observed_signals", []),
        "confidence": sample.get("confidence"),
    }


def _manifest_evidence_url(sample: dict[str, Any] | None) -> str:
    if not sample:
        return ""
    return normalize_text(str(sample.get("evidence_url") or ""))


def capture_fixture(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_dir).resolve()
    purpose = normalize_purpose(args.purpose)
    manifest = getattr(args, "_manifest_context", None) or _manifest_context(
        getattr(args, "from_manifest", None), purpose
    )
    if manifest and manifest.sample is None:
        raise CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            f"manifest does not define fixtures.doi_samples.{purpose}",
            retryable=False,
        )
    if manifest and manifest.sample and manifest.sample.get("purpose"):
        purpose = normalize_purpose(str(manifest.sample["purpose"]))
    sample_doi = manifest.sample.get("doi") if manifest and manifest.sample else None
    raw_doi = args.doi or sample_doi
    provider = args.provider or (manifest.provider if manifest else None)
    if raw_doi is None:
        sample_path = (
            manifest.sample_path
            if manifest and manifest.sample_path
            else f"fixtures.doi_samples.{purpose}"
        )
        return {
            "status": "SKIPPED",
            "skipped": True,
            "purpose": purpose,
            "provider": provider,
            "manifest": manifest.path.as_posix() if manifest else None,
            "reason": f"{sample_path}.doi is null",
            "evidence": _manifest_evidence(manifest.sample if manifest else None),
            "evidence_confidence": (manifest.sample or {}).get("confidence")
            if manifest
            else None,
        }
    doi = normalize_doi(str(raw_doi))
    slug = doi_slug(doi)
    provider = provider or infer_provider_from_doi(doi) or "unknown"
    source_url = (
        _manifest_evidence_url(manifest.sample if manifest else None)
        or f"https://doi.org/{doi}"
    )
    manifest_path = root / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    fixture_manifest = _load_manifest(manifest_path)
    samples = fixture_manifest["samples"]
    existing_entry = samples.get(slug) if isinstance(samples.get(slug), dict) else {}
    manifest_planned_content_type = _planned_content_type_from_manifest(
        purpose, manifest.sample if manifest else None
    )
    planned_content_type = (
        manifest_planned_content_type
        if purpose == "pdf_fallback"
        else (
            str(existing_entry.get("content_type") or "")
            or manifest_planned_content_type
        )
    )
    reuse_fixture_path = (
        _fixture_path_from_entry(
            root,
            existing_entry,
            purpose=purpose,
            content_type=planned_content_type,
        )
        if isinstance(existing_entry, dict)
        else None
    ) or _fixture_path(root, slug, purpose, planned_content_type)
    existing_matches_plan = (
        isinstance(existing_entry, dict)
        and bool(existing_entry)
        and _entry_matches_capture_plan(
            existing_entry,
            purpose=purpose,
            content_type=planned_content_type,
        )
    )
    if (
        not args.force
        and not args.dry_run
        and slug in samples
        and reuse_fixture_path.exists()
        and existing_matches_plan
    ):
        summary = {
            "status": "OK",
            "reused": True,
            "doi": doi,
            "dry_run": False,
            "fixture_path": reuse_fixture_path.relative_to(root).as_posix(),
            "manifest_sample_id": slug,
            "manifest_entry": existing_entry,
            "content_type": existing_entry.get("content_type") or planned_content_type,
            "bytes": reuse_fixture_path.stat().st_size,
            "route": existing_entry.get("route_kind")
            or _extension_for(planned_content_type, purpose),
            "capture_route": "reused",
            "route_kind": existing_entry.get("route_kind")
            or _extension_for(planned_content_type, purpose),
            "purpose": purpose,
            "provider": provider,
        }
        if getattr(args, "from_manifest", None):
            provider_manifest = getattr(
                args, "_manifest_context", None
            ) or _manifest_context(getattr(args, "from_manifest", None), purpose)
            summary["manifest"] = str(args.from_manifest)
            summary["manifest_sample"] = _manifest_evidence(
                provider_manifest.sample if provider_manifest else None
            )
            summary["evidence_confidence"] = (
                (provider_manifest.sample or {}).get("confidence")
                if provider_manifest
                else None
            )
            summary["provider_routing"] = (
                provider_manifest.routing if provider_manifest else {}
            )
            summary["manifest_sample_path"] = (
                provider_manifest.sample_path if provider_manifest else None
            )
        return summary
    if (
        not args.force
        and not args.dry_run
        and slug in samples
        and isinstance(existing_entry, dict)
        and existing_entry
        and not existing_matches_plan
    ):
        raise CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            "existing fixture route does not satisfy requested capture purpose: "
            f"{slug} has route_kind={existing_entry.get('route_kind')!r}, "
            f"requested purpose={purpose!r}",
            retryable=False,
        )

    fetched_at = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    if args.dry_run:
        content_type = planned_content_type
        body = b""
        final_url = source_url
        route = _select_capture_route(args, manifest=manifest, purpose=purpose)
    else:
        route = _select_capture_route(args, manifest=manifest, purpose=purpose)
        try:
            response = _capture_route(
                doi,
                route=route,
                source_url=source_url,
                provider=provider,
                purpose=purpose,
                root=root,
            )
            content_type, body, final_url = _validate_capture_response(
                response=response,
                purpose=purpose,
                route=route,
            )
            final_url = final_url or source_url
        except CaptureFixtureError as exc:
            retry_via = _auto_retry_via(args, manifest=manifest, selected_route=route)
            if _should_retry_via(exc, retry_via=retry_via, manifest=manifest):
                route = retry_via
                try:
                    response = _capture_route(
                        doi,
                        route=route,
                        source_url=source_url,
                        provider=provider,
                        purpose=purpose,
                        root=root,
                    )
                    content_type, body, final_url = _validate_capture_response(
                        response=response,
                        purpose=purpose,
                        route=route,
                    )
                    final_url = final_url or source_url
                except CaptureFixtureError as retry_exc:
                    if retry_exc.previous_code is None:
                        retry_exc.previous_code = exc.code
                    raise retry_exc from exc
            else:
                raise

    fixture_path = _fixture_path(root, slug, purpose, content_type)
    exists = fixture_path.exists() or slug in samples
    if exists and not args.force and not args.dry_run:
        raise CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            f"refusing to overwrite existing fixture or manifest sample: {slug}",
            retryable=False,
        )

    manifest_source_url = (
        source_url if purpose == "pdf_fallback" and route == "browser" else final_url
    )
    entry = _manifest_entry(
        doi=doi,
        provider=provider,
        source_url=manifest_source_url,
        fetched_at=fetched_at,
        purpose=purpose,
        fixture_path=fixture_path,
        root=root,
        content_type=content_type,
    )
    if (
        purpose == "pdf_fallback"
        and route == "browser"
        and final_url != manifest_source_url
    ):
        entry["diagnostics"] = {
            "browser_final_url": _redact_transient_url(final_url),
            "browser_final_url_redacted": "token=" in final_url.lower(),
            "capture_source_url": source_url,
        }
    summary = {
        "status": "OK",
        "doi": doi,
        "dry_run": bool(args.dry_run),
        "fixture_path": fixture_path.relative_to(root).as_posix(),
        "manifest_sample_id": slug,
        "manifest_entry": entry,
        "content_type": content_type,
        "bytes": len(body),
        "route": entry["route_kind"],
        "capture_route": route,
        "route_kind": entry["route_kind"],
        "purpose": purpose,
        "provider": provider,
    }
    if final_url != manifest_source_url:
        summary["capture_final_url"] = final_url
    if getattr(args, "from_manifest", None):
        provider_manifest = getattr(
            args, "_manifest_context", None
        ) or _manifest_context(getattr(args, "from_manifest", None), purpose)
        summary["manifest"] = str(args.from_manifest)
        summary["manifest_sample"] = _manifest_evidence(
            provider_manifest.sample if provider_manifest else None
        )
        summary["evidence_confidence"] = (
            (provider_manifest.sample or {}).get("confidence")
            if provider_manifest
            else None
        )
        summary["provider_routing"] = (
            provider_manifest.routing if provider_manifest else {}
        )
        summary["manifest_sample_path"] = (
            provider_manifest.sample_path if provider_manifest else None
        )

    if args.dry_run:
        summary["would_write"] = [
            summary["fixture_path"],
            "tests/fixtures/golden_criteria/manifest.json",
        ]
        summary["would_overwrite"] = bool(exists)
        return summary

    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_bytes(body)
    samples[slug] = entry
    _write_manifest(manifest_path, fixture_manifest)
    return summary


def capture_all_from_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "from_manifest", None):
        raise CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            "--all requires --from-manifest",
            retryable=False,
        )
    contexts = _iter_manifest_capture_contexts(args.from_manifest)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for context in contexts:
        sample = context.sample or {}
        purpose = normalize_purpose(
            str(sample.get("purpose") or (context.sample_path or "").rsplit(".", 1)[-1])
        )
        child_values = vars(args).copy()
        child_values.update(
            {
                "doi": None,
                "provider": None,
                "purpose": purpose,
                "_manifest_context": context,
            }
        )
        child_args = argparse.Namespace(**child_values)
        try:
            results.append(capture_fixture(child_args))
        except CaptureFixtureError as exc:
            if getattr(args, "fail_fast", False):
                raise
            failures.append(
                exc.to_payload(
                    provider=context.provider,
                    manifest=context.path.as_posix(),
                    purpose=purpose,
                    task_id=f"{context.provider}-step3-capture-fixtures"
                    if context.provider
                    else "capture-fixtures",
                )
            )
    status = "OK" if not failures else "FAILED"
    return {
        "status": status,
        "dry_run": bool(args.dry_run),
        "manifest": str(args.from_manifest),
        "target_count": len(contexts),
        "captured_count": sum(1 for result in results if result.get("status") == "OK"),
        "skipped_count": sum(
            1 for result in results if result.get("status") == "SKIPPED"
        ),
        "failure_count": len(failures),
        "results": results,
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = CaptureArgumentParser(
        description="Capture a DOI replay fixture and register it in the golden manifest."
    )
    parser.add_argument("--doi", help="DOI to capture, for example 10.1234/sample")
    parser.add_argument(
        "--provider", help="provider name; defaults to DOI/catalog inference"
    )
    parser.add_argument(
        "--via", choices=("http", "playwright", "browser"), default="http"
    )
    parser.add_argument(
        "--auto-via",
        action="store_true",
        help="choose http or browser capture from manifest probe and access review",
    )
    parser.add_argument("--purpose", choices=CLI_PURPOSES)
    parser.add_argument(
        "--from-manifest",
        help="ProviderManifest YAML input; reads DOI, evidence, and routing by purpose",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="capture every non-null manifest DOI sample and extra fixture",
    )
    parser.add_argument(
        "--retry-via",
        choices=("browser", "playwright"),
        help="retry failed capture through another route",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="emit JSON stderr and exit non-zero on the first failure",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned writes without fetching or writing",
    )
    parser.add_argument(
        "--output-dir",
        default=_repo_root(),
        help="repo root to write into; defaults to this checkout",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing fixture and manifest sample",
    )
    return parser


def _error_context(args: argparse.Namespace) -> dict[str, str | None]:
    purpose = (
        normalize_purpose(args.purpose) if getattr(args, "purpose", None) else None
    )
    provider = args.provider
    if getattr(args, "from_manifest", None):
        try:
            manifest = _manifest_context(args.from_manifest, purpose)
        except Exception:
            manifest = None
        if manifest and manifest.provider:
            provider = provider or manifest.provider
    return {
        "provider": provider,
        "manifest": getattr(args, "from_manifest", None),
        "purpose": purpose,
        "task_id": f"{provider}-step3-capture-fixtures"
        if provider
        else "capture-fixtures",
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.all and not args.from_manifest:
        error = CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            "--all requires --from-manifest",
            retryable=False,
        )
        context = _error_context(args)
        emit_error(error.to_payload(**context))
        return 1
    if not args.all and not args.purpose:
        error = CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            "--purpose is required unless --all is provided",
            retryable=False,
        )
        context = _error_context(args)
        emit_error(error.to_payload(**context))
        return 1
    if not args.all and not args.doi and not args.from_manifest:
        error = CaptureFixtureError(
            "UNSUITABLE_DOI_SAMPLE",
            "--doi is required unless --from-manifest is provided",
            retryable=False,
        )
        context = _error_context(args)
        emit_error(error.to_payload(**context))
        return 1
    try:
        summary = capture_all_from_manifest(args) if args.all else capture_fixture(args)
    except ToolError as exc:
        context = _error_context(args)
        details = dict(exc.details)
        if context.get("purpose"):
            details.setdefault("purpose", context["purpose"])
        emit_error(
            error_payload(
                exc.code,
                exc.message,
                provider=exc.provider or context["provider"],
                manifest=exc.manifest or context["manifest"],
                task_id=exc.task_id or context["task_id"],
                retryable=exc.retryable,
                details=details,
            )
        )
        return 1
    except CaptureFixtureError as exc:
        context = _error_context(args)
        emit_error(exc.to_payload(**context))
        return 1
    except Exception as exc:
        context = _error_context(args)
        error = CaptureFixtureError("UNSUITABLE_DOI_SAMPLE", str(exc), retryable=False)
        emit_error(error.to_payload(**context))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary.get("status") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
