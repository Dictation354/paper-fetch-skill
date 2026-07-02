"""Shared Markdown figure-link matching and injection."""

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Any
from collections.abc import Callable, Mapping

from ...common_patterns import (
    FIGURE_BASENAME_PATTERN,
    FIGURE_LABEL_PATTERN,
    SHORT_FIGURE_BASENAME_PATTERN,
)
from ...markdown.images import render_markdown_image
from ...models import normalize_markdown_text
from ...utils import normalize_text
from .asset_fields import DEFAULT_ASSET_URL_FIELDS

MARKDOWN_FIGURE_BLOCK_PATTERN = re.compile(
    r"^\*\*\s*((?:Fig(?:ure)?\.?)\s+\d+[A-Za-z]?\.?)(?:\s*\*\*|[\s\S]*\*\*$)",
    flags=re.IGNORECASE,
)
MARKDOWN_IMAGE_BLOCK_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
BODY_FIGURE_REFERENCE_PATTERN = re.compile(
    r"\bfig(?:ure)?s?\.?\s+"
    r"(?P<numbers>[A-Za-z]?\d+[A-Za-z]?"
    r"(?:\s*(?:,|and|&)\s*[A-Za-z]?\d+[A-Za-z]?){0,6})",
    flags=re.IGNORECASE,
)
FIGURE_REFERENCE_NUMBER_PATTERN = re.compile(r"[A-Za-z]?\d+[A-Za-z]?")
FRONT_MATTER_HEADINGS = {
    "abstract",
    "article highlights",
    "author summary",
    "graphical abstract",
    "highlights",
    "keywords",
    "plain language summary",
    "significance",
    "significance statement",
    "summary",
}
NON_BODY_FIGURE_REFERENCE_HEADING_PATTERN = re.compile(
    r"\b("
    r"acknowledg(?:e)?ments?|"
    r"appendix|"
    r"author(?:s'? contributions?)?|"
    r"bibliography|"
    r"competing interests?|"
    r"data accessibility|"
    r"data availability|"
    r"ethics|"
    r"figure captions?|"
    r"figures?|"
    r"funding|"
    r"references?|"
    r"supplementary|"
    r"supporting information"
    r")\b",
    flags=re.IGNORECASE,
)
CAPTION_VIEWER_NOISE_PATTERN = re.compile(
    r"\b(open in figure viewer|powerpoint|download figure|download slide|view full size)\b",
    flags=re.IGNORECASE,
)
NON_FIGURE_IMAGE_ALT_PATTERN = re.compile(
    r"^(?:extended\s+data\s+table|supplementary\s+table|table|formula|equation)\b",
    flags=re.IGNORECASE,
)
FIGURE_ASSET_URL_FIELDS = (
    "full_size_url",
    *(field for field in DEFAULT_ASSET_URL_FIELDS if field != "full_size_url"),
    "path",
)


