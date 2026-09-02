"""arXiv official HTML parsing orchestration and shared DOM helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping
import re

from ..common_patterns import WORD_TOKEN_PATTERN
from ..extraction.html._runtime import clean_markdown
from ..extraction.html.html_tags import HTML_DROP_TAGS
from ..extraction.html.semantics import (
    HTML_BLOCK_TAGS,
    SECTION_HEADING_PATTERN,
    heading_category,
    node_source_selector,
    section_hint_kind_for_category,
)
from ..extraction.html.tables import (
    TABLE_PLACEHOLDER_PREFIX,
    inject_inline_table_blocks,
)
from ..models.markdown import normalize_markdown_text
from ..metadata.types import ProviderMetadata
from ..quality.html_availability import assess_plain_text_fulltext_availability
from ..reason_codes import FULLTEXT, NO_RESULT
from ..utils import normalize_text
from ._arxiv_parsing import ARXIV_HTML_PARSER
from ._html_section_markdown import (
    render_clean_text_from_html,
    render_container_markdown,
    render_heading_text_from_html,
)
from .base import ProviderFailure

from bs4 import BeautifulSoup, Tag

MIN_HTML_MARKDOWN_WORDS = 500
_WORD_PATTERN = WORD_TOKEN_PATTERN
_ARXIV_BASE_CHROME_SELECTORS = ("script", "style")
_ARXIV_AR5IV_SELECTORS: Mapping[str, tuple[str, ...]] = {
    "watermark": ("#watermark-tr", ".ltx_page_header", ".ltx_page_footer"),
    "frontmatter_noise": (
        *_ARXIV_BASE_CHROME_SELECTORS,
        "math",
        ".ltx_note",
        ".ltx_contact",
        ".ltx_author_notes",
        ".ltx_role_email",
        ".ltx_role_orcid",
        ".ltx_role_affiliation",
        "a[href^='mailto:']",
        ".ltx_font_typewriter",
    ),
    "author_creators": (".ltx_creator.ltx_role_author",),
    "author_person_names": (".ltx_personname",),
    "document_title": ("h1.ltx_title_document",),
    "abstract": ("div.ltx_abstract",),
    "abstract_heading": (".ltx_title_abstract", "h1", "h2", "h3", "h4", "h5", "h6"),
    "bibliography_containers": ("section.ltx_bibliography", "section#bib"),
    "bibliography_items": (".ltx_bibitem", "li.ltx_bibitem"),
    "reference_noise": (
        *_ARXIV_BASE_CHROME_SELECTORS,
        ".ltx_bib_cited",
        ".ltx_bib_links",
    ),
    "reference_links": (".ltx_bib_links", ".ltx_bib_cited"),
    "reference_blocks": (".ltx_bibblock",),
    "reference_year": (".ltx_bib_year",),
    "reference_title": (".ltx_bib_title",),
    "algorithm_listing": ("div.ltx_listing",),
    "latexml_error_nodes": (".ltx_ERROR", ".undefined"),
    "math_nodes": ("math.ltx_Math",),
    "note_nodes": ("span.ltx_note",),
    "note_markers": (".ltx_note_mark", ".ltx_tag_note"),
    "note_content": (".ltx_note_content",),
    "listing_noise": (".ltx_rule", ".ltx_linenumber"),
    "listing_lines": (".ltx_listingline",),
    "article_root": ("article.ltx_document",),
    "article_chrome": (
        *_ARXIV_BASE_CHROME_SELECTORS,
        "nav",
        "header",
        "footer",
        "h1.ltx_title_document",
        "div.ltx_authors",
        "div.ltx_dates",
        "span.ltx_note.ltx_role_thanks",
        "span.ltx_note.ltx_note_frontmatter",
        "span.ltx_role_submissionid",
        "span.ltx_role_journal",
        "span.ltx_role_ccs",
        ".ltx_pagination",
    ),
}
_ARXIV_AR5IV_FATAL_ERROR_TEXTS = (
    "an error in the conversion from latex to xml has occurred",
)
_ARXIV_PLACEHOLDER_PATTERN = re.compile(
    rf"\b{re.escape(TABLE_PLACEHOLDER_PREFIX)}\d{{4}}\b"
)
_ARXIV_HTML_FATAL_ERROR_PATTERNS = (
    *(
        re.compile(r"\s+".join(re.escape(part) for part in text.split()), re.IGNORECASE)
        for text in _ARXIV_AR5IV_FATAL_ERROR_TEXTS
    ),
)
_ARXIV_SECTION_HINT_SKIP_CLASS_TOKENS = {
    "ltx_toc",
    "ltx_toclist",
    "ltx_tocentry",
    "ltx_page_navbar",
    "ltx_page_header",
    "ltx_page_footer",
    "ltx_pagination",
    "ltx_authors",
    "ltx_dates",
    "ltx_role_thanks",
    "ltx_note_frontmatter",
}
_ARXIV_SECTION_HINT_STRUCTURAL_SKIP_TAGS = (
    "aside",
    "figcaption",
    "footer",
    "header",
    "nav",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
)
_ARXIV_SECTION_HINT_SKIP_TAGS = {
    "figure",
    "math",
    *(tag for tag in HTML_DROP_TAGS if tag in {"script", "style", "svg"}),
    *(
        tag
        for tag in _ARXIV_SECTION_HINT_STRUCTURAL_SKIP_TAGS
        if tag in HTML_BLOCK_TAGS
    ),
}


@dataclass(frozen=True)
class ArxivHtmlExtraction:
    markdown_text: str
    merged_metadata: ProviderMetadata
    extracted_assets: list[dict[str, Any]]
    section_hints: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    warnings: list[str]


@dataclass(frozen=True)
class ArxivSemanticPreparation:
    entries: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    warnings: list[str]


def _arxiv_ar5iv_selectors(name: str) -> tuple[str, ...]:
    return _ARXIV_AR5IV_SELECTORS.get(name, ())


def _arxiv_select(node: Any, selector_group: str) -> list[Any]:
    if not isinstance(node, Tag):
        return []
    matches: list[Any] = []
    for selector in _arxiv_ar5iv_selectors(selector_group):
        matches.extend(node.select(selector))
    return matches


def _arxiv_select_one(node: Any, selector_group: str) -> Any:
    if not isinstance(node, Tag):
        return None
    for selector in _arxiv_ar5iv_selectors(selector_group):
        match = node.select_one(selector)
        if isinstance(match, Tag):
            return match
    return None


def _clean_arxiv_frontmatter_text(node: Any, *, remove_line_breaks: bool = True) -> str:
    if not isinstance(node, Tag):
        return ""
    clone = copy.deepcopy(node)
    if not isinstance(clone, Tag):
        return ""
    for selector in _arxiv_ar5iv_selectors("frontmatter_noise"):
        for match in clone.select(selector):
            match.decompose()
    separator = " " if remove_line_breaks else "\n"
    text = render_clean_text_from_html(clone).replace("\u200b", " ")
    text = text.replace("\u2005", " ").replace("\u200a", " ").replace("\u2003", " ")
    text = re.sub(r"\s*\n\s*", separator, text)
    return normalize_text(text)


def _arxiv_node_classes(node: Any) -> set[str]:
    if not isinstance(node, Tag):
        return set()
    raw_classes = (getattr(node, "attrs", None) or {}).get("class") or []
    if isinstance(raw_classes, str):
        return {
            normalize_text(item).lower()
            for item in raw_classes.split()
            if normalize_text(item)
        }
    return {
        normalize_text(str(item)).lower()
        for item in raw_classes
        if normalize_text(str(item))
    }


def _arxiv_node_has_class(node: Any, class_name: str) -> bool:
    return normalize_text(class_name).lower() in _arxiv_node_classes(node)


def _looks_like_html(content_type: str | None, body: bytes) -> bool:
    normalized = normalize_text(content_type).lower()
    if "html" in normalized or "xhtml" in normalized:
        return True
    prefix = body[:512].lstrip().lower()
    return prefix.startswith((b"<!doctype html", b"<html"))


def _markdown_word_count(markdown_text: str) -> int:
    return len(_WORD_PATTERN.findall(normalize_text(markdown_text)))


def _split_markdown_block_around_placeholder(
    block: str, placeholder: str, replacement: str
) -> list[str]:
    pieces: list[str] = []
    remaining = block
    while placeholder in remaining:
        before, remaining = remaining.split(placeholder, 1)
        if normalize_text(before):
            pieces.append(normalize_markdown_text(before))
        pieces.extend(
            normalize_markdown_text(part)
            for part in re.split(r"\n\s*\n", replacement)
            if normalize_text(part)
        )
    if normalize_text(remaining):
        pieces.append(normalize_markdown_text(remaining))
    return pieces


def _inject_arxiv_semantic_blocks(
    markdown_text: str,
    *,
    entries: list[dict[str, Any]],
) -> tuple[str, dict[str, int], list[str]]:
    if not entries:
        return markdown_text, {"inserted_count": 0, "appended_count": 0}, []

    markdown_text = inject_inline_table_blocks(
        markdown_text,
        table_entries=entries,
        clean_markdown_fn=clean_markdown,
    )
    replacement_by_placeholder = {
        normalize_text(str(entry.get("placeholder") or "")): normalize_markdown_text(
            str(entry.get("markdown") or "")
        )
        for entry in entries
        if normalize_text(str(entry.get("placeholder") or ""))
        and normalize_text(str(entry.get("markdown") or ""))
    }
    inserted: set[str] = {
        placeholder
        for placeholder, replacement in replacement_by_placeholder.items()
        if replacement
        and replacement in markdown_text
        and placeholder not in markdown_text
    }
    blocks = [
        normalize_markdown_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    injected: list[str] = []
    for block in blocks:
        placeholders = [
            placeholder
            for placeholder in _ARXIV_PLACEHOLDER_PATTERN.findall(block)
            if placeholder in replacement_by_placeholder
        ]
        if not placeholders:
            injected.append(block)
            continue
        pending_blocks = [block]
        for placeholder in placeholders:
            replacement = replacement_by_placeholder[placeholder]
            next_blocks: list[str] = []
            for pending_block in pending_blocks:
                if placeholder in pending_block:
                    next_blocks.extend(
                        _split_markdown_block_around_placeholder(
                            pending_block, placeholder, replacement
                        )
                    )
                    inserted.add(placeholder)
                else:
                    next_blocks.append(pending_block)
            pending_blocks = next_blocks
        injected.extend(pending_blocks)

    appended_markdown: list[str] = []
    appended_count = 0
    for entry in entries:
        placeholder = normalize_text(str(entry.get("placeholder") or ""))
        replacement = replacement_by_placeholder.get(placeholder, "")
        if not placeholder or not replacement or placeholder in inserted:
            continue
        appended_markdown.append(replacement)
        appended_count += 1

    warnings: list[str] = []
    if appended_markdown:
        warnings.append(
            f"arXiv HTML semantic block placeholders could not all be reinserted; appended {appended_count} block(s) at document end."
        )
    cleaned = clean_markdown("\n\n".join([*injected, *appended_markdown]))
    return (
        cleaned,
        {"inserted_count": len(inserted), "appended_count": appended_count},
        warnings,
    )


def _clean_arxiv_html_markdown_noise(markdown_text: str) -> str:
    blocks = [
        normalize_markdown_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    cleaned_blocks: list[str] = []
    for block in blocks:
        normalized = normalize_text(block)
        if normalized in {"****"}:
            continue
        cleaned_blocks.append(block)
    cleaned = "\n\n".join(cleaned_blocks)
    cleaned = re.sub(
        r"(<sup>(?P<marker>[^<]+)</sup>)\s*<sup>(?P=marker)</sup>\s*(?P=marker)\s*",
        r"\1 ",
        cleaned,
    )
    cleaned = re.sub(r"(?m)^-\s+[•◦▪▫‣⁃∙●○◾◽◼□■]\s*", "- ", cleaned)
    return clean_markdown(cleaned)


def _arxiv_html_contains_fatal_conversion_error(markdown_text: str) -> bool:
    normalized = normalize_text(markdown_text)
    return any(
        pattern.search(normalized) for pattern in _ARXIV_HTML_FATAL_ERROR_PATTERNS
    )


def _is_arxiv_bibliography_title_heading(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    if _arxiv_node_has_class(node, "ltx_title_bibliography"):
        return True
    text = normalize_text(render_heading_text_from_html(node)).lower().strip(" .:")
    return text in {"references", "bibliography"}


def _arxiv_heading_in_skipped_hint_scope(node: Any, article: Any) -> bool:
    if not isinstance(node, Tag):
        return True
    current: Any = node
    while isinstance(current, Tag) and current is not article:
        name = normalize_text(current.name or "").lower()
        if name in _ARXIV_SECTION_HINT_SKIP_TAGS:
            return True
        classes = _arxiv_node_classes(current)
        if classes.intersection(_ARXIV_SECTION_HINT_SKIP_CLASS_TOKENS):
            return True
        if "ltx_bibliography" in classes and not _is_arxiv_bibliography_title_heading(
            node
        ):
            return True
        current = getattr(current, "parent", None)
    return False


def _arxiv_section_hint_kind(
    node: Any, heading: str, *, title: str | None
) -> str | None:
    node_name = normalize_text(getattr(node, "name", "") or "").lower()
    category = heading_category(node_name, heading, title=title)
    if category in {"abstract", "front_matter"}:
        return None
    shared_kind = section_hint_kind_for_category(category)
    if shared_kind is not None:
        return shared_kind
    return "body"


def _collect_arxiv_html_section_hints(
    article: Any, *, title: str | None = None
) -> list[dict[str, Any]]:
    if not isinstance(article, Tag):
        return []
    hints: list[dict[str, Any]] = []
    for node in article.find_all(SECTION_HEADING_PATTERN):
        if not isinstance(node, Tag) or _arxiv_heading_in_skipped_hint_scope(
            node, article
        ):
            continue
        heading = normalize_text(render_heading_text_from_html(node))
        if not heading:
            continue
        kind = _arxiv_section_hint_kind(node, heading, title=title)
        if kind is None:
            continue
        level_match = SECTION_HEADING_PATTERN.fullmatch(
            normalize_text(node.name or "").lower()
        )
        level = int(level_match.group(1)) if level_match else 2
        selector_node = (
            node.parent if isinstance(getattr(node, "parent", None), Tag) else node
        )
        hints.append(
            {
                "heading": heading,
                "level": level,
                "kind": kind,
                "order": len(hints),
                "language": None,
                "source_selector": node_source_selector(selector_node) or None,
            }
        )
    return hints


def _extract_arxiv_html_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any],
) -> ArxivHtmlExtraction:
    soup = BeautifulSoup(html_text, ARXIV_HTML_PARSER)
    article = _arxiv_select_one(soup, "article_root") or soup.find("article")
    if not isinstance(article, Tag):
        raise ProviderFailure(
            NO_RESULT, "arXiv official HTML did not expose a LaTeXML article body."
        )

    from ._arxiv_assets import (
        _annotate_arxiv_inline_figure_images,
        _extract_arxiv_html_assets,
    )
    from ._arxiv_authors import _clean_official_html_latexml_noise
    from ._arxiv_metadata import (
        _extract_arxiv_html_frontmatter,
        _merge_arxiv_metadata_layers,
    )
    from ._arxiv_references import (
        _extract_arxiv_html_references,
        _prepare_arxiv_semantic_blocks,
    )

    html_frontmatter = _extract_arxiv_html_frontmatter(
        soup,
        article,
        source_url,
        metadata=metadata,
    )
    noise_diagnostics = _clean_official_html_latexml_noise(article)
    extracted_references = _extract_arxiv_html_references(article)
    extracted_assets = _extract_arxiv_html_assets(str(article), source_url)
    semantic_preparation = _prepare_arxiv_semantic_blocks(article, soup)
    inline_figure_diagnostics = _annotate_arxiv_inline_figure_images(
        article, extracted_assets, source_url
    )

    for selector in _arxiv_ar5iv_selectors("article_chrome"):
        for node in article.select(selector):
            node.decompose()

    section_hints = _collect_arxiv_html_section_hints(
        article,
        title=normalize_text(metadata.get("title")),
    )
    lines: list[str] = []
    render_container_markdown(article, lines, level=2, section_content_selectors=())
    markdown_text = normalize_markdown_text("\n".join(lines))
    markdown_text, insertion_diagnostics, insertion_warnings = (
        _inject_arxiv_semantic_blocks(
            markdown_text,
            entries=semantic_preparation.entries,
        )
    )
    markdown_text = _clean_arxiv_html_markdown_noise(markdown_text)
    if _arxiv_html_contains_fatal_conversion_error(markdown_text):
        raise ProviderFailure(
            NO_RESULT, "arXiv official HTML was not classified as usable full text."
        )
    if _markdown_word_count(markdown_text) < MIN_HTML_MARKDOWN_WORDS:
        raise ProviderFailure(
            NO_RESULT, "arXiv official HTML did not expose enough body text."
        )
    if "##" not in markdown_text:
        raise ProviderFailure(
            NO_RESULT, "arXiv official HTML did not expose section headings."
        )

    diagnostics = assess_plain_text_fulltext_availability(
        markdown_text,
        metadata,
        title=normalize_text(metadata.get("title")),
        section_hints=section_hints,
    ).to_dict()
    if diagnostics.get("content_kind") != FULLTEXT:
        raise ProviderFailure(
            NO_RESULT, "arXiv official HTML was not classified as usable full text."
        )
    diagnostics.setdefault("extraction", {})
    diagnostics["extraction"] = {
        **dict(diagnostics.get("extraction") or {}),
        "parser": "latexml_html",
        "source_url": source_url,
        "word_count": _markdown_word_count(markdown_text),
        "formula_block_count": markdown_text.count("$$") // 2,
        "reference_count": len(extracted_references),
        "asset_count": len(extracted_assets),
        "section_hints": [dict(item) for item in section_hints],
        **noise_diagnostics,
        **inline_figure_diagnostics,
        **semantic_preparation.diagnostics,
        **{
            "semantic_block_inserted_count": insertion_diagnostics.get(
                "inserted_count", 0
            ),
            "semantic_block_appended_count": insertion_diagnostics.get(
                "appended_count", 0
            ),
        },
    }
    semantic_loss_count = int(
        semantic_preparation.diagnostics.get("semantic_block_loss_count") or 0
    )
    diagnostics["semantic_losses"] = {
        "table_fallback_count": semantic_loss_count,
        "table_semantic_loss_count": semantic_loss_count,
    }
    merged_metadata = _merge_arxiv_metadata_layers(
        metadata,
        html_metadata=html_frontmatter,
        references=extracted_references,
    )
    return ArxivHtmlExtraction(
        markdown_text=markdown_text,
        merged_metadata=merged_metadata,
        extracted_assets=extracted_assets,
        section_hints=[dict(item) for item in section_hints],
        diagnostics=diagnostics,
        warnings=[*semantic_preparation.warnings, *insertion_warnings],
    )
