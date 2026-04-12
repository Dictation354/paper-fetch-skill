"""Wiley provider client."""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

from ..config import build_user_agent
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure, build_text_preview
from ..metadata_types import ProviderMetadata
from ..models import article_from_markdown, metadata_only_article, normalize_text
from ..publisher_identity import normalize_doi
from ..utils import (
    build_output_path,
    empty_asset_results,
    save_payload,
)
from .base import ProviderClient, ProviderFailure, RawFulltextPayload, map_request_failure

WILEY_PDF_TEXT_MIN_CHARS = 1200
WILEY_PDF_FULLTEXT_MARKERS = (
    "abstract",
    "introduction",
    "methods",
    "materials and methods",
    "results",
    "discussion",
    "conclusion",
    "references",
    "keywords",
)
WILEY_PDF_SECTION_HEADINGS = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "methods": "Methods",
    "materials and methods": "Materials and Methods",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "references": "References",
    "keywords": "Keywords",
}


def is_pdf_payload(raw_payload: RawFulltextPayload) -> bool:
    content_type = (raw_payload.content_type or "").split(";", 1)[0].strip().lower()
    source_path = urllib.parse.urlparse(raw_payload.source_url or "").path.lower()
    return content_type == "application/pdf" or source_path.endswith(".pdf") or raw_payload.body.startswith(b"%PDF-")


def extract_pdf_text(body: bytes) -> str:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - exercised through metadata-only fallback
        raise RuntimeError("PyMuPDF is required for Wiley PDF extraction.") from exc

    try:
        with fitz.open(stream=body, filetype="pdf") as document:
            page_text = [page.get_text("text") for page in document]
    except Exception as exc:
        raise RuntimeError(f"Unable to parse Wiley PDF payload: {exc}") from exc

    raw_text = "\n\n".join(chunk for chunk in page_text if chunk)
    raw_text = re.sub(r"(?<=\w)-\n(?=\w)", "", raw_text)
    raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
    return normalize_text(raw_text)


def is_usable_pdf_text(text: str) -> bool:
    normalized = normalize_text(text)
    if len(normalized) < WILEY_PDF_TEXT_MIN_CHARS:
        return False
    lowered = normalized.lower()
    marker_hits = sum(1 for marker in WILEY_PDF_FULLTEXT_MARKERS if marker in lowered)
    return marker_hits >= 1 or len(normalized) >= 4000


def pdf_text_to_markdown(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""

    def detect_heading(line: str) -> str | None:
        candidate = normalize_text(line)
        if not candidate:
            return None
        cleaned = re.sub(r"[:.]+$", "", candidate).strip().lower()
        if len(cleaned.split()) > 4:
            return None
        return WILEY_PDF_SECTION_HEADINGS.get(cleaned)

    def render_section_text(lines: list[str]) -> str:
        paragraphs: list[str] = []
        current_paragraph: list[str] = []
        for line in lines:
            cleaned = normalize_text(line)
            if not cleaned:
                if current_paragraph:
                    paragraphs.append(" ".join(current_paragraph))
                    current_paragraph = []
                continue
            current_paragraph.append(cleaned)
        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))
        return "\n\n".join(paragraphs).strip()

    sections: list[tuple[str, str]] = []
    preamble_lines: list[str] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush_current_section() -> None:
        if current_heading is None:
            return
        rendered = render_section_text(current_lines)
        if rendered:
            sections.append((current_heading, rendered))

    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            if current_heading is None:
                if preamble_lines and preamble_lines[-1] != "":
                    preamble_lines.append("")
            elif current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        heading = detect_heading(line)
        if heading:
            if current_heading is None:
                if preamble_lines:
                    if heading == "Abstract":
                        current_heading = "Abstract"
                        current_lines = list(preamble_lines)
                        preamble_lines = []
                        continue
                    rendered_preamble = render_section_text(preamble_lines)
                    if rendered_preamble:
                        sections.append(("Abstract", rendered_preamble))
                    preamble_lines = []
            elif current_heading == heading and not current_lines:
                continue
            else:
                flush_current_section()
            current_heading = heading
            current_lines = []
            continue

        if current_heading is None:
            preamble_lines.append(line)
        else:
            current_lines.append(line)

    if current_heading is None:
        rendered_full_text = render_section_text(preamble_lines)
        if not rendered_full_text:
            return ""
        return f"## Full Text\n\n{rendered_full_text}"

    flush_current_section()
    rendered_sections = [
        f"## {heading}\n\n{section_text}"
        for heading, section_text in sections
        if section_text
    ]
    return "\n\n".join(rendered_sections).strip()


