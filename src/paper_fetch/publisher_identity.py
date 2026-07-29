"""Shared DOI and publisher identity helpers for the skill runtime."""

from __future__ import annotations

import html
import importlib
import functools
import re
import urllib.parse
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any
from collections.abc import Mapping

from rapidfuzz.fuzz import ratio

from .normalize_journal_name import normalize_journal_name
from .utils import normalize_text
from .provider_catalog import (
    doi_prefix_provider_map,
    ordered_provider_specs,
    provider_domain_matches,
    provider_html_path_templates,
    provider_landing_path_templates,
    provider_pdf_path_templates,
    provider_xml_path_templates,
)

PUBLISHER_PROVIDER_MAP: dict[str, str] | None = None
DOI_PREFIX_PROVIDER_MAP: dict[str, str] | None = None
URL_DOI_ROUTE_SUFFIXES_BY_PROVIDER: dict[str, frozenset[str]] = {}
URL_DOI_EXTENSION_SUFFIXES_BY_PROVIDER: dict[str, frozenset[str]] = {}
DOI_CORE_PATTERN = r"10\.\d{4,9}/[^\s\"'<>]+"
ASCII_DOI_CORE_PATTERN = r"10\.\d{4,9}/[!-~]+"
DOI_PATTERN = re.compile(DOI_CORE_PATTERN, flags=re.IGNORECASE)
SICI_DOI_PATTERN = re.compile(
    r"10\.\d{4,9}/"
    r"[^\s\"'<>]+"
    r"<[^>\s\"']+>"
    r"\d+\.\d+\.co;[^\s\"'<>]+",
    flags=re.IGNORECASE,
)
DOI_DASH_TRANSLATION = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        "﹣": "-",
        "－": "-",
    }
)
URL_DOI_ROUTE_SUFFIX_OVERRIDES: dict[str, frozenset[str]] = {
    "frontiers": frozenset({"epub"}),
}
URL_DOI_TEMPLATE_MARKERS = ("{doi}", "{doi_quoted}")
_ARXIV_ID_PATTERN = re.compile(
    r"(?:arxiv[.:/])?(?P<id>\d{4}\.\d{4,5})(?P<version>v\d+)?",
    flags=re.IGNORECASE,
)


@functools.lru_cache(maxsize=1)
def _idutils_module():
    try:
        return importlib.import_module("idutils")
    except ImportError:  # pragma: no cover - exercised by degraded installs
        return None


def _clean_doi_value(doi: str) -> str:
    value = (
        unicodedata.normalize("NFKC", doi)
        .strip()
        .lower()
        .translate(DOI_DASH_TRANSLATION)
    )
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    value = urllib.parse.unquote(value)
    value = re.sub(r"\s+", "", value)
    return value.rstrip(").,;")


def _idutils_normalized_doi(value: str) -> str:
    if not value:
        return ""
    idutils = _idutils_module()
    if idutils is None:
        return ""
    try:
        if not idutils.is_doi(value):
            return ""
        normalized = idutils.normalize_doi(value)
    except Exception:
        return ""
    return _clean_doi_value(str(normalized or ""))


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = _clean_doi_value(doi)
    return _idutils_normalized_doi(value) or value


def extract_doi(text: str | None) -> str | None:
    if not text:
        return None
    searchable_text = urllib.parse.unquote(html.unescape(text))
    match = SICI_DOI_PATTERN.search(searchable_text)
    if match:
        return normalize_doi(match.group(0).rstrip(").,;"))
    match = DOI_PATTERN.search(searchable_text)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(").,;"))


def _path_text_from_parsed_url(parsed: urllib.parse.ParseResult) -> str:
    path = parsed.path
    if parsed.params:
        path = f"{path};{parsed.params}"
    return urllib.parse.unquote(html.unescape(path))


def _tail_after_doi_template_marker(template: str) -> str:
    for marker in URL_DOI_TEMPLATE_MARKERS:
        if marker in template:
            return template.split(marker, 1)[1]
    return ""


def _url_doi_route_suffixes_from_template(template: str) -> frozenset[str]:
    tail = _tail_after_doi_template_marker(template)
    if not tail.startswith("/"):
        return frozenset()
    suffix = (
        tail.lstrip("/")
        .split("/", 1)[0]
        .split("?", 1)[0]
        .split("#", 1)[0]
        .strip()
        .lower()
    )
    if not suffix or "{" in suffix or "}" in suffix:
        return frozenset()
    return frozenset({suffix})


def _url_doi_extension_suffixes_from_template(template: str) -> frozenset[str]:
    tail = _tail_after_doi_template_marker(template)
    if not tail.startswith("."):
        return frozenset()
    extension = tail.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip().lower()
    if not extension or "{" in extension or "}" in extension:
        return frozenset()
    return frozenset({extension})


