"""IEEE Xplore landing metadata parsing and merging."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import html as html_lib
import json
import re
from typing import Any
from collections.abc import Mapping

from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS
from ..metadata.types import MetadataMergeRule, merge_metadata_layers
from ..models import SourceKind, article_from_markdown, metadata_only_article
from ..publisher_identity import normalize_doi
from ..reason_codes import PDF_FALLBACK
from ..tracing import fulltext_marker, trace_from_markers
from ..utils import dedupe_authors, normalize_text, strip_html_tags
from ._asset_retry import merge_asset_retry_results
from ._html_authors import AuthorExtractionPipeline, AuthorStep
from ._ieee_url import (
    IEEE_REFERENCES_URL_TEMPLATE,
    _article_number_from_metadata,
    _article_number_from_url,
)
from ._reference_doi import reference_doi_match as _reference_doi_match
from ._script_json import extract_assignment_json

IEEE_METADATA_ASSIGNMENT = "xplGlobal.document.metadata"
IEEE_SCRIPT_VALUE_PATTERN_TEMPLATE = r"""["']?{key}["']?\s*:\s*(?P<value>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|true|false|null|\d+)"""
IEEE_REFERENCE_PAGE_SIZE = 30
IEEE_MAX_REFERENCE_PAGES = 20


@dataclass(frozen=True)
class IeeeLandingAttempt:
    normalized_doi: str
    landing_url: str
    response_url: str
    html_text: str
    merged_metadata: dict[str, Any]
    article_number: str
    landing_metadata: dict[str, Any]
    acquisition_source: str = "direct_http"
    browser_context_seed: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = normalize_text(str(value or "")).lower()
    return normalized in {"1", "true", "yes", "y"}


def _landing_metadata_has_multimedia_scope(metadata: Mapping[str, Any] | None) -> bool:
    sections = (metadata or {}).get("sections")
    if isinstance(sections, Mapping) and _boolish(sections.get("multimedia")):
        return True
    return _boolish((metadata or {}).get("hasMultimedia")) or _boolish(
        (metadata or {}).get("multimedia")
    )


def _script_value(text: str, key: str) -> Any:
    pattern = re.compile(
        IEEE_SCRIPT_VALUE_PATTERN_TEMPLATE.format(key=re.escape(key)),
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    value = match.group("value")
    if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
        return value[1:-1].encode("utf-8").decode("unicode_escape", errors="replace")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "null":
        return None
    return value


def _first_metadata_text(metadata: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, Mapping):
            value = value.get("value") or value.get("text")
        text = normalize_text(str(value or ""))
        if text:
            return text
    return ""


def _author_pipeline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_author_pipeline_value(payload: str) -> Any:
    try:
        return json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None


def _load_author_pipeline_mapping(payload: str) -> Mapping[str, Any]:
    value = _load_author_pipeline_value(payload)
    return value if isinstance(value, Mapping) else {}


def _extract_ieee_author_name_field(author_payload: str) -> list[str]:
    author = _load_author_pipeline_value(author_payload)
    if not isinstance(author, Mapping):
        return []
    for key in ("name", "preferredName", "fullName", "authorName"):
        text = normalize_text(str(author.get(key) or ""))
        if text:
            return [text]
    return []


def _extract_ieee_author_first_last_name(author_payload: str) -> list[str]:
    author = _load_author_pipeline_value(author_payload)
    if not isinstance(author, Mapping):
        return []
    name = normalize_text(
        f"{normalize_text(str(author.get('firstName') or ''))} {normalize_text(str(author.get('lastName') or ''))}"
    )
    return [name] if name else []


def _extract_ieee_scalar_author_name(author_payload: str) -> list[str]:
    author = _load_author_pipeline_value(author_payload)
    if isinstance(author, Mapping):
        return []
    name = normalize_text(str(author or ""))
    return [name] if name else []


_AUTHOR_NAME_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("name-field", _extract_ieee_author_name_field),
    AuthorStep("first-last", _extract_ieee_author_first_last_name),
    AuthorStep("scalar", _extract_ieee_scalar_author_name),
)


def _ieee_author_items_from_metadata_key(metadata_payload: str, key: str) -> list[Any]:
    metadata = _load_author_pipeline_mapping(metadata_payload)
    authors = metadata.get(key)
    if isinstance(authors, Mapping):
        authors = authors.get("authors") or authors.get("author")
    return list(authors) if isinstance(authors, list) else []


def _extract_ieee_authors_from_items(items: list[Any]) -> list[str]:
    return [
        name
        for item in items
        for name in _AUTHOR_NAME_PIPELINE(_author_pipeline_json(item))
    ]


def _extract_ieee_authors(metadata_payload: str) -> list[str]:
    return _extract_ieee_authors_from_items(
        _ieee_author_items_from_metadata_key(metadata_payload, "authors")
    )


def _extract_ieee_authors_list(metadata_payload: str) -> list[str]:
    return _extract_ieee_authors_from_items(
        _ieee_author_items_from_metadata_key(metadata_payload, "authorsList")
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("authors", _extract_ieee_authors),
    AuthorStep("authorsList", _extract_ieee_authors_list),
)

_IEEE_METADATA_SCALAR_KEYS = (
    "provider",
    "official_provider",
    "publisher",
    "doi",
    "title",
    "abstract",
    "journal_title",
    "published",
    "landing_page_url",
    "article_number",
    "articleNumber",
    "articleId",
    "isDynamicHtml",
    "html_flag",
    "ml_html_flag",
    "pdfUrl",
    "pdfPath",
    "raw_ieee_metadata",
)
_IEEE_METADATA_TEXT_KEYS = (
    "publisher",
    "title",
    "abstract",
    "journal_title",
    "published",
    "landing_page_url",
    "article_number",
    "articleNumber",
    "articleId",
    "pdfUrl",
    "pdfPath",
)
_IEEE_METADATA_MERGE_RULE = MetadataMergeRule(
    overwrite=_IEEE_METADATA_SCALAR_KEYS,
    concat_unique=("keywords",),
)
_IEEE_AUTHOR_MERGE_RULE = MetadataMergeRule(concat_unique=("authors",))
_IEEE_KEYWORD_MERGE_RULE = MetadataMergeRule(concat_unique=("keywords",))


def _merge_ieee_keywords(*values: list[str]) -> list[str]:
    merged = merge_metadata_layers(
        [{"keywords": value} for value in values if value],
        rule=_IEEE_KEYWORD_MERGE_RULE,
    )
    return list(merged.get("keywords") or [])


def _keyword_text_parts(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;,]", value)]


def _keyword_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return _keyword_text_parts(value)
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value not in (None, "") else []


def _keywords_from_ieee_metadata(metadata: Mapping[str, Any]) -> list[str]:
    keyword_groups: list[list[str]] = []
    raw_keywords = metadata.get("keywords")
    if isinstance(raw_keywords, list):
        for item in raw_keywords:
            if isinstance(item, Mapping):
                values = (
                    item.get("kwd")
                    or item.get("keywords")
                    or item.get("terms")
                    or item.get("value")
                )
                if isinstance(values, str):
                    keyword_groups.append([values])
                elif isinstance(values, list):
                    keyword_groups.append([str(value) for value in values])
                continue
            keyword_groups.append([str(item)])
    elif isinstance(raw_keywords, str):
        keyword_groups.append(_keyword_text_parts(raw_keywords))
    for key in (
        "authorKeywords",
        "author_terms",
        "authorTerms",
        "indexTerms",
        "ieeeTerms",
        "controlledTerms",
        "meshTerms",
        "pubTopics",
    ):
        value = metadata.get(key)
        if isinstance(value, list):
            keyword_groups.append([str(item) for item in value])
        elif isinstance(value, str):
            keyword_groups.append(_keyword_text_parts(value))
    return _merge_ieee_keywords(*keyword_groups)


def _parse_landing_metadata(html_text: str) -> dict[str, Any]:
    parsed = extract_assignment_json(html_text, IEEE_METADATA_ASSIGNMENT)
    metadata = dict(parsed) if isinstance(parsed, Mapping) else {}
    for key in (
        "articleNumber",
        "articleId",
        "isDynamicHtml",
        "html_flag",
        "ml_html_flag",
        "pdfUrl",
        "pdfPath",
        "doi",
        "title",
        "displayDocTitle",
        "formulaStrippedArticleTitle",
        "publicationTitle",
        "publicationDate",
        "abstract",
    ):
        if key not in metadata:
            value = _script_value(html_text, key)
            if value not in (None, ""):
                metadata[key] = value
    return metadata


def _reference_doi_from_ieee_reference(item: Mapping[str, Any]) -> str:
    links = item.get("links")
    if isinstance(links, Mapping):
        for key in ("crossRefLink", "doiLink"):
            value = normalize_text(str(links.get(key) or ""))
            match = _reference_doi_match(value)
            if match is not None:
                return normalize_doi(match.group(0).rstrip(").,;")) or ""
    for key in (
        "doi",
        "googleScholarStructredQuery",
        "googleScholarStructuredQuery",
        "text",
    ):
        value = normalize_text(str(item.get(key) or ""))
        match = _reference_doi_match(value)
        if match is not None:
            return normalize_doi(match.group(0).rstrip(").,;")) or ""
    return ""


def _references_from_ieee_reference_payload(
    payload: Mapping[str, Any],
) -> list[dict[str, str | None]]:
    raw_references = payload.get("references")
    if not isinstance(raw_references, list):
        return []
    references: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_references, start=1):
        if not isinstance(item, Mapping):
            continue
        raw_text = normalize_text(
            html_lib.unescape(strip_html_tags(str(item.get("text") or "")) or "")
        )
        if not raw_text:
            continue
        label = normalize_text(str(item.get("order") or index))
        key = (label, raw_text)
        if key in seen:
            continue
        seen.add(key)
        references.append(
            {
                "label": label or None,
                "raw": raw_text,
                "doi": _reference_doi_from_ieee_reference(item) or None,
                "title": normalize_text(
                    html_lib.unescape(
                        strip_html_tags(str(item.get("title") or "")) or ""
                    )
                )
                or None,
            }
        )
    return references