def canonical_figure_label(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    match = FIGURE_LABEL_PATTERN.search(normalized)
    if not match:
        return None
    return f"figure {match.group(1).lower()}"


def canonical_figure_label_from_url(value: str | None) -> str | None:
    raw_value = normalize_text(str(value or ""))
    if not raw_value:
        return None
    parsed_path = urllib.parse.urlparse(raw_value).path or raw_value
    basename = normalize_text(
        os.path.basename(urllib.parse.unquote(parsed_path))
    ).lower()
    if not basename:
        return None
    match = FIGURE_BASENAME_PATTERN.search(
        basename
    ) or SHORT_FIGURE_BASENAME_PATTERN.search(basename)
    if match:
        return f"figure {match.group(1).lower()}"
    return None


def canonical_figure_label_from_image(
    alt_text: str | None, url: str | None
) -> str | None:
    return canonical_figure_label(
        str(alt_text or "")
    ) or canonical_figure_label_from_url(url)


def is_non_figure_image_alt(text: str | None) -> bool:
    normalized = normalize_text(text or "")
    if not normalized:
        return False
    return bool(NON_FIGURE_IMAGE_ALT_PATTERN.match(normalized))


def canonical_figure_label_from_asset(asset: Mapping[str, Any]) -> str | None:
    for field in ("heading",):
        candidate = canonical_figure_label(str(asset.get(field) or ""))
        if candidate:
            return candidate

    for field in FIGURE_ASSET_URL_FIELDS:
        candidate = canonical_figure_label_from_url(str(asset.get(field) or ""))
        if candidate:
            return candidate

    for field in ("caption",):
        candidate = canonical_figure_label(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return None


def inline_figure_markdown_entries(
    figure_assets: list[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for asset in figure_assets or []:
        kind = normalize_text(str(asset.get("kind") or "")).lower()
        if kind and kind != "figure":
            continue
        url = normalize_text(
            str(
                asset.get("path")
                or asset.get("full_size_url")
                or asset.get("url")
                or asset.get("preview_url")
                or asset.get("source_url")
                or asset.get("original_url")
                or ""
            )
        )
        if not url:
            continue
        aliases: list[str] = []
        for field in FIGURE_ASSET_URL_FIELDS:
            candidate = normalize_text(str(asset.get(field) or ""))
            if candidate and candidate not in aliases:
                aliases.append(candidate)
        entries.append(
            {
                "url": url,
                "heading": normalize_text(str(asset.get("heading") or "Figure"))
                or "Figure",
                "caption": normalize_text(str(asset.get("caption") or "")),
                "label_key": canonical_figure_label_from_asset(asset) or "",
                "aliases": "\n".join(aliases),
            }
        )
    return entries


def _base_panel_label_key(label_key: str) -> str | None:
    match = re.fullmatch(
        r"figure\s+([A-Za-z]?\d+)[A-Za-z]", normalize_text(label_key).lower()
    )
    if match is None:
        return None
    return f"figure {match.group(1).lower()}"


def _figure_reference_label_keys(text: str) -> list[str]:
    keys: list[str] = []
    for match in BODY_FIGURE_REFERENCE_PATTERN.finditer(normalize_text(text)):
        for number in FIGURE_REFERENCE_NUMBER_PATTERN.findall(match.group("numbers")):
            label_key = f"figure {number.lower()}"
            for candidate in (label_key, _base_panel_label_key(label_key)):
                if candidate and candidate not in keys:
                    keys.append(candidate)
    return keys


def _heading_key(block: str) -> str | None:
    match = MARKDOWN_HEADING_PATTERN.match(normalize_text(block))
    return normalize_text(match.group(1)).lower() if match is not None else None


def _body_heading_allows_figure_reference_injection(heading_key: str | None) -> bool:
    if not heading_key:
        return False
    if heading_key in FRONT_MATTER_HEADINGS:
        return False
    return not NON_BODY_FIGURE_REFERENCE_HEADING_PATTERN.search(heading_key)


def _inline_fallback_caption_block(
    entry: Mapping[str, str], original_markdown_text: str
) -> str:
    caption = normalize_text(entry.get("caption") or "")
    if not caption or caption in normalize_text(original_markdown_text):
        return ""
    if CAPTION_VIEWER_NOISE_PATTERN.search(caption):
        return ""
    heading = normalize_text(entry.get("heading") or "Figure").rstrip(".")
    if not heading:
        return caption
    caption_body = caption
    if caption_body.lower().startswith(heading.lower()):
        caption_body = caption_body[len(heading) :].lstrip(" .:")
    return (
        f"**{heading}.** {caption_body}".strip() if caption_body else f"**{heading}.**"
    )


def inject_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    clean_markdown_fn: Callable[[str], str],
) -> str:
    entries = inline_figure_markdown_entries(figure_assets)
    if not entries:
        return markdown_text
    has_labeled_entries = any(entry.get("label_key") for entry in entries)

    blocks = [
        normalize_markdown_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    if not blocks:
        return markdown_text

    injected: list[str] = []
    figure_index = 0
    used_entry_indexes: set[int] = set()
    indexed_entries_by_label: dict[str, list[int]] = {}
    indexed_entries_by_url: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        label_key = normalize_text(entry.get("label_key") or "").lower()
        if label_key:
            indexed_entries_by_label.setdefault(label_key, []).append(index)
        for candidate in normalize_text(entry.get("aliases") or "").split("\n"):
            normalized_candidate = normalize_text(candidate)
            if normalized_candidate:
                indexed_entries_by_url.setdefault(normalized_candidate, []).append(
                    index
                )

    def take_entry(index: int) -> dict[str, str] | None:
        nonlocal figure_index
        if index in used_entry_indexes:
            return None
        used_entry_indexes.add(index)
        if index >= figure_index:
            figure_index = index + 1
        return entries[index]

    def take_entry_for_label(label_key: str | None) -> dict[str, str] | None:
        nonlocal figure_index
        normalized_label = normalize_text(label_key or "").lower()
        if normalized_label and has_labeled_entries:
            for index in indexed_entries_by_label.get(normalized_label, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
            return None
        while figure_index < len(entries):
            index = figure_index
            figure_index += 1
            entry = take_entry(index)
            if entry is not None:
                return entry
        return None

    def take_entry_for_image(
        alt_text: str | None, url: str | None
    ) -> dict[str, str] | None:
        normalized_url = normalize_text(url)
        if normalized_url:
            for index in indexed_entries_by_url.get(normalized_url, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
        return take_entry_for_label(canonical_figure_label_from_image(alt_text, url))

    caption_label_keys: set[str] = set()
    existing_image_label_keys: set[str] = set()
    for block in blocks:
        normalized_existing_block = normalize_text(block)
        figure_match = MARKDOWN_FIGURE_BLOCK_PATTERN.match(normalized_existing_block)
        if figure_match is not None:
            figure_label_key = canonical_figure_label(figure_match.group(1).rstrip("."))
            if figure_label_key is not None:
                caption_label_keys.add(figure_label_key)
        existing_image_match = MARKDOWN_IMAGE_BLOCK_PATTERN.match(
            normalized_existing_block
        )
        if existing_image_match is not None and not is_non_figure_image_alt(
            existing_image_match.group(1)
        ):
            image_label_key = canonical_figure_label_from_image(
                existing_image_match.group(1),
                existing_image_match.group(2),
            )
            if image_label_key is not None:
                existing_image_label_keys.add(image_label_key)
    active_heading_key: str | None = None
    active_heading_allows_injection = False

    for block in blocks:
        normalized_block = normalize_text(block)
        current_heading_key = _heading_key(block)
        if current_heading_key is not None:
            active_heading_key = current_heading_key
            active_heading_allows_injection = not normalized_block.startswith(
                "# "
            ) and _body_heading_allows_figure_reference_injection(active_heading_key)
            injected.append(block)
            continue
        image_match = MARKDOWN_IMAGE_BLOCK_PATTERN.match(normalized_block)
        if image_match:
            alt_text = normalize_text(image_match.group(1))
            current_url = normalize_text(image_match.group(2))
            if is_non_figure_image_alt(alt_text):
                injected.append(block)
                continue
            image_entry = take_entry_for_image(alt_text, current_url)
            if image_entry is not None:
                heading = (
                    alt_text
                    or normalize_text(image_entry.get("heading") or "Figure")
                    or "Figure"
                )
                injected.append(
                    render_markdown_image("figure", heading, image_entry["url"])
                )
            else:
                injected.append(block)
            continue
        match = MARKDOWN_FIGURE_BLOCK_PATTERN.match(normalized_block)
        if match:
            label = match.group(1).rstrip(".")
            caption_entry = take_entry_for_label(canonical_figure_label(label))
            if caption_entry is not None:
                image_block = render_markdown_image(
                    "figure", label, caption_entry["url"]
                )
                if not injected or normalize_text(injected[-1]) != image_block:
                    injected.append(image_block)
                injected.append(block)
                continue
        injected.append(block)
        if not active_heading_allows_injection:
            continue
        for label_key in _figure_reference_label_keys(normalized_block):
            if (
                label_key in caption_label_keys
                or label_key in existing_image_label_keys
            ):
                continue
            referenced_entry = take_entry_for_label(label_key)
            if referenced_entry is not None:
                image_block = render_markdown_image(
                    "figure",
                    normalize_text(referenced_entry.get("heading") or label_key)
                    or "Figure",
                    referenced_entry["url"],
                )
                if image_block and normalize_text(injected[-1]) != image_block:
                    injected.append(image_block)
                caption_block = _inline_fallback_caption_block(
                    referenced_entry, markdown_text
                )
                if caption_block:
                    injected.append(caption_block)
    return clean_markdown_fn("\n\n".join(injected))


def rewrite_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    clean_markdown_fn: Callable[[str], str],
) -> str:
    return inject_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=clean_markdown_fn,
    )
