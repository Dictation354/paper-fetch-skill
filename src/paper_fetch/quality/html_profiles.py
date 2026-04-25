"""Provider-neutral HTML availability profiles and access signals."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..utils import normalize_text

HTML_STRONG_FULLTEXT_MARKERS = (
    'property="articleBody"',
    "property='articleBody'",
    'itemprop="articleBody"',
    "itemprop='articleBody'",
)
HTML_STRUCTURE_MARKERS = (
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
SCIENCE_NOISE_PROFILE = "generic"
SCIENCE_SITE_RULE_OVERRIDES: dict[str, Any] = {
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
        "#article_collateral_menu",
        "#core-collateral-fulltext-options",
        "#core-collateral-metrics",
        "#core-collateral-share",
        "#core-collateral-media",
        "#core-collateral-figures",
        "#core-collateral-tables",
    ],
    "drop_keywords": {"advert", "tab-nav", "jump-to"},
    "drop_text": {"Permissions"},
}
PNAS_NOISE_PROFILE = "pnas"
PNAS_SITE_RULE_OVERRIDES: dict[str, Any] = {
    "candidate_selectors": [
        ".article__fulltext",
        ".core-container",
        ".article-content",
    ],
    "remove_selectors": [
        ".article__access",
        ".article__footer",
        ".article__reference-links",
        ".core-collateral",
        ".card",
        ".signup-alert-ad",
    ],
    "drop_keywords": {"tab-nav"},
}
WILEY_NOISE_PROFILE = "generic"
WILEY_SITE_RULE_OVERRIDES: dict[str, Any] = {
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
}
AAAS_DATALAYER_PATTERN = re.compile(r"AAASdataLayer=(\{.*?\});(?:if\(|</script>)", flags=re.DOTALL)
PNAS_DATALAYER_PATTERN = re.compile(r"PNASdataLayer\s*=(\{.*?\});", flags=re.DOTALL)
WILEY_DATALAYER_PATTERN = re.compile(r"window\.adobeDataLayer\.push\((\{.*?\})\);", flags=re.DOTALL)


def dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def default_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    strong: list[str] = []
    soft: list[str] = []
    lowered = html_text.lower()
    if any(marker in lowered for marker in HTML_STRONG_FULLTEXT_MARKERS):
        strong.append("article_body_marker")
    if any(marker in lowered for marker in HTML_STRUCTURE_MARKERS):
        soft.append("article_body_structure_marker")
    if "<article" in lowered:
        soft.append("article_tag_present")
    return dedupe_signals(strong), dedupe_signals(soft), []


def looks_like_abstract_redirect(requested_url: str | None, final_url: str | None) -> bool:
    if not requested_url or not final_url:
        return False
    requested = requested_url.lower()
    final = final_url.lower()
    return "/doi/full/" in requested and "/doi/abs/" in final and requested != final


def load_aaas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    match = AAAS_DATALAYER_PATTERN.search(html_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def load_pnas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    match = PNAS_DATALAYER_PATTERN.search(html_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def load_wiley_datalayer(html_text: str) -> Mapping[str, Any] | None:
    for match in WILEY_DATALAYER_PATTERN.finditer(html_text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, Mapping):
            continue
        if isinstance(payload.get("content"), Mapping) or isinstance(payload.get("page"), Mapping):
            return payload
    return None


def science_blocking_fallback_signals(html_text: str) -> list[str]:
    payload = load_aaas_datalayer(html_text)
    if payload is None:
        return []
    page = payload.get("page")
    page_info = page.get("pageInfo", {}) if isinstance(page, Mapping) else {}
    user = payload.get("user", {}) if isinstance(payload.get("user"), Mapping) else {}
    signals: list[str] = []

    page_type = normalize_text(page_info.get("pageType")).lower()
    if page_type == "journal-article-denial":
        signals.append("aaas_page_type_denial")
    if page_type == "journal-article-abstract":
        signals.append("aaas_page_type_abstract")

    view_type = normalize_text(page_info.get("viewType")).lower()
    if view_type == "abs":
        signals.append("aaas_view_abs")

    user_entitled = normalize_text(user.get("entitled")).lower()
    user_access = normalize_text(user.get("access")).lower()
    if user_entitled == "false" and user_access != "yes":
        signals.append("aaas_entitlement_denied")

    return dedupe_signals(signals)


def science_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    strong, soft, abstract_only = default_positive_signals(html_text)
    payload = load_aaas_datalayer(html_text)
    if payload is None:
        return strong, soft, abstract_only
    page_info = payload.get("page", {}).get("pageInfo", {}) if isinstance(payload.get("page"), Mapping) else {}
    user = payload.get("user", {}) if isinstance(payload.get("user"), Mapping) else {}
    if str(page_info.get("pageType") or "").strip().lower() == "journal-article-full-text":
        soft.append("aaas_page_type_full_text")
    if "abstract" in str(page_info.get("pageType") or "").strip().lower():
        abstract_only.append("aaas_page_type_abstract")
    if str(page_info.get("viewType") or "").strip().lower() == "full":
        soft.append("aaas_view_full")
    if "abstract" in str(page_info.get("viewType") or "").strip().lower():
        abstract_only.append("aaas_view_abstract")
    if str(user.get("entitled") or "").strip().lower() == "true":
        strong.append("aaas_user_entitled")
    if str(user.get("access") or "").strip().lower() == "yes":
        strong.append("aaas_user_access_yes")
    if str(page_info.get("articleType") or "").strip():
        soft.append("aaas_article_type_present")
    return dedupe_signals(strong), dedupe_signals(soft), dedupe_signals(abstract_only)


def pnas_blocking_fallback_signals(html_text: str) -> list[str]:
    payload = load_pnas_datalayer(html_text)
    if payload is None:
        return []
    page = payload.get("page", {}) if isinstance(payload.get("page"), Mapping) else {}
    attributes = page.get("attributes", {}) if isinstance(page.get("attributes"), Mapping) else {}
    user = payload.get("user", {}) if isinstance(payload.get("user"), Mapping) else {}
    access_type = normalize_text(attributes.get("accessType")).lower()
    free_access = normalize_text(attributes.get("freeAccess")).lower()
    user_access = normalize_text(user.get("access")).lower()
    if access_type == "paywall" and free_access == "no" and user_access == "no":
        return ["pnas_paywall_no_access"]
    return []


def pnas_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return default_positive_signals(html_text)


def wiley_blocking_fallback_signals(html_text: str) -> list[str]:
    payload = load_wiley_datalayer(html_text)
    if payload is None:
        return []
    content = payload.get("content", {}) if isinstance(payload.get("content"), Mapping) else {}
    item = content.get("item", {}) if isinstance(content.get("item"), Mapping) else {}
    page = payload.get("page", {}) if isinstance(payload.get("page"), Mapping) else {}
    signals: list[str] = []

    if normalize_text(item.get("access")).lower() == "no":
        signals.append("wiley_access_no")
    if normalize_text(item.get("format-viewed") or item.get("format_viewed")).lower() == "abstract":
        signals.append("wiley_format_viewed_abstract")
    if normalize_text(page.get("tertiary-section") or page.get("tertiary_section")).lower() == "abs":
        signals.append("wiley_page_tertiary_abs")

    return dedupe_signals(signals)


def wiley_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return default_positive_signals(html_text)


@dataclass(frozen=True)
class HtmlAvailabilityProfile:
    noise_profile: str = "generic"
    site_rule_overrides: Mapping[str, Any] = field(default_factory=dict)
    positive_signals: Callable[[str], tuple[list[str], list[str], list[str]]] = default_positive_signals
    blocking_fallback_signals: Callable[[str], list[str]] = lambda _html_text: []


GENERIC_AVAILABILITY_PROFILE = HtmlAvailabilityProfile()
PUBLISHER_AVAILABILITY_PROFILES: dict[str, HtmlAvailabilityProfile] = {
    "science": HtmlAvailabilityProfile(
        noise_profile=SCIENCE_NOISE_PROFILE,
        site_rule_overrides=SCIENCE_SITE_RULE_OVERRIDES,
        positive_signals=science_positive_signals,
        blocking_fallback_signals=science_blocking_fallback_signals,
    ),
    "pnas": HtmlAvailabilityProfile(
        noise_profile=PNAS_NOISE_PROFILE,
        site_rule_overrides=PNAS_SITE_RULE_OVERRIDES,
        positive_signals=pnas_positive_signals,
        blocking_fallback_signals=pnas_blocking_fallback_signals,
    ),
    "wiley": HtmlAvailabilityProfile(
        noise_profile=WILEY_NOISE_PROFILE,
        site_rule_overrides=WILEY_SITE_RULE_OVERRIDES,
        positive_signals=wiley_positive_signals,
        blocking_fallback_signals=wiley_blocking_fallback_signals,
    ),
}


def availability_profile_for_publisher(publisher: str | None) -> HtmlAvailabilityProfile:
    normalized = normalize_text(publisher or "").lower()
    return PUBLISHER_AVAILABILITY_PROFILES.get(normalized, GENERIC_AVAILABILITY_PROFILE)


def site_rule_for_publisher(publisher: str | None) -> dict[str, Any]:
    profile = availability_profile_for_publisher(publisher)
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
    return availability_profile_for_publisher(publisher).noise_profile


def provider_positive_signals(
    publisher: str | None,
    html_text: str,
) -> tuple[list[str], list[str], list[str]]:
    return availability_profile_for_publisher(publisher).positive_signals(html_text)


def provider_blocking_fallback_signals(
    publisher: str | None,
    html_text: str,
) -> list[str]:
    return list(availability_profile_for_publisher(publisher).blocking_fallback_signals(html_text))
