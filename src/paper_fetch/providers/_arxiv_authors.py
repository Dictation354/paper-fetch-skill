"""arXiv author extraction and LaTeXML cleanup helpers."""

from __future__ import annotations

import copy
from importlib import resources
from typing import Any
from collections.abc import Sequence
import html as html_lib
import json
import re

from ..extraction.html import assets as html_assets
from ..formula.convert import normalize_latex
from ..utils import dedupe_authors, normalize_text
from ._arxiv_html import (
    BeautifulSoup,
    Tag,
    _arxiv_ar5iv_selectors,
    _arxiv_node_classes,
    _arxiv_select,
    _arxiv_select_one,
    _clean_arxiv_frontmatter_text,
)
from ._arxiv_parsing import ARXIV_HTML_PARSER
from ._html_authors import AuthorExtractionPipeline, AuthorStep
from ._html_section_markdown import render_clean_text_from_html

_ARXIV_AUTHOR_LABEL_PATTERN = re.compile(
    r"(?P<name>[^\d,;]+?)\s+(?:\d+(?:\s*,\s*\d+)*)\b"
)
_ARXIV_AUTHOR_BOUNDARY_PACKAGE = "paper_fetch.resources.arxiv"
_ARXIV_AUTHOR_BOUNDARY_RESOURCE = "author_boundaries.json"


def _load_arxiv_author_boundary_tokens(
    key: str, *, resource_name: str = _ARXIV_AUTHOR_BOUNDARY_RESOURCE
) -> tuple[str, ...]:
    """Load ar5iv/plain-text author-affiliation fallback boundaries.

    These are not a general country or institution knowledge base; they only
    mark common author/frontmatter boundary strings when arXiv HTML lacks clean
    person/affiliation structure.
    """

    try:
        payload = json.loads(
            resources.files(_ARXIV_AUTHOR_BOUNDARY_PACKAGE)
            .joinpath(resource_name)
            .read_text(encoding="utf-8")
        )
    except (
        AttributeError,
        FileNotFoundError,
        ModuleNotFoundError,
        OSError,
        json.JSONDecodeError,
    ):
        return ()
    if not isinstance(payload, dict):
        return ()
    values = payload.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(token for item in values if (token := str(item).strip()))


def _compile_arxiv_author_boundary_pattern(
    tokens: Sequence[str], *, prefix: str, suffix: str
) -> re.Pattern[str]:
    if not tokens:
        return re.compile(r"a\A")
    return re.compile(prefix + "|".join(tokens) + suffix, flags=re.IGNORECASE)


def _compile_arxiv_author_country_boundary_pattern(
    tokens: Sequence[str],
) -> re.Pattern[str]:
    return _compile_arxiv_author_boundary_pattern(
        tokens, prefix=r"[,;]\s*(?:", suffix=r")(?![A-Za-z])"
    )


def _compile_arxiv_author_institution_boundary_pattern(
    tokens: Sequence[str],
) -> re.Pattern[str]:
    return _compile_arxiv_author_boundary_pattern(
        tokens, prefix=r"(?<![A-Za-z])(?:", suffix=r")(?![A-Za-z])"
    )


_ARXIV_AUTHOR_INSTITUTION_BOUNDARY_TOKENS = _load_arxiv_author_boundary_tokens(
    "institution_boundary_patterns"
)
_ARXIV_AUTHOR_COUNTRY_BOUNDARY_TOKENS = _load_arxiv_author_boundary_tokens(
    "country_boundary_patterns"
)
_ARXIV_AUTHOR_INSTITUTION_BOUNDARY_PATTERN = (
    _compile_arxiv_author_institution_boundary_pattern(
        _ARXIV_AUTHOR_INSTITUTION_BOUNDARY_TOKENS
    )
)
_ARXIV_AUTHOR_COUNTRY_BOUNDARY_PATTERN = _compile_arxiv_author_country_boundary_pattern(
    _ARXIV_AUTHOR_COUNTRY_BOUNDARY_TOKENS
)
_ARXIV_AUTHOR_ADDRESS_BOUNDARY_PATTERN = re.compile(
    r"[,;]\s*(?:[A-Z]{1,3}[- ]?)?\d{3,}\b"
)
_ARXIV_AUTHOR_COUNTRY_CODE_BOUNDARY_PATTERN = re.compile(r"[,;]\s*[A-Z]{2,3}\.?\s*$")
_ARXIV_EMAIL_PATTERN = re.compile(r"\b\S+@\S+\b")
_ARXIV_ORCID_PATTERN = re.compile(
    r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", flags=re.IGNORECASE
)
_ARXIV_INITIAL_TOKEN_PATTERN = re.compile(r"^[A-Z]\.?$")