def _merge_ieee_metadata(
    base_metadata: Mapping[str, Any],
    landing_metadata: Mapping[str, Any],
    response_url: str,
) -> dict[str, Any]:
    base_layer = dict(base_metadata or {})
    base_layer["journal_title"] = base_layer.get("journal_title") or base_layer.get(
        "journal"
    )
    base_layer["keywords"] = _keyword_values(base_layer.get("keywords"))
    for key in _IEEE_METADATA_TEXT_KEYS:
        if key in base_layer:
            base_layer[key] = normalize_text(str(base_layer.get(key) or "")) or None
    if base_layer.get("doi"):
        base_layer["doi"] = normalize_doi(str(base_layer.get("doi") or "")) or None
    base_layer.pop("authors", None)
    title = strip_html_tags(
        _first_metadata_text(
            landing_metadata, "formulaStrippedArticleTitle", "displayDocTitle", "title"
        )
    ) or normalize_text(str(base_layer.get("title") or ""))
    abstract = strip_html_tags(
        _first_metadata_text(landing_metadata, "abstract")
    ) or normalize_text(str(base_layer.get("abstract") or ""))
    landing_authors = _AUTHOR_PIPELINE(_author_pipeline_json(landing_metadata))
    base_authors = [
        normalize_text(str(item))
        for item in (base_metadata or {}).get("authors") or []
        if normalize_text(str(item))
    ]
    article_number = _article_number_from_metadata(
        landing_metadata
    ) or _article_number_from_url(response_url)
    landing_layer = {
        "provider": "ieee",
        "official_provider": True,
        "doi": normalize_doi(_first_metadata_text(landing_metadata, "doi")) or None,
        "title": title or None,
        "abstract": abstract or None,
        "journal_title": _first_metadata_text(landing_metadata, "publicationTitle"),
        "published": _first_metadata_text(
            landing_metadata, "publicationDate", "onlineDate", "publicationYear"
        ),
        "keywords": _keywords_from_ieee_metadata(landing_metadata),
        "landing_page_url": response_url,
        "article_number": article_number or None,
        "articleNumber": article_number or None,
        "articleId": _first_metadata_text(landing_metadata, "articleId")
        or article_number
        or None,
        "isDynamicHtml": _boolish(landing_metadata.get("isDynamicHtml")),
        "html_flag": _boolish(landing_metadata.get("html_flag")),
        "ml_html_flag": _boolish(landing_metadata.get("ml_html_flag")),
        "pdfUrl": _first_metadata_text(landing_metadata, "pdfUrl") or None,
        "pdfPath": _first_metadata_text(landing_metadata, "pdfPath") or None,
        "raw_ieee_metadata": dict(landing_metadata),
    }
    merged = merge_metadata_layers(
        [base_layer, landing_layer], rule=_IEEE_METADATA_MERGE_RULE
    )
    authors_layer = merge_metadata_layers(
        [{"authors": landing_authors}, {"authors": base_authors}],
        rule=_IEEE_AUTHOR_MERGE_RULE,
    )
    merged["publisher"] = merged.get("publisher") or "IEEE"
    merged["keywords"] = list(merged.get("keywords") or [])
    merged["authors"] = dedupe_authors(
        [str(item) for item in (authors_layer.get("authors") or [])]
    )
    return merged


