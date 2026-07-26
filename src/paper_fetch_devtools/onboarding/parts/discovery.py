# ruff: noqa
from __future__ import annotations


def default_evidence_pack_path(
    provider: str, output_dir: Path | str | None = None
) -> str:
    provider_name = _provider_slug(provider)
    if output_dir is None:
        return f".paper-fetch-runs/{provider_name}-onboarding/{DISCOVERY_EVIDENCE_RELATIVE_PATH}"
    base = Path(output_dir)
    return (base / DISCOVERY_EVIDENCE_RELATIVE_PATH).as_posix()


def _query_identity_terms(
    provider: str, domain: str | None, doi_prefix: str | None
) -> list[str]:
    terms = [provider]
    if domain:
        terms.append(domain)
    if doi_prefix:
        terms.append(doi_prefix.rstrip("/"))
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        normalized = str(term).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def build_discovery_query_plan(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> dict[str, list[str]]:
    provider_name = _provider_slug(provider)
    identity = _query_identity_terms(provider_name, domain, doi_prefix)
    prefix_or_provider = doi_prefix.rstrip("/") if doi_prefix else provider_name
    site_query = f"site:{domain}" if domain else provider_name
    query_plan: dict[str, list[str]] = {}
    for purpose in DOI_SAMPLE_PURPOSES:
        keywords = PURPOSE_KEYWORDS[purpose]
        keyword_phrase = " ".join(keywords[:2])
        queries = [
            f"{provider_name} {prefix_or_provider} {keyword_phrase} DOI candidates",
            f"{site_query} {provider_name} {keyword_phrase} article DOI",
            f"{prefix_or_provider} {keyword_phrase} fixture discovery {identity[0]}",
        ]
        query_plan[purpose] = queries[:DISCOVERY_MAX_QUERIES_PER_PURPOSE]
    return query_plan


def _route_contract_template(step: str) -> dict[str, Any]:
    if step == "article_html":
        return {
            "success_requires": [
                "provider article container is present",
                "title or DOI metadata is present",
                "body text or body sections are present",
            ],
            "reject_if_any": [
                "challenge page",
                "access gate only",
                "site navigation only",
                "empty article shell",
            ],
            "min_body_chars": 1200,
            "min_body_sections": 1,
        }
    if step == "landing_html":
        return {
            "success_requires": [
                "landing page resolves for the DOI",
                "title or DOI metadata is present",
                "route can discover a full text or fallback candidate",
            ],
            "reject_if_any": [
                "challenge page",
                "access gate only",
                "unrelated search page",
                "empty article shell",
            ],
            "min_body_chars": 400,
        }
    if step == "xml":
        return {
            "success_requires": [
                "XML response parses as article metadata or body content",
                "title or DOI metadata is present",
                "article body, references, or abstract nodes are present",
            ],
            "reject_if_any": [
                "HTML wrapper",
                "challenge page",
                "access gate page",
                "error XML",
            ],
        }
    if step == "pdf_fallback":
        return {
            "success_requires": [
                "PDF response has application/pdf content type or PDF magic bytes",
                "PDF text extraction produces body text",
            ],
            "reject_if_any": [
                "HTML wrapper",
                "challenge page",
                "access gate page",
                "error page",
            ],
            "require_pdf_magic": True,
            "reject_html_wrapper": True,
        }
    if step == "abstract_only":
        return {
            "success_requires": [
                "metadata contains DOI or title",
                "abstract text is present",
                "result is marked as abstract-only",
            ],
            "reject_if_any": [
                "fabricated body text",
                "provider fulltext source without fulltext",
            ],
        }
    return {
        "success_requires": [
            "metadata contains DOI or title",
            "source trail marks metadata-only fallback",
        ],
        "reject_if_any": [
            "fabricated body text",
            "provider-specific fulltext source without fulltext",
        ],
    }


def _markdown_contract_template(
    *,
    purpose: str,
    doi: str,
    observed_signals: list[str] | None = None,
) -> dict[str, Any]:
    signals = set(observed_signals or [])
    include_by_purpose = {
        "structure": "## Abstract",
        "table": "Table",
        "formula": "Equation",
        "figure": "Figure",
        "supplementary": "Supplementary",
        "references": "Reference",
        "pdf_fallback": "#",
        "abstract_only": "## Abstract",
        "access_gate": "access",
        "empty_shell": "metadata",
    }
    exclude_by_purpose = {
        "structure": "Download PDF",
        "table": "Google Scholar",
        "formula": "[Formula unavailable]",
        "figure": "Article Metrics",
        "supplementary": "Download Citation",
        "references": "Google Scholar",
        "pdf_fallback": "Access Denied",
        "abstract_only": "References",
        "access_gate": "full text body",
        "empty_shell": "site navigation",
    }
    contract: dict[str, Any] = {
        "doi": doi,
        "must_include": [include_by_purpose.get(purpose, "## Abstract")],
        "must_not_include": [exclude_by_purpose.get(purpose, "Download PDF")],
    }
    if purpose == "table" or "body_tables" in signals:
        contract["must_match"] = [r"(?m)^\|.+\|$"]
    elif purpose == "formula" or {"formula", "mathjax", "mathml"} & signals:
        contract["must_match"] = [r"(?:\$\$|!\[Formula\]|Equation)"]
    elif purpose == "figure" or {"figures", "body_figures"} & signals:
        contract["must_match"] = [r"(?:!\[Figure|\*\*Figure)"]
    return contract


def _contract_templates_for_discovery() -> dict[str, Any]:
    return {
        "route_contract": {
            step: _route_contract_template(step)
            for step in [
                "landing_html",
                "article_html",
                "xml",
                "pdf_fallback",
                "abstract_only",
                "metadata_only",
            ]
        },
        "markdown_contract": {
            purpose: {
                "must_include_hint": _markdown_contract_template(
                    purpose=purpose,
                    doi="10.0000/example",
                )["must_include"],
                "must_not_include_hint": _markdown_contract_template(
                    purpose=purpose,
                    doi="10.0000/example",
                )["must_not_include"],
            }
            for purpose in DOI_SAMPLE_PURPOSES
        },
        "asset_contract": {
            "figures": {
                "with_body_figure_signal": {
                    "inline": "body",
                    "download": "required",
                    "purposes": ["figure"],
                    "exception_reason": None,
                },
                "without_body_figure_signal": {
                    "inline": "not_applicable",
                    "download": "not_applicable",
                    "purposes": ["figure"],
                    "exception_reason": (
                        "Discovery evidence did not show stable body figure assets."
                    ),
                },
            }
        },
    }


def _decode_response_body(response: Mapping[str, Any]) -> str:
    body = response.get("body", b"")
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _load_optional_access_review(provider: str) -> dict[str, Any] | None:
    try:
        return _load_access_review(provider)
    except ToolError:
        return None


def _access_review_allowed_runtimes(review: Mapping[str, Any] | None) -> set[str]:
    runtimes = review.get("allowed_runtimes") if isinstance(review, Mapping) else None
    if isinstance(runtimes, list):
        return {
            str(runtime).strip().lower() for runtime in runtimes if str(runtime).strip()
        }
    return set()


def _access_review_allows_browser(review: Mapping[str, Any] | None) -> bool:
    return bool(_access_review_allowed_runtimes(review) & {"browser", "playwright"})


def _manifest_probe_for_provider(provider: str) -> dict[str, Any]:
    manifest_path = _repo_root() / default_manifest_path(provider)
    if not manifest_path.exists():
        return {}
    try:
        manifest = _read_manifest(manifest_path)
    except ToolError:
        return {}
    probe = manifest.get("probe") if isinstance(manifest.get("probe"), dict) else {}
    return dict(probe)


def _provider_requires_browser_runtime(provider: str) -> bool:
    probe = _manifest_probe_for_provider(provider)
    if bool(probe.get("requires_browser_runtime") or probe.get("requires_playwright")):
        return True
    try:
        from paper_fetch.provider_catalog import PROVIDER_CATALOG

        spec = PROVIDER_CATALOG.get(provider)
    except Exception:
        return False
    return bool(
        spec
        and (
            getattr(spec, "requires_browser_runtime", False)
            or getattr(spec, "requires_playwright", False)
        )
    )


def _discovery_browser_fallback_policy(
    *,
    provider: str,
    mode: str,
    no_network: bool,
) -> dict[str, Any]:
    review = _load_optional_access_review(provider)
    allowed_runtimes = sorted(_access_review_allowed_runtimes(review))
    provider_requires_browser = _provider_requires_browser_runtime(provider)
    enabled = (
        mode == "auto" and not no_network and _access_review_allows_browser(review)
    )
    disabled_reason = None
    if mode == "off":
        disabled_reason = "cli_disabled"
    elif no_network:
        disabled_reason = "no_network"
    elif not _access_review_allows_browser(review):
        disabled_reason = "access_review_disallows_browser"
    return {
        "mode": mode,
        "enabled": enabled,
        "access_review": default_access_review_path(provider),
        "access_review_present": review is not None,
        "allowed_runtimes": allowed_runtimes,
        "provider_requires_browser_runtime": provider_requires_browser,
        "disabled_reason": disabled_reason,
    }


def _candidate_rejection_hint(purpose: str) -> str:
    keywords = ", ".join(PURPOSE_KEYWORDS.get(purpose, [purpose]))
    return (
        f"Reject if the page does not expose stable {keywords} evidence "
        "or belongs to a different provider route."
    )


def _candidate_confidence(score: float) -> str:
    if score >= DISCOVERY_HIGH_CONFIDENCE_SCORE:
        return "high"
    if score >= DISCOVERY_MEDIUM_CONFIDENCE_SCORE:
        return "medium"
    return "low"


def _merge_candidate(
    candidates: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
) -> None:
    doi = _normalize_doi_or_none(candidate.get("doi"))
    if doi is None:
        return
    candidate["doi"] = doi
    existing = candidates.get(doi)
    if existing is None:
        candidates[doi] = candidate
        return
    for key in [
        "title",
        "journal_title",
        "publisher",
        "landing_page_url",
        "evidence_url",
    ]:
        if not existing.get(key) and candidate.get(key):
            existing[key] = candidate[key]
    existing_queries = existing.setdefault("source_queries", [])
    for query in candidate.get("source_queries") or []:
        if query not in existing_queries:
            existing_queries.append(query)
    existing_sources = existing.setdefault("metadata_sources", [])
    for source in candidate.get("metadata_sources") or []:
        if source not in existing_sources:
            existing_sources.append(source)
    existing_signals = existing.setdefault("observed_signals", [])
    for signal in candidate.get("observed_signals") or []:
        if signal not in existing_signals:
            existing_signals.append(signal)


def _crossref_candidate(
    metadata: Mapping[str, Any],
    *,
    purpose: str,
    query: str,
    domain: str | None = None,
) -> dict[str, Any] | None:
    doi = _normalize_doi_or_none(metadata.get("doi"))
    if doi is None:
        return None
    landing_url = _preferred_crossref_evidence_url(
        metadata,
        purpose=purpose,
        doi=doi,
        domain=domain,
    )
    signals = ["crossref_metadata"]
    if metadata.get("abstract"):
        signals.append("abstract")
    if metadata.get("references"):
        signals.append("references")
    for link in metadata.get("fulltext_links") or []:
        if isinstance(link, Mapping):
            content_type = str(link.get("content_type") or "").lower()
            url = str(link.get("url") or "").lower()
            if "pdf" in content_type or url.endswith(".pdf") or "/pdf" in url:
                signals.append("pdf_link")
    return {
        "doi": doi,
        "purpose": purpose,
        "title": metadata.get("title"),
        "journal_title": metadata.get("journal_title"),
        "publisher": metadata.get("publisher"),
        "landing_page_url": landing_url,
        "evidence_url": landing_url,
        "source_queries": [query],
        "metadata_sources": [{"source": "crossref", "url": metadata.get("source_url")}],
        "observed_signals": sorted(set(signals)),
        "rejection_hint": _candidate_rejection_hint(purpose),
    }


def _preferred_crossref_evidence_url(
    metadata: Mapping[str, Any],
    *,
    purpose: str,
    doi: str,
    domain: str | None = None,
) -> str:
    domain_token = normalize_text(domain).lower()
    pdf_urls: list[str] = []
    html_urls: list[str] = []
    other_urls: list[str] = []
    for link in metadata.get("fulltext_links") or []:
        if not isinstance(link, Mapping):
            continue
        url = _safe_url(link.get("url"))
        if url is None:
            continue
        normalized_url = url.lower()
        if domain_token and domain_token not in normalized_url:
            continue
        content_type = normalize_text(str(link.get("content_type") or "")).lower()
        if "pdf" in content_type or normalized_url.rstrip("/").endswith("/pdf"):
            pdf_urls.append(url)
        elif "html" in content_type or "/article/" in normalized_url:
            html_urls.append(url)
        else:
            other_urls.append(url)
    if purpose == "pdf_fallback" and pdf_urls:
        return pdf_urls[0]
    if html_urls:
        return html_urls[0]
    if pdf_urls:
        return pdf_urls[0]
    if other_urls:
        return other_urls[0]
    return _safe_url(metadata.get("landing_page_url")) or _doi_url(doi)


def _normalized_doi_prefix(value: str | None) -> str | None:
    normalized = normalize_text(value).lower().rstrip("/")
    return normalized or None


def _candidate_matches_provider_seed(
    candidate: Mapping[str, Any],
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> bool:
    normalized_prefix = _normalized_doi_prefix(doi_prefix)
    doi = normalize_text(str(candidate.get("doi") or "")).lower()
    if normalized_prefix and not doi.startswith(f"{normalized_prefix}/"):
        return False
    domain_token = normalize_text(domain).lower().strip("/")
    if not domain_token:
        return True
    url_text = " ".join(
        normalize_text(str(candidate.get(key) or "")).lower()
        for key in ["evidence_url", "landing_page_url"]
    )
    if domain_token in url_text:
        return True
    identity_text = " ".join(
        normalize_text(str(candidate.get(key) or "")).lower()
        for key in ["publisher", "journal_title", "title"]
    )
    provider_terms = {provider.replace("_", " "), provider}
    return any(term and term in identity_text for term in provider_terms)


def _search_crossref_discovery_candidates(
    crossref: Any,
    query: str,
    *,
    doi_prefix: str | None,
    rows: int,
) -> list[Mapping[str, Any]]:
    if doi_prefix:
        try:
            return list(
                crossref.search_bibliographic_candidates(
                    query,
                    rows=rows,
                    doi_prefix=_normalized_doi_prefix(doi_prefix),
                )
            )
        except TypeError as exc:
            if "doi_prefix" not in str(exc):
                raise
    return list(crossref.search_bibliographic_candidates(query, rows=rows))


def _openalex_candidates(
    *,
    transport: Any,
    query: str,
    purpose: str,
) -> list[dict[str, Any]]:
    try:
        response = transport.request(
            "GET",
            "https://api.openalex.org/works",
            headers={"Accept": "application/json"},
            query={"search": query, "per-page": "3"},
            timeout=DISCOVERY_PROBE_TIMEOUT_SECONDS,
            retry_on_rate_limit=True,
            retry_on_transient=True,
        )
    except Exception:
        return []
    try:
        payload = json.loads(_decode_response_body(response))
    except json.JSONDecodeError:
        return []
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    candidates: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, Mapping):
            continue
        doi = _normalize_doi_or_none(item.get("doi"))
        if doi is None:
            continue
        primary_location = item.get("primary_location")
        source = (
            primary_location.get("source")
            if isinstance(primary_location, Mapping)
            else {}
        )
        landing_url = _safe_url(item.get("landing_page_url"))
        if landing_url is None and isinstance(primary_location, Mapping):
            landing_url = _safe_url(primary_location.get("landing_page_url"))
        signals = ["openalex_metadata"]
        abstract = item.get("abstract_inverted_index")
        if isinstance(abstract, dict) and abstract:
            signals.append("abstract")
        if item.get("referenced_works_count"):
            signals.append("references")
        candidates.append(
            {
                "doi": doi,
                "purpose": purpose,
                "title": item.get("display_name"),
                "journal_title": (
                    source.get("display_name") if isinstance(source, Mapping) else None
                ),
                "publisher": item.get("publisher"),
                "landing_page_url": landing_url or _doi_url(doi),
                "evidence_url": landing_url or _doi_url(doi),
                "source_queries": [query],
                "metadata_sources": [
                    {"source": "openalex", "url": item.get("id") or response.get("url")}
                ],
                "observed_signals": signals,
                "rejection_hint": _candidate_rejection_hint(purpose),
            }
        )
    return candidates


def _probe_landing_page(
    *,
    transport: Any,
    url: str,
    purpose: str,
    provider: str | None = None,
    browser_fallback_enabled: bool = False,
    browser_required: bool = False,
    browser_probe_func: Any | None = None,
) -> dict[str, Any]:
    http_probe = _http_probe_landing_page(transport=transport, url=url, purpose=purpose)
    fallback_reason = _browser_fallback_reason(
        http_probe,
        purpose=purpose,
        browser_required=browser_required,
    )
    if not browser_fallback_enabled or fallback_reason is None:
        return _decorate_probe_result(
            http_probe,
            route="http",
            browser_attempted=False,
            fallback_from=None,
            http_probe=http_probe,
            browser_probe=None,
        )

    probe_func = browser_probe_func or _browser_probe_landing_page
    browser_probe = probe_func(url=url, purpose=purpose, provider=provider)
    browser_failure_code = _probe_failure_code(browser_probe)
    if browser_probe.get("status") == "ok":
        return _decorate_probe_result(
            browser_probe,
            route="browser",
            browser_attempted=True,
            fallback_from=fallback_reason,
            http_probe=http_probe,
            browser_probe=browser_probe,
        )

    result = _decorate_probe_result(
        http_probe,
        route="http",
        browser_attempted=True,
        fallback_from=fallback_reason,
        http_probe=http_probe,
        browser_probe=browser_probe,
    )
    result["browser_failure_code"] = browser_failure_code
    return result


def _decorate_probe_result(
    probe: Mapping[str, Any],
    *,
    route: str,
    browser_attempted: bool,
    fallback_from: str | None,
    http_probe: Mapping[str, Any],
    browser_probe: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = dict(probe)
    result["route"] = route
    result["browser_attempted"] = browser_attempted
    result["fallback_from"] = fallback_from
    result["http_probe"] = dict(http_probe)
    if browser_probe is not None:
        result["browser_probe"] = dict(browser_probe)
    return result


def _http_probe_landing_page(
    *,
    transport: Any,
    url: str,
    purpose: str,
) -> dict[str, Any]:
    try:
        response = transport.request(
            "GET",
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1",
            },
            timeout=DISCOVERY_PROBE_TIMEOUT_SECONDS,
            retry_on_rate_limit=False,
            retry_on_transient=True,
        )
    except (ProviderFailure, RequestFailure, Exception) as exc:
        return {
            "url": url,
            "status": "request_failed",
            "route": "http",
            "observed_signals": [],
            "reason": str(exc),
        }
    return _html_probe_from_response(response, url=url, purpose=purpose, route="http")


def _browser_probe_landing_page(
    *,
    url: str,
    purpose: str,
    provider: str | None = None,
) -> dict[str, Any]:
    try:
        from paper_fetch.providers.browser_workflow.html_extraction import (
            fetch_html_with_fast_browser,
        )

        result = fetch_html_with_fast_browser(
            [url],
            publisher=provider or "unknown",
            user_agent=build_browser_user_agent(os.environ),
            timeout_ms=DISCOVERY_PROBE_TIMEOUT_SECONDS * 1000,
        )
    except HtmlExtractionFailure as exc:
        return _browser_failure_probe(url=url, exc=exc)
    except Exception as exc:
        return _browser_failure_probe(url=url, exc=exc)

    headers = {
        str(key).lower(): str(value)
        for key, value in (result.response_headers or {}).items()
    }
    headers.setdefault("content-type", "text/html")
    return _html_probe_from_response(
        {
            "headers": headers,
            "body": result.html,
            "url": result.final_url or url,
            "status_code": result.response_status or 200,
        },
        url=url,
        purpose=purpose,
        route="browser",
    )


def _browser_failure_probe(*, url: str, exc: Exception) -> dict[str, Any]:
    failure_code = (
        getattr(exc, "reason", None)
        or getattr(exc, "kind", None)
        or getattr(exc, "code", None)
        or exc.__class__.__name__
    )
    message = getattr(exc, "message", None) or str(exc)
    signals = _signals_from_failure_code(str(failure_code))
    return {
        "url": url,
        "status": "request_failed",
        "route": "browser",
        "observed_signals": signals,
        "reason": str(message),
        "browser_failure_code": str(failure_code),
    }


def _signals_from_failure_code(failure_code: str) -> list[str]:
    normalized = failure_code.strip().lower()
    signals: list[str] = []
    if any(token in normalized for token in ["challenge", "captcha", "cloudflare"]):
        signals.append("challenge")
    if any(
        token in normalized for token in ["access", "paywall", "forbidden", "denied"]
    ):
        signals.append("access_gate")
    if "empty" in normalized:
        signals.append("empty_shell")
    return signals


def _html_probe_from_response(
    response: Mapping[str, Any],
    *,
    url: str,
    purpose: str,
    route: str,
) -> dict[str, Any]:
    content_type = str(
        (response.get("headers") or {}).get("content-type") or ""
    ).lower()
    body = _decode_response_body(response)
    signals: list[str] = []
    if "pdf" in content_type or body.startswith("%PDF"):
        signals.extend(["pdf_fallback", "pdf_content"])
        return {
            "url": response.get("url") or url,
            "status": "ok",
            "route": route,
            "status_code": response.get("status_code"),
            "content_type": content_type,
            "observed_signals": sorted(set(signals)),
        }
    body_fragment = body[:250_000]
    body_lower = body_fragment.lower()
    soup = BeautifulSoup(body_fragment, "html.parser")
    text = " ".join(soup.get_text(" ", strip=True).split())
    text_lower = text.lower()
    if soup.find(["article", "main"]) or len(text) >= 1200:
        signals.extend(["article_html", "html_body"])
    if soup.find("abstract") or "abstract" in text_lower:
        signals.append("abstract")
    if soup.find("table") or re.search(r"\btable\s+\d+\b", text_lower):
        signals.extend(["body_tables", "table"])
    if soup.find("math") or any(
        token in body.lower() for token in ["mathjax", "mathml", "<mml:math"]
    ):
        signals.extend(["formula", "mathml"])
    if re.search(r"\b(equation|formula)\s+\d+\b", text_lower):
        signals.extend(["formula", "equation"])
    if soup.find("figure") or soup.select("img[src]"):
        signals.extend(["figures", "body_figures"])
    if "supplementary" in text_lower or "supporting information" in text_lower:
        signals.extend(["supplementary", "supporting_information"])
    if "references" in text_lower or "bibliography" in text_lower:
        signals.extend(["references", "bibliography"])
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").lower()
        label = anchor.get_text(" ", strip=True).lower()
        if href.endswith(".pdf") or "/pdf" in href or label == "pdf":
            signals.append("pdf_link")
        if (
            "supplement" in href
            or "supplement" in label
            or "supporting information" in label
        ):
            signals.append("supplementary")
    status_code = _response_status_code(response)
    if any(token in body_lower or token in text_lower for token in CHALLENGE_PATTERNS):
        signals.append("challenge")
    if status_code in {401, 402, 403}:
        signals.extend(["access_gate", f"http_{status_code}"])
    if status_code == 429:
        signals.extend(["rate_limited", "http_429"])
    if contains_access_gate_text(text_lower) or any(
        token in text_lower
        for token in ["access denied", "sign in", "subscribe", "purchase access"]
    ):
        signals.append("access_gate")
    if len(text) < 500 and not (set(signals) & {"html_body", "pdf_content"}):
        signals.append("empty_shell")
    if purpose in PURPOSE_SIGNAL_MAP and PURPOSE_SIGNAL_MAP[purpose] & set(signals):
        signals.append(f"{purpose}_evidence")
    status = "ok"
    if route == "browser":
        if "challenge" in signals:
            status = "challenge"
        elif "access_gate" in signals:
            status = "access_gate"
        elif "empty_shell" in signals:
            status = "empty_shell"
    return {
        "url": response.get("url") or url,
        "status": status,
        "route": route,
        "status_code": status_code,
        "content_type": content_type,
        "title": soup.title.get_text(" ", strip=True) if soup.title else None,
        "body_chars": len(text),
        "observed_signals": sorted(set(signals)),
    }


def _response_status_code(response: Mapping[str, Any]) -> int | None:
    status_code = response.get("status_code")
    try:
        return int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        return None


def _probe_failure_code(probe: Mapping[str, Any]) -> str | None:
    explicit = probe.get("browser_failure_code")
    if explicit:
        return str(explicit)
    status = str(probe.get("status") or "").strip()
    if status and status != "ok":
        return status
    status_code = _response_status_code(probe)
    if status_code in {401, 402, 403, 429}:
        return f"http_{status_code}"
    signals = {str(signal) for signal in probe.get("observed_signals") or []}
    for signal in ("challenge", "access_gate", "empty_shell"):
        if signal in signals:
            return signal
    return None


def _browser_fallback_reason(
    probe: Mapping[str, Any],
    *,
    purpose: str,
    browser_required: bool,
) -> str | None:
    status = str(probe.get("status") or "")
    if status == "request_failed":
        return "http_request_failed"
    status_code = _response_status_code(probe)
    if status_code in {401, 402, 403, 429}:
        return "http_access_or_rate_limit"
    signals = {str(signal) for signal in probe.get("observed_signals") or []}
    if "challenge" in signals:
        return "http_challenge"
    if "empty_shell" in signals:
        return "http_empty_shell"
    expected = PURPOSE_SIGNAL_MAP.get(purpose)
    if expected and not (expected & signals):
        return (
            "browser_required_missing_purpose_signal"
            if browser_required
            else "http_missing_purpose_signal"
        )
    return None


def _score_discovery_candidate(
    candidate: Mapping[str, Any],
    *,
    purpose: str,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> float:
    score = 0.1 if _normalize_doi_or_none(candidate.get("doi")) else 0.0
    doi = str(candidate.get("doi") or "").lower()
    if doi_prefix and doi.startswith(doi_prefix.rstrip("/").lower()):
        score += 0.25
    evidence_url = str(
        candidate.get("evidence_url") or candidate.get("landing_page_url") or ""
    ).lower()
    if domain and domain.lower().strip("/") in evidence_url:
        score += 0.18
    identity_text = " ".join(
        str(candidate.get(key) or "")
        for key in ["publisher", "journal_title", "title", "landing_page_url"]
    ).lower()
    provider_terms = {provider.replace("_", " "), provider}
    if domain:
        provider_terms.add(domain.lower())
    if any(term and term in identity_text for term in provider_terms):
        score += 0.16
    signals = set(str(signal) for signal in candidate.get("observed_signals") or [])
    if PURPOSE_SIGNAL_MAP.get(purpose, set()) & signals:
        score += 0.3
    if f"{purpose}_evidence" in signals:
        score += 0.12
    if {"article_html", "html_body"} & signals and purpose in {
        "structure",
        "table",
        "formula",
        "figure",
        "supplementary",
        "references",
    }:
        score += 0.08
    if "crossref_metadata" in signals or "openalex_metadata" in signals:
        score += 0.06
    probe = candidate.get("probe")
    if isinstance(probe, Mapping):
        score += 0.04
        failure_code = normalize_text(_probe_failure_code(probe)).lower()
        if purpose in DISCOVERY_FULLTEXT_SAMPLE_PURPOSES and any(
            token in failure_code
            for token in [
                "access",
                "captcha",
                "challenge",
                "cloudflare",
                "denied",
                "empty",
                "forbidden",
            ]
        ):
            score = min(score, DISCOVERY_MEDIUM_CONFIDENCE_SCORE)
    elif purpose in DISCOVERY_FULLTEXT_SAMPLE_PURPOSES:
        score = min(score, DISCOVERY_MEDIUM_CONFIDENCE_SCORE)
    return min(score, 1.0)


def _finalize_discovery_candidate(
    candidate: dict[str, Any],
    *,
    purpose: str,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> dict[str, Any]:
    signals = list(
        dict.fromkeys(str(signal) for signal in candidate.get("observed_signals") or [])
    )
    candidate["observed_signals"] = signals
    score = _score_discovery_candidate(
        candidate,
        purpose=purpose,
        provider=provider,
        domain=domain,
        doi_prefix=doi_prefix,
    )
    candidate["score"] = round(score, 3)
    candidate["confidence"] = _candidate_confidence(score)
    candidate.setdefault(
        "evidence_url",
        candidate.get("landing_page_url") or _doi_url(candidate.get("doi")),
    )
    candidate.setdefault("rejection_hint", _candidate_rejection_hint(purpose))
    return candidate


def _prepare_discovery_candidates(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    query_plan: dict[str, list[str]],
    transport: Any,
    browser_fallback_enabled: bool = False,
    browser_required: bool = False,
    browser_probe_func: Any | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    crossref = CrossrefLookupClient(transport, os.environ)
    candidates_by_purpose: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    for purpose, queries in query_plan.items():
        merged: dict[str, dict[str, Any]] = {}
        for query in queries:
            try:
                for metadata in _search_crossref_discovery_candidates(
                    crossref,
                    query,
                    doi_prefix=doi_prefix,
                    rows=3,
                ):
                    candidate = _crossref_candidate(
                        metadata,
                        purpose=purpose,
                        query=query,
                        domain=domain,
                    )
                    if candidate is not None:
                        _merge_candidate(merged, candidate)
            except Exception as exc:
                errors.append(
                    {
                        "source": "crossref",
                        "purpose": purpose,
                        "query": query,
                        "reason": str(exc),
                    }
                )
            for candidate in _openalex_candidates(
                transport=transport,
                query=query,
                purpose=purpose,
            ):
                _merge_candidate(merged, candidate)
        candidates = [
            candidate
            for candidate in merged.values()
            if _candidate_matches_provider_seed(
                candidate,
                provider=provider,
                domain=domain,
                doi_prefix=doi_prefix,
            )
        ]
        candidates.sort(
            key=lambda candidate: (
                -_score_discovery_candidate(
                    candidate,
                    purpose=purpose,
                    provider=provider,
                    domain=domain,
                    doi_prefix=doi_prefix,
                ),
                str(candidate.get("doi") or ""),
            )
        )
        candidates = candidates[:DISCOVERY_MAX_METADATA_CANDIDATES_PER_PURPOSE]
        for candidate in candidates[:DISCOVERY_MAX_PAGE_PROBES_PER_PURPOSE]:
            url = _safe_url(candidate.get("landing_page_url")) or _doi_url(
                candidate.get("doi")
            )
            probe = _probe_landing_page(
                transport=transport,
                url=url,
                purpose=purpose,
                provider=provider,
                browser_fallback_enabled=browser_fallback_enabled,
                browser_required=browser_required,
                browser_probe_func=browser_probe_func,
            )
            candidate["probe"] = probe
            candidate["evidence_url"] = _safe_url(probe.get("url")) or url
            for signal in probe.get("observed_signals") or []:
                signals = candidate.setdefault("observed_signals", [])
                if signal not in signals:
                    signals.append(signal)
        finalized = [
            _finalize_discovery_candidate(
                candidate,
                purpose=purpose,
                provider=provider,
                domain=domain,
                doi_prefix=doi_prefix,
            )
            for candidate in candidates
        ]
        finalized.sort(
            key=lambda item: (
                -float(item.get("score") or 0),
                str(item.get("doi") or ""),
            )
        )
        candidates_by_purpose[purpose] = finalized
    return candidates_by_purpose, errors


def prepare_manifest_discovery(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    output_dir: Path | str,
    no_network: bool = False,
    browser_fallback: str = "auto",
    transport: Any | None = None,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    fallback_mode = str(browser_fallback or "auto").strip().lower()
    if fallback_mode not in DISCOVERY_BROWSER_FALLBACK_MODES:
        raise ValueError(
            "--browser-fallback must be one of: "
            + ", ".join(DISCOVERY_BROWSER_FALLBACK_MODES)
        )
    output_path = Path(default_evidence_pack_path(provider_name, output_dir))
    if not output_path.is_absolute():
        output_path = _repo_root() / output_path
    query_plan = build_discovery_query_plan(
        provider=provider_name,
        domain=domain,
        doi_prefix=doi_prefix,
    )
    fallback_policy = _discovery_browser_fallback_policy(
        provider=provider_name,
        mode=fallback_mode,
        no_network=no_network,
    )
    pack: dict[str, Any] = {
        "schema_version": 1,
        "provider": provider_name,
        "generated_at": _utc_now_iso(),
        "network": {"enabled": not no_network},
        "browser_fallback": fallback_policy,
        "provider_seed": {
            "name": provider_name,
            "domain": domain,
            "doi_prefix_hint": doi_prefix,
        },
        "routing_evidence": {
            "seed_domain": domain,
            "seed_doi_prefix": doi_prefix,
            "identity_terms": _query_identity_terms(provider_name, domain, doi_prefix),
            "candidate_primary": "doi_prefix" if doi_prefix else "domain",
        },
        "query_plan": query_plan,
        "doi_candidates": {purpose: [] for purpose in DOI_SAMPLE_PURPOSES},
        "network_errors": [],
    }
    if not no_network:
        active_transport = transport or HttpTransport(
            cache_ttl=300,
            max_response_bytes=250_000,
            pool_num_pools=4,
            pool_maxsize=2,
            per_host_concurrency=2,
        )
        candidates, errors = _prepare_discovery_candidates(
            provider=provider_name,
            domain=domain,
            doi_prefix=doi_prefix,
            query_plan=query_plan,
            transport=active_transport,
            browser_fallback_enabled=bool(fallback_policy.get("enabled")),
            browser_required=bool(
                fallback_policy.get("provider_requires_browser_runtime")
            ),
        )
        pack["doi_candidates"] = candidates
        pack["network_errors"] = errors
    write_text(output_path, json.dumps(pack, indent=2, sort_keys=True) + "\n")
    return pack


def _compact_evidence_pack_summary(pack: Mapping[str, Any]) -> dict[str, Any]:
    query_plan = (
        pack.get("query_plan") if isinstance(pack.get("query_plan"), Mapping) else {}
    )
    candidates = (
        pack.get("doi_candidates")
        if isinstance(pack.get("doi_candidates"), Mapping)
        else {}
    )
    summary: dict[str, Any] = {
        "provider": pack.get("provider"),
        "network_enabled": bool((pack.get("network") or {}).get("enabled"))
        if isinstance(pack.get("network"), Mapping)
        else None,
        "query_count_by_purpose": {
            str(purpose): len(queries) if isinstance(queries, list) else 0
            for purpose, queries in query_plan.items()
        },
        "top_candidates": {},
    }
    top_candidates: dict[str, Any] = {}
    for purpose, items in candidates.items():
        if not isinstance(items, list) or not items:
            continue
        top = items[0]
        if not isinstance(top, Mapping):
            continue
        top_candidates[str(purpose)] = {
            "doi": top.get("doi"),
            "score": top.get("score"),
            "confidence": top.get("confidence"),
            "observed_signals": top.get("observed_signals"),
            "evidence_url": top.get("evidence_url"),
            "probe_route": (top.get("probe") or {}).get("route")
            if isinstance(top.get("probe"), Mapping)
            else None,
            "browser_attempted": (top.get("probe") or {}).get("browser_attempted")
            if isinstance(top.get("probe"), Mapping)
            else None,
        }
    summary["top_candidates"] = top_candidates
    return summary


def _load_evidence_pack(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "DISCOVERY_EVIDENCE_INVALID",
            "Discovery evidence pack cannot be loaded.",
            retryable=False,
            task_id="prepare-discovery",
            details={"path": path.as_posix(), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "DISCOVERY_EVIDENCE_INVALID",
            "Discovery evidence pack root must be an object.",
            retryable=False,
            task_id="prepare-discovery",
            details={"path": path.as_posix()},
        )
    return data


def _candidate_list(
    evidence_pack: Mapping[str, Any], purpose: str
) -> list[dict[str, Any]]:
    raw_candidates = evidence_pack.get("doi_candidates")
    if not isinstance(raw_candidates, Mapping):
        return []
    items = raw_candidates.get(purpose)
    if not isinstance(items, list):
        return []
    candidates = [item for item in items if isinstance(item, dict)]
    candidates.sort(
        key=lambda item: (-float(item.get("score") or 0), str(item.get("doi") or ""))
    )
    return candidates


def _best_high_confidence_candidate(
    evidence_pack: Mapping[str, Any],
    purpose: str,
) -> dict[str, Any] | None:
    for candidate in _candidate_list(evidence_pack, purpose):
        doi = _normalize_doi_or_none(candidate.get("doi"))
        score = float(candidate.get("score") or 0)
        if doi and (
            candidate.get("confidence") == "high"
            or score >= DISCOVERY_HIGH_CONFIDENCE_SCORE
        ):
            return candidate
    return None


def _autofix_default_routing(evidence_pack: Mapping[str, Any]) -> dict[str, Any]:
    seed = (
        evidence_pack.get("provider_seed")
        if isinstance(evidence_pack.get("provider_seed"), Mapping)
        else {}
    )
    provider = str(seed.get("name") or evidence_pack.get("provider") or "provider")
    domain = str(seed.get("domain") or "").strip()
    doi_prefix = str(seed.get("doi_prefix_hint") or "").strip()
    return {
        "primary": "doi_prefix" if doi_prefix else "domain",
        "doi_prefixes": [doi_prefix if doi_prefix.endswith("/") else f"{doi_prefix}/"]
        if doi_prefix
        else [],
        "domains": [domain] if domain else [],
        "domain_suffixes": [],
        "publisher_aliases": [provider.replace("_", " ")],
        "crossref_publisher": None,
    }


def _sample_from_candidate(
    candidate: Mapping[str, Any] | None,
    *,
    purpose: str,
    domain: str | None,
) -> dict[str, Any]:
    if candidate is None:
        return {
            "doi": None,
            "evidence_url": _seed_base_url(domain),
            "evidence_reason": (
                f"Discovery evidence did not produce a high-confidence {purpose} DOI sample."
            ),
            "observed_signals": [],
            "confidence": "low",
        }
    doi = _normalize_doi_or_none(candidate.get("doi"))
    return {
        "doi": doi,
        "evidence_url": _safe_url(candidate.get("evidence_url")) or _doi_url(doi),
        "evidence_reason": (
            f"Discovery evidence selected {doi} for {purpose} with "
            f"{candidate.get('confidence', 'low')} confidence."
        ),
        "observed_signals": [
            str(signal)
            for signal in candidate.get("observed_signals") or ["crossref_metadata"]
        ],
        "confidence": str(candidate.get("confidence") or "low"),
    }


def _ensure_manifest_containers(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    provider = str(manifest.get("name") or evidence_pack.get("provider") or "provider")
    seed = (
        evidence_pack.get("provider_seed")
        if isinstance(evidence_pack.get("provider_seed"), Mapping)
        else {}
    )
    domain = seed.get("domain") if isinstance(seed.get("domain"), str) else None
    if not manifest.get("schema_version"):
        manifest["schema_version"] = 1
        changes.append("schema_version")
    if not isinstance(manifest.get("name"), str):
        manifest["name"] = provider
        changes.append("name")
    if not isinstance(manifest.get("display_source"), str):
        manifest["display_source"] = f"{_provider_slug(str(manifest['name']))}_html"
        changes.append("display_source")
    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        generation = {}
        manifest["generation"] = generation
        changes.append("generation")
    for key, value in {
        "generated_by": "ai_discovery",
        "generated_at": _utc_now_iso(),
        "source_queries": [],
        "confidence": "low",
    }.items():
        if key not in generation or generation.get(key) in (None, "", []):
            generation[key] = value
            changes.append(f"generation.{key}")
    if not isinstance(manifest.get("routing"), dict):
        manifest["routing"] = _autofix_default_routing(evidence_pack)
        changes.append("routing")
    if not isinstance(manifest.get("main_path"), list) or not manifest.get("main_path"):
        manifest["main_path"] = ["article_html", "pdf_fallback", "metadata_only"]
        changes.append("main_path")
    if not isinstance(manifest.get("success_criteria"), dict):
        manifest["success_criteria"] = {}
        changes.append("success_criteria")
    for step in manifest.get("main_path") or []:
        if step not in manifest["success_criteria"]:
            manifest["success_criteria"][step] = {}
            changes.append(f"success_criteria.{step}")
    if not isinstance(manifest.get("route_contract"), dict):
        manifest["route_contract"] = {}
        changes.append("route_contract")
    if not isinstance(manifest.get("markdown_contract"), dict):
        manifest["markdown_contract"] = {}
        changes.append("markdown_contract")
    if not isinstance(manifest.get("asset_profile"), dict):
        manifest["asset_profile"] = {
            "none": [],
            "body": ["figures", "body_tables", "formula_images"],
            "all": ["figures", "body_tables", "formula_images", "supplementary"],
        }
        changes.append("asset_profile")
    if not isinstance(manifest.get("asset_contract"), dict):
        manifest["asset_contract"] = {}
        changes.append("asset_contract")
    if not isinstance(manifest.get("supplementary_scope"), dict):
        manifest["supplementary_scope"] = {"selector": None, "url_pattern": None}
        changes.append("supplementary_scope")
    if not manifest.get("abstract_only_strategy"):
        manifest["abstract_only_strategy"] = "metadata_only"
        changes.append("abstract_only_strategy")
    if not isinstance(manifest.get("probe"), dict):
        manifest["probe"] = {
            "env_requirements": [],
            "requires_playwright": False,
            "requires_browser_runtime": False,
            "ping_url": _seed_base_url(domain) if domain else None,
        }
        changes.append("probe")
    else:
        probe = manifest["probe"]
        for key, value in {
            "env_requirements": [],
            "requires_playwright": False,
            "requires_browser_runtime": False,
        }.items():
            if key not in probe:
                probe[key] = value
                changes.append(f"probe.{key}")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, dict):
        fixtures = {}
        manifest["fixtures"] = fixtures
        changes.append("fixtures")
    if not isinstance(fixtures.get("doi_samples"), dict):
        fixtures["doi_samples"] = {}
        changes.append("fixtures.doi_samples")
    if not isinstance(fixtures.get("discovery_proof"), dict):
        fixtures["discovery_proof"] = {}
        changes.append("fixtures.discovery_proof")
    if not isinstance(manifest.get("extraction_hints"), dict):
        manifest["extraction_hints"] = {}
        changes.append("extraction_hints")
    for key, value in {
        "datalayer_signal_set": None,
        "text_marker_signal_set": None,
        "front_matter": None,
        "asset_retry": None,
        "metadata_merge": [],
    }.items():
        if key not in manifest["extraction_hints"]:
            manifest["extraction_hints"][key] = value
            changes.append(f"extraction_hints.{key}")
    if not isinstance(manifest.get("owner_reuse_exceptions"), list):
        manifest["owner_reuse_exceptions"] = []
        changes.append("owner_reuse_exceptions")
    if not isinstance(manifest.get("docs"), dict):
        manifest["docs"] = {
            "providers_md_capability_row": (
                f"{manifest['name']} | discovery-generated routing | pending implementation"
            ),
            "changelog_summary": (
                f"Add discovery-generated onboarding manifest for {manifest['name']}."
            ),
        }
        changes.append("docs")
    else:
        docs = manifest["docs"]
        if not docs.get("providers_md_capability_row"):
            docs["providers_md_capability_row"] = (
                f"{manifest['name']} | discovery-generated routing | pending implementation"
            )
            changes.append("docs.providers_md_capability_row")
        if not docs.get("changelog_summary"):
            docs["changelog_summary"] = (
                f"Add discovery-generated onboarding manifest for {manifest['name']}."
            )
            changes.append("docs.changelog_summary")


def _autofix_doi_samples(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    seed = (
        evidence_pack.get("provider_seed")
        if isinstance(evidence_pack.get("provider_seed"), Mapping)
        else {}
    )
    domain = seed.get("domain") if isinstance(seed.get("domain"), str) else None
    doi_samples = manifest["fixtures"]["doi_samples"]
    for purpose in DOI_SAMPLE_PURPOSES:
        sample = doi_samples.get(purpose)
        if not isinstance(sample, dict):
            candidate = _best_high_confidence_candidate(evidence_pack, purpose)
            doi_samples[purpose] = _sample_from_candidate(
                candidate, purpose=purpose, domain=domain
            )
            changes.append(f"fixtures.doi_samples.{purpose}")
            continue
        sample_doi = _normalize_doi_or_none(sample.get("doi"))
        raw_doi = sample.get("doi")
        invalid_doi = raw_doi not in (None, "") and sample_doi is None
        if (sample_doi is None or invalid_doi) and (
            candidate := _best_high_confidence_candidate(evidence_pack, purpose)
        ):
            doi_samples[purpose] = _sample_from_candidate(
                candidate, purpose=purpose, domain=domain
            )
            changes.append(f"fixtures.doi_samples.{purpose}.doi")
            continue
        if invalid_doi and purpose not in REQUIRED_DISCOVERY_SAMPLE_PURPOSES:
            sample["doi"] = None
            changes.append(f"fixtures.doi_samples.{purpose}.doi")
        for key, value in {
            "evidence_url": _seed_base_url(domain),
            "evidence_reason": (
                f"Discovery evidence records {purpose} as unavailable or pending confirmation."
            ),
            "observed_signals": [],
            "confidence": "low",
        }.items():
            if key not in sample or sample.get(key) in (None, ""):
                sample[key] = value
                changes.append(f"fixtures.doi_samples.{purpose}.{key}")


REQUIRED_DISCOVERY_SAMPLE_PURPOSES = {"structure", "figure", "references"}


def _autofix_discovery_proof(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    query_plan = (
        evidence_pack.get("query_plan")
        if isinstance(evidence_pack.get("query_plan"), Mapping)
        else {}
    )
    proof = manifest["fixtures"]["discovery_proof"]
    doi_samples = manifest["fixtures"]["doi_samples"]
    source_queries = manifest["generation"].setdefault("source_queries", [])
    if not isinstance(source_queries, list):
        manifest["generation"]["source_queries"] = []
        source_queries = manifest["generation"]["source_queries"]
        changes.append("generation.source_queries")
    for purpose in MANDATORY_DISCOVERY_PROOF_PURPOSES:
        entry = proof.get(purpose)
        if not isinstance(entry, dict):
            entry = {}
            proof[purpose] = entry
            changes.append(f"fixtures.discovery_proof.{purpose}")
        queries = [
            str(query)
            for query in (
                query_plan.get(purpose)
                if isinstance(query_plan.get(purpose), list)
                else []
            )
            if str(query).strip()
        ][:DISCOVERY_MAX_QUERIES_PER_PURPOSE]
        if len(queries) < 3:
            provider = str(
                manifest.get("name") or evidence_pack.get("provider") or "provider"
            )
            fallback_plan = build_discovery_query_plan(
                provider=provider,
                domain=None,
                doi_prefix=None,
            )
            queries = fallback_plan[purpose]
        existing_queries = entry.get("queries")
        if not isinstance(existing_queries, list) or len(existing_queries) < 3:
            entry["queries"] = queries
            changes.append(f"fixtures.discovery_proof.{purpose}.queries")
            active_queries = queries
        else:
            active_queries = [
                str(query) for query in existing_queries if str(query).strip()
            ]
        for query in active_queries:
            if query not in source_queries:
                source_queries.append(query)
                changes.append("generation.source_queries")
        sample = (
            doi_samples.get(purpose)
            if isinstance(doi_samples.get(purpose), dict)
            else {}
        )
        sample_doi = _normalize_doi_or_none(sample.get("doi"))
        candidate_dois = [
            doi
            for doi in (
                _normalize_doi_or_none(candidate.get("doi"))
                for candidate in _candidate_list(evidence_pack, purpose)
            )
            if doi
        ]
        if sample_doi and sample_doi not in candidate_dois:
            candidate_dois.insert(0, sample_doi)
        seen: set[str] = set()
        deduped = [doi for doi in candidate_dois if not (doi in seen or seen.add(doi))]
        existing_candidates = [
            doi
            for doi in (
                _normalize_doi_or_none(candidate)
                for candidate in (entry.get("candidates") or [])
            )
            if doi
        ]
        merged_candidates = list(existing_candidates)
        for doi in deduped:
            if doi not in merged_candidates:
                merged_candidates.append(doi)
        if entry.get("candidates") != merged_candidates:
            entry["candidates"] = merged_candidates
            changes.append(f"fixtures.discovery_proof.{purpose}.candidates")
        selected_value = sample.get("doi") if sample_doi else None
        if "selected_doi" not in entry or entry.get("selected_doi") != selected_value:
            entry["selected_doi"] = selected_value
            changes.append(f"fixtures.discovery_proof.{purpose}.selected_doi")
        exhausted = sample_doi is None
        if entry.get("exhausted") is not exhausted:
            entry["exhausted"] = exhausted
            changes.append(f"fixtures.discovery_proof.{purpose}.exhausted")
        rejections = entry.get("rejections")
        if not isinstance(rejections, dict):
            rejections = {}
            entry["rejections"] = rejections
            changes.append(f"fixtures.discovery_proof.{purpose}.rejections")
        for candidate in _candidate_list(evidence_pack, purpose):
            doi = _normalize_doi_or_none(candidate.get("doi"))
            if not doi or doi == sample_doi:
                continue
            if doi not in rejections:
                rejections[doi] = str(
                    candidate.get("rejection_hint")
                    or _candidate_rejection_hint(purpose)
                )
                changes.append(f"fixtures.discovery_proof.{purpose}.rejections.{doi}")
        summary = (
            f"Selected {sample_doi} from discovery evidence for {purpose}."
            if sample_doi
            else (
                f"Discovery evidence for {purpose} was exhausted without a "
                "high-confidence replacement; candidates are recorded with rejection reasons."
            )
        )
        if not entry.get("evidence_summary"):
            entry["evidence_summary"] = summary
            changes.append(f"fixtures.discovery_proof.{purpose}.evidence_summary")


def _autofix_contracts(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    route_contract = manifest["route_contract"]
    for step in manifest.get("main_path") or []:
        if step not in route_contract or not isinstance(route_contract.get(step), dict):
            route_contract[step] = _route_contract_template(str(step))
            changes.append(f"route_contract.{step}")
        elif not route_contract[step].get("success_requires"):
            route_contract[step].update(_route_contract_template(str(step)))
            changes.append(f"route_contract.{step}.success_requires")
    doi_samples = manifest["fixtures"]["doi_samples"]
    markdown_contract = manifest["markdown_contract"]
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict):
            continue
        doi = _normalize_doi_or_none(sample.get("doi"))
        if doi is None:
            continue
        contract = markdown_contract.get(purpose)
        observed_signals = [
            str(signal) for signal in sample.get("observed_signals") or []
        ]
        if not isinstance(contract, dict):
            markdown_contract[purpose] = _markdown_contract_template(
                purpose=str(purpose),
                doi=doi,
                observed_signals=observed_signals,
            )
            changes.append(f"markdown_contract.{purpose}")
            continue
        if contract.get("doi") != sample.get("doi"):
            contract["doi"] = sample.get("doi")
            changes.append(f"markdown_contract.{purpose}.doi")
        template = _markdown_contract_template(
            purpose=str(purpose),
            doi=doi,
            observed_signals=observed_signals,
        )
        for key in ["must_include", "must_not_include"]:
            if not contract.get(key):
                contract[key] = template[key]
                changes.append(f"markdown_contract.{purpose}.{key}")
    asset_contract = manifest["asset_contract"]
    figures = asset_contract.get("figures")
    figure_sample = (
        doi_samples.get("figure") if isinstance(doi_samples.get("figure"), dict) else {}
    )
    figure_signals = set(
        str(signal) for signal in figure_sample.get("observed_signals") or []
    )
    if not figure_signals:
        for candidate in _candidate_list(evidence_pack, "figure")[:1]:
            figure_signals.update(
                str(signal) for signal in candidate.get("observed_signals") or []
            )
    if {"figures", "body_figures", "body_images"} & figure_signals:
        template = {
            "inline": "body",
            "download": "required",
            "purposes": ["figure"],
            "exception_reason": None,
        }
    else:
        template = {
            "inline": "not_applicable",
            "download": "not_applicable",
            "purposes": ["figure"],
            "exception_reason": (
                "Discovery evidence did not show stable downloadable body figure assets."
            ),
        }
    if not isinstance(figures, dict):
        asset_contract["figures"] = template
        changes.append("asset_contract.figures")
    else:
        for key, value in template.items():
            current = figures.get(key)
            if (
                key not in figures
                or current in ([], "")
                or (current is None and value is not None)
            ):
                figures[key] = value
                changes.append(f"asset_contract.figures.{key}")


def autofix_manifest_data(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    *,
    targeted: bool = False,
) -> dict[str, Any]:
    changes: list[str] = []
    _ensure_manifest_containers(manifest, evidence_pack, changes)
    _autofix_doi_samples(manifest, evidence_pack, changes)
    _autofix_discovery_proof(manifest, evidence_pack, changes)
    _autofix_contracts(manifest, evidence_pack, changes)
    return {
        "changed": bool(changes),
        "changed_paths": sorted(set(changes)),
        "targeted": targeted,
    }


def _read_manifest_for_autofix(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest cannot be loaded for autofix.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="autofix-manifest",
            details={"path": path.as_posix(), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest root must be a mapping for autofix.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="autofix-manifest",
            details={"path": path.as_posix()},
        )
    return data


def autofix_manifest_file(
    *,
    manifest_path: Path,
    evidence_pack_path: Path,
    write: bool,
    targeted: bool = False,
) -> dict[str, Any]:
    manifest = _read_manifest_for_autofix(manifest_path)
    evidence_pack = _load_evidence_pack(evidence_pack_path)
    result = autofix_manifest_data(manifest, evidence_pack, targeted=targeted)
    if write and result["changed"]:
        write_text(
            manifest_path,
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        )
    return {
        **result,
        "manifest": manifest_path.as_posix(),
        "evidence_pack": evidence_pack_path.as_posix(),
        "write": write,
    }


def inspect_manifest_discovery(
    *,
    manifest: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
) -> dict[str, Any]:
    fixtures = (
        manifest.get("fixtures")
        if isinstance(manifest.get("fixtures"), Mapping)
        else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), Mapping)
        else {}
    )
    proof = (
        fixtures.get("discovery_proof")
        if isinstance(fixtures.get("discovery_proof"), Mapping)
        else {}
    )
    purposes: dict[str, Any] = {}
    low_confidence: list[str] = []
    proof_gaps: list[dict[str, Any]] = []
    for purpose in DOI_SAMPLE_PURPOSES:
        candidates = _candidate_list(evidence_pack, purpose)
        top = candidates[0] if candidates else None
        sample = (
            doi_samples.get(purpose)
            if isinstance(doi_samples.get(purpose), Mapping)
            else {}
        )
        sample_confidence = (
            sample.get("confidence") if isinstance(sample, Mapping) else None
        )
        purposes[purpose] = {
            "sample_doi": sample.get("doi") if isinstance(sample, Mapping) else None,
            "sample_confidence": sample_confidence,
            "candidate_count": len(candidates),
            "top_candidates": [
                {
                    "doi": candidate.get("doi"),
                    "score": candidate.get("score"),
                    "confidence": candidate.get("confidence"),
                    "observed_signals": candidate.get("observed_signals"),
                    "evidence_url": candidate.get("evidence_url"),
                }
                for candidate in candidates[:3]
            ],
        }
        if top is None or top.get("confidence") == "low" or sample_confidence == "low":
            low_confidence.append(purpose)
    for purpose in MANDATORY_DISCOVERY_PROOF_PURPOSES:
        entry = proof.get(purpose) if isinstance(proof.get(purpose), Mapping) else None
        sample = (
            doi_samples.get(purpose)
            if isinstance(doi_samples.get(purpose), Mapping)
            else {}
        )
        if entry is None:
            proof_gaps.append({"purpose": purpose, "gap": "missing_discovery_proof"})
            continue
        if len(entry.get("queries") or []) < 3:
            proof_gaps.append({"purpose": purpose, "gap": "fewer_than_three_queries"})
        if entry.get("selected_doi") != sample.get("doi"):
            proof_gaps.append({"purpose": purpose, "gap": "selected_doi_mismatch"})
        candidates = entry.get("candidates") or []
        rejections = (
            entry.get("rejections")
            if isinstance(entry.get("rejections"), Mapping)
            else {}
        )
        for candidate in candidates:
            if candidate != entry.get("selected_doi") and candidate not in rejections:
                proof_gaps.append(
                    {
                        "purpose": purpose,
                        "gap": "missing_rejection",
                        "doi": candidate,
                    }
                )
    return {
        "provider": manifest.get("name") or evidence_pack.get("provider"),
        "purposes": purposes,
        "low_confidence_purposes": low_confidence,
        "proof_gaps": proof_gaps,
    }