def _arxiv_author_boundary_start(text: str) -> int | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    matches = [
        match
        for match in (
            _ARXIV_AUTHOR_INSTITUTION_BOUNDARY_PATTERN.search(normalized),
            _ARXIV_AUTHOR_COUNTRY_BOUNDARY_PATTERN.search(normalized),
            _ARXIV_AUTHOR_ADDRESS_BOUNDARY_PATTERN.search(normalized),
            _ARXIV_AUTHOR_COUNTRY_CODE_BOUNDARY_PATTERN.search(normalized),
        )
        if match is not None
    ]
    if not matches:
        return None
    return min(match.start() for match in matches)


def _arxiv_author_text_has_boundary(text: str) -> bool:
    return _arxiv_author_boundary_start(text) is not None


def _trim_arxiv_author_text_at_boundary(text: str) -> str:
    boundary_start = _arxiv_author_boundary_start(text)
    if boundary_start is None:
        return normalize_text(text)
    return normalize_text(text[:boundary_start])


def _candidate_arxiv_author_text_from_person_node(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    clone = copy.deepcopy(node)
    if not isinstance(clone, Tag):
        return ""
    for selector in _arxiv_ar5iv_selectors("frontmatter_noise"):
        for match in clone.select(selector):
            match.decompose()

    pieces: list[str] = []
    for child in list(clone.children):
        if isinstance(child, Tag):
            child_name = normalize_text(child.name or "").lower()
            if child_name == "sup":
                break
            child_text = normalize_text(child.get_text(" ", strip=True))
            if child_name == "br":
                pieces.append(";")
                continue
            if pieces and _arxiv_author_text_has_boundary(child_text):
                break
            if child_text:
                pieces.append(child_text)
        else:
            child_text = normalize_text(str(child))
            if pieces and _arxiv_author_text_has_boundary(child_text):
                break
            if child_text:
                pieces.append(child_text)

    text = normalize_text(" ".join(pieces).replace("\u200b", " "))
    text = _ARXIV_EMAIL_PATTERN.sub(" ", text)
    text = _ARXIV_ORCID_PATTERN.sub(" ", text)
    text = _trim_arxiv_author_text_at_boundary(text)
    text = re.sub(r"\s*;\s*", " ; ", text)
    return normalize_text(text)


def _looks_like_arxiv_author_name(text: str) -> bool:
    normalized = normalize_text(text).strip(" ,;")
    if not normalized or "@" in normalized:
        return False
    if _arxiv_author_text_has_boundary(normalized):
        return False
    tokens = [token for token in normalized.split() if token]
    if not tokens or len(tokens) > 6:
        return False
    return any(any(character.isalpha() for character in token) for token in tokens)


def _split_compact_arxiv_author_sequence(text: str) -> list[str]:
    normalized = normalize_text(re.sub(r"\b\d+(?:\s*,\s*\d+)*\b", " ", text))
    tokens = [token.strip(" ,;") for token in normalized.split() if token.strip(" ,;")]
    if len(tokens) <= 4:
        return [normalized] if _looks_like_arxiv_author_name(normalized) else []
    authors: list[str] = []
    current: list[str] = []
    substantive_tokens = 0
    for token in tokens:
        current.append(token)
        if not _ARXIV_INITIAL_TOKEN_PATTERN.fullmatch(token):
            substantive_tokens += 1
        if substantive_tokens >= 2:
            candidate = normalize_text(" ".join(current))
            if _looks_like_arxiv_author_name(candidate):
                authors.append(candidate)
            current = []
            substantive_tokens = 0
    remainder = normalize_text(" ".join(current))
    if remainder and authors:
        authors[-1] = normalize_text(f"{authors[-1]} {remainder}")
    elif remainder and _looks_like_arxiv_author_name(remainder):
        authors.append(remainder)
    return authors


def _split_arxiv_author_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    labeled_authors = [
        normalize_text(match.group("name").strip(" ,;"))
        for match in _ARXIV_AUTHOR_LABEL_PATTERN.finditer(normalized)
        if _looks_like_arxiv_author_name(match.group("name"))
    ]
    if len(labeled_authors) >= 2:
        return dedupe_authors(labeled_authors)

    parts = [
        normalize_text(part.strip(" ,;"))
        for part in re.split(r"\s+(?:and|&)\s+|;|\n", normalized)
        if normalize_text(part.strip(" ,;"))
    ]
    authors: list[str] = []
    for part in parts or [normalized]:
        if _looks_like_arxiv_author_name(part) and len(part.split()) <= 4:
            authors.append(part)
            continue
        authors.extend(_split_compact_arxiv_author_sequence(part))
    return dedupe_authors(authors)


def _arxiv_author_article_from_html(html_text: str) -> Any:
    soup = BeautifulSoup(html_text, ARXIV_HTML_PARSER)
    article = soup.find("article")
    if isinstance(article, Tag):
        return article
    wrapper_soup = BeautifulSoup(f"<article>{html_text}</article>", ARXIV_HTML_PARSER)
    return wrapper_soup.find("article")


def _extract_arxiv_creator_authors(html_text: str) -> list[str]:
    article = _arxiv_author_article_from_html(html_text)
    if not isinstance(article, Tag):
        return []
    creators = [
        node
        for node in _arxiv_select(article, "author_creators")
        if isinstance(node, Tag)
    ]
    if len(creators) <= 1:
        return []
    authors: list[str] = []
    for creator in creators:
        person_node = _arxiv_select_one(creator, "author_person_names") or creator
        candidate = _clean_arxiv_frontmatter_text(person_node)
        if _looks_like_arxiv_author_name(candidate):
            authors.append(candidate)
    return dedupe_authors(authors)


def _extract_arxiv_person_authors(html_text: str) -> list[str]:
    article = _arxiv_author_article_from_html(html_text)
    if not isinstance(article, Tag):
        return []
    authors = []
    for person_node in _arxiv_select(article, "author_person_names"):
        candidate_text = _candidate_arxiv_author_text_from_person_node(person_node)
        authors.extend(_split_arxiv_author_text(candidate_text))
    return dedupe_authors(authors)


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("creators", _extract_arxiv_creator_authors),
    AuthorStep("person-names", _extract_arxiv_person_authors),
)