class WileyClient(ProviderClient):
    name = "wiley"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.endpoint_template = env.get("WILEY_TDM_URL_TEMPLATE", "").strip()
        self.token = env.get("WILEY_TDM_TOKEN", "").strip()
        self.auth_header = env.get("WILEY_TDM_AUTH_HEADER", "Wiley-TDM-Client-Token").strip() or "Wiley-TDM-Client-Token"
        self.user_agent = build_user_agent(env)

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            "not_supported",
            "Wiley official metadata retrieval is not implemented because the public docs in this repo do not define a stable metadata endpoint.",
        )

    def fetch_fulltext(self, doi: str, metadata: ProviderMetadata, output_dir: Path | None) -> dict[str, Any]:
        payload = self.fetch_raw_fulltext(doi, metadata)
        normalized_doi = normalize_doi(doi)
        output_path = build_output_path(output_dir, normalized_doi, metadata.get("title"), payload.content_type, payload.source_url)
        return {
            "attempted": True,
            "status": "saved" if output_path else "fetched",
            "provider": "wiley",
            "official_provider": True,
            "source_url": payload.source_url,
            "content_type": payload.content_type,
            "path": save_payload(output_path, payload.body),
            "markdown_path": None,
            "downloaded_bytes": len(payload.body),
            "content_preview": build_text_preview(payload.body, payload.content_type),
            "reason": str(payload.metadata.get("reason") or "Downloaded full text from the configured Wiley TDM endpoint."),
            **empty_asset_results(),
        }

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", "Wiley full-text retrieval requires a DOI.")
        if not self.endpoint_template or not self.token:
            raise ProviderFailure(
                "not_configured",
                "WILEY_TDM_URL_TEMPLATE and WILEY_TDM_TOKEN are required for Wiley full-text retrieval.",
            )

        encoded_doi = urllib.parse.quote(normalized_doi, safe="")
        url = self.endpoint_template.format(doi=encoded_doi, raw_doi=normalized_doi)
        headers = {
            self.auth_header: self.token,
            "User-Agent": self.user_agent,
            # The public Wiley TDM endpoint has been observed to return PDF by default.
            # Other content formats require Wiley to provide explicit support details.
            "Accept": "*/*",
        }
        try:
            response = self.transport.request(
                "GET",
                url,
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_rate_limit=True,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        content_type = response["headers"].get("content-type", "application/octet-stream")
        needs_local_copy = not (content_type.startswith("text/") or content_type.endswith("xml"))
        return RawFulltextPayload(
            provider="wiley",
            source_url=response["url"],
            content_type=content_type,
            body=response["body"],
            metadata={"reason": "Downloaded full text from the configured Wiley TDM endpoint."},
            needs_local_copy=needs_local_copy,
        )

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        doi = normalize_doi(metadata.get("doi"))
        warnings: list[str] = []
        content_type = (raw_payload.content_type or "").split(";", 1)[0].strip().lower()
        if content_type.startswith("text/"):
            try:
                text = raw_payload.body.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            if text.strip():
                warnings.append("Wiley full text was returned as plain text/HTML instead of XML.")
            return article_from_markdown(
                source="wiley",
                metadata=metadata,
                doi=doi or None,
                markdown_text=text,
                warnings=warnings,
                source_trail=["fulltext:wiley_text_ok"],
            )
        if is_pdf_payload(raw_payload):
            try:
                extracted_text = extract_pdf_text(raw_payload.body)
            except RuntimeError as exc:
                warnings.append(str(exc))
                return metadata_only_article(
                    source="wiley",
                    metadata=metadata,
                    doi=doi or None,
                    warnings=warnings,
                    source_trail=["fulltext:wiley_pdf_extract_fail"],
                )
            if is_usable_pdf_text(extracted_text):
                warnings.append("Wiley full text was extracted from PDF rather than XML.")
                return article_from_markdown(
                    source="wiley",
                    metadata=metadata,
                    doi=doi or None,
                    markdown_text=pdf_text_to_markdown(extracted_text),
                    warnings=warnings,
                    source_trail=["fulltext:wiley_pdf_extract_ok"],
                )
            warnings.append("Wiley PDF extraction did not produce enough usable article text.")
            return metadata_only_article(
                source="wiley",
                metadata=metadata,
                doi=doi or None,
                warnings=warnings,
                source_trail=["fulltext:wiley_pdf_extract_fail"],
            )
        warnings.append("Wiley full text is available only as PDF/binary in this workflow.")
        return metadata_only_article(
            source="wiley",
            metadata=metadata,
            doi=doi or None,
            warnings=warnings,
            source_trail=["fulltext:wiley_binary_only"],
        )
