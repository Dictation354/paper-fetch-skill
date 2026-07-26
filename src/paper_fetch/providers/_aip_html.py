"""AIP Publishing provider-owned browser-workflow rules."""

from __future__ import annotations

from difflib import SequenceMatcher
from functools import partial
import re
from typing import Any
from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

from ..extraction.html.inline import render_html_inline_node
from ..extraction.html.parsing import choose_parser
from ..models import markdown_image_fullmatch, normalize_markdown_text
from ..publisher_identity import DOI_CORE_PATTERN
from ..utils import normalize_text
from ._html_authors import (
    AuthorExtractionPipeline,
    AuthorStep,
    extract_jsonld_authors,
    extract_meta_authors,
)
from ._html_references import extract_numbered_references_from_html


AIP_JSONLD_ARTICLE_TYPES = frozenset({"article", "scholarlyarticle"})
# SITE_UI_COPY_REGRESSION_MARKER: AIP article chrome selectors owned by provider cleanup policy.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup removes these only from AIP article HTML.
AIP_DOM_CHROME_SELECTORS = (
    ".article-metrics",
    ".article-tools",
    ".articleTool",
    ".article-toolbar",
    ".article-nav",
    ".articleNav",
    ".article-navigation",
    ".citationTools",
    ".download-citation",
    ".relatedContent",
    ".recommendations",
    ".rightsLink",
    ".share-tools",
    ".toc-widget",
    "[class*='ArticleMetrics']",
    "[class*='article-metrics']",
    "[class*='citation-tools']",
    "script",
    "style",
    "noscript",
)
# SITE_UI_COPY_REGRESSION_MARKER: AIP article navigation/action labels owned by provider cleanup policy.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup removes these only after AIP markdown rendering.
AIP_MARKDOWN_CHROME_PATTERNS = (
    re.compile(r"\n{2,}Topics\n\n[^#\n][^\n]*(?=\n\n##\s+[IVX0-9A-Z])", re.IGNORECASE),
    re.compile(
        r"\n{2,}Article (?:Navigation|Contents)\n\n.*?(?=\n\n##\s+)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\n{2,}(?:Download Citation|Get Permissions|Share Icon)\b.*?(?=\n\n##\s+)",
        re.IGNORECASE | re.DOTALL,
    ),
)
AIP_FIGURE_MODAL_ACTION_TEXTS = frozenset(
    {
        "close modal",
        "open figure viewer",
        "view large",
    }
)
AIP_BOLD_FIGURE_CAPTION_RE = re.compile(
    r"^\*\*\s*fig(?:ure)?\.?\s*\d+[A-Za-z]?\..*?\*\*$",
    re.IGNORECASE | re.DOTALL,
)
AIP_BOLD_BLOCK_RE = re.compile(r"^\*\*.+\*\*$", re.DOTALL)
AIP_FIGURE_LABEL_RE = re.compile(
    r"^\s*fig(?:ure)?\.?\s*\d+[A-Za-z]?\.?\s*",
    re.IGNORECASE,
)
AIP_MARKDOWN_STRONG_WRAPPER_RE = re.compile(r"^\*\*(?P<text>.*)\*\*$", re.DOTALL)
AIP_CAPTION_KEY_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)
AIP_MIN_MODAL_CAPTION_KEY_LENGTH = 40
AIP_TITLE_BADGE_RE = re.compile(r"(?:\s+\*?open access\*?)+\s*$", re.IGNORECASE)
AIP_RETAINED_BACK_MATTER_HEADINGS = frozenset(
    {
        "acknowledgments",
        "acknowledgements",
        "author contributions",
        "author declarations",
        "conflict of interest",
        "supplemental material",
        "supplementary material",
    }
)
AIP_BACK_MATTER_STOP_HEADINGS = frozenset(
    {
        "data availability",
        "references",
    }
)
AIP_HEADING_TAG_RE = re.compile(r"^h[1-6]$", re.IGNORECASE)
AIP_REFERENCE_META_SPLIT = re.compile(r"\s*;\s*")
AIP_REFERENCE_FIELD_RE = re.compile(r"citation_([a-z_]+)=([^;]+)")
AIP_REFERENCE_DOI_RE = re.compile(DOI_CORE_PATTERN, flags=re.IGNORECASE)
AIP_REFERENCE_YEAR_RE = re.compile(r"\b((?:18|19|20)\d{2})\b")