def _provider_url_doi_templates(provider: str | None) -> tuple[str, ...]:
    if not provider:
        return ()
    return (
        *provider_html_path_templates(provider),
        *provider_landing_path_templates(provider),
        *provider_xml_path_templates(provider),
        *provider_pdf_path_templates(provider),
    )


def _provider_url_doi_route_suffixes(provider: str | None) -> frozenset[str]:
    normalized_provider = str(provider or "").strip().lower()
    if not normalized_provider:
        return frozenset()
    cached = URL_DOI_ROUTE_SUFFIXES_BY_PROVIDER.get(normalized_provider)
    if cached is not None:
        return cached
    suffixes: set[str] = set(
        URL_DOI_ROUTE_SUFFIX_OVERRIDES.get(normalized_provider, frozenset())
    )
    for template in _provider_url_doi_templates(normalized_provider):
        suffixes.update(_url_doi_route_suffixes_from_template(template))
    result = frozenset(suffixes)
    URL_DOI_ROUTE_SUFFIXES_BY_PROVIDER[normalized_provider] = result
    return result


def _provider_url_doi_extension_suffixes(provider: str | None) -> frozenset[str]:
    normalized_provider = str(provider or "").strip().lower()
    if not normalized_provider:
        return frozenset()
    cached = URL_DOI_EXTENSION_SUFFIXES_BY_PROVIDER.get(normalized_provider)
    if cached is not None:
        return cached
    suffixes: set[str] = set()
    for template in _provider_url_doi_templates(normalized_provider):
        suffixes.update(_url_doi_extension_suffixes_from_template(template))
    result = frozenset(suffixes)
    URL_DOI_EXTENSION_SUFFIXES_BY_PROVIDER[normalized_provider] = result
    return result


def _strip_url_doi_route_suffixes(doi: str, provider: str | None) -> str:
    value = normalize_doi(doi)
    if not value:
        return ""
    route_suffixes = _provider_url_doi_route_suffixes(provider)
    if route_suffixes:
        candidate = value.rstrip("/")
        head, separator, tail = candidate.rpartition("/")
        if separator and tail.lower() in route_suffixes:
            value = head
    for extension in sorted(
        _provider_url_doi_extension_suffixes(provider), key=len, reverse=True
    ):
        if value.lower().endswith(extension):
            value = value[: -len(extension)]
            break
    return normalize_doi(value)


def extract_doi_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return extract_doi(url)
    provider = infer_provider_from_url(url)
    for _, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False):
        query_doi = extract_doi(value)
        if query_doi:
            return _strip_url_doi_route_suffixes(query_doi, provider) or query_doi
    path_doi = extract_doi(_path_text_from_parsed_url(parsed))
    if path_doi:
        return _strip_url_doi_route_suffixes(path_doi, provider) or path_doi
    return None


def infer_provider_from_doi(doi: str | None) -> str | None:
    normalized = normalize_doi(doi)
    global DOI_PREFIX_PROVIDER_MAP
    if DOI_PREFIX_PROVIDER_MAP is None:
        DOI_PREFIX_PROVIDER_MAP = doi_prefix_provider_map()
    for prefix, provider in DOI_PREFIX_PROVIDER_MAP.items():
        if normalized.startswith(prefix):
            return provider
    return None


def infer_provider_from_publisher(publisher: str | None) -> str | None:
    if not publisher:
        return None
    normalized = normalize_journal_name(publisher)
    global PUBLISHER_PROVIDER_MAP
    if PUBLISHER_PROVIDER_MAP is None:
        PUBLISHER_PROVIDER_MAP = {
            normalize_journal_name(alias): spec.name
            for spec in ordered_provider_specs()
            for alias in spec.publisher_aliases
        }
    return PUBLISHER_PROVIDER_MAP.get(normalized)


def infer_provider_from_url(url: str | None) -> str | None:
    if not url:
        return None
    hostname = (urllib.parse.urlparse(url).hostname or "").lower()
    for spec in ordered_provider_specs():
        if provider_domain_matches(spec.name, hostname):
            return spec.name
    return None


