"""Browser-workflow HTML heuristics built on top of the generic markdown pipeline."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ..metadata_types import ProviderMetadata
from ..models import classify_article_content, filtered_body_sections, normalize_markdown_text
from ..utils import normalize_text
from ._article_markdown_math import render_external_mathml_expression
from ._html_access_signals import (
    CHALLENGE_PATTERNS,
    NOT_FOUND_PATTERNS,
    PAYWALL_PATTERNS,
    SciencePnasHtmlFailure as _SharedSciencePnasHtmlFailure,
    detect_html_access_signals,
    detect_html_block as _shared_detect_html_block,
    html_failure_message as _shared_html_failure_message,
    summarize_html as _shared_summarize_html,
)
from ._html_availability import (
    FulltextAvailabilityDiagnostics as _SharedFulltextAvailabilityDiagnostics,
    StructuredBodyAnalysis as _SharedStructuredBodyAnalysis,
    assess_html_fulltext_availability as _shared_assess_html_fulltext_availability,
    assess_plain_text_fulltext_availability as _shared_assess_plain_text_fulltext_availability,
    assess_structured_article_fulltext_availability as _shared_assess_structured_article_fulltext_availability,
    availability_failure_message as _shared_availability_failure_message,
)
from ._html_citations import clean_citation_markers
from ._html_tables import (
    inject_inline_table_blocks as _shared_inject_inline_table_blocks,
    render_table_inline_text as _shared_render_table_inline_text,
    render_table_markdown as _shared_render_table_markdown,
    table_headers_and_data as _shared_table_headers_and_data,
    table_placeholder as _shared_table_placeholder,
)
from ._science_pnas_postprocess import (
    normalize_browser_workflow_markdown as _shared_normalize_browser_workflow_markdown,
    rewrite_inline_figure_links as _shared_rewrite_inline_figure_links,
)
from ._science_pnas_profiles import (
    build_html_candidates as _profile_build_html_candidates,
    build_pdf_candidates as _profile_build_pdf_candidates,
    extract_pdf_url_from_crossref as _profile_extract_pdf_url_from_crossref,
    looks_like_abstract_redirect as _profile_looks_like_abstract_redirect,
    noise_profile_for_publisher as _profile_noise_profile_for_publisher,
    preferred_html_candidate_from_landing_page as _profile_preferred_html_candidate_from_landing_page,
    provider_positive_signals as _profile_positive_signals,
    publisher_profile as _publisher_profile,
    site_rule_for_publisher as _profile_site_rule_for_publisher,
)
from . import html_noise as _html_noise

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    NavigableString = None
    Tag = None

clean_markdown = _html_noise.clean_markdown
extract_article_markdown = _html_noise.extract_article_markdown
body_metrics = _html_noise.body_metrics
has_sufficient_article_body = _html_noise.has_sufficient_article_body
SITE_RULE_OVERRIDES: dict[str, dict[str, Any]] = {
    "science": {
        "candidate_selectors": [
            ".article__fulltext",
            ".article-view",
        ],
        "remove_selectors": [
            "header .social-share",
            ".jump-to-nav",
            ".article-access-info",
            ".references-tab",
            ".permissions",
            ".issue-item__citation",
            ".article-header__access",
        ],
        "drop_keywords": {
            "advert",
            "tab-nav",
            "jump-to",
        },
        "drop_text": {
            "Permissions",
        },
    },
    "pnas": {
        "candidate_selectors": [
            ".article__fulltext",
            ".core-container",
            ".article-content",
        ],
        "remove_selectors": [
            ".article__access",
            ".article__footer",
            ".article__reference-links",
        ],
        "drop_keywords": {
            "tab-nav",
        },
    },
    "wiley": {
        "candidate_selectors": [
            ".article-section__content",
            ".issue-item__body",
            ".epub-section",
            ".doi-access",
        ],
        "remove_selectors": [
            ".citation-tools",
            ".epub-reference",
            ".article-section__tableofcontents",
            ".publicationHistory",
        ],
        "drop_text": {
            "Recommended articles",
        },
    },
}
PUBLISHER_HOSTS: dict[str, tuple[str, ...]] = {
    "science": ("science.org", "www.science.org"),
    "pnas": ("pnas.org", "www.pnas.org"),
    "wiley": ("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com"),
}
PDF_URL_TOKENS = ("/doi/pdf/", "/doi/pdfdirect/", "/doi/epdf/", "/fullpdf", ".pdf", "download=true")
AAAS_DATALAYER_PATTERN = re.compile(r"AAASdataLayer=(\{.*?\});(?:if\(|</script>)", flags=re.DOTALL)
HTML_FULLTEXT_MARKERS = (
    'property="articleBody"',
    "property='articleBody'",
    'itemprop="articleBody"',
    "itemprop='articleBody'",
    'data-article-access="full"',
    "data-article-access='full'",
    'data-article-access-type="full"',
    "data-article-access-type='full'",
    'id="bodymatter"',
    "id='bodymatter'",
)
DEFAULT_SITE_RULE: dict[str, Any] = {
    "candidate_selectors": [
        "article",
        "main article",
        "[role='main'] article",
        "[itemprop='articleBody']",
        "[property='articleBody']",
        "[itemprop='mainEntity']",
        ".article",
        ".article__body",
        ".article__content",
        ".article-body",
        ".main-content",
        "#main-content",
        "main",
        "[role='main']",
        "body",
    ],
    "remove_selectors": [
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        ".social-share",
        ".article-tools",
        ".article-metrics",
        ".metrics-widget",
        ".recommended-articles",
        ".related-content",
        ".breadcrumbs",
        ".toc",
        ".tab__nav",
        ".accessDenialWidget",
        ".cookie-banner",
        ".cookie-consent",
    ],
    "drop_keywords": {
        "metrics",
        "metric",
        "share",
        "social",
        "recommend",
        "related",
        "toolbar",
        "breadcrumb",
        "download",
        "cookie",
        "promo",
        "banner",
        "citation-tool",
        "nav",
        "access-widget",
        "rightslink",
    },
    "drop_text": {
        "Check for updates",
        "View Metrics",
        "Share",
        "Cite",
    },
}
BODY_CONTAINER_TOKENS = (
    "articlebody",
    "article-body",
    "article_body",
    "bodymatter",
    "fulltext",
    "full-text",
)
ABSTRACT_TOKENS = (
    "abstract",
    "structured-abstract",
    "structured_abstract",
    "editor-abstract",
    "summary",
    "key-points",
    "highlights",
)
BACK_MATTER_TOKENS = (
    "reference",
    "bibliograph",
    "acknowledg",
    "supplement",
    "supporting-information",
    "supporting_information",
    "funding",
    "author-contribution",
    "conflict",
    "disclosure",
    "ethics",
)
DATA_AVAILABILITY_TOKENS = (
    "data-availability",
    "data_availability",
)
ANCILLARY_TOKENS = (
    "related",
    "recommend",
    "metric",
    "share",
    "social",
    "toolbar",
    "breadcrumb",
    "access",
    "cookie",
    "banner",
    "promo",
    "figure-pop",
    "viewer",
    "citation",
    "permissions",
    "eletter",
    "signup",
)
ABSTRACT_HEADINGS = {
    "abstract",
    "structured abstract",
}
FRONT_MATTER_HEADINGS = {
    "editor's summary",
    "editor’s summary",
    "summary",
    "key points",
    "highlights",
    "graphical abstract",
}
BACK_MATTER_HEADINGS = (
    "references",
    "references and notes",
    "acknowledgments",
    "supplementary materials",
    "supplementary material",
    "supplementary information",
    "supporting information",
    "notes",
    "author contributions",
    "funding",
    "ethics",
    "conflict of interest",
    "conflicts of interest",
    "competing interests",
    "disclosures",
)
DATA_AVAILABILITY_HEADINGS = (
    "data availability",
    "data availability statement",
    "data, materials, and software availability",
    "data, code, and materials availability",
    "availability of data and materials",
)
ANCILLARY_HEADINGS = {
    "recommended",
    "related content",
    "related articles",
    "metrics",
    "view options",
    "authors",
    "affiliations",
    "author information",
    "information & authors",
    "information and authors",
    "citations",
    "submission history",
    "license information",
    "cite as",
    "export citation",
    "cited by",
    "citing literature",
    "figures",
    "tables",
    "media",
}
NARRATIVE_ARTICLE_TYPE_TOKENS = {
    "perspective",
    "review",
    "editorial",
    "commentary",
    "article-commentary",
}
BODY_PARAGRAPH_MIN_CHARS = 80
NARRATIVE_BODY_RUN_MIN_CHARS = 400
SENTENCE_PATTERN = re.compile(r"[.!?。！？]+")
ARTICLE_TYPE_META_PATTERN = re.compile(
    r"<meta[^>]+(?:name|property)=['\"](?:citation_article_type|dc\.type|prism\.section|article:section)['\"][^>]+content=['\"]([^'\"]+)['\"]",
    flags=re.IGNORECASE,
)
DATA_TYPE_PATTERN = re.compile(r"data-type=['\"]([^'\"]+)['\"]", flags=re.IGNORECASE)
FRONT_MATTER_LINE_PATTERNS = (
    re.compile(r"^doi:\s*", flags=re.IGNORECASE),
    re.compile(r"^(vol\.?|volume)\b", flags=re.IGNORECASE),
    re.compile(r"^issue\b", flags=re.IGNORECASE),
    re.compile(r"^[A-Z][a-z]{2,9}\s+\d{4}$"),
    re.compile(r"^[0-3]?\d\s+[A-Z][a-z]{2,9}\s+\d{4}$"),
)
FRONT_MATTER_EXACT_TEXTS = {
    "full access",
    "open access",
    "free access",
    "research article",
    "perspective",
    "review",
    "editorial",
    "commentary",
}
POST_CONTENT_BREAK_PREFIXES = (
    "copyright",
    "license information",
    "submission history",
)
POST_CONTENT_BREAK_TEXTS = {
    "these authors contributed equally to this work.",
}
POST_CONTENT_BREAK_TOKENS = (
    "view all articles by this author",
    "purchase digital access to this article",
    "purchase access to other journals in the science family",
    "select the format you want to export the citation of this publication",
    "loading institution options",
    "become a aaas member",
    "activate your aaas id",
    "account help",
)
PROMO_BLOCK_TOKENS = (
    "sign up for pnas alerts",
    "get alerts for new articles, or get an alert when an article is cited",
)
FIGURE_LABEL_PATTERN = re.compile(r"\bfig(?:ure)?\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
TABLE_LABEL_PATTERN = re.compile(r"\btable\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
EQUATION_NUMBER_PATTERN = re.compile(r"(\d+[A-Za-z]?)")
MARKDOWN_FIGURE_BLOCK_PATTERN = re.compile(r"^\*\*(Figure\s+\d+[A-Za-z]?\.?)\*\*(?:\s+.*)?$", flags=re.IGNORECASE)
MARKDOWN_IMAGE_BLOCK_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
CONTENT_ABSTRACT_SELECTORS = (
    "#abstracts",
    "section[role='doc-abstract']",
    "[property='abstract'][typeof='Text']",
    "[itemprop='description']",
    ".abstract",
    ".article-section__abstract",
)
CONTENT_BODY_SELECTORS = (
    "#bodymatter",
    "[data-extent='bodymatter']",
    "[property='articleBody']",
    "[itemprop='articleBody']",
    ".article__body",
    ".article-body",
    ".article__content",
    ".article-section__content",
    ".article__fulltext",
    ".epub-section",
)
CONTENT_DATA_AVAILABILITY_SELECTORS = (
    "#data-availability",
    "section[id*='data-availability']",
    "section[class*='data-availability']",
    "div[id*='data-availability']",
    "div[class*='data-availability']",
)


@dataclass
class StructuredBodyAnalysis:
    explicit_body_container: bool = False
    post_abstract_body_run: bool = False
    narrative_article_type: bool = False
    paywall_text_outside_body_ignored: bool = False
    body_run_paragraph_count: int = 0
    body_run_char_count: int = 0
    body_paragraph_count: int = 0
    body_candidate_text: str = ""
    paywall_gate_detected: bool = False
    page_has_paywall_text: bool = False
    container_has_paywall_text: bool = False


class SciencePnasHtmlFailure(_SharedSciencePnasHtmlFailure):
    pass


@dataclass
class FulltextAvailabilityDiagnostics:
    accepted: bool
    reason: str
    content_kind: str
    hard_negative_signals: list[str] = field(default_factory=list)
    strong_positive_signals: list[str] = field(default_factory=list)
    soft_positive_signals: list[str] = field(default_factory=list)
    body_metrics: dict[str, Any] = field(default_factory=dict)
    figure_count: int = 0
    title: str | None = None
    container_tag: str | None = None
    container_text_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preferred_html_candidate_from_landing_page(
    publisher: str,
    doi: str,
    landing_page_url: str | None,
) -> str | None:
    return _profile_preferred_html_candidate_from_landing_page(publisher, doi, landing_page_url)


def _publisher_base_urls(publisher: str, landing_page_url: str | None = None) -> list[str]:
    preferred = normalize_text(landing_page_url)
    base_urls: list[str] = []
    if preferred:
        parsed = urllib.parse.urlparse(preferred)
        hostname = normalize_text(parsed.hostname or "").lower()
        if parsed.scheme in {"http", "https"} and hostname:
            if any(hostname == token or hostname.endswith(f".{token}") for token in PUBLISHER_HOSTS.get(publisher, ())):
                base_urls.append(f"{parsed.scheme}://{hostname}")

    if publisher == "science":
        candidates = ["https://www.science.org", "https://science.org"]
    elif publisher == "pnas":
        candidates = ["https://www.pnas.org", "https://pnas.org"]
    else:
        candidates = ["https://onlinelibrary.wiley.com"]

    for candidate in candidates:
        if candidate not in base_urls:
            base_urls.append(candidate)
    return base_urls


def build_html_candidates(publisher: str, doi: str, landing_page_url: str | None = None) -> list[str]:
    return _profile_build_html_candidates(publisher, doi, landing_page_url)


def build_pdf_candidates(publisher: str, doi: str, crossref_pdf_url: str | None) -> list[str]:
    return _profile_build_pdf_candidates(publisher, doi, crossref_pdf_url)


def extract_pdf_url_from_crossref(metadata: Mapping[str, Any]) -> str | None:
    return _profile_extract_pdf_url_from_crossref(metadata)


def looks_like_abstract_redirect(requested_url: str, final_url: str | None) -> bool:
    return _profile_looks_like_abstract_redirect(requested_url, final_url)


def _noise_profile_for_publisher(publisher: str | None) -> str:
    return _profile_noise_profile_for_publisher(publisher)


def _site_rule(publisher: str | None) -> dict[str, Any]:
    return _profile_site_rule_for_publisher(publisher)


def _contains_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = normalize_text(text).lower()
    return any(pattern in lowered for pattern in patterns)


def _normalize_heading(text: str) -> str:
    return normalize_text(text).lower().strip(" :")


def _sentence_count(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized:
        return 0
    matches = SENTENCE_PATTERN.findall(normalized)
    if matches:
        return len(matches)
    return 1 if len(normalized) >= BODY_PARAGRAPH_MIN_CHARS else 0


def _is_substantial_prose(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized) >= BODY_PARAGRAPH_MIN_CHARS or _sentence_count(normalized) >= 2


def _looks_like_explicit_body_container(node: Tag | None) -> bool:
    if node is None:
        return False
    attrs = getattr(node, "attrs", None) or {}
    values: list[str] = [normalize_text(node.name or "")]
    for key in ("id", "property", "itemprop", "data-type", "role", "aria-label"):
        value = attrs.get(key)
        if value:
            values.append(str(value))
    for class_name in attrs.get("class", []):
        values.append(str(class_name))
    identity = " ".join(values).lower()
    return any(token in identity for token in BODY_CONTAINER_TOKENS)


def _normalized_page_text(html_text: str) -> str:
    if BeautifulSoup is None:
        return normalize_text(re.sub(r"<[^>]+>", " ", html_text))
    soup = BeautifulSoup(html_text, choose_parser())
    return normalize_text(" ".join(soup.stripped_strings))


def _extract_article_type(
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
) -> str | None:
    for key in (
        "article_type",
        "type",
        "publication_type",
        "document_type",
        "content_type",
        "dc_type",
        "nlm_article_type",
    ):
        value = normalize_text(str((metadata or {}).get(key) or ""))
        if value:
            return value

    if html_text:
        if provider == "science":
            payload = _parse_aaas_datalayer(html_text)
            if isinstance(payload, Mapping):
                page = payload.get("page") if isinstance(payload.get("page"), Mapping) else {}
                page_info = page.get("pageInfo") if isinstance(page, Mapping) and isinstance(page.get("pageInfo"), Mapping) else {}
                article_type = normalize_text(str(page_info.get("articleType") or page_info.get("nlmArticleType") or ""))
                if article_type:
                    return article_type
        for pattern in (ARTICLE_TYPE_META_PATTERN, DATA_TYPE_PATTERN):
            match = pattern.search(html_text)
            if match:
                value = normalize_text(match.group(1))
                if value:
                    return value
    return None


def _is_narrative_article_type(article_type: str | None) -> bool:
    normalized = normalize_text(article_type or "").lower()
    return any(token in normalized for token in NARRATIVE_ARTICLE_TYPE_TOKENS)


def _final_url_looks_like_access_page(final_url: str | None) -> bool:
    normalized = normalize_text(final_url or "").lower()
    if not normalized:
        return False
    return any(
        token in normalized
        for token in ("/abstract", "/summary", "/doi/abs/", "/article/access", "/access", "/article-abstract")
    )


def _heading_category(node_name: str, text: str, *, title: str | None = None) -> str:
    if normalize_text(node_name or "").lower() == "h1":
        return "front_matter"
    normalized = _normalize_heading(text)
    if title and normalized == _normalize_heading(title):
        return "front_matter"
    if normalized in ABSTRACT_HEADINGS or normalized.startswith("abstract"):
        return "abstract"
    if normalized in FRONT_MATTER_HEADINGS:
        return "front_matter"
    if any(normalized.startswith(token) for token in DATA_AVAILABILITY_HEADINGS):
        return "data_availability"
    if any(normalized.startswith(token) for token in BACK_MATTER_HEADINGS):
        return "references_or_back_matter"
    if normalized in ANCILLARY_HEADINGS:
        return "ancillary"
    return "body_heading"


def _detect_html_hard_negative_signals_impl(
    title: str,
    text: str,
    response_status: int | None,
    *,
    requested_url: str | None = None,
    final_url: str | None = None,
    include_paywall_text: bool = True,
    provider_metadata: Mapping[str, Any] | None = None,
) -> list[str]:
    redirected_to_abstract = bool(requested_url and looks_like_abstract_redirect(requested_url, final_url))
    return detect_html_access_signals(
        title,
        text,
        response_status,
        redirected_to_abstract=redirected_to_abstract,
        include_paywall_text=include_paywall_text,
        explicit_no_access=bool(provider_metadata and provider_metadata.get("explicit_no_access")),
    )


def detect_html_hard_negative_signals(
    title: str,
    text: str,
    response_status: int | None,
    *,
    requested_url: str | None = None,
    final_url: str | None = None,
) -> list[str]:
    return _detect_html_hard_negative_signals_impl(
        title,
        text,
        response_status,
        requested_url=requested_url,
        final_url=final_url,
        include_paywall_text=True,
    )


def detect_html_block(title: str, text: str, response_status: int | None) -> SciencePnasHtmlFailure | None:
    failure = _shared_detect_html_block(title, text, response_status)
    if failure is None:
        return None
    return SciencePnasHtmlFailure(failure.reason, failure.message)


def summarize_html(html_text: str, limit: int = 1000) -> str:
    return _shared_summarize_html(html_text, limit=limit)


def choose_parser() -> str:
    return "lxml" if importlib.util.find_spec("lxml") is not None else "html.parser"


def score_container(node: Tag) -> float:
    text = " ".join(node.stripped_strings)
    text_length = len(text)
    paragraph_count = len(node.find_all("p"))
    heading_count = len(node.find_all(re.compile(r"^h[1-6]$")))
    link_count = len(node.find_all("a"))
    score = text_length / 120.0
    score += paragraph_count * 6.0
    score += heading_count * 12.0
    score -= max(0, link_count - paragraph_count * 2) * 1.5
    lowered = text.lower()
    if any(pattern in lowered for pattern in CHALLENGE_PATTERNS):
        score -= 500
    if "abstract" in lowered:
        score += 20
    if "references" in lowered:
        score += 20
    return score


def select_best_container(soup: BeautifulSoup, publisher: str):
    selectors = _site_rule(publisher)["candidate_selectors"]
    candidates: list[tuple[float, Tag]] = []
    seen: set[int] = set()
    for selector in selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            continue
        for node in nodes:
            if id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append((score_container(node), node))
    if not candidates:
        for node in soup.find_all(["article", "main", "body"]):
            if id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append((score_container(node), node))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return _prefer_complete_ancestor(candidates[0][1])


def node_identity_text(node: Tag) -> str:
    attrs = getattr(node, "attrs", None) or {}
    values: list[str] = []
    for key in ("id", "role", "property", "itemprop", "data-type", "aria-label"):
        value = attrs.get(key)
        if value:
            values.append(str(value))
    for class_name in attrs.get("class", []):
        values.append(str(class_name))
    return " ".join(values).lower()


def should_drop_node(node: Tag, publisher: str) -> bool:
    if node.name in {"script", "style", "noscript", "svg", "iframe", "button", "input", "form"}:
        return True

    identity = node_identity_text(node)
    text = normalize_text(node.get_text(" ", strip=True))
    if _looks_like_access_gate_text(text):
        return False
    short_text = len(text) <= 200
    for keyword in _site_rule(publisher)["drop_keywords"]:
        if keyword in identity and short_text:
            return True
    if short_text and text in _site_rule(publisher)["drop_text"]:
        return True
    if short_text and any(pattern in text.lower() for pattern in {"share this", "view metrics", "article metrics"}):
        return True
    return False


def clean_container(container: Tag, publisher: str) -> Tag:
    for selector in _site_rule(publisher)["remove_selectors"]:
        for node in list(container.select(selector)):
            node.decompose()

    for node in list(container.find_all(True)):
        if should_drop_node(node, publisher):
            node.decompose()
    return container


def _short_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def _normalize_table_inline_text(value: str) -> str:
    text = value.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s*(<br>)\s*", r"\1", text)
    text = re.sub(r"<(sub|sup)>\s+", r"<\1>", text)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text)
    text = re.sub(r"(</sub>)\s+\(", r"\1(", text)
    text = re.sub(r"(</(?:sub|sup)>)\s+([,.;:%\]\}])", r"\1\2", text)
    return text.strip()


def _wrap_table_text_fragment(text: str, marker: str | None) -> str:
    value = text.replace("\xa0", " ")
    has_leading_space = bool(value[:1].isspace())
    has_trailing_space = bool(value[-1:].isspace())
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return ""
    if marker:
        normalized = f"{marker}{normalized}{marker}"
    if has_leading_space:
        normalized = f" {normalized}"
    if has_trailing_space:
        normalized = f"{normalized} "
    return normalized


def _render_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if node is None:
        return ""
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    parts: list[str] = []
    for child in node.children:
        if NavigableString is not None and isinstance(child, NavigableString):
            parts.append(_wrap_table_text_fragment(str(child), text_style))
            continue
        if not isinstance(child, Tag):
            continue

        name = normalize_text(child.name or "").lower()
        if name in {"i", "em"}:
            parts.append(_render_table_inline_node(child, text_style="*"))
        elif name in {"b", "strong"}:
            parts.append(_render_table_inline_node(child, text_style="**"))
        elif name == "sub":
            text = _render_table_inline_node(child)
            if text:
                parts.append(f"<sub>{text}</sub>")
        elif name == "sup":
            text = _render_table_inline_node(child)
            if text:
                parts.append(f"<sup>{text}</sup>")
        elif name == "br":
            parts.append("<br>")
        else:
            parts.append(_render_table_inline_node(child, text_style=text_style))

    return _normalize_table_inline_text("".join(parts))


def _render_table_inline_text(node: Any) -> str:
    return _shared_render_table_inline_text(node)


def _normalize_non_table_inline_text(value: str) -> str:
    text = value.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s*(<br>)\s*", r"\1", text)
    text = re.sub(r"<(sub|sup)>\s+", r"<\1>", text)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text)
    text = re.sub(r"(</sub>)\s+\(", r"\1(", text)
    text = re.sub(r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", r"\1\2", text)
    return text.strip()


def _render_non_table_inline_fragment(node: Any, *, text_style: str | None = None) -> str:
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    name = normalize_text(node.name or "").lower()
    if name in {"i", "em"}:
        return _render_non_table_inline_node(node, text_style="*")
    if name in {"b", "strong"}:
        return _render_non_table_inline_node(node, text_style="**")
    if name == "sub":
        text = _render_non_table_inline_node(node)
        return f"<sub>{text}</sub>" if text else ""
    if name == "sup":
        text = _render_non_table_inline_node(node)
        return f"<sup>{text}</sup>" if text else ""
    if name == "br":
        return "<br>"
    return _render_non_table_inline_node(node, text_style=text_style)


def _render_non_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if node is None:
        return ""
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    parts: list[str] = []
    for child in node.children:
        rendered_child = _render_non_table_inline_fragment(child, text_style=text_style)
        if rendered_child:
            parts.append(rendered_child)

    return _normalize_non_table_inline_text("".join(parts))


def _render_non_table_inline_text(node: Any) -> str:
    return _render_non_table_inline_node(node)


def _join_non_table_text_fragments(fragments: list[str]) -> str:
    joined = ""
    for fragment in fragments:
        normalized_fragment = normalize_text(fragment)
        if not normalized_fragment:
            continue
        if (
            joined
            and not joined.endswith((" ", "\n", "<br>", "(", "[", "{", "/"))
            and not normalized_fragment.startswith((".", ",", ";", ":", ")", "]", "}", "%", "<br>"))
        ):
            joined += " "
        joined += normalized_fragment
    return _normalize_non_table_inline_text(joined)


def _render_caption_text(node: Tag) -> str:
    fragments: list[str] = []
    direct_tag_children = 0
    for child in node.children:
        if NavigableString is not None and isinstance(child, NavigableString):
            text = _wrap_table_text_fragment(str(child), None)
        elif isinstance(child, Tag):
            direct_tag_children += 1
            text = _render_non_table_inline_fragment(child)
        else:
            text = ""
        if text:
            fragments.append(text)
    if direct_tag_children > 1:
        return _join_non_table_text_fragments(fragments)
    return _render_non_table_inline_text(node)


def _is_non_table_paragraph_node(node: Tag) -> bool:
    name = normalize_text(node.name or "").lower()
    if name in {"p", "li"}:
        return True
    if name == "div" and normalize_text(str((getattr(node, "attrs", None) or {}).get("role") or "")).lower() == "paragraph":
        return True
    return False


def _normalize_non_table_inline_blocks(container: Tag) -> None:
    candidates = [
        node
        for node in container.find_all(["p", "li", "div"])
        if isinstance(node, Tag) and node.parent is not None and _is_non_table_paragraph_node(node)
    ]
    for node in _dedupe_top_level_nodes(candidates):
        if node.find_parent("table") is not None:
            continue
        rendered = _render_non_table_inline_text(node)
        if not rendered:
            continue
        node.clear()
        node.append(rendered)


def _soup_root(node: Tag | None) -> BeautifulSoup | None:
    current: Any = node
    while current is not None and not isinstance(current, BeautifulSoup):
        parent = current.parent if isinstance(getattr(current, "parent", None), (Tag, BeautifulSoup)) else None
        current = parent
    return current if isinstance(current, BeautifulSoup) else None


def _append_text_block(parent: Tag, text: str, *, tag_name: str = "p", soup: BeautifulSoup | None = None) -> None:
    soup = soup or _soup_root(parent)
    if soup is None:
        return
    block = soup.new_tag(tag_name)
    block.string = text
    parent.append(block)


def _promotional_parent(node: Tag) -> Tag:
    current = node
    while isinstance(current.parent, Tag):
        parent = current.parent
        parent_text = _short_text(parent).lower()
        if not parent_text or len(parent_text) > 320:
            break
        if any(token in parent_text for token in PROMO_BLOCK_TOKENS) or parent_text == "learn more":
            current = parent
            continue
        break
    return current


def _drop_promotional_blocks(container: Tag, publisher: str) -> None:
    if publisher != "pnas":
        return
    for node in list(container.find_all(True)):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        text = _short_text(node).lower()
        if not text or len(text) > 220:
            continue
        if any(token in text for token in PROMO_BLOCK_TOKENS) or text == "learn more":
            _promotional_parent(node).decompose()


def _abstract_nodes(container: Tag) -> list[Tag]:
    nodes: list[Tag] = []
    for selector in CONTENT_ABSTRACT_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _normalize_abstract_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    for node in _abstract_nodes(container):
        if node.name not in {"section", "div"}:
            node.name = "section"
        heading = node.find(re.compile(r"^h[1-6]$"))
        if isinstance(heading, Tag):
            heading.name = "h2"
            if not _normalize_heading(_short_text(heading)):
                heading.string = "Abstract"
            continue
        heading = soup.new_tag("h2")
        heading.string = "Abstract"
        node.insert(0, heading)


def _markdown_has_abstract_heading(markdown_text: str) -> bool:
    for block in re.split(r"\n\s*\n", markdown_text):
        heading_info = _markdown_heading_info(block)
        if heading_info is None:
            continue
        level, heading_text = heading_info
        if _heading_category(f"h{min(level, 6)}", heading_text) == "abstract":
            return True
    return False


def _abstract_block_texts(node: Tag) -> list[str]:
    heading = node.find(re.compile(r"^h[1-6]$"))
    texts: list[str] = []
    seen: set[str] = set()

    for candidate in node.find_all(True):
        if candidate is heading:
            continue
        if normalize_text(candidate.get("role") or "").lower() == "paragraph" or candidate.name in {"p", "li"}:
            text = _render_non_table_inline_text(candidate)
            if text and text not in seen:
                texts.append(text)
                seen.add(text)

    if texts:
        return texts

    fallback_text = _render_non_table_inline_text(node)
    heading_text = _short_text(heading)
    if heading_text:
        pattern = re.compile(rf"^{re.escape(heading_text)}[:\s-]*", flags=re.IGNORECASE)
        fallback_text = normalize_text(pattern.sub("", fallback_text, count=1))
    return [fallback_text] if fallback_text else []


def _missing_abstract_markdown(container: Tag, markdown_text: str, *, publisher: str) -> str:
    if _markdown_has_abstract_heading(markdown_text):
        return ""

    existing_normalized = normalize_text(markdown_text)
    abstract_blocks: list[str] = []
    for node in _abstract_nodes(container):
        heading = node.find(re.compile(r"^h[1-6]$"))
        heading_text = normalize_text(_short_text(heading) or "Abstract") or "Abstract"
        body_parts = _abstract_block_texts(node)
        if not body_parts:
            continue
        body_text = "\n\n".join(part for part in body_parts if part)
        normalized_body_text = normalize_text(body_text)
        if normalized_body_text and normalized_body_text in existing_normalized:
            continue
        abstract_blocks.append(f"## {heading_text}\n\n{body_text}")

    if not abstract_blocks:
        return ""
    return clean_markdown(
        "\n\n".join(abstract_blocks),
        noise_profile=_noise_profile_for_publisher(publisher),
    )


def _mathml_element_from_node(node: Tag | None) -> ET.Element | None:
    if node is None:
        return None
    math_node = node if normalize_text(node.name or "").lower() == "math" else node.find("math")
    if not isinstance(math_node, Tag):
        return None
    raw_mathml = str(math_node)
    try:
        return ET.fromstring(raw_mathml)
    except ET.ParseError:
        raw_mathml = raw_mathml.replace("&nbsp;", " ")
        try:
            return ET.fromstring(raw_mathml)
        except ET.ParseError:
            return None


def _latex_from_math_node(node: Tag, *, display_mode: bool) -> str:
    element = _mathml_element_from_node(node)
    if element is not None:
        expression = normalize_text(render_external_mathml_expression(element, display_mode=display_mode))
        if expression:
            return expression
    return _short_text(node)


def _display_formula_nodes(container: Tag) -> list[Tag]:
    nodes: list[Tag] = []
    for selector in (".display-formula", ".disp-formula", "math[display='block']", "div[role='math']"):
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _equation_label(node: Tag) -> str:
    candidates: list[str] = []
    for candidate in (
        node.select_one(".label"),
        node.find_previous_sibling(class_="label"),
    ):
        if isinstance(candidate, Tag):
            candidates.append(_short_text(candidate))
    node_id = normalize_text(str((getattr(node, "attrs", None) or {}).get("id") or ""))
    if node_id:
        candidates.append(node_id)
    for text in candidates:
        match = EQUATION_NUMBER_PATTERN.search(text)
        if match:
            return f"Equation {match.group(1)}."
    return ""


def _display_formula_replacement(node: Tag, soup: BeautifulSoup) -> Tag | None:
    latex = _latex_from_math_node(node, display_mode=True)
    if not latex:
        return None
    replacement = soup.new_tag("div")
    label = _equation_label(node)
    if label:
        _append_text_block(replacement, f"**{label}**", soup=soup)
    for line in ("$$", latex, "$$"):
        _append_text_block(replacement, line, soup=soup)
    return replacement


def _direct_child_with_parent(node: Tag, parent: Tag) -> Tag | None:
    current: Tag | None = node
    while isinstance(current, Tag) and current.parent is not None:
        if current.parent is parent:
            return current
        current = current.parent if isinstance(current.parent, Tag) else None
    return None


def _clone_shallow_tag(node: Tag, soup: BeautifulSoup) -> Tag:
    clone = soup.new_tag(node.name)
    clone.attrs = copy.deepcopy(getattr(node, "attrs", None) or {})
    return clone


def _insert_split_paragraph(parent: Tag, children: list[Any], soup: BeautifulSoup) -> None:
    segment = _clone_shallow_tag(parent, soup)
    for child in children:
        if (NavigableString is not None and isinstance(child, NavigableString)) or isinstance(child, Tag):
            segment.append(child.extract())
    if normalize_text(segment.get_text(" ", strip=True)):
        parent.insert_before(segment)
        return
    segment.decompose()


def _split_paragraph_display_formula_blocks(parent: Tag, soup: BeautifulSoup) -> bool:
    formula_nodes: dict[int, Tag] = {}
    for formula_node in _display_formula_nodes(parent):
        direct_child = _direct_child_with_parent(formula_node, parent)
        if isinstance(direct_child, Tag):
            formula_nodes[id(direct_child)] = formula_node
    if not formula_nodes:
        return False

    pending_children: list[Any] = []
    for child in list(parent.contents):
        formula_node = formula_nodes.get(id(child))
        if formula_node is None:
            pending_children.append(child)
            continue
        if pending_children:
            _insert_split_paragraph(parent, pending_children, soup)
            pending_children = []
        replacement = _display_formula_replacement(formula_node, soup)
        if replacement is not None:
            parent.insert_before(replacement)
    if pending_children:
        _insert_split_paragraph(parent, pending_children, soup)
    parent.decompose()
    return True


def _normalize_display_formula_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    handled_parents: set[int] = set()
    nodes = _display_formula_nodes(container)
    for node in nodes:
        if not isinstance(node, Tag) or not isinstance(node.parent, Tag):
            continue
        parent = node.parent
        if not _is_non_table_paragraph_node(parent) or id(parent) in handled_parents:
            continue
        if _split_paragraph_display_formula_blocks(parent, soup):
            handled_parents.add(id(parent))

    for node in nodes:
        if not isinstance(node, Tag) or node.parent is None:
            continue
        replacement = _display_formula_replacement(node, soup)
        if replacement is None:
            continue
        node.replace_with(replacement)


def _is_display_formula_math(node: Tag) -> bool:
    attrs = getattr(node, "attrs", None) or {}
    if normalize_text(str(attrs.get("display") or "")).lower() == "block":
        return True
    identity = _ancestor_identity_text(node)
    return any(token in identity for token in ("display-formula", "disp-formula")) or normalize_text(str(attrs.get("role") or "")).lower() == "math"


def _inline_math_replacement_target(node: Tag) -> Tag:
    for current in (
        node.find_parent("mjx-container"),
        node.find_parent("mjx-assistive-mml"),
    ):
        if isinstance(current, Tag):
            return current
    return node


def _normalize_inline_math_nodes(container: Tag) -> None:
    for math_node in list(container.find_all("math")):
        if not isinstance(math_node, Tag) or math_node.parent is None:
            continue
        if _is_display_formula_math(math_node):
            continue
        latex = _latex_from_math_node(math_node, display_mode=False)
        if not latex:
            continue
        _inline_math_replacement_target(math_node).replace_with(f"${latex}$")


def _caption_label(node: Tag, *, kind: str) -> str:
    label_pattern = FIGURE_LABEL_PATTERN if kind == "Figure" else TABLE_LABEL_PATTERN
    for candidate in (
        node.select_one("header .label"),
        node.select_one(".label"),
    ):
        if isinstance(candidate, Tag):
            text = _short_text(candidate)
            match = label_pattern.search(text)
            if match:
                return f"{kind} {match.group(1)}."
    match = label_pattern.search(_short_text(node))
    if match:
        return f"{kind} {match.group(1)}."
    return kind


def _caption_text(node: Tag) -> str:
    for selector in (".figure__caption-text", "figcaption", ".figure__caption", "[role='doc-caption']", ".caption"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _render_caption_text(candidate)
            if text:
                return text
    return ""


def _strip_caption_label(text: str, label: str) -> str:
    label_text = normalize_text(label).rstrip(".")
    if not label_text:
        return text
    variants = [label_text]
    if label_text.lower().startswith("figure "):
        variants.append(f"Fig. {label_text.split(' ', 1)[1]}")
    for variant in variants:
        text = re.sub(rf"^{re.escape(variant)}\.?\s*", "", text, flags=re.IGNORECASE)
    return normalize_text(text).lstrip(".:;,-) ]")


def _table_caption_text(node: Tag, label: str) -> str:
    for selector in (".article-table-caption", ".caption", "figcaption", "caption", "header"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _strip_caption_label(_render_caption_text(candidate), label)
            if text:
                return text
    return ""


def _is_glossary_table(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if "list-paired" in node_identity_text(current):
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _table_like_nodes(container: Tag) -> list[Tag]:
    nodes: list[Tag] = []
    for table in container.find_all("table"):
        if not isinstance(table, Tag):
            continue
        if _is_glossary_table(table):
            continue
        identity = _ancestor_identity_text(table)
        if any(token in identity for token in BACK_MATTER_TOKENS + ANCILLARY_TOKENS):
            continue
        best: Tag = table
        current = table.parent if isinstance(table.parent, Tag) else None
        depth = 0
        while isinstance(current, Tag) and current is not container and depth < 8:
            current_identity = node_identity_text(current)
            if (
                current.name == "figure"
                or "figure-wrap" in current_identity
                or "table-wrap" in current_identity
                or "article-table" in current_identity
                or current_identity.startswith("table ")
                or " table " in f" {current_identity} "
            ):
                best = current
            current = current.parent if isinstance(current.parent, Tag) else None
            depth += 1
        nodes.append(best)
    return _dedupe_top_level_nodes(nodes)


def _first_abstract_node(container: Tag) -> Tag | None:
    nodes = _abstract_nodes(container)
    return nodes[0] if nodes else None


def _is_front_matter_teaser_figure(node: Tag, *, publisher: str, abstract_anchor: Tag | None = None) -> bool:
    if publisher != "science":
        return False
    if _caption_label(node, kind="Figure") != "Figure":
        return False
    if any(token in _ancestor_identity_text(node) for token in ABSTRACT_TOKENS):
        return True
    if abstract_anchor is None:
        return False
    return abstract_anchor in node.find_all_next()


def _drop_front_matter_teaser_figures(container: Tag, publisher: str) -> None:
    abstract_anchor = _first_abstract_node(container)
    if abstract_anchor is None:
        return
    for node in list(container.find_all("figure")):
        if isinstance(node, Tag) and _is_front_matter_teaser_figure(node, publisher=publisher, abstract_anchor=abstract_anchor):
            node.decompose()


def _drop_table_blocks(container: Tag) -> None:
    for node in list(_table_like_nodes(container)):
        if isinstance(node, Tag):
            node.decompose()


def _figure_like_nodes(container: Tag) -> list[Tag]:
    table_nodes = _table_like_nodes(container)
    abstract_anchor = _first_abstract_node(container)
    nodes: list[Tag] = []
    for selector in (".figure-wrap", "figure"):
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag):
                continue
            if any(
                match is table_node or _is_descendant(match, table_node) or _is_descendant(table_node, match)
                for table_node in table_nodes
            ):
                continue
            if _is_front_matter_teaser_figure(match, publisher="science", abstract_anchor=abstract_anchor):
                continue
            if any(token in _ancestor_identity_text(match) for token in BACK_MATTER_TOKENS + ANCILLARY_TOKENS):
                continue
            if match.find("table") is not None:
                continue
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _table_cell_data(cell: Tag) -> dict[str, Any]:
    rowspan_text = normalize_text(str(cell.get("rowspan") or "1")) or "1"
    colspan_text = normalize_text(str(cell.get("colspan") or "1")) or "1"
    try:
        rowspan = max(1, int(rowspan_text))
    except ValueError:
        rowspan = 1
    try:
        colspan = max(1, int(colspan_text))
    except ValueError:
        colspan = 1
    return {
        "text": _render_table_inline_text(cell),
        "is_header": normalize_text(cell.name or "").lower() == "th",
        "rowspan": rowspan,
        "colspan": colspan,
    }


def _table_rows(table: Tag) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [cell for cell in row.find_all(["th", "td"], recursive=False) if isinstance(cell, Tag)]
        if not cells:
            cells = [cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
        if not cells:
            continue
        rows.append([_table_cell_data(cell) for cell in cells])
    return rows


def _table_header_row_count(table: Tag, rows: list[list[dict[str, Any]]]) -> int:
    thead = table.find("thead")
    if isinstance(thead, Tag):
        return len([row for row in thead.find_all("tr") if isinstance(row, Tag)])
    leading_all_header_rows = 0
    for row in rows:
        if row and all(cell.get("is_header") for cell in row):
            leading_all_header_rows += 1
            continue
        break
    if leading_all_header_rows:
        return leading_all_header_rows
    if rows and rows[0] and any(cell.get("is_header") for cell in rows[0]):
        return 1
    return 0


def _expanded_table_matrix(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]] | None:
    if not rows:
        return None
    grid: dict[tuple[int, int], dict[str, Any]] = {}
    max_width = 0

    for row_index, row in enumerate(rows):
        col_index = 0
        for cell in row:
            while (row_index, col_index) in grid:
                col_index += 1
            rowspan = max(1, int(cell.get("rowspan") or 1))
            colspan = max(1, int(cell.get("colspan") or 1))
            for row_offset in range(rowspan):
                for col_offset in range(colspan):
                    grid[(row_index + row_offset, col_index + col_offset)] = {
                        "text": cell.get("text") or "",
                        "is_header": bool(cell.get("is_header")),
                        "rowspan": 1,
                        "colspan": 1,
                    }
            col_index += colspan
            max_width = max(max_width, col_index)

    if max_width <= 0:
        return None

    expanded_rows: list[list[dict[str, Any]]] = []
    for row_index in range(len(rows)):
        expanded_row: list[dict[str, Any]] = []
        for col_index in range(max_width):
            cell = grid.get((row_index, col_index))
            if cell is None:
                return None
            expanded_row.append(cell)
        expanded_rows.append(expanded_row)
    return expanded_rows


def _flatten_table_header_rows(rows: list[list[dict[str, Any]]]) -> list[str]:
    if not rows:
        return []
    width = len(rows[0])
    headers: list[str] = []
    for col_index in range(width):
        parts: list[str] = []
        for row in rows:
            if col_index >= len(row):
                return []
            text = normalize_text(str(row[col_index].get("text") or ""))
            if not text:
                continue
            if not parts or text != parts[-1]:
                parts.append(text)
        headers.append(" / ".join(parts) or f"Column {col_index + 1}")
    return headers


def _table_headers_and_data(table: Tag) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
    return _shared_table_headers_and_data(table, render_inline_text=_render_table_inline_text)


def _escape_markdown_table_cell(text: str) -> str:
    return normalize_text(text).replace("|", r"\|")


def _render_aligned_markdown_table(matrix: list[list[str]]) -> list[str]:
    if not matrix:
        return []

    width = max(len(row) for row in matrix)
    normalized_rows = [row + [""] * max(0, width - len(row)) for row in matrix]
    escaped_rows = [[_escape_markdown_table_cell(cell) for cell in row] for row in normalized_rows]
    column_widths = [
        max(3, max(len(row[index]) for row in escaped_rows))
        for index in range(width)
    ]

    def format_row(row: list[str]) -> str:
        padded = [f" {cell.ljust(column_widths[index])} " for index, cell in enumerate(row)]
        return "|" + "|".join(padded) + "|"

    header = format_row(escaped_rows[0])
    separator = "|" + "|".join(f" {'-' * column_widths[index]} " for index in range(width)) + "|"
    body = [format_row(row) for row in escaped_rows[1:]]
    return [header, separator, *body]


def _render_table_markdown(table_node: Tag, *, label: str, caption: str) -> str:
    return _shared_render_table_markdown(
        table_node,
        label=label,
        caption=caption,
        render_inline_text=_render_table_inline_text,
    )


def _table_placeholder(index: int) -> str:
    return _shared_table_placeholder(index)


def _normalize_table_blocks(container: Tag) -> list[dict[str, str]]:
    soup = _soup_root(container)
    if soup is None:
        return []

    entries: list[dict[str, str]] = []
    for node in _table_like_nodes(container):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        label = _caption_label(node, kind="Table")
        caption = _table_caption_text(node, label)
        rendered_markdown = _render_table_markdown(node, label=label, caption=caption)
        if not rendered_markdown:
            continue
        placeholder = _table_placeholder(len(entries) + 1)
        block = soup.new_tag("p")
        block.string = placeholder
        node.replace_with(block)
        entries.append({"placeholder": placeholder, "markdown": rendered_markdown})
    return entries


def _normalize_figure_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    for node in _figure_like_nodes(container):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        label = _caption_label(node, kind="Figure")
        caption = _strip_caption_label(_caption_text(node), label)
        if not caption and label == "Figure":
            continue
        block = soup.new_tag("p")
        block.string = f"**{label}** {caption}".strip()
        node.replace_with(block)


def _move_wiley_abbreviations_to_end(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    headings = [
        node
        for node in container.find_all(re.compile(r"^h[1-6]$"))
        if _normalize_heading(_short_text(node)) == "abbreviations"
    ]
    if not headings:
        return

    heading = headings[0]
    parent = heading.parent if isinstance(heading.parent, Tag) else None
    if parent is None:
        return
    glossary = heading.find_next_sibling()
    if not isinstance(glossary, Tag) or "list-paired" not in node_identity_text(glossary):
        return

    appendix = soup.new_tag("section")
    appendix["class"] = ["article-section__content", "article-section__appendix"]
    appendix_heading = soup.new_tag("h2")
    appendix_heading.string = "Abbreviations"
    appendix.append(appendix_heading)
    glossary_pairs: list[tuple[str, str]] = []
    for row in glossary.select("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [cell for cell in row.find_all(["th", "td"], recursive=False) if isinstance(cell, Tag)]
        if len(cells) < 2:
            cells = [cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
        if len(cells) < 2:
            continue
        term = _short_text(cells[0])
        expansion = _short_text(cells[1])
        if term and expansion:
            glossary_pairs.append((term, expansion))
    if glossary_pairs:
        for term, expansion in glossary_pairs:
            _append_text_block(appendix, f"{term}: {expansion}", soup=soup)
        glossary.decompose()
    else:
        appendix.append(glossary.extract())

    target_parent = parent if parent.parent is not None else container
    heading.extract()
    if not _short_text(parent):
        parent.decompose()

    insert_before: Tag | None = None
    for child in target_parent.find_all(recursive=False):
        if child is appendix or not isinstance(child, Tag):
            continue
        child_heading = child.find(re.compile(r"^h[1-6]$"))
        child_heading_text = _short_text(child_heading) if isinstance(child_heading, Tag) else ""
        if (
            any(token in node_identity_text(child) for token in BACK_MATTER_TOKENS)
            or _heading_category("h2", child_heading_text) == "references_or_back_matter"
        ):
            insert_before = child
            break

    if insert_before is not None:
        insert_before.insert_before(appendix)
    else:
        target_parent.append(appendix)


def _normalize_special_blocks(container: Tag, publisher: str) -> list[dict[str, str]]:
    _drop_promotional_blocks(container, publisher)
    _normalize_abstract_blocks(container)
    _drop_front_matter_teaser_figures(container, publisher)
    _normalize_display_formula_blocks(container)
    _normalize_inline_math_nodes(container)
    table_entries = _normalize_table_blocks(container)
    _normalize_figure_blocks(container)
    _normalize_non_table_inline_blocks(container)
    profile = _publisher_profile(publisher)
    if profile.dom_postprocess is not None:
        profile.dom_postprocess(container)
    return table_entries


def extract_page_title(soup: BeautifulSoup) -> str | None:
    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text((getattr(node, "attrs", None) or {}).get("content", ""))
        elif node.name == "h1":
            title = _render_non_table_inline_text(node)
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def _ancestor_identity_text(node: Tag | None) -> str:
    if node is None:
        return ""
    values: list[str] = []
    current = node
    depth = 0
    while current is not None and depth < 6:
        values.append(node_identity_text(current))
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
        depth += 1
    return " ".join(value for value in values if value).lower()


def _looks_like_front_matter_paragraph(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if title and lowered == normalize_text(title).lower():
        return True
    if lowered in FRONT_MATTER_EXACT_TEXTS:
        return True
    if "authors info" in lowered or "affiliations" in lowered:
        return True
    if len(normalized) <= 80 and normalized.upper() == normalized and len(normalized.split()) <= 5:
        return True
    if lowered.startswith("by ") and _sentence_count(normalized) <= 1:
        return True
    if any(pattern.match(normalized) for pattern in FRONT_MATTER_LINE_PATTERNS):
        return True
    return lowered in {"science", "pnas", "wiley interdisciplinary reviews"}


def _looks_like_access_gate_text(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(pattern in lowered for pattern in PAYWALL_PATTERNS):
        return True
    return any(
        pattern in lowered
        for pattern in (
            "get access",
            "sign in to access",
            "view access options",
            "access provided by",
            "institutional login",
            "purchase article",
        )
    )


def _markdown_heading_info(block: str) -> tuple[int, str] | None:
    stripped = block.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s*(.*)$", stripped)
    if not match:
        return None
    return len(match.group(1)), normalize_text(match.group(2))


def _looks_like_post_content_noise_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(token in lowered for token in PROMO_BLOCK_TOKENS) or lowered == "learn more":
        return True
    if lowered in POST_CONTENT_BREAK_TEXTS:
        return True
    if any(lowered.startswith(prefix) for prefix in POST_CONTENT_BREAK_PREFIXES):
        return True
    return any(token in lowered for token in POST_CONTENT_BREAK_TOKENS)


def _looks_like_markdown_auxiliary_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if lowered == "$$":
        return True
    return lowered.startswith("**equation") or lowered.startswith("**figure") or lowered.startswith("**table")


def _is_descendant(node: Tag, candidate_ancestor: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if current is candidate_ancestor:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _dedupe_top_level_nodes(nodes: list[Tag]) -> list[Tag]:
    deduped: list[Tag] = []
    seen: set[int] = set()
    for node in nodes:
        if id(node) in seen:
            continue
        if any(_is_descendant(node, existing) for existing in deduped):
            continue
        deduped = [existing for existing in deduped if not _is_descendant(existing, node)]
        deduped.append(node)
        seen.add(id(node))
    return deduped


def _has_selector_descendant(node: Tag, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        try:
            if node.select_one(selector) is not None:
                return True
        except Exception:
            continue
    return False


def _container_completeness_score(node: Tag) -> int:
    score = 0
    if isinstance(node.find("h1"), Tag) or normalize_text(node.name or "").lower() == "h1":
        score += 40
    if _abstract_nodes(node):
        score += 40
    if _looks_like_explicit_body_container(node) or _has_selector_descendant(node, CONTENT_BODY_SELECTORS):
        score += 40
    if normalize_text(node.name or "").lower() == "article":
        score += 10
    if normalize_text(node.name or "").lower() == "main":
        score += 5
    return score


def _prefer_complete_ancestor(node: Tag) -> Tag:
    best = node
    best_key = (_container_completeness_score(node), score_container(node))
    current = node.parent if isinstance(node.parent, Tag) else None
    depth = 0
    while isinstance(current, Tag) and depth < 8:
        current_key = (_container_completeness_score(current), score_container(current))
        if current_key > best_key:
            best = current
            best_key = current_key
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return best


def _nodes_from_selectors(container: Tag, selectors: tuple[str, ...]) -> list[Tag]:
    nodes: list[Tag] = []
    for selector in selectors:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _data_availability_node_score(node: Tag) -> int:
    score = 0
    identity = _ancestor_identity_text(node)
    node_id = normalize_text(str((getattr(node, "attrs", None) or {}).get("id") or "")).lower()
    if node_id == "data-availability":
        score += 120
    if normalize_text(node.name or "").lower() == "section":
        score += 10
    if any(token in identity for token in BODY_CONTAINER_TOKENS):
        score += 40
    if any(token in identity for token in DATA_AVAILABILITY_TOKENS):
        score += 20
    if any(token in identity for token in ANCILLARY_TOKENS):
        score -= 60
    if any(token in identity for token in ("collateral", "tabpanel", "tab-panel", "tab_panel", "info-panel", "info_panel")):
        score -= 120
    return score


def _select_data_availability_nodes(container: Tag, body_nodes: list[Tag]) -> list[Tag]:
    chosen_by_text: dict[str, tuple[int, int, Tag]] = {}
    for index, node in enumerate(_nodes_from_selectors(container, CONTENT_DATA_AVAILABILITY_SELECTORS)):
        if any(_is_descendant(node, body_node) for body_node in body_nodes):
            continue
        text_key = normalize_text(node.get_text(" ", strip=True)).lower()
        if not text_key:
            continue
        candidate = (_data_availability_node_score(node), index, node)
        current = chosen_by_text.get(text_key)
        if current is None or candidate[0] > current[0]:
            chosen_by_text[text_key] = candidate
    return _dedupe_top_level_nodes(
        [entry[2] for entry in sorted(chosen_by_text.values(), key=lambda entry: entry[1])]
    )


def _select_content_nodes(container: Tag) -> list[Tag]:
    selected: list[Tag] = []
    title_node = container.find("h1")
    if isinstance(title_node, Tag):
        selected.append(title_node)

    abstract_nodes = _nodes_from_selectors(container, CONTENT_ABSTRACT_SELECTORS)
    body_nodes = _nodes_from_selectors(container, CONTENT_BODY_SELECTORS)
    data_availability_nodes = _select_data_availability_nodes(container, body_nodes)
    selected.extend(abstract_nodes)
    selected.extend(body_nodes)
    selected.extend(data_availability_nodes)

    return _dedupe_top_level_nodes(selected)


def _content_fragment_html(container: Tag) -> str:
    content_nodes = _select_content_nodes(container)
    if not content_nodes:
        return str(container)
    return "<div>" + "".join(str(node) for node in content_nodes) + "</div>"


def _strip_heading_terminal_punctuation(heading_text: str) -> str:
    normalized = normalize_text(heading_text)
    if normalized.endswith("."):
        return normalized[:-1].rstrip()
    return normalized


def _inline_figure_markdown_entries(
    figure_assets: list[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for asset in figure_assets or []:
        url = normalize_text(
            str(
                asset.get("path")
                or asset.get("full_size_url")
                or asset.get("url")
                or asset.get("preview_url")
                or asset.get("source_url")
                or asset.get("original_url")
                or ""
            )
        )
        if not url:
            continue
        aliases: list[str] = []
        for field in ("full_size_url", "url", "preview_url", "source_url", "original_url", "path"):
            candidate = normalize_text(str(asset.get(field) or ""))
            if candidate and candidate not in aliases:
                aliases.append(candidate)
        entries.append(
            {
                "url": url,
                "heading": normalize_text(str(asset.get("heading") or "Figure")) or "Figure",
                "label_key": _canonical_figure_label(
                    normalize_text(str(asset.get("heading") or ""))
                    or normalize_text(str(asset.get("caption") or ""))
                )
                or "",
                "aliases": "\n".join(aliases),
            }
        )
    return entries


def _canonical_figure_label(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    match = FIGURE_LABEL_PATTERN.search(normalized)
    if not match:
        return None
    return f"figure {match.group(1).lower()}"


def _inject_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    publisher: str,
) -> str:
    entries = _inline_figure_markdown_entries(figure_assets)
    if not entries:
        return markdown_text
    has_labeled_entries = any(entry.get("label_key") for entry in entries)

    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    if not blocks:
        return markdown_text

    injected: list[str] = []
    figure_index = 0
    used_entry_indexes: set[int] = set()
    indexed_entries_by_label: dict[str, list[int]] = {}
    indexed_entries_by_url: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        label_key = normalize_text(entry.get("label_key") or "").lower()
        if label_key:
            indexed_entries_by_label.setdefault(label_key, []).append(index)
        for candidate in normalize_text(entry.get("aliases") or "").split("\n"):
            normalized_candidate = normalize_text(candidate)
            if normalized_candidate:
                indexed_entries_by_url.setdefault(normalized_candidate, []).append(index)

    def take_entry(index: int) -> dict[str, str] | None:
        nonlocal figure_index
        if index in used_entry_indexes:
            return None
        used_entry_indexes.add(index)
        if index >= figure_index:
            figure_index = index + 1
        return entries[index]

    def take_entry_for_label(label_key: str | None) -> dict[str, str] | None:
        nonlocal figure_index
        normalized_label = normalize_text(label_key or "").lower()
        if normalized_label and has_labeled_entries:
            for index in indexed_entries_by_label.get(normalized_label, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
            return None
        while figure_index < len(entries):
            index = figure_index
            figure_index += 1
            entry = take_entry(index)
            if entry is not None:
                return entry
        return None

    def take_entry_for_image(alt_text: str | None, url: str | None) -> dict[str, str] | None:
        normalized_url = normalize_text(url)
        if normalized_url:
            for index in indexed_entries_by_url.get(normalized_url, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
        return take_entry_for_label(_canonical_figure_label(normalize_text(alt_text or "")))

    for block in blocks:
        normalized_block = normalize_text(block)
        image_match = MARKDOWN_IMAGE_BLOCK_PATTERN.match(normalized_block)
        if image_match:
            alt_text = normalize_text(image_match.group(1))
            current_url = normalize_text(image_match.group(2))
            entry = take_entry_for_image(alt_text, current_url)
            if entry is not None:
                heading = alt_text or normalize_text(entry.get("heading") or "Figure") or "Figure"
                injected.append(f"![{heading}]({entry['url']})")
            else:
                injected.append(block)
            continue
        match = MARKDOWN_FIGURE_BLOCK_PATTERN.match(normalized_block)
        if match:
            label = match.group(1).rstrip(".")
            entry = take_entry_for_label(_canonical_figure_label(label))
            if entry is not None:
                image_block = f"![{label}]({entry['url']})"
                if not injected or normalize_text(injected[-1]) != image_block:
                    injected.append(image_block)
                injected.append(block)
                continue
        injected.append(block)
    return clean_markdown(
        "\n\n".join(injected),
        noise_profile=_noise_profile_for_publisher(publisher),
    )


def rewrite_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    publisher: str,
) -> str:
    return _shared_rewrite_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def _inject_inline_table_blocks(
    markdown_text: str,
    *,
    table_entries: list[Mapping[str, str]] | None,
    publisher: str,
) -> str:
    return _shared_inject_inline_table_blocks(
        markdown_text,
        table_entries=table_entries,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def _known_abstract_block_texts(container: Tag) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for node in _abstract_nodes(container):
        for block in _abstract_block_texts(node):
            normalized = normalize_text(normalize_markdown_text(block))
            if normalized and normalized not in seen:
                texts.append(normalized)
                seen.add(normalized)
    return texts


def _block_matches_known_abstract_text(block: str, abstract_block_texts: list[str]) -> bool:
    normalized_block = normalize_text(normalize_markdown_text(block))
    if not normalized_block:
        return False
    for known in abstract_block_texts:
        if not known:
            continue
        if normalized_block == known or normalized_block in known or known in normalized_block:
            return True
    return False


def _normalize_equation_markdown_blocks(markdown_text: str) -> str:
    text = re.sub(r"(\S)(\*\*Equation\s+\d+[A-Za-z]?\.\*\*)", r"\1\n\n\2", markdown_text)
    text = re.sub(r"(?<=\S)(\$\$)", r"\n\n\1", text)

    def normalize_display_math(match: re.Match[str]) -> str:
        body = match.group(1).strip()
        return f"$$\n{body}\n$$"

    text = re.sub(r"\$\$\s*(.+?)\s*\$\$", normalize_display_math, text, flags=re.DOTALL)
    return re.sub(r"(?<=\$\$)(?=[^\s\n])", "\n\n", text)


def _merge_science_citation_italics(markdown_text: str) -> str:
    token_pattern = r"(?:\d+[A-Za-z]*|[A-Za-z]+\d+[A-Za-z0-9]*)"
    patterns = (
        re.compile(rf"\*(?P<left>{token_pattern})\*\*(?P<sep>[–,;])\*\s*\*(?P<right>{token_pattern})\*"),
        re.compile(rf"\*(?P<left>{token_pattern})\*(?P<sep>\s*[–,;]\s*)\*(?P<right>{token_pattern})\*"),
    )

    def render_separator(separator_text: str) -> str:
        separator = normalize_text(separator_text)
        if separator in {",", ";"}:
            return f"{separator} "
        return separator

    merged = markdown_text
    changed = True
    while changed:
        changed = False
        for pattern in patterns:
            merged, replacements = pattern.subn(
                lambda match: (
                    f"*{match.group('left')}{render_separator(match.group('sep'))}{match.group('right')}*"
                ),
                merged,
            )
            changed = changed or replacements > 0
    return merged


def _normalize_browser_workflow_markdown(markdown_text: str, *, publisher: str) -> str:
    return _shared_normalize_browser_workflow_markdown(
        markdown_text,
        markdown_postprocess=_publisher_profile(publisher).markdown_postprocess,
    )


def _postprocess_browser_workflow_markdown(
    markdown_text: str,
    *,
    title: str | None,
    publisher: str,
    figure_assets: list[Mapping[str, Any]] | None = None,
    table_entries: list[Mapping[str, str]] | None = None,
    abstract_block_texts: list[str] | None = None,
) -> str:
    markdown_text = _normalize_browser_workflow_markdown(markdown_text, publisher=publisher)
    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    kept: list[str] = []
    normalized_title = normalize_text(title or "")
    normalized_title_lower = normalized_title.lower()
    known_abstract_blocks = [normalize_text(text) for text in abstract_block_texts or [] if normalize_text(text)]
    title_kept = False
    started_content = False
    in_front_matter = False
    in_abstract = False
    in_back_matter = False
    in_data_availability = False

    for block in blocks:
        heading_info = _markdown_heading_info(block)
        if heading_info is not None:
            level, heading_text = heading_info
            normalized_heading = _normalize_heading(heading_text)
            if normalized_title and normalized_heading == normalized_title_lower:
                if not title_kept:
                    kept.append(f"# {normalized_title}")
                    title_kept = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                continue

            category = _heading_category(f"h{min(level, 6)}", heading_text, title=normalized_title or None)
            if category == "front_matter":
                in_front_matter = True
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                continue
            if category in {"references_or_back_matter", "ancillary"}:
                if category == "ancillary" and started_content:
                    break
                in_front_matter = False
                in_abstract = False
                in_back_matter = category == "references_or_back_matter"
                in_data_availability = False
                continue
            if category == "abstract":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                kept.append(block)
                started_content = True
                in_front_matter = False
                in_abstract = True
                in_back_matter = False
                in_data_availability = False
                continue
            if category == "data_availability":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                cleaned_heading = _strip_heading_terminal_punctuation(heading_text)
                kept.append(f"{'#' * level} {cleaned_heading}")
                started_content = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = True
                continue
            if category == "body_heading":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                cleaned_heading = _strip_heading_terminal_punctuation(heading_text)
                kept.append(f"{'#' * level} {cleaned_heading}")
                started_content = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                continue

        normalized_block = normalize_text(block)
        if not normalized_block:
            continue
        is_auxiliary_block = _looks_like_markdown_auxiliary_block(normalized_block)
        if _looks_like_post_content_noise_block(normalized_block):
            if started_content:
                break
            continue
        if in_front_matter:
            continue
        if in_abstract:
            if (
                known_abstract_blocks
                and _is_substantial_prose(normalized_block)
                and not is_auxiliary_block
                and not _block_matches_known_abstract_text(block, known_abstract_blocks)
            ):
                kept.append("## Main Text")
                in_abstract = False
            else:
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                kept.append(block)
                started_content = True
                continue
        if in_back_matter:
            continue
        if in_data_availability:
            if not title_kept and normalized_title:
                kept.insert(0, f"# {normalized_title}")
                title_kept = True
            kept.append(block)
            started_content = True
            continue
        if _looks_like_access_gate_text(normalized_block):
            if started_content:
                break
            continue
        if not started_content and is_auxiliary_block:
            continue
        if not is_auxiliary_block and _looks_like_front_matter_paragraph(normalized_block, title=normalized_title or None):
            continue
        if not started_content and not is_auxiliary_block and not _is_substantial_prose(normalized_block):
            continue
        if not title_kept and normalized_title:
            kept.insert(0, f"# {normalized_title}")
            title_kept = True
        kept.append(block)
        started_content = True

    if not kept and normalized_title:
        kept.append(f"# {normalized_title}")
    elif normalized_title and not any(
        (_markdown_heading_info(block) or (0, ""))[1].lower() == normalized_title_lower for block in kept
    ):
        kept.insert(0, f"# {normalized_title}")
    cleaned = clean_markdown(
        "\n\n".join(kept),
        noise_profile=_noise_profile_for_publisher(publisher),
    )
    cleaned = _normalize_browser_workflow_markdown(cleaned, publisher=publisher)
    cleaned = _inject_inline_table_blocks(cleaned, table_entries=table_entries, publisher=publisher)
    cleaned = _normalize_browser_workflow_markdown(cleaned, publisher=publisher)
    return _inject_inline_figure_links(
        cleaned,
        figure_assets=figure_assets,
        publisher=publisher,
    )


def _container_has_explicit_body_container(container: Tag) -> bool:
    if _looks_like_explicit_body_container(container):
        return True
    return any(_looks_like_explicit_body_container(node) for node in container.find_all(True))


def _iter_html_blocks(container: Tag) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    seen_markers: set[int] = set()
    if _looks_like_explicit_body_container(container):
        blocks.append({"kind": "marker", "node": container, "text": ""})
        seen_markers.add(id(container))

    for node in container.find_all(True):
        if id(node) in seen_markers:
            continue
        if _looks_like_explicit_body_container(node):
            blocks.append({"kind": "marker", "node": node, "text": ""})
            seen_markers.add(id(node))
            continue

        name = normalize_text(node.name or "").lower()
        if not name:
            continue
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "heading", "node": node, "text": text})
            continue
        if name in {"figure", "table", "figcaption"}:
            text = normalize_text(node.get_text(" ", strip=True))
            blocks.append({"kind": "figure_or_table", "node": node, "text": text})
            continue
        if name == "p":
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "paragraph", "node": node, "text": text})
            continue
        if name == "div" and normalize_text(str((getattr(node, "attrs", None) or {}).get("role") or "")).lower() == "paragraph":
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "paragraph", "node": node, "text": text})
            continue
        if name == "li":
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "paragraph", "node": node, "text": text})
    return blocks


def _classify_html_paragraph(
    node: Tag,
    text: str,
    *,
    title: str | None = None,
    in_back_matter: bool = False,
    in_abstract: bool = False,
    in_data_availability: bool = False,
) -> str:
    if in_back_matter:
        return "references_or_back_matter"
    if in_abstract:
        return "abstract"
    if in_data_availability:
        return "data_availability"

    identity = _ancestor_identity_text(node)
    lowered = normalize_text(text).lower()
    if any(token in identity for token in BACK_MATTER_TOKENS):
        return "references_or_back_matter"
    if any(token in identity for token in DATA_AVAILABILITY_TOKENS):
        return "data_availability"
    if any(token in identity for token in ABSTRACT_TOKENS):
        return "abstract"
    if any(token in identity for token in ANCILLARY_TOKENS):
        return "ancillary"
    if _looks_like_access_gate_text(lowered):
        return "ancillary"
    if _looks_like_front_matter_paragraph(text, title=title):
        return "front_matter"
    if _is_substantial_prose(text):
        return "body_paragraph"
    return "ancillary"


def _run_candidate_barrier(kind: str) -> bool:
    return kind in {"front_matter", "abstract", "references_or_back_matter", "ancillary", "data_availability"}


def _analyze_html_structure(
    html_text: str,
    *,
    provider: str | None,
    title: str | None,
    metadata: Mapping[str, Any] | None,
    final_url: str | None,
) -> tuple[StructuredBodyAnalysis, str | None, int | None]:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=_is_narrative_article_type(_extract_article_type(metadata, provider=provider, html_text=html_text))
    )
    if BeautifulSoup is None:
        return analysis, None, None

    soup = BeautifulSoup(html_text, choose_parser())
    container = select_best_container(soup, provider or "html_generic")
    if container is None:
        return analysis, None, None

    clean_container(container, provider or "html_generic")
    analysis.explicit_body_container = _container_has_explicit_body_container(container)
    container_text = normalize_text(container.get_text(" ", strip=True))
    page_text = _normalized_page_text(html_text)
    analysis.page_has_paywall_text = _contains_pattern(page_text, PAYWALL_PATTERNS)
    analysis.container_has_paywall_text = _contains_pattern(container_text, PAYWALL_PATTERNS)

    blocks = _iter_html_blocks(container)
    body_chunks: list[str] = []
    in_abstract = False
    in_back_matter = False
    in_data_availability = False
    abstract_seen = False
    body_heading_after_abstract = False
    current_run_paragraphs = 0
    current_run_chars = 0

    for block in blocks:
        if block["kind"] == "marker":
            analysis.explicit_body_container = True
            continue

        node = block["node"]
        text = block["text"]
        if block["kind"] == "heading":
            category = _heading_category(normalize_text(node.name or "").lower(), text, title=title)
        elif block["kind"] == "figure_or_table":
            category = "figure_or_table"
        else:
            category = _classify_html_paragraph(
                node,
                text,
                title=title,
                in_back_matter=in_back_matter,
                in_abstract=in_abstract,
                in_data_availability=in_data_availability,
            )

        if category == "abstract":
            abstract_seen = True
            in_abstract = True
            in_back_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "references_or_back_matter":
            in_back_matter = True
            in_abstract = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "data_availability":
            in_data_availability = True
            in_abstract = False
            in_back_matter = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "front_matter":
            in_abstract = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "ancillary":
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "body_heading":
            in_abstract = False
            in_back_matter = False
            in_data_availability = False
            if abstract_seen:
                body_heading_after_abstract = True
            continue
        if category == "figure_or_table":
            continue
        if category != "body_paragraph":
            if _run_candidate_barrier(category):
                current_run_paragraphs = 0
                current_run_chars = 0
            continue

        in_abstract = False
        in_back_matter = False
        in_data_availability = False
        analysis.body_paragraph_count += 1
        body_chunks.append(text)
        current_run_paragraphs += 1
        current_run_chars += len(normalize_text(text))
        analysis.body_run_paragraph_count = max(analysis.body_run_paragraph_count, current_run_paragraphs)
        analysis.body_run_char_count = max(analysis.body_run_char_count, current_run_chars)
        if abstract_seen and body_heading_after_abstract:
            analysis.post_abstract_body_run = True

    analysis.body_candidate_text = "\n\n".join(body_chunks)
    analysis.paywall_text_outside_body_ignored = (
        analysis.page_has_paywall_text and not analysis.container_has_paywall_text and analysis.body_paragraph_count > 0
    )
    analysis.paywall_gate_detected = (
        analysis.body_paragraph_count == 0
        and (analysis.container_has_paywall_text or _final_url_looks_like_access_page(final_url))
    )
    return analysis, container.name, len(" ".join(container.stripped_strings))


def _analyze_markdown_structure(
    markdown_text: str,
    *,
    metadata: Mapping[str, Any] | None,
    title: str | None,
) -> StructuredBodyAnalysis:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=_is_narrative_article_type(_extract_article_type(metadata))
    )
    blocks = [normalize_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    in_abstract = False
    in_back_matter = False
    in_data_availability = False
    abstract_seen = False
    body_heading_after_abstract = False
    current_run_paragraphs = 0
    current_run_chars = 0
    body_chunks: list[str] = []

    for block in blocks:
        stripped = block.strip()
        if stripped.startswith("#"):
            match = re.match(r"^(#+)\s*(.*)$", stripped)
            heading = normalize_text(match.group(2) if match else stripped)
            level = len(match.group(1)) if match else 2
            category = _heading_category(f"h{min(level, 6)}", heading, title=title)
        else:
            category = "body_paragraph" if _is_substantial_prose(block) and not _looks_like_front_matter_paragraph(block, title=title) else "front_matter"
            if in_back_matter:
                category = "references_or_back_matter"
            elif in_data_availability:
                category = "data_availability"
            elif in_abstract:
                category = "abstract"
            elif _looks_like_access_gate_text(block):
                category = "ancillary"

        if category == "abstract":
            abstract_seen = True
            in_abstract = True
            in_back_matter = False
            in_data_availability = False
            current_run_paragraphs = 0
            current_run_chars = 0
            continue
        if category == "references_or_back_matter":
            in_back_matter = True
            in_abstract = False
            in_data_availability = False
            current_run_paragraphs = 0
            current_run_chars = 0
            continue
        if category == "data_availability":
            in_data_availability = True
            in_abstract = False
            in_back_matter = False
            current_run_paragraphs = 0
            current_run_chars = 0
            continue
        if category == "front_matter":
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "ancillary":
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "body_heading":
            in_abstract = False
            in_back_matter = False
            in_data_availability = False
            if abstract_seen:
                body_heading_after_abstract = True
            continue
        if category != "body_paragraph":
            continue

        in_abstract = False
        in_back_matter = False
        in_data_availability = False
        analysis.body_paragraph_count += 1
        body_chunks.append(block)
        current_run_paragraphs += 1
        current_run_chars += len(normalize_text(block))
        analysis.body_run_paragraph_count = max(analysis.body_run_paragraph_count, current_run_paragraphs)
        analysis.body_run_char_count = max(analysis.body_run_char_count, current_run_chars)
        if abstract_seen and body_heading_after_abstract:
            analysis.post_abstract_body_run = True

    analysis.body_candidate_text = "\n\n".join(body_chunks)
    return analysis


def _structure_accepts_fulltext(analysis: StructuredBodyAnalysis) -> bool:
    if analysis.explicit_body_container and analysis.body_paragraph_count >= 1:
        return True
    if analysis.post_abstract_body_run:
        return True
    if analysis.body_run_paragraph_count >= 3:
        return True
    if analysis.narrative_article_type and (
        analysis.body_run_paragraph_count >= 2
        or (analysis.explicit_body_container and analysis.body_run_char_count >= NARRATIVE_BODY_RUN_MIN_CHARS)
    ):
        return True
    return False


def availability_failure_message(diagnostics: FulltextAvailabilityDiagnostics) -> str:
    return _shared_availability_failure_message(diagnostics)


def _dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _diagnostics_content_kind(*, body_ok: bool, has_abstract: bool) -> str:
    if body_ok:
        return "fulltext"
    if has_abstract:
        return "abstract_only"
    return "metadata_only"


def _normalized_text_field(value: Any) -> str:
    return normalize_text(value) if isinstance(value, str) else ""


def _dom_access_hints(
    html_text: str,
    *,
    final_url: str | None,
    metadata: Mapping[str, Any] | None,
) -> tuple[list[str], list[str]]:
    hard_negative_signals: list[str] = []
    abstract_only_hints: list[str] = []
    if BeautifulSoup is None:
        if _final_url_looks_like_access_page(final_url):
            abstract_only_hints.append("access_page_url")
        return _dedupe_signals(hard_negative_signals), _dedupe_signals(abstract_only_hints)

    soup = BeautifulSoup(html_text, choose_parser())
    if soup.select_one(".accessDenialWidget"):
        hard_negative_signals.append("publisher_paywall")
    if _final_url_looks_like_access_page(final_url):
        abstract_only_hints.append("access_page_url")
    for node in soup.select("[data-article-access], [data-article-access-type]"):
        attrs = getattr(node, "attrs", None) or {}
        values = [
            normalize_text(str(attrs.get("data-article-access") or "")),
            normalize_text(str(attrs.get("data-article-access-type") or "")),
        ]
        joined = " ".join(value.lower() for value in values if value)
        if any(token in joined for token in {"abstract", "summary", "preview", "teaser", "limited"}):
            abstract_only_hints.append("data_article_access_abstract")
        if any(token in joined for token in {"denied", "subscription", "restricted", "paywall"}):
            hard_negative_signals.append("publisher_paywall")
    for node in soup.select("[itemprop='isAccessibleForFree']"):
        value = normalize_text(str((getattr(node, "attrs", None) or {}).get("content") or node.get_text(" ", strip=True))).lower()
        if value in {"false", "0", "no"}:
            hard_negative_signals.append("publisher_paywall")
    wt_node = soup.select_one("meta[name='WT.z_cg_type']")
    if wt_node is not None:
        wt_value = normalize_text(str((getattr(wt_node, "attrs", None) or {}).get("content") or "")).lower()
        if "abstract" in wt_value or "summary" in wt_value:
            abstract_only_hints.append("wt_abstract_page_type")
    citation_abstract_url = normalize_text(str((metadata or {}).get("citation_abstract_html_url") or ""))
    citation_fulltext_url = normalize_text(str((metadata or {}).get("citation_fulltext_html_url") or ""))
    normalized_final_url = normalize_text(final_url or "")
    if citation_abstract_url:
        abstract_only_hints.append("citation_abstract_html_url")
        if normalized_final_url and normalized_final_url == citation_abstract_url:
            abstract_only_hints.append("final_url_matches_citation_abstract_html_url")
    if citation_fulltext_url and normalized_final_url and normalized_final_url == citation_fulltext_url:
        hard_negative_signals = [signal for signal in hard_negative_signals if signal != "publisher_paywall"]
    return _dedupe_signals(hard_negative_signals), _dedupe_signals(abstract_only_hints)


def _count_figures_from_html(html_text: str) -> int:
    lowered = html_text.lower()
    if BeautifulSoup is None:
        return lowered.count("<figure")
    soup = BeautifulSoup(html_text, choose_parser())
    figure_count = len(soup.find_all("figure"))
    if figure_count:
        return figure_count
    return len(soup.select(".figure, .figure-wrap, [data-open='viewer']"))


def _parse_aaas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    match = AAAS_DATALAYER_PATTERN.search(html_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def _provider_positive_signals(
    provider: str | None,
    html_text: str,
) -> tuple[list[str], list[str], list[str]]:
    return _profile_positive_signals(provider, html_text)


def assess_html_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
    title: str | None = None,
    response_status: int | None = None,
    requested_url: str | None = None,
    final_url: str | None = None,
    container_tag: str | None = None,
    container_text_length: int | None = None,
) -> FulltextAvailabilityDiagnostics:
    return _shared_assess_html_fulltext_availability(
        markdown_text,
        metadata,
        provider=provider,
        html_text=html_text,
        title=title,
        response_status=response_status,
        requested_url=requested_url,
        final_url=final_url,
        container_tag=container_tag,
        container_text_length=container_text_length,
    )


def assess_plain_text_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    title: str | None = None,
) -> FulltextAvailabilityDiagnostics:
    return _shared_assess_plain_text_fulltext_availability(
        markdown_text,
        metadata,
        title=title,
    )


def assess_structured_article_fulltext_availability(
    article: Any,
    *,
    title: str | None = None,
) -> FulltextAvailabilityDiagnostics:
    return _shared_assess_structured_article_fulltext_availability(article, title=title)


def extract_browser_workflow_markdown(
    html_text: str,
    source_url: str,
    publisher: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    if BeautifulSoup is None:
        raise SciencePnasHtmlFailure("missing_bs4", "BeautifulSoup is required for browser-workflow HTML extraction.")

    soup = BeautifulSoup(html_text, choose_parser())
    title = extract_page_title(soup)
    container = select_best_container(soup, publisher)
    if container is None:
        raise SciencePnasHtmlFailure(
            "article_container_not_found",
            "Could not identify the main article container in publisher HTML.",
        )

    clean_container(container, publisher)
    from .html_assets import extract_figure_assets

    asset_container = copy.deepcopy(container)
    _normalize_abstract_blocks(asset_container)
    _drop_front_matter_teaser_figures(asset_container, publisher)
    _drop_table_blocks(asset_container)
    figure_assets = extract_figure_assets(_content_fragment_html(asset_container), source_url)

    abstract_block_texts = _known_abstract_block_texts(container)
    table_entries = _normalize_special_blocks(container, publisher)
    container_html = _content_fragment_html(container)
    noise_profile = _noise_profile_for_publisher(publisher)
    markdown = clean_markdown(
        extract_article_markdown(
            container_html,
            source_url,
            trafilatura_backend=None,
            noise_profile=noise_profile,
        ),
        noise_profile=noise_profile,
    )
    abstract_markdown = _missing_abstract_markdown(container, markdown, publisher=publisher)
    if abstract_markdown:
        markdown = clean_markdown(f"{abstract_markdown}\n\n{markdown}", noise_profile=noise_profile)
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip() + "\n"
    markdown = _inject_inline_table_blocks(markdown, table_entries=table_entries, publisher=publisher)
    markdown = _postprocess_browser_workflow_markdown(
        markdown,
        title=title,
        publisher=publisher,
        figure_assets=figure_assets,
        table_entries=table_entries,
        abstract_block_texts=abstract_block_texts,
    )

    quality_metadata = dict(metadata or {})
    if title and not quality_metadata.get("title"):
        quality_metadata["title"] = title
    diagnostics = assess_html_fulltext_availability(
        markdown,
        quality_metadata,
        provider=publisher,
        html_text=html_text,
        title=title,
        final_url=source_url,
        container_tag=container.name,
        container_text_length=len(" ".join(container.stripped_strings)),
    )
    if not diagnostics.accepted:
        raise SciencePnasHtmlFailure(diagnostics.reason, availability_failure_message(diagnostics))

    return markdown, {
        "title": title,
        "abstract_text": "\n\n".join(abstract_block_texts) if abstract_block_texts else None,
        "container_tag": container.name,
        "container_text_length": len(" ".join(container.stripped_strings)),
        "availability_diagnostics": diagnostics.to_dict(),
    }


def extract_science_pnas_markdown(
    html_text: str,
    source_url: str,
    publisher: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    return extract_browser_workflow_markdown(
        html_text,
        source_url,
        publisher,
        metadata=metadata,
    )
