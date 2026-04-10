"""Fallback helpers for publisher links advertised in metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from fetch_common import (
    HttpTransport,
    ProviderFailure,
    RequestFailure,
    build_output_path,
    build_text_preview,
    empty_asset_results,
    map_request_failure,
    save_payload,
)


def download_from_fulltext_links(
    transport: HttpTransport,
    metadata: Mapping[str, Any],
    *,
    output_dir: Path | None,
    user_agent: str,
) -> dict[str, Any]:
    links = metadata.get("fulltext_links") or []
    if not isinstance(links, list) or not links:
        raise ProviderFailure("no_result", "No full-text links are available in the metadata payload.")

    preferred_order = {
        "application/pdf": 0,
        "application/xml": 1,
        "text/xml": 1,
        "application/jats+xml": 1,
        "text/plain": 2,
        "text/html": 3,
    }

    sorted_links = sorted(
        [item for item in links if isinstance(item, dict) and item.get("url")],
        key=lambda item: preferred_order.get((item.get("content_type") or "").lower(), 9),
    )

    for link in sorted_links:
        url = link["url"]
        try:
            response = transport.request(
                "GET",
                url,
                headers={"User-Agent": user_agent, "Accept": "*/*"},
            )
        except RequestFailure as exc:
            if exc.status_code in {401, 403, 404}:
                continue
            raise map_request_failure(exc) from exc

        content_type = response["headers"].get("content-type", link.get("content_type"))
        output_path = build_output_path(output_dir, metadata.get("doi"), metadata.get("title"), content_type, response["url"])
        return {
            "attempted": True,
            "status": "saved" if output_path else "fetched",
            "provider": "crossref-link",
            "official_provider": False,
            "source_url": response["url"],
            "content_type": content_type,
            "path": save_payload(output_path, response["body"]),
            "markdown_path": None,
            "downloaded_bytes": len(response["body"]),
            "content_preview": build_text_preview(response["body"], content_type),
            "reason": "Downloaded full text from a publisher link advertised in Crossref metadata.",
            **empty_asset_results(),
        }

    raise ProviderFailure("no_access", "No downloadable full-text link succeeded.")
