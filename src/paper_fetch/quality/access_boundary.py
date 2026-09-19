"""Confirmed access restrictions on the requested article body.

Availability labels alone (abstract pages, non-OA, HTTP status) are insufficient.
Evidence travels in existing provider/availability diagnostics.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from ..publisher_identity import extract_doi_from_url, normalize_doi
from ..utils import normalize_text

if TYPE_CHECKING:
    from ..runtime import RuntimeContext

CONFIRMED_PAYWALL = "confirmed_article_paywall"
_DENIAL = re.compile(
    r"you (?:do not|don't) (?:currently )?have access(?: to (?:this|the) (?:article|content))?"
    r"|not (?:registered by an institution with a subscription to this article|entitled to (?:access |view )?(?:the |this )?(?:full.?text|article))"
    r"|this is a preview of subscription content"
    r"|(?:purchase|rent|buy) (?:access to )?this article"
    r"|subscribe to (?:continue|read (?:the |this )?(?:full |complete )?article)"
    r"|(?:sign|log) in to (?:read|access|view) (?:the |this )?(?:full.?text|article)"
    r"|access to (?:the |this )?(?:full.?text|article) (?:is |has been )?(?:denied|restricted)",
    re.I,
)
_GATE_SELECTORS = (
    "#no-access-message, #accessDenialWidget, .access-denial, .access-denied, "
    ".article-access, .paywall, #paywall, [data-test='paywall'], "
    ".access-options"
)
_HIDDEN = re.compile(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.I)


def confirmed_paywall(value: Any) -> bool:
    if not isinstance(value, Mapping):
        value = getattr(value, "details", None)
    if not isinstance(value, Mapping):
        return False
    evidence = value.get(CONFIRMED_PAYWALL)
    return isinstance(evidence, Mapping) and evidence.get("confirmed") is True


def _visible_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for node in list(soup.find_all(True)):
        if node.attrs is None:
            continue
        if (
            node.name
            in {"script", "style", "template", "noscript", "header", "footer", "aside"}
            or (
                node.name == "nav"
                and "article-navigation-bar" not in node.get("class", [])
            )
            or (
                "modal" in node.get("class", [])
                and "show" not in node.get("class", [])
                and node.get("aria-modal") != "true"
            )
            or node.has_attr("hidden")
            or bool({"hidden", "d-none", "is-hidden"} & set(node.get("class", [])))
            or node.get("aria-hidden") == "true"
            or (
                str(node.get("id") or "").startswith("core-collateral-")
                and node.get("data-active-pane") == "false"
            )
            or _HIDDEN.search(str(node.get("style") or ""))
        ):
            node.decompose()
    for node in soup.select(
        "figure, figcaption, .references, #references, .ref-list, .bibliography, "
        ".recommended, .recommendations, .related, .related-articles, .supplementary-material, "
        "[data-title='References'], .c-article-references, .c-article-supplementary__item, .u-hide, "
        "[data-title='Acknowledgements'], #author-information-section, #article-info-section, "
        ".citation-details, .articleMetadata, [id*='supplement'], [class*='supplement'], "
        "[id*='Supplement'], [class*='Supplement'], .snippet-text, .Footer, .Footer-bottom"
    ):
        node.decompose()
    return soup


def html_paywall_diagnostics(
    html: str | bytes,
    *,
    metadata: Mapping[str, Any] | None = None,
    source_url: str = "",
    provider: str | None = None,
) -> dict[str, Any]:
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    if not html or "<" not in html:
        return {}
    # Most article responses contain none of these words; avoid DOM parsing on
    # that common path without changing any availability decision.
    if not re.search(r"access|subscri|purchas|entitl|paywall|denial", html, re.I):
        return {}
    metadata = metadata or {}
    soup = BeautifulSoup(html, "html.parser")
    from ..extraction.html._metadata import extract_doi_from_meta, parse_html_metadata

    meta: dict[str, list[str]] = {}
    for node in soup.find_all("meta"):
        key = str(node.get("name") or node.get("property") or "").lower()
        meta.setdefault(key, []).append(str(node.get("content") or ""))
    observed_doi = normalize_doi(extract_doi_from_meta(meta))
    if not observed_doi:
        observed_doi = normalize_doi(
            extract_doi_from_meta({"citation_doi": meta.get("publication_doi", [])})
        )
    ieee_metadata: dict[str, Any] = {}
    if provider == "ieee":
        from ..providers._ieee_metadata import _parse_landing_metadata

        ieee_metadata = _parse_landing_metadata(html)
        observed_doi = observed_doi or normalize_doi(
            str(ieee_metadata.get("doi") or "")
        )
    expected_doi = normalize_doi(str(metadata.get("doi") or ""))
    url_doi = normalize_doi(extract_doi_from_url(unquote(source_url)))
    if expected_doi and observed_doi and expected_doi != observed_doi:
        return {}
    article_number = str(metadata.get("article_number") or "")
    number_matches = bool(
        provider == "ieee"
        and article_number
        and re.search(
            r"/(?:rest/)?document/" + re.escape(article_number) + r"(?:/|$|\?)",
            source_url,
        )
    )
    if expected_doi:
        if expected_doi not in {observed_doi, url_doi} and not number_matches:
            return {}
    elif not observed_doi and not url_doi:
        return {}
    parsed_metadata = parse_html_metadata(html, source_url)
    received: dict[str, Any] = {
        key: parsed_metadata[key]
        for key in ("title", "abstract", "authors")
        if parsed_metadata.get(key)
    }
    if provider == "ieee":
        received.update(
            {
                key: value
                for key, value in ieee_metadata.items()
                if key in {"title", "abstract", "authors", "doi"} and value
            }
        )
    for field, selector in (
        ("title", "meta[name='citation_title'], meta[property='og:title']"),
        (
            "abstract",
            "meta[name='citation_abstract'], meta[name='dc.Description'], meta[name='DC.Description'], meta[name='description']",
        ),
    ):
        node = soup.select_one(selector)
        if node is not None:
            received[field] = normalize_text(node.get("content"))
    from ..extraction.html.provider_rules import availability_rules_for_provider

    rules = availability_rules_for_provider(provider)
    visible = _visible_soup(html)
    if rules.paywall_remove_selectors:
        for node in visible.select(rules.paywall_remove_selectors):
            node.decompose()
    abstract = visible.select_one(
        "#abstract, #abstracts, [role='doc-abstract'], .abstract, .abstractSection, .abstractInFull, .abstractInHTML, .hlFld-Abstract, .article-abstract, [data-title='Abstract'], #Abs1, .c-article-section__content[id^='Abs']"
    )
    if rules.paywall_abstract_selector:
        abstract = visible.select_one(rules.paywall_abstract_selector) or abstract
    if abstract is not None:
        received["abstract"] = normalize_text(abstract.get_text(" ", strip=True))
    for node in visible.select("[data-doi], [data-article-doi]"):
        if node.attrs is None:
            continue
        other_doi = normalize_doi(
            str(node.get("data-doi") or node.get("data-article-doi") or "")
        )
        if other_doi and other_doi != (expected_doi or observed_doi or url_doi):
            node.decompose()
    for node in visible.select(
        "#abstract, #abstracts, [role='doc-abstract'], .abstract, .abstractSection, .abstractInFull, .abstractInHTML, .hlFld-Abstract, .article-abstract, [data-title='Abstract'], [id^='Abs']"
    ):
        node.decompose()
    gates = list(visible.select(_GATE_SELECTORS))
    if rules.paywall_gate_selectors:
        gates.extend(
            node
            for node in visible.select(rules.paywall_gate_selectors)
            if not rules.paywall_gate_text
            or normalize_text(node.get_text(" ", strip=True)) == rules.paywall_gate_text
        )
    # Only a short notice can establish denial; research prose and references
    # mentioning paywalls cannot establish the reader's entitlement.
    matches = [
        (node, match)
        for node in visible.find_all(["p", "div", "section", "span", "h2"])
        if len(text := normalize_text(node.get_text(" ", strip=True))) <= 1200
        if (match := _DENIAL.search(text))
        if match.start() == 0
        or node in gates
        or any(parent in gates for parent in node.parents)
    ]
    gate_pattern = (
        r"purchase options|buy online access|sign in\s+or purchase|get access"
    )
    if rules.paywall_gate_pattern:
        gate_pattern += "|" + rules.paywall_gate_pattern
    for gate in gates:
        if match := re.search(
            gate_pattern,
            gate.get_text(" ", strip=True),
            re.I,
        ):
            matches.append((gate, match))
    from .html_signals import evaluate_datalayer_blocking_signals

    signal_set = rules.datalayer_signal_set
    signal_html = (
        "\n".join(
            str(script)
            for script in soup.find_all("script")
            if not any(
                parent.name in {"template", "noscript"}
                or parent.has_attr("hidden")
                or parent.get("aria-hidden") == "true"
                or _HIDDEN.search(str(parent.get("style") or ""))
                or bool(
                    {"hidden", "d-none", "is-hidden"} & set(parent.get("class", []))
                )
                for parent in [script, *script.parents]
            )
        )
        if signal_set is not None
        else ""
    )
    entitlement_signals = (
        set(evaluate_datalayer_blocking_signals(signal_html, signal_set))
        & set(rules.paywall_entitlement_signals)
        if signal_set is not None
        else set()
    )
    if not matches and not entitlement_signals:
        return {}
    # A readable body outweighs peripheral purchasing prompts. Hidden body
    # remnants have already been excluded above.
    body = visible.select_one(
        ".article-body, .article__body, .articleBody, #bodymatter, #body-text, .hlFld-Fulltext, [itemprop='articleBody'], .c-article-body, #full-text-section"
    )
    if rules.paywall_body_selector:
        # Strict provider body selectors exclude chrome and bibliography.
        body = visible.select_one(rules.paywall_body_selector)
        if body is None:
            body = BeautifulSoup("", "html.parser")
    if body is None:
        body = visible.select_one(".article-content, article, main")
    if body is None:
        body = visible
    paragraph_nodes = body.select(rules.paywall_paragraph_selector)
    paragraphs = [
        normalize_text(node.get_text(" ", strip=True))
        for node in paragraph_nodes
        if not _DENIAL.search(normalize_text(node.get_text(" ", strip=True)))
        and not any(parent in gates for parent in node.parents)
    ]
    readable = sum(len(text) for text in paragraphs if len(text) >= 100) >= 600
    blocking_overlay = any(
        node.get("aria-modal") == "true" or "overlay" in " ".join(node.get("class", []))
        for node in gates
        if node.attrs is not None
    )
    if readable and not blocking_overlay:
        return {}
    basis = matches[0][1].group(0) if matches else sorted(entitlement_signals)[0]
    received["doi"] = expected_doi or observed_doi or url_doi
    received["landing_page_url"] = source_url
    return {
        CONFIRMED_PAYWALL: {
            "confirmed": True,
            "provider": provider,
            "source_url": source_url,
            "doi": received["doi"],
            "basis": basis,
            "identity": "citation_doi"
            if observed_doi
            else "article_number"
            if number_matches
            else "article_url",
        },
        "accepted": False,
        "reason": "publisher_paywall",
        "content_kind": "abstract_only"
        if received.get("abstract") or metadata.get("abstract")
        else "metadata_only",
        "blocking_fallback_signals": ["publisher_paywall"],
        "received_metadata": received,
    }


def raise_for_paywall(
    body: str | bytes,
    *,
    metadata: Mapping[str, Any] | None = None,
    source_url: str = "",
    provider: str | None = None,
) -> None:
    diagnostics = html_paywall_diagnostics(
        body, metadata=metadata, source_url=source_url, provider=provider
    )
    if diagnostics:
        raise paywall_failure(diagnostics, body=body)


def paywall_failure(diagnostics: Mapping[str, Any], *, body: str | bytes = b""):
    from ..failure import FailureDiagnostics
    from ..providers.base import ProviderFailure

    evidence = diagnostics[CONFIRMED_PAYWALL]
    return ProviderFailure(
        "no_access",
        "The publisher confirms that this article's full text requires access; further retrieval stopped.",
        diagnostics=FailureDiagnostics(
            provider=evidence.get("provider"),
            retryable=False,
            details={
                **diagnostics,
                "received_html": body.decode("utf-8", errors="replace")
                if isinstance(body, bytes)
                else body,
            },
        ),
    )


def propagate_paywall(exc: Exception) -> None:
    """Keep the terminal evidence when an adapter would otherwise retry/wrap."""
    if confirmed_paywall(exc):
        raise exc


def raise_for_api_entitlement(
    body: bytes | str,
    *,
    source_url: str,
    provider: str,
    headers: Mapping[str, Any] | None = None,
) -> None:
    """Explicit official full-text API refusal, never a bare HTTP 401/403."""
    url = urlsplit(source_url)
    official_article_api = (
        provider == "elsevier"
        and url.hostname == "api.elsevier.com"
        and url.path.startswith("/content/article/")
        or provider == "wiley"
        and url.hostname == "api.wiley.com"
        and url.path.startswith("/onlinelibrary/tdm/v1/articles/")
    )
    if not official_article_api:
        return
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    signals = [
        str(v) for k, v in (headers or {}).items() if k.lower() == "x-els-status"
    ]
    # Restrict matching to API error/entitlement objects, never article prose.
    if text.lstrip().startswith("{"):
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {}
        if isinstance(payload, Mapping):
            signals.extend(
                str(payload[key])
                for key in (
                    "error",
                    "errors",
                    "error-response",
                    "service-error",
                    "document-entitlement",
                )
                if payload.get(key)
            )
    elif text.lstrip().startswith("<"):
        from ..xml_security import parse_xml

        try:
            root = parse_xml(text)
        except ValueError:
            root = None
        if root is not None and str(root.tag).split("}")[-1] in {
            "error",
            "error-response",
            "service-error",
            "document-entitlement",
        }:
            signals.append(" ".join(root.itertext()))
    match = re.search(
        r"NOT_ENTITLED|not entitled|FULL_TEXT_ACCESS_DENIED", " ".join(signals), re.I
    )
    if not match:
        return
    evidence = {
        "confirmed": True,
        "provider": provider,
        "source_url": source_url,
        "basis": match.group(0),
        "identity": "official_article_api_request",
    }
    raise paywall_failure(
        {
            CONFIRMED_PAYWALL: evidence,
            "reason": "publisher_paywall",
            "accepted": False,
            "blocking_fallback_signals": ["publisher_paywall"],
        }
    )


def check_payload_paywall(
    payload: Any,
    metadata: Mapping[str, Any],
    *,
    context: RuntimeContext | None = None,
    checked_input: tuple[Any, ...] | None = None,
) -> tuple[Any, ...]:
    """Inspect changed body inputs, and always inspect current diagnostics."""
    content = payload.content
    merged = {**metadata, **dict(content.merged_metadata or {})}
    # Response metadata must not replace the identity we are checking against.
    expected_doi = normalize_doi(str(metadata.get("doi") or ""))
    if expected_doi:
        merged["doi"] = expected_doi
        merged["article_number"] = metadata.get("article_number")
    diagnostics = content.diagnostics
    availability = diagnostics.get("availability_diagnostics") or {}
    current_input = (
        payload.provider,
        content.source_url,
        content.content_type,
        content.body,
        *(merged.get(key) for key in ("doi", "article_number", "abstract")),
    )
    if current_input != checked_input and "html" in content.content_type.lower():

        def detect() -> dict[str, Any]:
            return html_paywall_diagnostics(
                content.body,
                metadata=merged,
                source_url=content.source_url,
                provider=payload.provider,
            )

        if context is None:
            detected = detect()
        else:
            key = context.build_parse_cache_key(
                provider=payload.provider,
                role="article_paywall",
                source=content.source_url,
                body=content.body,
                parser="html.parser",
                config={
                    key: merged.get(key)
                    for key in ("doi", "article_number", "abstract")
                },
            )
            detected = context.get_or_set_parse_cache(key, detect)
        if detected:
            raise paywall_failure(detected, body=content.body)
    if confirmed_paywall(diagnostics) or confirmed_paywall(availability):
        details = diagnostics if confirmed_paywall(diagnostics) else availability
        observed_doi = normalize_doi(str(details[CONFIRMED_PAYWALL].get("doi") or ""))
        if expected_doi and observed_doi and expected_doi != observed_doi:
            from ..providers.base import ProviderFailure

            raise ProviderFailure(
                "identity_mismatch", "Access evidence belongs to a different article."
            )
        received = {**merged, **dict(details.get("received_metadata") or {})}
        extraction = diagnostics.get("extraction") or {}
        if extraction.get("abstract_text"):
            received["abstract"] = extraction["abstract_text"]
        raise paywall_failure(
            {**details, "received_metadata": received}, body=content.body
        )
    return current_input