_ARXIV_UNDEFINED_MACRO_PATTERN = re.compile(r"^\\[A-Za-z@]+\*?$")
_ARXIV_UNESCAPED_DOLLAR_PATTERN = re.compile(r"(?<!\\)\$")


def _clean_official_html_latexml_noise(article: Any) -> dict[str, int]:
    if not isinstance(article, Tag):
        return {
            "latexml_error_nodes_removed": 0,
            "figure_alt_placeholders_removed": 0,
            "math_nodes_normalized": 0,
            "footnote_nodes_normalized": 0,
        }

    removed_error_nodes = 0
    for node in list(_arxiv_select(article, "latexml_error_nodes")):
        if not isinstance(node, Tag):
            continue
        classes = _arxiv_node_classes(node)
        text = normalize_text(node.get_text("", strip=True))
        if ("ltx_error" in classes or "undefined" in classes) and (
            not text or _ARXIV_UNDEFINED_MACRO_PATTERN.fullmatch(text)
        ):
            node.decompose()
            removed_error_nodes += 1

    removed_alt_placeholders = 0
    for image in article.find_all("img"):
        if not isinstance(image, Tag):
            continue
        alt_text = normalize_text(str(image.get("alt") or ""))
        if alt_text and not html_assets.clean_noisy_image_alt_text(alt_text):
            del image["alt"]
            removed_alt_placeholders += 1

    math_nodes_normalized = _normalize_official_html_latexml_math_nodes(article)
    footnote_nodes_normalized = _normalize_official_html_latexml_notes(article)

    return {
        "latexml_error_nodes_removed": removed_error_nodes,
        "figure_alt_placeholders_removed": removed_alt_placeholders,
        "math_nodes_normalized": math_nodes_normalized,
        "footnote_nodes_normalized": footnote_nodes_normalized,
    }


