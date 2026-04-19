"""Publisher profile data and candidate builders for browser-workflow providers."""

from __future__ import annotations

import copy
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..utils import normalize_text

PUBLISHER_HOSTS: dict[str, tuple[str, ...]] = {
    "science": ("www.science.org", "science.org"),
    "pnas": ("www.pnas.org", "pnas.org"),
    "wiley": ("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com"),
}
PUBLISHER_BASE_HOSTS: dict[str, tuple[str, ...]] = {
    "science": ("www.science.org", "science.org"),
    "pnas": ("www.pnas.org", "pnas.org"),
    "wiley": ("onlinelibrary.wiley.com",),
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


@dataclass(frozen=True)
class PublisherProfile:
    name: str
    hosts: tuple[str, ...]
    noise_profile: str = "generic"
    site_rule_overrides: Mapping[str, Any] = field(default_factory=dict)
    html_candidate_builder: Callable[[str, str | None], list[str]] | None = None
    pdf_candidate_builder: Callable[[str, str | None], list[str]] | None = None
    positive_signals: Callable[[str], tuple[list[str], list[str], list[str]]] | None = None
    markdown_postprocess: Callable[[str], str] | None = None
    dom_postprocess: Callable[[Any], None] | None = None


def _science_markdown_postprocess(markdown_text: str) -> str:
    from ._science_pnas_postprocess import merge_science_citation_italics

    return merge_science_citation_italics(markdown_text)


def _wiley_dom_postprocess(container: Any) -> None:
    from ._science_pnas_postprocess import move_wiley_abbreviations_to_end

    move_wiley_abbreviations_to_end(container)


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
    for host in PUBLISHER_BASE_HOSTS.get(publisher, PUBLISHER_HOSTS.get(publisher, ())):
        candidate = f"https://{host}"
        if candidate not in base_urls:
            base_urls.append(candidate)
    return base_urls


def _build_science_html_candidates(doi: str, landing_page_url: str | None) -> list[str]:
    path_templates = ("/doi/full/{doi}", "/doi/{doi}")
    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page("science", doi, landing_page_url)
    if preferred_candidate:
        candidates.append(preferred_candidate)
    for base in _publisher_base_urls("science", landing_page_url):
        for template in path_templates:
            candidate = f"{base}{template.format(doi=doi)}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _build_pnas_html_candidates(doi: str, landing_page_url: str | None) -> list[str]:
    path_templates = ("/doi/{doi}", "/doi/full/{doi}")
    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page("pnas", doi, landing_page_url)
    if preferred_candidate:
        candidates.append(preferred_candidate)
    for base in _publisher_base_urls("pnas", landing_page_url):
        for template in path_templates:
            candidate = f"{base}{template.format(doi=doi)}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _build_wiley_html_candidates(doi: str, landing_page_url: str | None) -> list[str]:
    path_templates = ("/doi/full/{doi}", "/doi/{doi}")
    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page("wiley", doi, landing_page_url)
    if preferred_candidate:
        candidates.append(preferred_candidate)
    for base in _publisher_base_urls("wiley", landing_page_url):
        for template in path_templates:
            candidate = f"{base}{template.format(doi=doi)}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _build_science_pdf_candidates(doi: str, crossref_pdf_url: str | None) -> list[str]:
    candidates: list[str] = []

    def append(candidate: str | None) -> None:
        normalized = normalize_text(candidate)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    append(crossref_pdf_url)
    for base in _publisher_base_urls("science", crossref_pdf_url):
        for template in ("/doi/epdf/{doi}", "/doi/pdf/{doi}", "/doi/pdf/{doi}?download=true"):
            append(f"{base}{template.format(doi=doi)}")
    return candidates


def _build_pnas_pdf_candidates(doi: str, crossref_pdf_url: str | None) -> list[str]:
    candidates: list[str] = []

    def append(candidate: str | None) -> None:
        normalized = normalize_text(candidate)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    append(crossref_pdf_url)
    for base in _publisher_base_urls("pnas", crossref_pdf_url):
        for template in ("/doi/epdf/{doi}", "/doi/pdf/{doi}?download=true", "/doi/pdf/{doi}"):
            append(f"{base}{template.format(doi=doi)}")
    return candidates


def _build_wiley_pdf_candidates(doi: str, crossref_pdf_url: str | None) -> list[str]:
    candidates: list[str] = []

    def append(candidate: str | None) -> None:
        normalized = normalize_text(candidate)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    for base in _publisher_base_urls("wiley", None):
        append(f"{base}/doi/epdf/{doi}")
    append(crossref_pdf_url)
    for base in _publisher_base_urls("wiley", None):
        append(f"{base}/doi/pdf/{doi}")
        append(f"{base}/doi/pdfdirect/{doi}")
        append(f"{base}/wol1/doi/{doi}/fullpdf")
    return candidates


def _parse_aaas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    match = AAAS_DATALAYER_PATTERN.search(html_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def _dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _default_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    strong: list[str] = []
    soft: list[str] = []
    lowered = html_text.lower()
    if any(marker in lowered for marker in HTML_FULLTEXT_MARKERS):
        strong.append("article_body_marker")
    if "<article" in lowered:
        soft.append("article_tag_present")
    return _dedupe_signals(strong), _dedupe_signals(soft), []


def _science_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    strong, soft, abstract_only = _default_positive_signals(html_text)
    payload = _parse_aaas_datalayer(html_text)
    if not isinstance(payload, Mapping):
        return strong, soft, abstract_only
    page_info = payload.get("page", {}).get("pageInfo", {}) if isinstance(payload.get("page"), Mapping) else {}
    user = payload.get("user", {}) if isinstance(payload.get("user"), Mapping) else {}
    if normalize_text(str(page_info.get("pageType") or "")).lower() == "journal-article-full-text":
        strong.append("aaas_page_type_full_text")
    if "abstract" in normalize_text(str(page_info.get("pageType") or "")).lower():
        abstract_only.append("aaas_page_type_abstract")
    if normalize_text(str(page_info.get("viewType") or "")).lower() == "full":
        strong.append("aaas_view_full")
    if "abstract" in normalize_text(str(page_info.get("viewType") or "")).lower():
        abstract_only.append("aaas_view_abstract")
    if normalize_text(str(user.get("entitled") or "")).lower() == "true":
        strong.append("aaas_user_entitled")
    if normalize_text(str(user.get("access") or "")).lower() == "yes":
        strong.append("aaas_user_access_yes")
    if normalize_text(str(page_info.get("articleType") or "")):
        soft.append("aaas_article_type_present")
    return _dedupe_signals(strong), _dedupe_signals(soft), _dedupe_signals(abstract_only)


PROFILES: dict[str, PublisherProfile] = {
    "science": PublisherProfile(
        name="science",
        hosts=PUBLISHER_HOSTS["science"],
        site_rule_overrides={
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
            "drop_keywords": {"advert", "tab-nav", "jump-to"},
            "drop_text": {"Permissions"},
        },
        html_candidate_builder=_build_science_html_candidates,
        pdf_candidate_builder=_build_science_pdf_candidates,
        positive_signals=_science_positive_signals,
        markdown_postprocess=_science_markdown_postprocess,
    ),
    "pnas": PublisherProfile(
        name="pnas",
        hosts=PUBLISHER_HOSTS["pnas"],
        noise_profile="pnas",
        site_rule_overrides={
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
            "drop_keywords": {"tab-nav"},
        },
        html_candidate_builder=_build_pnas_html_candidates,
        pdf_candidate_builder=_build_pnas_pdf_candidates,
        positive_signals=_default_positive_signals,
    ),
    "wiley": PublisherProfile(
        name="wiley",
        hosts=PUBLISHER_HOSTS["wiley"],
        site_rule_overrides={
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
            "drop_text": {"Recommended articles"},
        },
        html_candidate_builder=_build_wiley_html_candidates,
        pdf_candidate_builder=_build_wiley_pdf_candidates,
        positive_signals=_default_positive_signals,
        dom_postprocess=_wiley_dom_postprocess,
    ),
}

GENERIC_PROFILE = PublisherProfile(
    name="generic",
    hosts=tuple(),
    positive_signals=_default_positive_signals,
)


def publisher_profile(publisher: str | None) -> PublisherProfile:
    normalized = normalize_text(publisher or "").lower()
    return PROFILES.get(normalized, GENERIC_PROFILE)


def site_rule_for_publisher(publisher: str | None) -> dict[str, Any]:
    profile = publisher_profile(publisher)
    merged = copy.deepcopy(DEFAULT_SITE_RULE)
    for key, value in profile.site_rule_overrides.items():
        default_value = merged.get(key)
        if isinstance(default_value, list):
            merged[key] = [*default_value, *[item for item in value if item not in default_value]]
            continue
        if isinstance(default_value, set):
            merged[key] = set(default_value) | set(value)
            continue
        merged[key] = copy.deepcopy(value)
    return merged


def noise_profile_for_publisher(publisher: str | None) -> str:
    return publisher_profile(publisher).noise_profile


def build_html_candidates(publisher: str, doi: str, landing_page_url: str | None = None) -> list[str]:
    builder = publisher_profile(publisher).html_candidate_builder
    if builder is None:
        raise ValueError(f"Unsupported browser-workflow HTML publisher: {publisher!r}")
    return builder(doi, landing_page_url)


def build_pdf_candidates(publisher: str, doi: str, crossref_pdf_url: str | None) -> list[str]:
    builder = publisher_profile(publisher).pdf_candidate_builder
    if builder is None:
        raise ValueError(f"Unsupported browser-workflow PDF publisher: {publisher!r}")
    return builder(doi, crossref_pdf_url)


def provider_positive_signals(
    publisher: str | None,
    html_text: str,
) -> tuple[list[str], list[str], list[str]]:
    return publisher_profile(publisher).positive_signals(html_text)


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