def _extract_jsonld_authors(html_text: str) -> list[str]:
    return extract_jsonld_authors(
        html_text,
        article_types=AIP_JSONLD_ARTICLE_TYPES,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep(
        "meta",
        partial(extract_meta_authors, keys={"citation_author", "dc.creator"}),
    ),
    AuthorStep("jsonld", _extract_jsonld_authors),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


def aip_classify_heading(heading: str, title: str | None) -> str | None:
    del title
    normalized = _aip_normalized_heading(heading)
    if normalized in AIP_RETAINED_BACK_MATTER_HEADINGS:
        return "body_heading"
    return None


def _aip_normalized_heading(heading: str) -> str:
    normalized = normalize_text(heading).rstrip(".:").lower()
    return re.sub(r"^(?:[ivxlcdm]+|\d+)\.?\s+", "", normalized)


def _decompose_matching(container: Any, selectors: tuple[str, ...]) -> None:
    if not isinstance(container, Tag):
        return
    for selector in selectors:
        for node in list(container.select(selector)):
            node.decompose()


def aip_before_block_normalization(container: Any) -> None:
    from .atypon_browser_workflow.profile import (
        _drop_promotional_blocks,
        _promo_block_tokens,
    )

    _decompose_matching(container, AIP_DOM_CHROME_SELECTORS)
    _drop_promotional_blocks(container, promo_block_tokens=_promo_block_tokens("aip"))


def aip_body_container(container: Any) -> None:
    _decompose_matching(container, AIP_DOM_CHROME_SELECTORS)


def _aip_caption_key(block: str) -> str:
    text = normalize_markdown_text(block)
    strong_match = AIP_MARKDOWN_STRONG_WRAPPER_RE.match(text)
    if strong_match is not None:
        text = strong_match.group("text")
    text = AIP_FIGURE_LABEL_RE.sub("", text, count=1)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("*", "").replace("_", "")
    return AIP_CAPTION_KEY_NON_WORD_RE.sub("", text.lower())


def _aip_is_duplicate_modal_caption(block: str, caption_key: str) -> bool:
    if not caption_key:
        return False
    block_key = _aip_caption_key(block)
    if not block_key:
        return False
    if block_key == caption_key:
        return True
    shorter, longer = sorted((block_key, caption_key), key=len)
    return len(shorter) >= 80 and (
        shorter in longer
        or SequenceMatcher(None, block_key, caption_key).ratio() >= 0.82
    )


def _drop_aip_figure_modal_blocks(markdown_text: str) -> str:
    blocks = [
        normalize_markdown_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    if not blocks:
        return markdown_text

    kept: list[str] = []
    active_caption_key = ""
    previous_block_was_image = False
    for block in blocks:
        normalized = normalize_text(block).lower()
        if normalized in AIP_FIGURE_MODAL_ACTION_TEXTS:
            continue
        block_is_image = markdown_image_fullmatch(block.strip()) is not None
        caption_key = _aip_caption_key(block)
        if AIP_BOLD_FIGURE_CAPTION_RE.match(block) or (
            previous_block_was_image
            and AIP_BOLD_BLOCK_RE.match(block)
            and len(caption_key) >= AIP_MIN_MODAL_CAPTION_KEY_LENGTH
        ):
            kept.append(block)
            active_caption_key = caption_key
            previous_block_was_image = False
            continue
        if _aip_is_duplicate_modal_caption(block, active_caption_key):
            continue
        active_caption_key = ""
        kept.append(block)
        previous_block_was_image = block_is_image
    return "\n\n".join(kept)


def aip_normalize_markdown(markdown_text: str) -> str:
    text = markdown_text
    for pattern in AIP_MARKDOWN_CHROME_PATTERNS:
        text = pattern.sub("", text)
    text = _drop_aip_figure_modal_blocks(text)
    return normalize_markdown_text(text)


def _strip_aip_title_badges(value: str) -> str:
    text = normalize_markdown_text(value)
    return normalize_text(AIP_TITLE_BADGE_RE.sub("", text))


def _strip_aip_markdown_title_badges(markdown_text: str) -> str:
    lines = normalize_markdown_text(markdown_text).splitlines()
    if not lines:
        return ""
    first_line = lines[0]
    if first_line.startswith("# "):
        stripped_title = _strip_aip_title_badges(first_line[2:])
        if stripped_title:
            lines[0] = f"# {stripped_title}"
    return normalize_markdown_text("\n".join(lines))


def _is_aip_supplementary_widget_heading(node: Tag) -> bool:
    classes = {str(item).lower() for item in node.get("class") or []}
    if "supplementary-data-section-title" in classes:
        return True
    return _is_aip_supplementary_widget_node(node)


def _is_aip_supplementary_widget_node(node: Tag) -> bool:
    classes = {str(item) for item in node.get("class") or []}
    if "widget-ArticleDataSupplements" in classes:
        return True
    return node.find_parent(class_="widget-ArticleDataSupplements") is not None


def _markdown_heading_for_html_heading(heading: Tag) -> str:
    level_match = AIP_HEADING_TAG_RE.match(heading.name or "")
    level = int((level_match.group(0) if level_match else "h2")[1:])
    heading_text = normalize_text(heading.get_text(" ", strip=True))
    return f"{'#' * min(max(level, 2), 6)} {heading_text}"


def _render_aip_paragraph_blocks(container: Tag) -> list[str]:
    paragraphs: list[str] = []
    for paragraph in container.find_all("p"):
        if not isinstance(paragraph, Tag):
            continue
        rendered = normalize_text(render_html_inline_node(paragraph))
        if rendered:
            paragraphs.append(rendered)
    return paragraphs


def _extract_retained_back_matter_markdown(html_text: str) -> str:
    soup = BeautifulSoup(html_text, choose_parser())
    headings = [
        node for node in soup.find_all(AIP_HEADING_TAG_RE) if isinstance(node, Tag)
    ]
    start_heading: Tag | None = None
    for heading in headings:
        if not isinstance(heading, Tag):
            continue
        if _is_aip_supplementary_widget_heading(heading):
            continue
        heading_text = normalize_text(heading.get_text(" ", strip=True))
        if (
            _aip_normalized_heading(heading_text)
            not in AIP_RETAINED_BACK_MATTER_HEADINGS
        ):
            continue
        start_heading = heading
        break
    if start_heading is None:
        return ""

    blocks: list[str] = []
    keep_following_content = False
    for node in [start_heading, *list(start_heading.next_siblings)]:
        if not isinstance(node, Tag):
            continue
        if AIP_HEADING_TAG_RE.match(node.name or ""):
            if _is_aip_supplementary_widget_heading(node):
                keep_following_content = False
                continue
            normalized_heading = _aip_normalized_heading(node.get_text(" ", strip=True))
            if normalized_heading in AIP_BACK_MATTER_STOP_HEADINGS:
                break
            keep_following_content = (
                normalized_heading in AIP_RETAINED_BACK_MATTER_HEADINGS
            )
            if keep_following_content:
                blocks.append(_markdown_heading_for_html_heading(node))
            continue
        if _is_aip_supplementary_widget_node(node):
            continue
        if keep_following_content:
            blocks.extend(_render_aip_paragraph_blocks(node))

    return normalize_markdown_text("\n\n".join(blocks))


def _inject_retained_back_matter_markdown(markdown_text: str, html_text: str) -> str:
    normalized_existing = normalize_text(markdown_text).lower()
    if (
        "acknowledgment" in normalized_existing
        or "acknowledgement" in normalized_existing
        or "author contributions" in normalized_existing
    ):
        return markdown_text
    back_matter_markdown = _extract_retained_back_matter_markdown(html_text)
    if not back_matter_markdown:
        return markdown_text
    markdown = normalize_markdown_text(markdown_text)
    insertion_match = re.search(
        r"(?m)^##\s+(?:data availability|references)\b",
        markdown,
        flags=re.IGNORECASE,
    )
    if insertion_match is None:
        return normalize_markdown_text(f"{markdown}\n\n{back_matter_markdown}")
    return normalize_markdown_text(
        f"{markdown[: insertion_match.start()].rstrip()}\n\n"
        f"{back_matter_markdown}\n\n"
        f"{markdown[insertion_match.start() :].lstrip()}"
    )


def _aip_section_hint_is_data_supplement_widget(hint: Mapping[str, Any]) -> bool:
    selector = normalize_text(str(hint.get("source_selector") or "")).lower()
    return "articledatasupplements" in selector


def _normalize_aip_section_hints(
    section_hints: Any,
) -> list[dict[str, Any]] | None:
    if not isinstance(section_hints, list):
        return None
    normalized_hints: list[dict[str, Any]] = []
    changed = False
    for item in section_hints:
        if not isinstance(item, Mapping):
            continue
        hint = dict(item)
        normalized_heading = _aip_normalized_heading(str(hint.get("heading") or ""))
        if (
            normalized_heading in AIP_RETAINED_BACK_MATTER_HEADINGS
            and not _aip_section_hint_is_data_supplement_widget(hint)
        ):
            if hint.get("kind") != "body":
                hint["kind"] = "body"
                changed = True
        normalized_hints.append(hint)
    return normalized_hints if changed else None


def _meta_content_values(html_text: str, name: str) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    values: list[str] = []
    for node in soup.find_all("meta"):
        if not isinstance(node, Tag):
            continue
        node_name = normalize_text(str(node.get("name") or "")).lower()
        if node_name != name:
            continue
        content = normalize_text(str(node.get("content") or ""))
        if content:
            values.append(content)
    return values


def _reference_from_citation_meta(
    value: str, *, index: int
) -> dict[str, str | None] | None:
    fields: dict[str, list[str]] = {}
    for part in AIP_REFERENCE_META_SPLIT.split(value):
        match = AIP_REFERENCE_FIELD_RE.match(part.strip())
        if match is None:
            continue
        key = match.group(1)
        fields.setdefault(key, []).append(normalize_text(match.group(2)))
    if not fields:
        return None

    authors = fields.get("author") or []
    journal = fields.get("journal_title") or fields.get("title") or []
    year_values = fields.get("year") or []
    volume_values = fields.get("volume") or []
    page_values = fields.get("pages") or []
    doi_values = fields.get("doi") or []
    year = year_values[0] if year_values else None
    volume = volume_values[0] if volume_values else None
    pages = page_values[0] if page_values else None
    doi = doi_values[0] if doi_values else None
    raw_parts = [", ".join(authors), *(journal[:1]), year, volume, pages]
    raw = normalize_text(
        ", ".join(str(part) for part in raw_parts if part and normalize_text(part))
    )
    if not raw:
        raw = normalize_text(value)
    if doi is None:
        doi_match = AIP_REFERENCE_DOI_RE.search(value)
        doi = normalize_text(doi_match.group(0)) if doi_match else None
    if year is None:
        year_match = AIP_REFERENCE_YEAR_RE.search(value)
        year = year_match.group(1) if year_match else None
    return {
        "label": f"{index}.",
        "raw": raw,
        "doi": doi,
        "year": year,
    }


def extract_references(html_text: str) -> list[dict[str, str | None]]:
    references = extract_numbered_references_from_html(html_text)
    if references:
        return references
    extracted: list[dict[str, str | None]] = []
    for index, value in enumerate(
        _meta_content_values(html_text, "citation_reference"), start=1
    ):
        reference = _reference_from_citation_meta(value, index=index)
        if reference is not None:
            extracted.append(reference)
    return extracted


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del source_url, metadata
    finalized = dict(extraction)
    markdown_text = _inject_retained_back_matter_markdown(markdown_text, html_text)
    markdown_text = aip_normalize_markdown(markdown_text)
    markdown_text = _strip_aip_markdown_title_badges(markdown_text)
    if normalize_text(str(finalized.get("title") or "")):
        finalized["title"] = _strip_aip_title_badges(str(finalized["title"]))
    normalized_section_hints = _normalize_aip_section_hints(
        finalized.get("section_hints")
    )
    if normalized_section_hints is not None:
        finalized["section_hints"] = normalized_section_hints
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_references(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    return markdown_text, finalized


def scoped_asset_extractor(*args: Any, **kwargs: Any) -> list[dict[str, str]]:
    from .atypon_browser_workflow.asset_scopes import extract_scoped_html_assets

    return extract_scoped_html_assets(*args, **kwargs)


__all__ = [
    "aip_before_block_normalization",
    "aip_body_container",
    "aip_classify_heading",
    "aip_normalize_markdown",
    "extract_authors",
    "extract_references",
    "finalize_extraction",
    "scoped_asset_extractor",
]
