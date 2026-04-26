"""Provider-neutral landing-page HTML fetch helpers."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ...http import DEFAULT_TIMEOUT_SECONDS, HttpTransport
from ...metadata_types import HtmlMetadata
from ._metadata import parse_html_metadata
from ._runtime import decode_html

REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})

HtmlDecoder = Callable[[bytes], str]
HtmlMetadataParser = Callable[[str, str], HtmlMetadata]


@dataclass(frozen=True)
class LandingHtmlFetchResult:
    response: Mapping[str, Any]
    final_url: str
    html_text: str
    metadata: HtmlMetadata
    status_code: int
    headers: Mapping[str, str]


class LandingRedirectLimitExceeded(Exception):
    """Raised when a caller chooses to treat redirect exhaustion as failure."""

    def __init__(self, url: str, max_redirects: int) -> None:
        super().__init__(f"Landing HTML retrieval exceeded {max_redirects} redirects for {url}.")
        self.url = url
        self.max_redirects = max_redirects


def _response_url(response: Mapping[str, Any], current_url: str) -> str:
    return urllib.parse.urljoin(current_url, str(response.get("url") or "").strip() or current_url)


def _response_headers(response: Mapping[str, Any]) -> Mapping[str, str]:
    headers = response.get("headers") or {}
    return headers if isinstance(headers, Mapping) else {}


def _redirect_location(response: Mapping[str, Any]) -> str:
    return str(_response_headers(response).get("location") or "").strip()


def _status_code(response: Mapping[str, Any]) -> int:
    return int(response.get("status_code") or 0)


def _build_result(
    response: Mapping[str, Any],
    *,
    current_url: str,
    decoder: HtmlDecoder,
    metadata_parser: HtmlMetadataParser,
) -> LandingHtmlFetchResult:
    final_url = _response_url(response, current_url)
    html_text = decoder(response["body"])
    metadata = metadata_parser(html_text, final_url)
    return LandingHtmlFetchResult(
        response=response,
        final_url=final_url,
        html_text=html_text,
        metadata=metadata,
        status_code=_status_code(response),
        headers=_response_headers(response),
    )


def fetch_landing_html(
    landing_url: str,
    *,
    transport: HttpTransport,
    headers: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retry_on_transient: bool = True,
    max_redirects: int = 0,
    redirect_base: str = "response_url",
    raise_on_redirect_limit: bool = False,
    decoder: HtmlDecoder = decode_html,
    metadata_parser: HtmlMetadataParser = parse_html_metadata,
) -> LandingHtmlFetchResult:
    """Fetch a landing HTML page and parse provider-neutral metadata.

    ``redirect_base`` preserves legacy caller behavior for relative redirect
    resolution: ``response_url`` uses the response URL as the base, while
    ``current_url`` uses the URL that was requested for that hop.
    """

    current_url = landing_url
    request_headers = dict(headers or {})
    response = transport.request(
        "GET",
        current_url,
        headers=request_headers,
        timeout=timeout,
        retry_on_transient=retry_on_transient,
    )

    for _ in range(max(0, int(max_redirects))):
        status_code = _status_code(response)
        redirect_location = _redirect_location(response)
        if status_code not in REDIRECT_STATUS_CODES or not redirect_location:
            return _build_result(
                response,
                current_url=current_url,
                decoder=decoder,
                metadata_parser=metadata_parser,
            )
        final_url = _response_url(response, current_url)
        base_url = current_url if redirect_base == "current_url" else final_url
        current_url = urllib.parse.urljoin(base_url, redirect_location)
        response = transport.request(
            "GET",
            current_url,
            headers=request_headers,
            timeout=timeout,
            retry_on_transient=retry_on_transient,
        )

    if raise_on_redirect_limit:
        raise LandingRedirectLimitExceeded(landing_url, max(0, int(max_redirects)))

    return _build_result(
        response,
        current_url=current_url,
        decoder=decoder,
        metadata_parser=metadata_parser,
    )
