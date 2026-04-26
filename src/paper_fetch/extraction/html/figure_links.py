"""Shared Markdown figure-link matching and injection."""

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Any, Callable, Mapping

from ...models import normalize_markdown_text
from ...utils import normalize_text

FIGURE_LABEL_PATTERN = re.compile(r"\bfig(?:ure)?\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
FIGURE_BASENAME_PATTERN = re.compile(r"(?:^|[^a-z])fig(?:ure)?[_-]?0*(\d+[A-Za-z]?)(?=$|[^a-z0-9])", flags=re.IGNORECASE)
SHORT_FIGURE_BASENAME_PATTERN = re.compile(r"(?:^|[^a-z])f[_-]?0*(\d+[A-Za-z]?)(?=$|[^a-z0-9])", flags=re.IGNORECASE)
MARKDOWN_FIGURE_BLOCK_PATTERN = re.compile(r"^\*\*(Figure\s+\d+[A-Za-z]?\.?)\*\*(?:[\s\S]*)$", flags=re.IGNORECASE)
MARKDOWN_IMAGE_BLOCK_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
FIGURE_ASSET_URL_FIELDS = ("full_size_url", "url", "preview_url", "source_url", "original_url", "path")


def canonical_figure_label(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    match = FIGURE_LABEL_PATTERN.search(normalized)
    if not match:
        return None
    return f"figure {match.group(1).lower()}"


def canonical_figure_label_from_asset(asset: Mapping[str, Any]) -> str | None:
    for field in ("heading",):
        candidate = canonical_figure_label(str(asset.get(field) or ""))
        if candidate:
            return candidate

    for field in FIGURE_ASSET_URL_FIELDS:
        raw_value = normalize_text(str(asset.get(field) or ""))
        if not raw_value:
            continue
        parsed_path = urllib.parse.urlparse(raw_value).path or raw_value
        basename = normalize_text(os.path.basename(urllib.parse.unquote(parsed_path))).lower()
        if not basename:
            continue
        match = FIGURE_BASENAME_PATTERN.search(basename) or SHORT_FIGURE_BASENAME_PATTERN.search(basename)
        if match:
            return f"figure {match.group(1).lower()}"

    for field in ("caption",):
        candidate = canonical_figure_label(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return None


def inline_figure_markdown_entries(figure_assets: list[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for asset in figure_assets or []:
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
                "heading": normalize_text(str(asset.get("heading") or "Figure")) or "Figure",
                "label_key": canonical_figure_label_from_asset(asset) or "",
                "aliases": "\n".join(aliases),
            }
        )
    return entries


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

    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
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
                indexed_entries_by_url.setdefault(normalized_candidate, []).append(index)

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

    def take_entry_for_image(alt_text: str | None, url: str | None) -> dict[str, str] | None:
        normalized_url = normalize_text(url)
        if normalized_url:
            for index in indexed_entries_by_url.get(normalized_url, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
        return take_entry_for_label(canonical_figure_label(normalize_text(alt_text or "")))

    for block in blocks:
        normalized_block = normalize_text(block)
        image_match = MARKDOWN_IMAGE_BLOCK_PATTERN.match(normalized_block)
        if image_match:
            alt_text = normalize_text(image_match.group(1))
            current_url = normalize_text(image_match.group(2))
            entry = take_entry_for_image(alt_text, current_url)
            if entry is not None:
                heading = alt_text or normalize_text(entry.get("heading") or "Figure") or "Figure"
                injected.append(f"![{heading}]({entry['url']})")
            else:
                injected.append(block)
            continue
        match = MARKDOWN_FIGURE_BLOCK_PATTERN.match(normalized_block)
        if match:
            label = match.group(1).rstrip(".")
            entry = take_entry_for_label(canonical_figure_label(label))
            if entry is not None:
                image_block = f"![{label}]({entry['url']})"
                if not injected or normalize_text(injected[-1]) != image_block:
                    injected.append(image_block)
                injected.append(block)
                continue
        injected.append(block)
    return clean_markdown_fn("\n\n".join(injected))