def ordered_provider_candidates(
    *,
    landing_urls: list[str | None] | None = None,
    publishers: list[str | None] | None = None,
    doi: str | None = None,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    for url in landing_urls or []:
        provider = infer_provider_from_url(url)
        if provider and provider not in seen:
            seen.add(provider)
            candidates.append((provider, "domain"))

    for publisher in publishers or []:
        provider = infer_provider_from_publisher(publisher)
        if provider and provider not in seen:
            seen.add(provider)
            candidates.append((provider, "publisher"))

    provider = infer_provider_from_doi(doi)
    if provider and provider not in seen:
        candidates.append((provider, "doi"))
    return candidates


def infer_provider_from_signals(
    *,
    landing_urls: list[str | None] | None = None,
    publishers: list[str | None] | None = None,
    doi: str | None = None,
) -> str | None:
    candidates = ordered_provider_candidates(
        landing_urls=landing_urls,
        publishers=publishers,
        doi=doi,
    )
    return candidates[0][0] if candidates else None


@dataclass(frozen=True)
class IdentityValidationResult:
    status: str
    method: str
    confidence: str
    expected_doi: str | None = None
    observed_doi: str | None = None
    expected_arxiv_id: str | None = None
    observed_arxiv_id: str | None = None
    title_score: float | None = None
    reason: str | None = None

    @property
    def mismatch(self) -> bool:
        return self.status == "mismatch"

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value for key, value in asdict(self).items() if value not in (None, "")
        }


def _arxiv_identity(value: str | None) -> tuple[str, str | None]:
    normalized = normalize_doi(value)
    candidate = normalized
    if candidate.startswith("10.48550/arxiv."):
        candidate = candidate.removeprefix("10.48550/arxiv.")
    match = _ARXIV_ID_PATTERN.search(candidate)
    if not match:
        return "", None
    return match.group("id").lower(), (
        match.group("version").lower() if match.group("version") else None
    )


def _identity_value(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def validate_extracted_identity(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None = None,
) -> IdentityValidationResult:
    """Compare independent response identity before related assets are fetched."""

    observed_mapping = dict(observed or {})
    evidence_mapping = dict(evidence or {})
    expected_doi = normalize_doi(_identity_value(expected, "doi")) or None
    observed_doi = (
        normalize_doi(
            _identity_value(evidence_mapping, "doi", "response_doi")
            or _identity_value(observed_mapping, "response_doi")
        )
        or None
    )

    expected_arxiv, expected_version = _arxiv_identity(
        _identity_value(expected, "arxiv_id", "doi")
    )
    observed_arxiv, observed_version = _arxiv_identity(
        _identity_value(evidence_mapping, "arxiv_id", "doi")
        or _identity_value(observed_mapping, "response_arxiv_id")
    )
    if expected_arxiv and observed_arxiv:
        if expected_arxiv != observed_arxiv or (
            expected_version
            and observed_version
            and expected_version != observed_version
        ):
            return IdentityValidationResult(
                status="mismatch",
                method="arxiv_id",
                confidence="high",
                expected_doi=expected_doi,
                observed_doi=observed_doi,
                expected_arxiv_id=expected_arxiv + (expected_version or ""),
                observed_arxiv_id=observed_arxiv + (observed_version or ""),
                reason="The response arXiv identifier does not match the request.",
            )
        return IdentityValidationResult(
            status="match",
            method="arxiv_id",
            confidence="high",
            expected_doi=expected_doi,
            observed_doi=observed_doi,
            expected_arxiv_id=expected_arxiv + (expected_version or ""),
            observed_arxiv_id=observed_arxiv + (observed_version or ""),
        )

    if expected_doi and observed_doi:
        if expected_doi != observed_doi:
            return IdentityValidationResult(
                status="mismatch",
                method="doi",
                confidence="high",
                expected_doi=expected_doi,
                observed_doi=observed_doi,
                reason="The response DOI does not match the requested DOI.",
            )
        return IdentityValidationResult(
            status="match",
            method="doi",
            confidence="high",
            expected_doi=expected_doi,
            observed_doi=observed_doi,
        )

    expected_title = normalize_text(_identity_value(expected, "title"))
    observed_title = normalize_text(
        _identity_value(evidence_mapping, "title")
        or _identity_value(observed_mapping, "response_title")
    )
    if expected_title and observed_title:
        title_score = round(
            ratio(expected_title.casefold(), observed_title.casefold()), 2
        )
        return IdentityValidationResult(
            status="match" if title_score >= 92.0 else "insufficient",
            method="title",
            confidence="medium" if title_score >= 92.0 else "low",
            expected_doi=expected_doi,
            observed_doi=observed_doi,
            title_score=title_score,
            reason=(
                None
                if title_score >= 92.0
                else "Response title evidence is not strong enough to prove identity."
            ),
        )

    return IdentityValidationResult(
        status="insufficient",
        method="none",
        confidence="none",
        expected_doi=expected_doi,
        observed_doi=observed_doi,
        reason="The response did not expose an independent identity signal.",
    )
