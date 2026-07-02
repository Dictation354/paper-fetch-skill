# ruff: noqa: F401
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from paper_fetch.providers import _ieee_html, _ieee_metadata, ieee as ieee_provider
from paper_fetch.providers._pdf_common import PdfFetchFailure, PdfFetchResult
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.ieee import IeeeClient
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers
from paper_fetch.workflow.types import FetchStrategy
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_dir_for_doi,
    golden_criteria_manifest,
)
from tests.paths import REPO_ROOT
from tests.unit._paper_fetch_support import RecordingTransport


def _landing_html(
    *,
    doi: str = "10.1109/ACCESS.2024.3352924",
    article_number: str = "10388355",
    dynamic: bool = True,
    abstract: str = "IEEE abstract text.",
) -> bytes:
    metadata = {
        "articleNumber": article_number,
        "articleId": article_number,
        "doi": doi,
        "title": "IEEE Dynamic Article",
        "publicationTitle": "IEEE Access",
        "publicationDate": "2024",
        "abstract": abstract,
        "authors": [{"name": "Alice Example"}, {"name": "Bob Example"}],
        "isDynamicHtml": dynamic,
        "html_flag": False,
        "ml_html_flag": dynamic,
        "pdfUrl": f"/stamp/stamp.jsp?tp=&arnumber={article_number}",
        "pdfPath": f"/iel7/6287639/10380310/{article_number}.pdf",
    }
    return (
        "<html><head><title>IEEE Dynamic Article</title></head><body>"
        "<script>xplGlobal = {document: {}}; xplGlobal.document.metadata = "
        + json.dumps(metadata)
        + ";</script></body></html>"
    ).encode("utf-8")


def _dynamic_html(article_number: str = "10388355") -> bytes:
    paragraph = "This IEEE body paragraph describes methods, results, and evaluation evidence across several experiments. "
    return (
        '<?xml version="1.0" encoding="UTF-8"?><response><accessType>Open Access</accessType>'
        '<div id="BodyWrapper"><div id="article">'
        '<div class="section" id="sec1"><h2>Introduction</h2><p>'
        + paragraph
        * 25
        + '</p><figure id="fig1"><figcaption>Fig. 1. Example system overview.</figcaption></figure></div>'
        '<div class="section_2" id="sec2"><h3>Results</h3><p>'
        + paragraph
        * 25
        + "</p><tex-math>\\alpha + \\beta</tex-math><table><tr><td>Metric</td></tr></table></div>"
        '<a href="javascript:void()" data-docId="'
        + article_number
        + '">Show All</a></div></div></response>'
    ).encode("utf-8")


def _raw_ieee_html_payload(
    *,
    doi: str,
    article_number: str,
    html_text: str,
    source_url: str,
    trace_markers: list[str] | None = None,
) -> RawFulltextPayload:
    metadata = {
        "doi": doi,
        "title": "IEEE Dynamic Article",
        "abstract": "IEEE abstract text.",
        "authors": ["Alice Example", "Bob Example"],
        "article_number": article_number,
        "articleNumber": article_number,
        "landing_page_url": f"https://ieeexplore.ieee.org/document/{article_number}/",
    }
    extraction = _ieee_html._extract_ieee_html(html_text, source_url, metadata=metadata)
    body = extraction.html_text.encode("utf-8")
    return RawFulltextPayload(
        provider="ieee",
        source_url=source_url,
        content_type="text/html",
        body=body,
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=dict(metadata),
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "marker_counts": extraction.marker_counts,
                }
            },
            reason="Downloaded full text from the IEEE Xplore clean-browser HTML fallback route.",
            fetcher="playwright_html",
            extracted_assets=extraction.extracted_assets,
        ),
        trace=trace_from_markers(trace_markers or ["fulltext:ieee_html_ok"]),
        merged_metadata=metadata,
    )


def _dynamic_html_with_ieee_media_assets(article_number: str = "10388355") -> bytes:
    paragraph = "This IEEE body paragraph describes methods, results, and evaluation evidence across several experiments. "
    return (
        '<?xml version="1.0" encoding="UTF-8"?><response><accessType>Open Access</accessType>'
        '<div id="BodyWrapper"><div id="article">'
        '<div class="section" id="sec1"><h2>Introduction</h2><p>'
        + paragraph
        * 25
        + "</p>"
        '<a href="/assets/img/icon.support.gif">support</a>'
        '<img src="/assets/img/icon.support.gif" alt="Formula"/>'
        '<div class="figure figure-full" id="fig1">'
        '<a href="/mediastore/IEEE/content/media/'
        + article_number
        + "/"
        + article_number
        + '-fig-1-large.gif">'
        '<img src="/mediastore/IEEE/content/media/'
        + article_number
        + "/"
        + article_number
        + '-fig-1-small.gif" alt="System overview image"/></a>'
        '<div class="figcaption"><span class="title">Fig. 1.</span> Example system overview.</div>'
        "</div>"
        '<div class="figure figure-full table" id="table1">'
        '<a href="/mediastore/IEEE/content/media/'
        + article_number
        + "/"
        + article_number
        + '-table-1-large.gif">'
        '<img src="/mediastore/IEEE/content/media/'
        + article_number
        + "/"
        + article_number
        + '-table-1-small.gif" alt="Table comparison image"/></a>'
        '<div class="figcaption"><span class="title">Table I.</span> Comparison of methods.</div>'
        "</div>"
        '<div class="section supplementary-materials" id="supplementary-materials"><h2>Supplementary Materials</h2>'
        '<a href="/documents/supplementary.pdf">Supplementary PDF</a></div>'
        '<div class="section multimedia-files" id="multimedia"><h2>Multimedia</h2>'
        '<a href="/documents/multimedia.mp4" title="Multimedia file">Movie clip</a></div>'
        '</div><div class="section_2" id="sec2"><h3>Results</h3><p>'
        + paragraph * 25
        + "</p></div></div></div></response>"
    ).encode("utf-8")