def _arxiv_math_annotation_latex(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    for annotation in node.find_all("annotation"):
        if not isinstance(annotation, Tag):
            continue
        encoding = normalize_text(str(annotation.get("encoding") or "")).lower()
        if encoding == "application/x-tex":
            latex = annotation.get_text("", strip=False)
            return _sanitize_arxiv_math_annotation_latex(html_lib.unescape(latex))
    alttext = normalize_text(str(node.get("alttext") or ""))
    return _sanitize_arxiv_math_annotation_latex(html_lib.unescape(alttext))


def _latex_braces_are_balanced(text: str) -> bool:
    depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
        index += 1
    return depth == 0


def _sanitize_arxiv_math_annotation_latex(value: str) -> str:
    latex = normalize_latex(value)
    if not latex:
        return ""
    latex = _ARXIV_UNESCAPED_DOLLAR_PATTERN.sub("", latex)
    latex = normalize_latex(latex)
    if not latex or _ARXIV_UNESCAPED_DOLLAR_PATTERN.search(latex):
        return ""
    if r"\[" in latex or r"\]" in latex:
        return ""
    if not _latex_braces_are_balanced(latex):
        return ""
    return latex


def _arxiv_math_is_display(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    return normalize_text(str(node.get("display") or "")).lower() == "block"


def _arxiv_math_markdown(node: Any) -> str:
    latex = _arxiv_math_annotation_latex(node)
    if not latex:
        return ""
    if _arxiv_math_is_display(node):
        return f"\n\n$$\n{latex}\n$$\n\n"
    return f"${latex}$"


def _normalize_official_html_latexml_math_nodes(article: Any) -> int:
    if not isinstance(article, Tag):
        return 0
    normalized_count = 0
    for node in list(_arxiv_select(article, "math_nodes")):
        if not isinstance(node, Tag):
            continue
        replacement = _arxiv_math_markdown(node)
        if not replacement:
            continue
        node.replace_with(replacement)
        normalized_count += 1
    return normalized_count


def _normalize_official_html_latexml_notes(article: Any) -> int:
    if not isinstance(article, Tag):
        return 0
    normalized_count = 0
    for note in list(_arxiv_select(article, "note_nodes")):
        if not isinstance(note, Tag):
            continue
        classes = _arxiv_node_classes(note)
        if "ltx_role_footnote" not in classes and "ltx_role_endnote" not in classes:
            continue
        marker_node = _arxiv_select_one(note, "note_markers")
        marker = normalize_text(
            marker_node.get_text(" ", strip=True)
            if isinstance(marker_node, Tag)
            else ""
        )
        content_node = _arxiv_select_one(note, "note_content")
        if not isinstance(content_node, Tag):
            continue

        content = copy.deepcopy(content_node)
        if not isinstance(content, Tag):
            continue
        for duplicate_marker in _arxiv_select(content, "note_markers"):
            duplicate_marker.decompose()
        content_text = normalize_text(
            render_clean_text_from_html(content).replace("\n", " ")
        )
        if not marker and not content_text:
            continue

        note.clear()
        if marker:
            sup = BeautifulSoup("", ARXIV_HTML_PARSER).new_tag("sup")
            sup.string = marker
            note.append(sup)
        if content_text:
            if marker:
                note.append(" ")
            note.append(content_text)
        normalized_count += 1
    return normalized_count
