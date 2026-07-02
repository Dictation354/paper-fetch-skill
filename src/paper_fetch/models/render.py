"""Article rendering and asset block helpers."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any
from collections.abc import Mapping

from ..common_patterns import EXTENDED_DATA_FIGURE_LABEL
from ..markdown.images import render_markdown_image
from ..utils import normalize_text, safe_text
from .markdown import (
    NATURE_TABLE_LIKE_FIGURE_ASSET_PATTERN,
    NUMBERED_REFERENCE_PATTERN,
    TABLE_LIKE_FIGURE_ASSET_PATTERN,
    image_reference_candidates,
    image_references_match,
    iter_markdown_images,
    normalize_inline_html_text,
    normalize_markdown_text,
    replace_markdown_images,
    strip_markdown_images,
)
from .schema import (
    Asset,
    AssetProfile,
    ArticleModel,
    MaxTokensMode,
    Reference,
    RenderContext,
    RenderedBlock,
    Section,
    _MarkdownRenderPlan,
)
from .sections import (
    BODY_SECTION_EXCLUDED_KINDS,
    RETAINED_NON_BODY_SECTION_KINDS,
    abstract_sections,
    first_abstract_text,
    renderable_body_sections,
    section_priority,
    split_leading_abstract_context_sections,
)
from .tokens import (
    estimate_normalized_tokens,
    estimate_tokens,
    normalize_token_budget,
    truncate_text_to_tokens,
)

MARKDOWN_DECORATION_PATTERN = re.compile(r"[*_`$]+")
# Rendering strips only already-rendered caption prefixes; this is narrower
# than provider extraction because it must not reinterpret arbitrary body text.
FIGURE_CAPTION_LABEL_PREFIX_PATTERN = re.compile(
    rf"^\s*(?:figure|fig\.?|{re.escape(EXTENDED_DATA_FIGURE_LABEL)}\.?)\s+\d+[A-Za-z]?\s*[:.]?\s*",
    flags=re.IGNORECASE,
)


def asset_link(asset: Asset) -> str:
    return normalize_text(asset.path or asset.url)


def is_table_like_figure_asset(asset: Asset) -> bool:
    for candidate in (asset.heading, asset.caption):
        normalized = normalize_text(candidate)
        if TABLE_LIKE_FIGURE_ASSET_PATTERN.match(
            normalized
        ) or NATURE_TABLE_LIKE_FIGURE_ASSET_PATTERN.match(normalized):
            return True
    return False


def resolve_reference_limit(include_refs: str, total: int) -> int:
    if include_refs == "none" or total <= 0:
        return 0
    if include_refs == "all":
        return total
    if include_refs.startswith("top"):
        suffix = include_refs[3:] or "10"
        try:
            return min(total, int(suffix))
        except ValueError:
            return min(total, 10)
    return min(total, 10)


def resolve_reference_mode(
    include_refs: str | None, *, full_text_requested: bool
) -> str:
    if include_refs is not None:
        return include_refs
    if full_text_requested:
        return "all"
    return "top10"


def resolve_figure_mode(
    include_figures: str | None, *, asset_profile: AssetProfile
) -> str:
    if include_figures is not None:
        return include_figures
    return "captions_only" if asset_profile == "none" else "inline"


def resolve_supplementary_mode(
    include_supplementary: bool | None, *, asset_profile: AssetProfile
) -> bool:
    if include_supplementary is not None:
        return include_supplementary
    return asset_profile == "all"


def _build_article_header_block(article: ArticleModel) -> RenderedBlock:
    lines = ["---"]
    front_matter_fields = (
        ("title", article.metadata.title),
        (
            "authors",
            ", ".join(article.metadata.authors) if article.metadata.authors else None,
        ),
        ("journal", article.metadata.journal),
        ("doi", article.doi),
        ("published", article.metadata.published),
    )
    for key, value in front_matter_fields:
        normalized_value = normalize_inline_html_text(value)
        if normalized_value:
            lines.append(f'{key}: "{normalized_value.replace(chr(34), chr(39))}"')
    display_title = (
        normalize_inline_html_text(article.metadata.title) or "Untitled Article"
    )
    lines.extend(
        [
            f'source: "{article.source}"',
            f"has_fulltext: {str(article.quality.has_fulltext).lower()}",
            f'content_kind: "{article.quality.content_kind}"',
            f"has_abstract: {str(article.quality.has_abstract).lower()}",
            f"token_estimate: {article.quality.token_estimate}",
            "---",
            "",
            f"# {display_title}",
            "",
        ]
    )
    return build_rendered_block(lines)


def _build_markdown_render_plan(
    article: ArticleModel,
    *,
    include_refs: str | None,
    include_figures: str | None,
    include_supplementary: bool | None,
    asset_profile: AssetProfile,
    max_tokens: MaxTokensMode,
) -> _MarkdownRenderPlan:
    token_budget, full_text_requested = normalize_token_budget(max_tokens)
    effective_include_refs = resolve_reference_mode(
        include_refs, full_text_requested=full_text_requested
    )
    effective_include_figures = resolve_figure_mode(
        include_figures, asset_profile=asset_profile
    )
    effective_include_supplementary = resolve_supplementary_mode(
        include_supplementary,
        asset_profile=asset_profile,
    )
    body_sections = tuple(renderable_body_sections(article.sections))
    rendered_abstract_sections = tuple(abstract_sections(article.sections))
    lead_sections, remaining_body_sections = split_leading_abstract_context_sections(
        body_sections
    )
    retained_sections = tuple(
        section
        for section in article.sections
        if strip_markdown_images(section.text)
        and normalize_text(section.kind).lower() in RETAINED_NON_BODY_SECTION_KINDS
    )
    remaining_ids = {id(section) for section in remaining_body_sections}
    retained_ids = {id(section) for section in retained_sections}
    source_ordered_main_sections = tuple(
        section
        for section in article.sections
        if id(section) in remaining_ids or id(section) in retained_ids
    )
    figure_assets = selected_figure_assets(article.assets, asset_profile=asset_profile)
    figure_assets = filter_inline_body_figure_assets(
        figure_assets,
        sections=(
            *lead_sections,
            *rendered_abstract_sections,
            *remaining_body_sections,
            *retained_sections,
        ),
    )
    figure_assets = suppress_repeated_body_figure_captions(
        figure_assets,
        sections=(*rendered_abstract_sections, *body_sections, *retained_sections),
    )
    table_assets = filter_inline_body_table_assets(
        selected_table_assets(article.assets, asset_profile=asset_profile),
        sections=(
            *lead_sections,
            *rendered_abstract_sections,
            *remaining_body_sections,
            *retained_sections,
        ),
    )
    return _MarkdownRenderPlan(
        token_budget=token_budget,
        abstract_text=first_abstract_text(
            abstract_text=article.metadata.abstract, sections=article.sections
        ),
        abstract_sections=rendered_abstract_sections,
        level_shift=compute_level_shift(body_sections or retained_sections),
        include_figures=effective_include_figures,
        reference_count=resolve_reference_limit(
            effective_include_refs, len(article.references)
        ),
        lead_sections=lead_sections,
        body_sections=source_ordered_main_sections,
        retained_sections=(),
        figure_assets=tuple(figure_assets),
        table_assets=tuple(table_assets),
        supplementary_assets=tuple(
            selected_supplementary_assets(
                article.assets,
                asset_profile=asset_profile,
                include_supplementary=effective_include_supplementary,
            )
        ),
    )


def render_abstract_section_block(abstract_text: str) -> RenderedBlock:
    return render_section_block(
        Section(heading="Abstract", level=2, kind="abstract", text=abstract_text)
    )


def _append_abstract_with_budget(
    lines: list[str],
    *,
    abstract_text: str,
    context: RenderContext,
    as_section: bool = False,
) -> None:
    if not abstract_text:
        return
    abstract_block = (
        render_abstract_section_block(abstract_text)
        if as_section
        else render_abstract_block(abstract_text)
    )
    if context.append_if_fits(lines, abstract_block):
        return
    truncated_text = truncate_text_to_tokens(
        abstract_text, max(int(context.remaining_budget - 8), 0)
    )
    if truncated_text:
        context.append_if_fits(
            lines,
            render_abstract_section_block(truncated_text)
            if as_section
            else render_abstract_block(truncated_text),
        )
    context.mark_truncated()


def _append_sections_with_budget(
    lines: list[str],
    *,
    sections: tuple[Section, ...],
    level_shift: int,
    context: RenderContext,
    preserve_source_order: bool = False,
) -> None:
    selected_sections: list[tuple[int, RenderedBlock]] = []
    indexed_sections = list(enumerate(sections))
    ordered_sections = (
        indexed_sections
        if preserve_source_order
        else sorted(
            indexed_sections,
            key=lambda item: (section_priority(item[1]), item[0]),
        )
    )
    for index, section in ordered_sections:
        section_block = render_section_block(section, level_shift=level_shift)
        if section_block.token_estimate <= context.remaining_budget:
            selected_sections.append((index, section_block))
            context.remaining_budget -= section_block.token_estimate
            continue
        if not math.isinf(context.remaining_budget) and context.remaining_budget > 64:
            truncated_text = truncate_text_to_tokens(
                section.text,
                max(
                    int(
                        context.remaining_budget - estimate_tokens(section.heading) - 4
                    ),
                    0,
                ),
            )
            if truncated_text:
                truncated_section = Section(
                    heading=section.heading,
                    level=section.level,
                    kind=section.kind,
                    text=truncated_text,
                )
                selected_sections.append(
                    (
                        index,
                        render_section_block(
                            truncated_section, level_shift=level_shift
                        ),
                    )
                )
                context.remaining_budget = 0
        context.mark_truncated()
        break

    for _, section_block in sorted(selected_sections, key=lambda item: item[0]):
        lines.extend(section_block.lines)


def normalize_asset_section(asset: Asset) -> str:
    normalized = normalize_text(asset.section).lower()
    return normalized or "body"


def normalize_asset_render_state(asset: Asset) -> str:
    return normalize_text(asset.render_state).lower()


def asset_is_appendable(asset: Asset) -> bool:
    return normalize_asset_render_state(asset) not in {"inline", "suppressed"}


def asset_in_body(asset: Asset) -> bool:
    return normalize_asset_section(asset) not in {"appendix", "supplementary"}


def selected_figure_assets(
    assets: list[Asset], *, asset_profile: AssetProfile
) -> list[Asset]:
    figure_assets = [
        asset
        for asset in assets
        if asset.kind == "figure" and asset_is_appendable(asset)
    ]
    if asset_profile == "body":
        return [asset for asset in figure_assets if asset_in_body(asset)]
    return figure_assets


def _inline_markdown_image_urls(sections: Sequence[Section]) -> set[str]:
    urls: set[str] = set()
    for section in sections:
        for image in iter_markdown_images(section.text or ""):
            candidate = normalize_text(image.url).strip("<>")
            if candidate:
                urls.add(candidate)
    return urls


def _asset_link_field(asset: Asset | Mapping[str, Any], field: str) -> str | None:
    if isinstance(asset, Asset):
        return getattr(asset, field, None)
    return safe_text(asset.get(field)) or None


def _asset_markdown_reference_candidates(asset: Asset | Mapping[str, Any]) -> set[str]:
    candidates: set[str] = set()
    for asset_field in (
        "path",
        "url",
        "original_url",
        "download_url",
        "source_url",
        "source_path",
        "source_href",
        "preview_url",
        "full_size_url",
        "link",
    ):
        candidates |= image_reference_candidates(_asset_link_field(asset, asset_field))
    return candidates


def _asset_image_markdown(
    asset: Asset | Mapping[str, Any],
    *,
    image_alt: str,
    replacement_path: str,
) -> str:
    kind = _asset_link_field(asset, "kind") or ""
    heading = _asset_link_field(asset, "heading") or image_alt
    return render_markdown_image(kind, heading, replacement_path)


def rewrite_markdown_asset_links(
    markdown_text: str, assets: Sequence[Asset | Mapping[str, Any]] | None
) -> str:
    if not markdown_text or not assets:
        return markdown_text

    indexed_assets: list[tuple[Asset | Mapping[str, Any], str, set[str]]] = []
    for asset in assets:
        replacement_path = safe_text(_asset_link_field(asset, "path"))
        if not replacement_path:
            continue
        candidates = _asset_markdown_reference_candidates(asset)
        if candidates:
            indexed_assets.append((asset, replacement_path, candidates))

    if not indexed_assets:
        return markdown_text

    def replace_image(image) -> str:
        inline_url = normalize_text(image.url).strip("<>")
        inline_candidates = image_reference_candidates(inline_url)
        if not inline_candidates:
            return image.text
        for asset, replacement_path, asset_candidates in indexed_assets:
            if image_references_match(asset_candidates, inline_candidates):
                return _asset_image_markdown(
                    asset,
                    image_alt=image.alt,
                    replacement_path=replacement_path,
                )
        return image.text

    return replace_markdown_images(markdown_text, replace_image)


def filter_inline_body_assets(
    assets: Sequence[Asset],
    *,
    sections: Sequence[Section],
) -> list[Asset]:
    inline_urls = _inline_markdown_image_urls(sections)
    if not inline_urls:
        return list(assets)
    inline_candidates = [image_reference_candidates(url) for url in inline_urls]

    remaining: list[Asset] = []
    for asset in assets:
        if not asset_in_body(asset):
            remaining.append(asset)
            continue
        asset_candidates = _asset_markdown_reference_candidates(asset)
        if asset_candidates and any(
            image_references_match(asset_candidates, inline_candidate)
            for inline_candidate in inline_candidates
            if inline_candidate
        ):
            continue
        remaining.append(asset)
    return remaining


def filter_inline_body_figure_assets(
    assets: Sequence[Asset],
    *,
    sections: Sequence[Section],
) -> list[Asset]:
    return filter_inline_body_assets(assets, sections=sections)


def filter_inline_body_table_assets(
    assets: Sequence[Asset],
    *,
    sections: Sequence[Section],
) -> list[Asset]:
    return filter_inline_body_assets(assets, sections=sections)


def _caption_match_text(value: str | None) -> str:
    text = strip_markdown_images(normalize_markdown_text(value or ""))
    text = re.sub(r"</?(?:sub|sup)>", "", text, flags=re.IGNORECASE)
    text = MARKDOWN_DECORATION_PATTERN.sub("", text)
    return re.sub(r"[\W_]+", "", normalize_text(text).lower(), flags=re.UNICODE)


def _caption_has_meaningful_body(value: str | None) -> bool:
    text = FIGURE_CAPTION_LABEL_PREFIX_PATTERN.sub("", normalize_text(value or ""))
    return len(_caption_match_text(text)) >= 8


def _figure_caption_candidates(asset: Asset) -> list[str]:
    caption = normalize_text(asset.caption)
    heading = normalize_text(asset.heading)
    candidates: list[str] = []
    if caption:
        candidates.append(caption)
    if (
        heading
        and caption
        and not normalize_text(caption).lower().startswith(heading.lower())
    ):
        candidates.append(f"{heading}. {caption}")
    return candidates


def suppress_repeated_body_figure_captions(
    assets: Sequence[Asset],
    *,
    sections: Sequence[Section],
) -> list[Asset]:
    if not assets or not sections:
        return list(assets)
    body_match_text = _caption_match_text(
        "\n\n".join(section.text for section in sections)
    )
    if not body_match_text:
        return list(assets)

    suppressed: list[Asset] = []
    for asset in assets:
        if not asset_in_body(asset) or not normalize_text(asset.caption):
            suppressed.append(asset)
            continue
        repeated = any(
            _caption_has_meaningful_body(candidate)
            and _caption_match_text(candidate) in body_match_text
            for candidate in _figure_caption_candidates(asset)
        )
        suppressed.append(replace(asset, caption=None) if repeated else asset)
    return suppressed


def selected_table_assets(
    assets: list[Asset], *, asset_profile: AssetProfile
) -> list[Asset]:
    table_assets = [
        asset
        for asset in assets
        if asset.kind == "table" and asset_is_appendable(asset)
    ]
    if asset_profile == "none":
        return []
    if asset_profile == "body":
        return [asset for asset in table_assets if asset_in_body(asset)]
    return table_assets


def selected_supplementary_assets(
    assets: list[Asset],
    *,
    asset_profile: AssetProfile,
    include_supplementary: bool,
) -> list[Asset]:
    if not include_supplementary:
        return []
    supplementary_assets = [asset for asset in assets if asset.kind == "supplementary"]
    if asset_profile == "body":
        return [asset for asset in supplementary_assets if asset_in_body(asset)]
    if asset_profile == "none":
        return []
    return supplementary_assets


def build_rendered_block(
    lines: list[str], *, normalized_text: str | None = None
) -> RenderedBlock:
    normalized = (
        normalized_text
        if normalized_text is not None
        else normalize_markdown_text("\n".join(lines))
    )
    return RenderedBlock(
        lines=tuple(lines),
        normalized_text=normalized,
        token_estimate=estimate_normalized_tokens(normalized),
    )


def render_abstract_block(abstract_text: str) -> RenderedBlock:
    return build_rendered_block([f"**Abstract.** {abstract_text}", ""])


def append_asset_block(
    lines: list[str], *, heading: str, item_groups: list[RenderedBlock]
) -> None:
    if not item_groups:
        return
    lines.extend([f"## {heading}", ""])
    for group in item_groups:
        lines.extend(group.lines)
    lines.append("")


def append_asset_block_with_budget(
    lines: list[str],
    *,
    heading: str,
    item_groups: list[RenderedBlock],
    context: RenderContext,
) -> None:
    if not item_groups:
        return

    header_block = build_rendered_block([f"## {heading}", ""])
    if header_block.token_estimate > context.remaining_budget:
        context.mark_truncated()
        return

    selected_groups: list[RenderedBlock] = []
    remaining_after_header = context.remaining_budget - header_block.token_estimate
    for group in item_groups:
        if group.token_estimate <= remaining_after_header:
            selected_groups.append(group)
            remaining_after_header -= group.token_estimate
            continue
        context.mark_truncated()
        break

    if not selected_groups:
        return

    lines.extend(header_block.lines)
    for group in selected_groups:
        lines.extend(group.lines)
    lines.append("")
    context.remaining_budget = remaining_after_header


def asset_block_heading(default_heading: str, assets: Sequence[Asset]) -> str:
    if assets and all(
        normalize_asset_render_state(asset) == "appendix" for asset in assets
    ):
        return f"Additional {default_heading}"
    return default_heading


def _render_reference_line(reference_raw: str) -> str:
    normalized = normalize_text(reference_raw)
    if NUMBERED_REFERENCE_PATTERN.match(normalized):
        return normalized
    return f"- {normalized}"


def append_reference_block(
    lines: list[str],
    *,
    references: list[Reference],
    total_references: int,
    shown_references: int,
) -> None:
    if not references:
        return
    lines.extend(
        [f"## References ({total_references} total, showing {shown_references})", ""]
    )
    for reference in references:
        lines.append(_render_reference_line(reference.raw))
    lines.append("")


def append_reference_block_with_budget(
    lines: list[str],
    *,
    references: list[Reference],
    total_references: int,
    context: RenderContext,
) -> None:
    if not references:
        return

    header_block = build_rendered_block(
        [f"## References ({total_references} total, showing {len(references)})", ""]
    )
    if header_block.token_estimate > context.remaining_budget:
        context.mark_truncated()
        return

    selected_references: list[RenderedBlock] = []
    remaining_after_header = context.remaining_budget - header_block.token_estimate
    for reference in references:
        candidate_block = build_rendered_block([_render_reference_line(reference.raw)])
        if candidate_block.token_estimate <= remaining_after_header:
            selected_references.append(candidate_block)
            remaining_after_header -= candidate_block.token_estimate
            continue
        if not math.isinf(remaining_after_header) and remaining_after_header > 16:
            truncated_reference = truncate_text_to_tokens(
                reference.raw, max(8, int(remaining_after_header - 2))
            )
            truncated_block = build_rendered_block(
                [_render_reference_line(truncated_reference)]
            )
            if truncated_block.token_estimate <= remaining_after_header:
                selected_references.append(truncated_block)
                remaining_after_header -= truncated_block.token_estimate
        context.mark_truncated()
        break

    if not selected_references:
        return

    lines.extend(
        build_rendered_block(
            [
                f"## References ({total_references} total, showing {len(selected_references)})",
                "",
            ]
        ).lines
    )
    for block in selected_references:
        lines.extend(block.lines)
    lines.append("")
    context.remaining_budget = remaining_after_header


def render_figure_asset_groups(
    assets: list[Asset], *, include_figures: str
) -> list[RenderedBlock]:
    if include_figures not in {"captions_only", "inline"}:
        return []

    item_groups: list[RenderedBlock] = []
    for asset in assets:
        if is_table_like_figure_asset(asset):
            continue
        heading = normalize_text(asset.heading) or "Figure"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        if include_figures == "inline" and link:
            group = [render_markdown_image("figure", heading, link), ""]
            if caption:
                group.extend([caption, ""])
            item_groups.append(build_rendered_block(group))
            continue
        if caption:
            item_groups.append(build_rendered_block([f"- {heading}: {caption}"]))
        elif heading:
            item_groups.append(build_rendered_block([f"- {heading}"]))
    return item_groups


def render_table_asset_groups(assets: list[Asset]) -> list[RenderedBlock]:
    item_groups: list[RenderedBlock] = []
    for asset in assets:
        heading = normalize_text(asset.heading) or "Table"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        if link:
            group = [render_markdown_image("table", heading, link), ""]
            if caption:
                group.extend([caption, ""])
            item_groups.append(build_rendered_block(group))
            continue
        if caption:
            item_groups.append(build_rendered_block([f"- {heading}: {caption}"]))
        elif heading:
            item_groups.append(build_rendered_block([f"- {heading}"]))
    return item_groups


def render_supplementary_asset_groups(assets: list[Asset]) -> list[RenderedBlock]:
    item_groups: list[RenderedBlock] = []
    for asset in assets:
        heading = normalize_text(asset.heading) or "Supplementary Material"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        bullet = f"- [{heading}]({link})" if link else f"- {heading}"
        if caption:
            bullet += f": {caption}"
        item_groups.append(build_rendered_block([bullet]))
    return item_groups


def render_heading(section: Section, *, level_shift: int = 0) -> str:
    if not normalize_text(section.heading):
        return ""
    level = max(2, min(section.level - level_shift, 6))
    return f"{'#' * level} {section.heading}"


def render_section(section: Section, *, level_shift: int = 0) -> str:
    heading = render_heading(section, level_shift=level_shift)
    if not heading:
        return section.text.strip()
    return f"{heading}\n\n{section.text}".strip()


def render_section_block(section: Section, *, level_shift: int = 0) -> RenderedBlock:
    heading = render_heading(section, level_shift=level_shift)
    if not heading:
        normalized_text = normalize_markdown_text(section.text)
        return build_rendered_block(
            [*normalized_text.splitlines(), ""],
            normalized_text=normalized_text,
        )
    if not normalize_text(section.text):
        normalized_text = normalize_markdown_text(heading)
        return build_rendered_block(
            [*normalized_text.splitlines(), ""],
            normalized_text=normalized_text,
        )
    normalized_text = normalize_markdown_text(f"{heading}\n\n{section.text}".strip())
    return build_rendered_block(
        [*normalized_text.splitlines(), ""],
        normalized_text=normalized_text,
    )


def compute_level_shift(sections: Sequence[Section]) -> int:
    """Return how many heading levels to subtract so the shallowest body
    section renders at level 2 (right under the article title at level 1).

    Diagnostics / hardcoded level=2 sections are excluded so we don't anchor
    on them.
    """
    body_levels = [
        section.level
        for section in sections
        if normalize_text(section.kind).lower() not in BODY_SECTION_EXCLUDED_KINDS
        and section.level > 0
    ]
    if not body_levels:
        return 0
    return max(0, min(body_levels) - 2)


__all__ = [
    "append_asset_block",
    "append_asset_block_with_budget",
    "append_reference_block",
    "append_reference_block_with_budget",
    "asset_block_heading",
    "asset_in_body",
    "asset_is_appendable",
    "asset_link",
    "build_rendered_block",
    "compute_level_shift",
    "filter_inline_body_figure_assets",
    "filter_inline_body_table_assets",
    "is_table_like_figure_asset",
    "normalize_asset_render_state",
    "normalize_asset_section",
    "render_abstract_block",
    "render_abstract_section_block",
    "render_figure_asset_groups",
    "render_heading",
    "render_section",
    "render_section_block",
    "render_supplementary_asset_groups",
    "render_table_asset_groups",
    "resolve_figure_mode",
    "resolve_reference_limit",
    "resolve_reference_mode",
    "resolve_supplementary_mode",
    "rewrite_markdown_asset_links",
    "selected_figure_assets",
    "selected_supplementary_assets",
    "selected_table_assets",
    "suppress_repeated_body_figure_captions",
]