def _dynamic_html_with_ieee_equation_alt_table_asset(
    article_number: str = "10388355",
) -> bytes:
    paragraph = "This IEEE body paragraph describes methods, results, and evaluation evidence across several experiments. "
    return (
        '<?xml version="1.0" encoding="UTF-8"?><response><accessType>Open Access</accessType>'
        '<div id="BodyWrapper"><div id="article">'
        '<div class="section" id="sec1"><h2>Results</h2><p>' + paragraph * 25 + "</p>"
        '<div class="figure figure-full table" id="table1">'
        '<a href="/mediastore/IEEE/content/media/'
        + article_number
        + "/"
        + article_number
        + '-table-1-large.gif">'
        '<img src="/mediastore/IEEE/content/media/'
        + article_number
        + "/"
        + article_number
        + '-table-1-small.gif" alt="Equation comparison table image"/></a>'
        '<div class="figcaption"><span class="title">Table I.</span> Equation comparison table.</div>'
        "</div></div></div></div></response>"
    ).encode("utf-8")


IEEE_REAL_HTML_SAMPLES = {
    "ACCESS": ("10.1109/ACCESS.2024.3352924", "10388355"),
    "CICTN": ("10.1109/CICTN64563.2025.10932570", "10932570"),
    "TBME": ("10.1109/TBME.2024.3434477", "10612240"),
    "TCOMM": ("10.1109/TCOMM.2024.3395332", "10511075"),
    "TDEI": ("10.1109/TDEI.2024.3373549", "10459335"),
    "TE": ("10.1109/TE.2024.3376795", "10496257"),
    "TIM": ("10.1109/TIM.2024.3509573", "10772041"),
}


def _real_ieee_fixture_metadata(*, doi: str, article_number: str) -> dict[str, object]:
    fixture_root = golden_criteria_dir_for_doi(doi)
    landing_metadata = _ieee_metadata._parse_landing_metadata(
        golden_criteria_asset(doi, "landing.html").read_text(encoding="utf-8")
    )
    metadata = _ieee_metadata._merge_ieee_metadata(
        {"doi": doi},
        landing_metadata,
        f"https://ieeexplore.ieee.org/document/{article_number}/",
    )
    references_payload = json.loads(
        (fixture_root / "references.json").read_text(encoding="utf-8")
    )
    references = _ieee_metadata._references_from_ieee_reference_payload(
        references_payload
    )
    if references:
        metadata["references"] = references
    return metadata


def _real_ieee_fixture_article(
    *,
    doi: str,
    article_number: str,
    tmpdir: Path,
):
    fixture_root = golden_criteria_dir_for_doi(doi)
    source_url = (
        f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
    )
    metadata = _real_ieee_fixture_metadata(doi=doi, article_number=article_number)
    extraction = _ieee_html._extract_ieee_html(
        (fixture_root / "original.html").read_text(encoding="utf-8"),
        source_url,
        metadata=metadata,
    )
    downloaded_assets: list[dict[str, object]] = []
    for index, item in enumerate(extraction.extracted_assets, start=1):
        if item.get("kind") not in {"figure", "table"} or item.get("section") != "body":
            continue
        asset_url = (
            item.get("url") or item.get("full_size_url") or item.get("preview_url")
        )
        if not asset_url:
            continue
        path = tmpdir / f"ieee-asset-{index}.gif"
        path.write_bytes(b"GIF89a\x01\x00\x01\x00\x00\x00;")
        downloaded = dict(item)
        downloaded.update(
            {
                "path": str(path),
                "download_url": asset_url,
                "source_url": asset_url,
                "content_type": "image/gif",
                "download_tier": "full_size",
            }
        )
        downloaded_assets.append(downloaded)

    body = extraction.html_text.encode("utf-8")
    raw_payload = RawFulltextPayload(
        provider="ieee",
        source_url=source_url,
        content_type="text/html",
        body=body,
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=metadata,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "marker_counts": extraction.marker_counts,
                }
            },
            reason="Loaded IEEE real HTML fixture.",
            extracted_assets=extraction.extracted_assets,
        ),
        trace=trace_from_markers(["fulltext:ieee_html_ok"]),
        merged_metadata=metadata,
    )
    client = IeeeClient(RecordingTransport({}), {})
    article = client.to_article_model(
        {"doi": doi}, raw_payload, downloaded_assets=downloaded_assets
    )
    markdown = article.to_ai_markdown(
        asset_profile="body", include_figures="inline", max_tokens="full_text"
    )
    return extraction, article, markdown


__all__ = [name for name in globals() if not name.startswith("__")]