def _references_url(article_number: str, *, start: int = 0) -> str:
    url = IEEE_REFERENCES_URL_TEMPLATE.format(article_number=article_number)
    if start > 0:
        return f"{url}?start={start}&rowsPerPage={IEEE_REFERENCE_PAGE_SIZE}"
    return url


def fetch_ieee_reference_metadata(
    transport: Any,
    article_number: str,
    *,
    headers: Mapping[str, str],
    timeout: float = DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    decode_body: Callable[[bytes], str],
    expected_count: int = 0,
) -> list[dict[str, str | None]]:
    if not article_number:
        return []
    references: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    max_expected = max(0, expected_count)
    for page_index in range(IEEE_MAX_REFERENCE_PAGES):
        start = page_index * IEEE_REFERENCE_PAGE_SIZE
        if max_expected and start >= max_expected:
            break
        response = transport.request(
            "GET",
            _references_url(article_number, start=start),
            headers=headers,
            timeout=timeout,
            retry_on_transient=True,
        )
        body = bytes(response.get("body") or b"")
        if not body:
            break
        try:
            payload = json.loads(decode_body(body))
        except (TypeError, ValueError):
            break
        if not isinstance(payload, Mapping):
            break
        page_references = _references_from_ieee_reference_payload(payload)
        if not page_references:
            break
        added = 0
        for reference in page_references:
            key = (
                normalize_text(str(reference.get("label") or "")),
                normalize_text(str(reference.get("raw") or "")),
            )
            if key in seen:
                continue
            seen.add(key)
            references.append(reference)
            added += 1
        if added == 0 or len(page_references) < IEEE_REFERENCE_PAGE_SIZE:
            break
    return references


