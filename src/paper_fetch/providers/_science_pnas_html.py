"""Browser-workflow HTML heuristics built on top of the generic markdown pipeline."""

from __future__ import annotations

import importlib.util
import re
import urllib.parse
from typing import Any, Mapping

from ..metadata_types import ProviderMetadata
from ..utils import normalize_text
from . import html_generic

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

CHALLENGE_PATTERNS = (
    "just a moment",
    "verify you are human",
    "checking your browser",
    "challenge-error-text",
    "attention required",
    "cloudflare",
)
PAYWALL_PATTERNS = (
    "purchase access",
    "institutional access",
    "log in to your account",
    "login to your account",
    "subscribe to continue",
    "access through your institution",
    "rent or buy",
    "purchase this article",
)
NOT_FOUND_PATTERNS = (
    "doi not found",
    "page not found",
    "article not found",
    "content not found",
)
COLLATERAL_HEADING_TITLES = {
    "continue reading",
    "information & authors",
    "metrics & citations",
    "view options",
    "figures",
    "tables",
    "media",
}
SITE_RULES: dict[str, dict[str, Any]] = {
    "science": {
        "candidate_selectors": [
            "article",
            "main article",
            "[role='main'] article",
            ".article",
            ".article__body",
            ".article__fulltext",
            ".article-view",
            "main",
            "[role='main']",
            "#main-content",
            ".main-content",
        ],
        "remove_selectors": [
            "script",
            "style",
            "noscript",
            "iframe",
            "svg",
            "header .social-share",
            ".social-share",
            ".metrics-widget",
            ".article-tools",
            ".related-content",
            ".recommended-articles",
            ".jump-to-nav",
            ".article-access-info",
            ".article-metrics",
            ".tab__nav",
            ".references-tab",
            ".permissions",
            ".toc",
            ".breadcrumbs",
            ".issue-item__citation",
            ".article-header__access",
        ],
        "drop_keywords": {
            "metrics",
            "metric",
            "share",
            "social",
            "recommend",
            "related",
            "citation-tool",
            "toolbar",
            "breadcrumb",
            "download",
            "access-widget",
            "advert",
            "cookie",
            "promo",
            "banner",
            "tab-nav",
            "jump-to",
        },
        "drop_text": {
            "Check for updates",
            "View Metrics",
            "Share",
            "Cite",
            "Permissions",
        },
    },
    "pnas": {
        "candidate_selectors": [
            "article",
            "main article",
            "[role='main'] article",
            ".article",
            ".article__body",
            ".article__fulltext",
            ".core-container",
            ".article-content",
            "main",
            "[role='main']",
            "#main-content",
            ".main-content",
        ],
        "remove_selectors": [
            "script",
            "style",
            "noscript",
            "iframe",
            "svg",
            ".social-share",
            ".article-tools",
            ".metrics-widget",
            ".related-content",
            ".recommended-articles",
            ".tab__nav",
            ".toc",
            ".breadcrumbs",
            ".article__access",
            ".article__footer",
            ".article__reference-links",
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
            "tab-nav",
        },
        "drop_text": {
            "Check for updates",
            "View Metrics",
            "Share",
            "Cite",
        },
    },
    "wiley": {
        "candidate_selectors": [
            "article",
            "main article",
            "[role='main'] article",
            ".article-section__content",
            ".article__body",
            ".article__content",
            ".issue-item__body",
            ".epub-section",
            ".doi-access",
            "main",
            "[role='main']",
            "#main-content",
            ".main-content",
        ],
        "remove_selectors": [
            "script",
            "style",
            "noscript",
            "iframe",
            "svg",
            ".article-tools",
            ".citation-tools",
            ".article-metrics",
            ".social-share",
            ".related-content",
            ".recommended-articles",
            ".epub-reference",
            ".article-section__tableofcontents",
            ".toc",
            ".breadcrumbs",
            ".publicationHistory",
            ".accessDenialWidget",
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
            "rightslink",
        },
        "drop_text": {
            "Check for updates",
            "View Metrics",
            "Share",
            "Cite",
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


class SciencePnasHtmlFailure(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def preferred_html_candidate_from_landing_page(
    publisher: str,
    doi: str,
    landing_page_url: str | None,
) -> str | None:
    candidate = normalize_text(landing_page_url)
    if not candidate:
        return None
    parsed = urllib.parse.urlparse(candidate)
    hostname = normalize_text(parsed.hostname or "").lower()
    allowed_hosts = PUBLISHER_HOSTS.get(publisher, ())
    if parsed.scheme not in {"http", "https"} or not any(
        hostname == token or hostname.endswith(f".{token}")
        for token in allowed_hosts
    ):
        return None
    if normalize_text(urllib.parse.unquote(candidate)).lower().find(doi.lower()) == -1:
        return None
    return candidate


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
    if publisher == "science":
        path_templates = ["/doi/full/{doi}", "/doi/{doi}"]
    elif publisher == "pnas":
        path_templates = ["/doi/{doi}", "/doi/full/{doi}"]
    else:
        path_templates = ["/doi/full/{doi}", "/doi/{doi}"]

    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page(publisher, doi, landing_page_url)
    if preferred_candidate:
        candidates.append(preferred_candidate)
    for base in _publisher_base_urls(publisher, landing_page_url):
        for template in path_templates:
            candidate = f"{base}{template.format(doi=doi)}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def build_pdf_candidates(publisher: str, doi: str, crossref_pdf_url: str | None) -> list[str]:
    candidates: list[str] = []

    def _append(candidate: str | None) -> None:
        normalized = normalize_text(candidate)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    if publisher == "science":
        if crossref_pdf_url:
            _append(crossref_pdf_url)
        path_templates = ["/doi/epdf/{doi}", "/doi/pdf/{doi}", "/doi/pdf/{doi}?download=true"]
        for base in _publisher_base_urls(publisher, crossref_pdf_url):
            for template in path_templates:
                _append(f"{base}{template.format(doi=doi)}")
        return candidates

    if publisher == "pnas":
        if crossref_pdf_url:
            _append(crossref_pdf_url)
        path_templates = ["/doi/epdf/{doi}", "/doi/pdf/{doi}?download=true", "/doi/pdf/{doi}"]
        for base in _publisher_base_urls(publisher, crossref_pdf_url):
            for template in path_templates:
                _append(f"{base}{template.format(doi=doi)}")
        return candidates

    for base in _publisher_base_urls(publisher, None):
        _append(f"{base}/doi/epdf/{doi}")
    _append(crossref_pdf_url)
    for base in _publisher_base_urls(publisher, None):
        _append(f"{base}/doi/pdf/{doi}")
        _append(f"{base}/doi/pdfdirect/{doi}")
        _append(f"{base}/wol1/doi/{doi}/fullpdf")
    return candidates


def extract_pdf_url_from_crossref(metadata: Mapping[str, Any]) -> str | None:
    for item in metadata.get("fulltext_links") or []:
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        if not url:
            continue
        lowered_url = url.lower()
        if any(token in lowered_url for token in PDF_URL_TOKENS) or normalize_text(
            str(item.get("content_type") or "")
        ).lower() == "application/pdf":
            return url
    return None


def looks_like_abstract_redirect(requested_url: str, final_url: str | None) -> bool:
    if not final_url:
        return False
    requested = requested_url.lower()
    final = final_url.lower()
    return "/doi/full/" in requested and "/doi/abs/" in final and requested != final


def detect_html_block(title: str, text: str, response_status: int | None) -> SciencePnasHtmlFailure | None:
    combined = normalize_text(" ".join([title, text])).lower()
    if any(pattern in combined for pattern in CHALLENGE_PATTERNS):
        return SciencePnasHtmlFailure(
            "cloudflare_challenge",
            "Encountered a challenge or CAPTCHA page while loading publisher HTML.",
        )
    if response_status == 404 or any(pattern in combined for pattern in NOT_FOUND_PATTERNS):
        return SciencePnasHtmlFailure("publisher_not_found", "Publisher page was not found for this DOI.")
    if response_status in {401, 402, 403} and not any(pattern in combined for pattern in CHALLENGE_PATTERNS):
        return SciencePnasHtmlFailure("publisher_access_denied", "Publisher denied access to the full-text page.")
    if any(pattern in combined for pattern in PAYWALL_PATTERNS):
        return SciencePnasHtmlFailure("publisher_paywall", "Publisher paywall or access gate detected on the page.")
    return None


def summarize_html(html_text: str, limit: int = 1000) -> str:
    if BeautifulSoup is None:
        return normalize_text(re.sub(r"<[^>]+>", " ", html_text))[:limit]
    soup = BeautifulSoup(html_text, choose_parser())
    return " ".join(soup.stripped_strings)[:limit]


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
    selectors = SITE_RULES[publisher]["candidate_selectors"]
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
    return candidates[0][1]


def node_identity_text(node: Tag) -> str:
    attrs = getattr(node, "attrs", None) or {}
    values: list[str] = []
    node_id = attrs.get("id")
    if node_id:
        values.append(str(node_id))
    for class_name in attrs.get("class", []):
        values.append(str(class_name))
    return " ".join(values).lower()


def should_drop_node(node: Tag, publisher: str) -> bool:
    if node.name in {"script", "style", "noscript", "svg", "iframe", "button", "input", "form"}:
        return True

    identity = node_identity_text(node)
    text = normalize_text(node.get_text(" ", strip=True))
    short_text = len(text) <= 200
    for keyword in SITE_RULES[publisher]["drop_keywords"]:
        if keyword in identity and short_text:
            return True
    if short_text and text in SITE_RULES[publisher]["drop_text"]:
        return True
    if short_text and any(pattern in text.lower() for pattern in {"share this", "view metrics", "article metrics"}):
        return True
    return False


def clean_container(container: Tag, publisher: str) -> Tag:
    for selector in SITE_RULES[publisher]["remove_selectors"]:
        for node in list(container.select(selector)):
            node.decompose()

    for node in list(container.find_all(True)):
        if should_drop_node(node, publisher):
            node.decompose()
    return container


def extract_page_title(soup: BeautifulSoup) -> str | None:
    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text((getattr(node, "attrs", None) or {}).get("content", ""))
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def heading_title(line: str) -> str:
    title = re.sub(r"^#+\s*", "", line).strip()
    title = title.replace("*", "")
    return normalize_text(title).lower()


def markdown_looks_like_fulltext(markdown: str) -> tuple[bool, str]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    heading_lines = [line for line in lines if line.startswith("## ")]
    paragraph_lines = [
        line
        for line in lines
        if not line.startswith("#") and not line.startswith("- ") and not re.match(r"^\d+\.\s", line)
    ]
    has_title = any(line.startswith("# ") for line in lines)
    if not has_title:
        return False, "missing_title"
    if len(paragraph_lines) < 5:
        return False, "insufficient_paragraphs"
    if len(heading_lines) < 1:
        return False, "missing_section_heading"
    substantive_headings = [
        line
        for line in heading_lines
        if heading_title(line) not in {"abstract", "references", *COLLATERAL_HEADING_TITLES}
    ]
    if not substantive_headings:
        return False, "looks_like_abstract_only"
    if len(markdown) < 1200:
        return False, "content_too_short"
    return True, "ok"


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
    container_html = str(container)
    markdown = html_generic.clean_markdown(html_generic.extract_article_markdown(container_html, source_url))
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip() + "\n"

    looks_ok, reason = markdown_looks_like_fulltext(markdown)
    if not looks_ok:
        raise SciencePnasHtmlFailure(reason, "HTML content does not look like a complete full-text article.")

    quality_metadata = dict(metadata or {})
    if title and not quality_metadata.get("title"):
        quality_metadata["title"] = title
    if not html_generic.has_sufficient_article_body(markdown, quality_metadata):
        raise SciencePnasHtmlFailure(
            "content_too_short",
            "HTML extraction did not produce enough article body text.",
        )

    return markdown, {
        "title": title,
        "container_tag": container.name,
        "container_text_length": len(" ".join(container.stripped_strings)),
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
