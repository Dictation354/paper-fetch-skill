"""Markdown postprocess helpers for Science/PNAS browser workflows."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ...extraction.html.figure_links import inject_inline_figure_links
from ...extraction.html.language import collect_html_abstract_blocks
from ...extraction.html.semantics import normalize_heading, node_source_selector
from ...extraction.html.shared import short_text as _short_text
from ...extraction.html.tables import inject_inline_table_blocks
from ...models import normalize_markdown_text
from ...utils import normalize_text
from .. import _science_pnas_postprocess
from .._science_pnas_postprocess import normalize_browser_workflow_markdown
from .._science_pnas_profiles import publisher_profile as _publisher_profile
from .normalization import _render_non_table_inline_text
from .profile import (
    HEADING_TAG_PATTERN,
    clean_markdown,
    _heading_category,
    _is_substantial_prose,
    _looks_like_access_gate_text,
    _looks_like_front_matter_paragraph,
    _looks_like_markdown_auxiliary_block,
    _looks_like_post_content_noise_block,
    _markdown_heading_info,
    _node_language_hint,
    _noise_profile_for_publisher,
    _strip_heading_terminal_punctuation,
    _structural_abstract_nodes,
)

try:
    from bs4 import Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    Tag = None

def _abstract_section_payloads(container: Tag) -> list[dict[str, Any]]:
    structural_nodes = _structural_abstract_nodes(container)
    if structural_nodes:
        payloads: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for order, node in enumerate(structural_nodes):
            heading = _short_text(node.find(HEADING_TAG_PATTERN)) or "Abstract"
            text = normalize_text("\n\n".join(_abstract_block_texts(node)))
            if not text:
                continue
            key = (normalize_heading(heading), normalize_text(text))
            if key in seen:
                continue
            seen.add(key)
            payloads.append(
                {
                    "heading": normalize_text(heading) or "Abstract",
                    "text": text,
                    "language": _node_language_hint(node),
                    "kind": "abstract",
                    "order": order,
                    "source_selector": node_source_selector(node) or None,
                }
            )
        return payloads
    return [
        payload
        for payload in collect_html_abstract_blocks(container)
        if normalize_text(payload.get("text"))
    ]


def _markdown_has_abstract_heading(markdown_text: str) -> bool:
    for block in re.split(r"\n\s*\n", markdown_text):
        heading_info = _markdown_heading_info(block)
        if heading_info is None:
            continue
        level, heading_text = heading_info
        if _heading_category(f"h{min(level, 6)}", heading_text) == "abstract":
            return True
    return False


def _ensure_body_markdown_heading(markdown_text: str, *, title: str | None = None) -> str:
    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    if not blocks:
        return normalize_markdown_text(markdown_text)

    normalized_title = normalize_heading(title or "")
    first_heading = _markdown_heading_info(blocks[0])
    if first_heading is None:
        return clean_markdown(f"## Main Text\n\n{markdown_text}", noise_profile=None)

    _, heading_text = first_heading
    if normalized_title and normalize_heading(heading_text) == normalized_title:
        if len(blocks) < 2:
            return normalize_markdown_text(markdown_text)
        second_heading = _markdown_heading_info(blocks[1])
        if second_heading is None:
            return clean_markdown(
                "\n\n".join([blocks[0], "## Main Text", *blocks[1:]]),
                noise_profile=None,
            )
    return normalize_markdown_text(markdown_text)


def _abstract_block_texts(node: Tag) -> list[str]:
    heading = node.find(HEADING_TAG_PATTERN)
    texts: list[str] = []
    seen: set[str] = set()

    for candidate in node.find_all(True):
        if candidate is heading:
            continue
        if normalize_text(candidate.get("role") or "").lower() == "paragraph" or candidate.name in {"p", "li"}:
            text = _render_non_table_inline_text(candidate)
            if text and text not in seen:
                texts.append(text)
                seen.add(text)

    if texts:
        return texts

    fallback_text = _render_non_table_inline_text(node)
    heading_text = _short_text(heading)
    if heading_text:
        pattern = re.compile(rf"^{re.escape(heading_text)}[:\s-]*", flags=re.IGNORECASE)
        fallback_text = normalize_text(pattern.sub("", fallback_text, count=1))
    return [fallback_text] if fallback_text else []


def _missing_abstract_markdown(container: Tag, markdown_text: str, *, publisher: str) -> str:
    existing_normalized = normalize_text(markdown_text)
    leading_semantic_text = _leading_semantic_markdown_text(markdown_text)
    if publisher == "pnas" and _markdown_has_heading(markdown_text, "significance") and _markdown_has_heading(
        markdown_text,
        "abstract",
    ):
        return ""
    abstract_blocks: list[str] = []
    for payload in _abstract_section_payloads(container):
        heading_text = normalize_text(payload.get("heading")) or "Abstract"
        body_text = normalize_text(payload.get("text"))
        normalized_body_text = normalize_text(body_text)
        if normalized_body_text and normalized_body_text in existing_normalized:
            continue
        if _semantic_text_matches(body_text, leading_semantic_text):
            continue
        abstract_blocks.append(f"## {heading_text}\n\n{body_text}")

    if not abstract_blocks:
        return ""
    return clean_markdown(
        "\n\n".join(abstract_blocks),
        noise_profile=_noise_profile_for_publisher(publisher),
    )


def _inject_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    publisher: str,
) -> str:
    return inject_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def rewrite_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    publisher: str,
) -> str:
    return _science_pnas_postprocess.rewrite_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def _inject_inline_table_blocks(
    markdown_text: str,
    *,
    table_entries: list[Mapping[str, str]] | None,
    publisher: str,
) -> str:
    return inject_inline_table_blocks(
        markdown_text,
        table_entries=table_entries,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def _known_abstract_block_texts(container: Tag) -> list[str]:
    return _abstract_block_texts_from_payloads(_abstract_section_payloads(container))


def _abstract_block_texts_from_payloads(payloads: list[Mapping[str, Any]] | None) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for payload in payloads or []:
        normalized = normalize_text(normalize_markdown_text(str(payload.get("text") or "")))
        if normalized and normalized not in seen:
            texts.append(normalized)
            seen.add(normalized)
    return texts


def _semantic_match_text(value: str) -> str:
    normalized = normalize_text(normalize_markdown_text(str(value or ""))).lower()
    if not normalized:
        return ""
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _shared_prefix_word_count(left_words: list[str], right_words: list[str]) -> int:
    count = 0
    for left_word, right_word in zip(left_words, right_words):
        if left_word != right_word:
            break
        count += 1
    return count


def _semantic_text_matches(left: str, right: str) -> bool:
    left_text = _semantic_match_text(left)
    right_text = _semantic_match_text(right)
    if not left_text or not right_text:
        return False
    if left_text == right_text or left_text in right_text or right_text in left_text:
        return True

    left_words = left_text.split()
    right_words = right_text.split()
    shared_prefix_words = _shared_prefix_word_count(left_words, right_words)
    required_prefix_words = min(24, max(12, min(len(left_words), len(right_words)) // 3))
    return shared_prefix_words >= required_prefix_words


def _leading_semantic_markdown_text(markdown_text: str, *, limit: int = 6) -> str:
    leading_blocks: list[str] = []
    for block in re.split(r"\n\s*\n", markdown_text):
        normalized_block = normalize_text(block)
        if not normalized_block:
            continue
        heading_info = _markdown_heading_info(block)
        if heading_info is not None:
            continue
        if _looks_like_markdown_auxiliary_block(normalized_block):
            continue
        if not _is_substantial_prose(normalized_block):
            continue
        leading_blocks.append(block)
        if len(leading_blocks) >= limit:
            break
    return "\n\n".join(leading_blocks)


def _markdown_has_heading(markdown_text: str, heading_text: str) -> bool:
    normalized_target = normalize_heading(heading_text)
    if not normalized_target:
        return False
    for block in re.split(r"\n\s*\n", markdown_text):
        heading_info = _markdown_heading_info(block)
        if heading_info is None:
            continue
        _, current_heading = heading_info
        if normalize_heading(current_heading) == normalized_target:
            return True
    return False


def _block_matches_known_abstract_text(block: str, abstract_block_texts: list[str]) -> bool:
    normalized_block = normalize_text(normalize_markdown_text(block))
    if not normalized_block:
        return False
    for known in abstract_block_texts:
        if not known:
            continue
        if normalized_block == known or normalized_block in known or known in normalized_block:
            return True
        if _semantic_text_matches(block, known):
            return True
    return False


def _normalize_browser_workflow_markdown(markdown_text: str, *, publisher: str) -> str:
    return normalize_browser_workflow_markdown(
        markdown_text,
        markdown_postprocess=_publisher_profile(publisher).markdown_postprocess,
    )


def _postprocess_browser_workflow_markdown(
    markdown_text: str,
    *,
    title: str | None,
    publisher: str,
    figure_assets: list[Mapping[str, Any]] | None = None,
    table_entries: list[Mapping[str, str]] | None = None,
    abstract_block_texts: list[str] | None = None,
) -> str:
    markdown_text = _normalize_browser_workflow_markdown(markdown_text, publisher=publisher)
    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    kept: list[str] = []
    normalized_title = normalize_text(title or "")
    normalized_title_lower = normalized_title.lower()
    known_abstract_blocks = [normalize_text(text) for text in abstract_block_texts or [] if normalize_text(text)]
    title_kept = False
    started_content = False
    in_front_matter = False
    in_abstract = False
    in_back_matter = False
    in_data_availability = False
    abstract_prose_blocks_seen = 0

    for block in blocks:
        heading_info = _markdown_heading_info(block)
        if heading_info is not None:
            level, heading_text = heading_info
            normalized_heading = normalize_heading(heading_text)
            if normalized_title and normalized_heading == normalized_title_lower:
                if not title_kept:
                    kept.append(f"# {normalized_title}")
                    title_kept = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue

            category = _heading_category(f"h{min(level, 6)}", heading_text, title=normalized_title or None)
            if category == "front_matter":
                in_front_matter = True
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue
            if category in {"references_or_back_matter", "ancillary"}:
                if category == "ancillary" and started_content:
                    break
                in_front_matter = False
                in_abstract = False
                in_back_matter = category == "references_or_back_matter"
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue
            if category == "abstract":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                kept.append(block)
                started_content = True
                in_front_matter = False
                in_abstract = True
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue
            if category in {"data_availability", "code_availability"}:
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                cleaned_heading = _strip_heading_terminal_punctuation(heading_text)
                kept.append(f"{'#' * level} {cleaned_heading}")
                started_content = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = True
                abstract_prose_blocks_seen = 0
                continue
            if category == "body_heading":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                cleaned_heading = _strip_heading_terminal_punctuation(heading_text)
                kept.append(f"{'#' * level} {cleaned_heading}")
                started_content = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue

        normalized_block = normalize_text(block)
        if not normalized_block:
            continue
        is_auxiliary_block = _looks_like_markdown_auxiliary_block(normalized_block)
        if _looks_like_post_content_noise_block(normalized_block):
            if started_content:
                break
            continue
        if in_front_matter:
            continue
        if in_abstract:
            if (
                known_abstract_blocks
                and _is_substantial_prose(normalized_block)
                and not is_auxiliary_block
                and not _block_matches_known_abstract_text(block, known_abstract_blocks)
            ):
                if publisher == "science" and abstract_prose_blocks_seen == 0:
                    if not title_kept and normalized_title:
                        kept.insert(0, f"# {normalized_title}")
                        title_kept = True
                    kept.append(block)
                    started_content = True
                    abstract_prose_blocks_seen += 1
                    continue
                kept.append("## Main Text")
                in_abstract = False
                abstract_prose_blocks_seen = 0
            else:
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                kept.append(block)
                started_content = True
                if _is_substantial_prose(normalized_block) and not is_auxiliary_block:
                    abstract_prose_blocks_seen += 1
                continue
        if in_back_matter:
            continue
        if in_data_availability:
            if not title_kept and normalized_title:
                kept.insert(0, f"# {normalized_title}")
                title_kept = True
            kept.append(block)
            started_content = True
            continue
        if _looks_like_access_gate_text(normalized_block):
            if started_content:
                break
            continue
        if not started_content and is_auxiliary_block:
            continue
        if not is_auxiliary_block and _looks_like_front_matter_paragraph(normalized_block, title=normalized_title or None):
            continue
        if not started_content and not is_auxiliary_block and not _is_substantial_prose(normalized_block):
            continue
        if not title_kept and normalized_title:
            kept.insert(0, f"# {normalized_title}")
            title_kept = True
        kept.append(block)
        started_content = True

    if not kept and normalized_title:
        kept.append(f"# {normalized_title}")
    elif normalized_title and not any(
        (_markdown_heading_info(block) or (0, ""))[1].lower() == normalized_title_lower for block in kept
    ):
        kept.insert(0, f"# {normalized_title}")
    cleaned = clean_markdown(
        "\n\n".join(kept),
        noise_profile=_noise_profile_for_publisher(publisher),
    )
    cleaned = _normalize_browser_workflow_markdown(cleaned, publisher=publisher)
    cleaned = _inject_inline_table_blocks(cleaned, table_entries=table_entries, publisher=publisher)
    cleaned = _normalize_browser_workflow_markdown(cleaned, publisher=publisher)
    return _inject_inline_figure_links(
        cleaned,
        figure_assets=figure_assets,
        publisher=publisher,
    )


__all__ = [
    "rewrite_inline_figure_links",
]