def _abstract_markdown(metadata: Mapping[str, Any]) -> str:
    title = normalize_text(str(metadata.get("title") or ""))
    abstract = normalize_text(str(metadata.get("abstract") or ""))
    lines: list[str] = []
    if title:
        lines.extend([f"# {title}", ""])
    if abstract:
        lines.extend(["## Abstract", "", abstract])
    return "\n".join(lines).strip()


def build_ieee_article_model(
    metadata: Mapping[str, Any],
    raw_payload: Any,
    *,
    downloaded_assets: list[Mapping[str, Any]] | None = None,
    asset_failures: list[Mapping[str, Any]] | None = None,
):
    from . import _ieee_html as ieee_html

    content = raw_payload.content
    merged_metadata = (
        content.merged_metadata if content is not None else raw_payload.merged_metadata
    )
    article_metadata = (
        merged_metadata if isinstance(merged_metadata, Mapping) else metadata
    )
    doi = normalize_doi(str(article_metadata.get("doi") or metadata.get("doi") or ""))
    markdown_text = str(
        (content.markdown_text if content is not None else "") or ""
    ).strip()
    route = normalize_text(content.route_kind if content is not None else "").lower()
    source: SourceKind = "ieee_pdf" if route == PDF_FALLBACK else "ieee_html"
    trace = list(
        raw_payload.trace
        or trace_from_markers([fulltext_marker("ieee", "ok", route="html")])
    )
    warnings = list(raw_payload.warnings)
    if asset_failures:
        if downloaded_assets:
            warnings.append(
                f"IEEE related assets were only partially downloaded ({len(asset_failures)} failed)."
            )
        else:
            warnings.append(
                f"IEEE related assets could not be downloaded ({len(asset_failures)} failed)."
            )
    if not markdown_text:
        warnings.append("IEEE retrieval did not produce usable Markdown.")
        return metadata_only_article(
            source=source,
            metadata=article_metadata,
            doi=doi or None,
            warnings=warnings,
            trace=trace,
        )
    extraction_payload = (
        content.diagnostics.get("extraction") if content is not None else None
    )
    abstract_sections = (
        list(extraction_payload.get("abstract_sections") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    section_hints = (
        list(extraction_payload.get("section_hints") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    extracted_assets = ieee_html._dedupe_ieee_assets_by_priority(
        [
            dict(item)
            for item in list(content.extracted_assets if content is not None else [])
        ],
        merge_fields=ieee_html.IEEE_ASSET_URL_FIELDS,
    )
    downloaded_asset_results = ieee_html._dedupe_ieee_assets_by_priority(
        [dict(item) for item in list(downloaded_assets or [])],
        merge_fields=(
            *ieee_html.IEEE_ASSET_URL_FIELDS,
            *ieee_html.IEEE_DOWNLOAD_MERGE_FIELDS,
        ),
    )
    assets = merge_asset_retry_results(
        extracted_assets,
        downloaded_asset_results,
        policy=ieee_html.IEEE_ASSET_RETRY_POLICY,
    )
    availability_diagnostics = (
        dict(content.diagnostics.get("availability_diagnostics") or {})
        if content is not None
        and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
        else None
    )
    article = article_from_markdown(
        source=source,
        metadata=article_metadata,
        doi=doi or None,
        markdown_text=markdown_text,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        assets=assets,
        warnings=warnings,
        trace=trace,
        availability_diagnostics=availability_diagnostics,
        semantic_losses={
            "formula_missing_count": markdown_text.count("[Formula unavailable]")
        },
        allow_downgrade_from_diagnostics=True,
    )
    if asset_failures:
        article.quality.asset_failures = [dict(item) for item in asset_failures]
    return article
