"""Shared article model and AI-friendly serialization helpers."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping

from .utils import normalize_text, safe_text

SourceKind = Literal[
    "elsevier_xml",
    "elsevier_browser",
    "springer_html",
    "wiley_browser",
    "science",
    "pnas",
    "html_generic",
    "crossref_meta",
]
OutputMode = Literal["article", "markdown", "metadata"]
AssetProfile = Literal["none", "body", "all"]
MaxTokensMode = int | Literal["full_text"]
MARKDOWN_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
MARKDOWN_TABLE_RULE_PATTERN = re.compile(r"^\s*[-+:| ]{3,}\s*$")
MARKDOWN_LIST_MARKER_PATTERN = re.compile(r"^(\s{0,3}(?:[-*+]|\d+[.)])\s+)(.*)$")
TRUNCATION_WARNING = "Output truncated to satisfy token budget."

SECTION_PRIORITY = {
    "abstract": 0,
    "introduction": 1,
    "background": 1,
    "methods": 2,
    "materials and methods": 2,
    "methodology": 2,
    "results": 3,
    "findings": 3,
    "discussion": 4,
    "conclusion": 5,
    "conclusions": 5,
    "references": 6,
}


def normalize_markdown_text(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    normalized_lines: list[str] = []
    in_fence = False
    blank_run = 0
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if MARKDOWN_FENCE_PATTERN.match(line):
            normalized_lines.append(line.strip())
            in_fence = not in_fence
            blank_run = 0
            continue

        if in_fence or should_preserve_markdown_line(line):
            normalized_line = line
        else:
            normalized_line = normalize_markdown_prose_line(line)

        if normalized_line:
            normalized_lines.append(normalized_line)
            blank_run = 0
            continue

        if in_fence or blank_run < 2:
            normalized_lines.append("")
        blank_run += 1

    return "\n".join(normalized_lines).strip()


def should_preserve_markdown_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if line.startswith(("    ", "\t")):
        return True
    if stripped.startswith("|") or stripped.endswith("|"):
        return True
    return bool(MARKDOWN_TABLE_RULE_PATTERN.match(stripped))


def normalize_markdown_prose_line(line: str) -> str:
    expanded = line.replace("\xa0", " ")
    list_match = MARKDOWN_LIST_MARKER_PATTERN.match(expanded)
    if list_match:
        marker, body = list_match.groups()
        body = re.sub(r"[ \t\r\f\v]+", " ", body).strip()
        return f"{marker}{body}" if body else marker.rstrip()

    leading_match = re.match(r"^\s*", expanded)
    leading = leading_match.group(0) if leading_match else ""
    body = re.sub(r"[ \t\r\f\v]+", " ", expanded[len(leading):]).strip()
    if not body:
        return ""
    return f"{leading}{body}" if leading else body


def estimate_tokens(text: str) -> int:
    normalized = normalize_markdown_text(text)
    return estimate_normalized_tokens(normalized)


def estimate_normalized_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def strip_markdown_images(text: str) -> str:
    stripped = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    return normalize_markdown_text(stripped)


def asset_link(asset: "Asset") -> str:
    return normalize_text(asset.path or asset.url)


def local_asset_link(value: Any) -> str | None:
    normalized = safe_text(value)
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://", "//")):
        return None
    return normalized


def truncate_text_to_tokens(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""
    normalized = normalize_markdown_text(text)
    if estimate_normalized_tokens(normalized) <= token_budget:
        return normalized
    max_chars = max(32, token_budget * 4)
    truncated = normalized[:max_chars].rstrip(" ,;:\n")
    if len(truncated) < len(normalized):
        truncated += "..."
    return truncated


def normalize_token_budget(max_tokens: MaxTokensMode) -> tuple[float, bool]:
    if max_tokens == "full_text":
        return math.inf, True
    return float(max_tokens), False


def section_kind_for_heading(heading: str) -> str:
    normalized = normalize_text(heading).lower()
    if not normalized:
        return "body"
    if normalized in {"references", "bibliography"}:
        return "references"
    if normalized in {"supplementary materials", "supplementary information"}:
        return "supplementary"
    if normalized in {"conversion notes"}:
        return "diagnostics"
    if normalized in {"abstract"}:
        return "abstract"
    return "body"


def section_priority(section: "Section") -> int:
    normalized = normalize_text(section.heading).lower()
    if normalized in SECTION_PRIORITY:
        return SECTION_PRIORITY[normalized]
    for key, priority in SECTION_PRIORITY.items():
        if key in normalized:
            return priority
    return 4


@dataclass
class Metadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    journal: str | None = None
    published: str | None = None
    keywords: list[str] = field(default_factory=list)
    license_urls: list[str] = field(default_factory=list)
    landing_page_url: str | None = None


@dataclass
class Section:
    heading: str
    level: int
    kind: str
    text: str


@dataclass
class Reference:
    raw: str
    doi: str | None = None
    title: str | None = None
    year: str | None = None


@dataclass
class Asset:
    kind: str
    heading: str
    caption: str | None = None
    url: str | None = None
    path: str | None = None
    section: str | None = None


@dataclass
class TokenEstimateBreakdown:
    abstract: int = 0
    body: int = 0
    refs: int = 0


def coerce_token_estimate_breakdown(
    value: TokenEstimateBreakdown | Mapping[str, Any] | None,
) -> TokenEstimateBreakdown:
    if isinstance(value, TokenEstimateBreakdown):
        return value
    if isinstance(value, Mapping):
        return TokenEstimateBreakdown(
            abstract=int(value.get("abstract") or 0),
            body=int(value.get("body") or 0),
            refs=int(value.get("refs") or 0),
        )
    return TokenEstimateBreakdown()


def build_token_estimate_breakdown(
    *,
    abstract_text: str | None,
    sections: Sequence["Section"],
    references: Sequence["Reference"],
) -> TokenEstimateBreakdown:
    abstract = estimate_tokens(abstract_text or "")
    body = estimate_tokens(
        "\n\n".join(
            normalize_text(section.text)
            for section in sections
            if section.kind not in {"abstract", "references"} and normalize_text(section.text)
        )
    )
    refs = estimate_tokens("\n".join(normalize_text(reference.raw) for reference in references if normalize_text(reference.raw)))
    return TokenEstimateBreakdown(abstract=abstract, body=body, refs=refs)


@dataclass
class Quality:
    has_fulltext: bool
    token_estimate: int
    warnings: list[str] = field(default_factory=list)
    source_trail: list[str] = field(default_factory=list)
    token_estimate_breakdown: TokenEstimateBreakdown = field(default_factory=TokenEstimateBreakdown)


@dataclass(frozen=True)
class RenderOptions:
    include_refs: str | None = None
    asset_profile: AssetProfile | None = None
    max_tokens: MaxTokensMode = "full_text"


@dataclass(frozen=True)
class RenderedBlock:
    lines: tuple[str, ...]
    normalized_text: str
    token_estimate: int


@dataclass(frozen=True)
class _MarkdownRenderPlan:
    token_budget: float
    abstract_text: str
    level_shift: int
    include_figures: str
    reference_count: int
    body_sections: tuple["Section", ...]
    figure_assets: tuple["Asset", ...]
    table_assets: tuple["Asset", ...]
    supplementary_assets: tuple["Asset", ...]


@dataclass
class RenderContext:
    remaining_budget: float
    warnings: list[str] = field(default_factory=list)
    truncated_any: bool = False

    def append_if_fits(self, lines: list[str], block: RenderedBlock) -> bool:
        if block.token_estimate > self.remaining_budget:
            return False
        lines.extend(block.lines)
        self.remaining_budget -= block.token_estimate
        return True

    def mark_truncated(self) -> None:
        self.truncated_any = True

    def finalize_warnings(self) -> None:
        if self.truncated_any and TRUNCATION_WARNING not in self.warnings:
            self.warnings.append(TRUNCATION_WARNING)


@dataclass
class FetchEnvelope:
    doi: str | None
    source: str
    has_fulltext: bool
    warnings: list[str] = field(default_factory=list)
    source_trail: list[str] = field(default_factory=list)
    token_estimate: int = 0
    token_estimate_breakdown: TokenEstimateBreakdown = field(default_factory=TokenEstimateBreakdown)
    article: "ArticleModel | None" = None
    markdown: str | None = None
    metadata: Metadata | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ArticleModel:
    doi: str | None
    source: SourceKind
    metadata: Metadata
    sections: list[Section] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    quality: Quality = field(default_factory=lambda: Quality(has_fulltext=False, token_estimate=0))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_ai_markdown(
        self,
        *,
        include_refs: str | None = None,
        include_figures: str | None = None,
        include_supplementary: bool | None = None,
        asset_profile: AssetProfile = "none",
        max_tokens: MaxTokensMode = "full_text",
    ) -> str:
        warnings = list(self.quality.warnings)
        render_plan = _build_markdown_render_plan(
            self,
            include_refs=include_refs,
            include_figures=include_figures,
            include_supplementary=include_supplementary,
            asset_profile=asset_profile,
            max_tokens=max_tokens,
        )
        front_matter_block = _build_article_header_block(self)
        lines = list(front_matter_block.lines)
        context = RenderContext(
            remaining_budget=render_plan.token_budget - front_matter_block.token_estimate,
            warnings=warnings,
        )
        if context.remaining_budget <= 0:
            context.mark_truncated()
            context.finalize_warnings()
            return "\n".join(lines).strip() + "\n"

        _append_abstract_with_budget(lines, abstract_text=render_plan.abstract_text, context=context)
        _append_sections_with_budget(
            lines,
            sections=render_plan.body_sections,
            level_shift=render_plan.level_shift,
            context=context,
        )

        append_asset_block_with_budget(
            lines,
            heading="Figures",
            item_groups=render_figure_asset_groups(list(render_plan.figure_assets), include_figures=render_plan.include_figures),
            context=context,
        )
        append_asset_block_with_budget(
            lines,
            heading="Tables",
            item_groups=render_table_asset_groups(list(render_plan.table_assets)),
            context=context,
        )
        append_asset_block_with_budget(
            lines,
            heading="Supplementary Materials",
            item_groups=render_supplementary_asset_groups(list(render_plan.supplementary_assets)),
            context=context,
        )

        append_reference_block_with_budget(
            lines,
            references=self.references[: render_plan.reference_count],
            total_references=len(self.references),
            context=context,
        )

        context.finalize_warnings()
        return "\n".join(lines).strip() + "\n"


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


def resolve_reference_mode(include_refs: str | None, *, full_text_requested: bool) -> str:
    if include_refs is not None:
        return include_refs
    if full_text_requested:
        return "all"
    return "top10"


def resolve_figure_mode(include_figures: str | None, *, asset_profile: AssetProfile) -> str:
    if include_figures is not None:
        return include_figures
    return "captions_only" if asset_profile == "none" else "inline"


def resolve_supplementary_mode(include_supplementary: bool | None, *, asset_profile: AssetProfile) -> bool:
    if include_supplementary is not None:
        return include_supplementary
    return asset_profile == "all"


def _build_article_header_block(article: "ArticleModel") -> RenderedBlock:
    lines = ["---"]
    front_matter_fields = (
        ("title", article.metadata.title),
        ("authors", ", ".join(article.metadata.authors) if article.metadata.authors else None),
        ("journal", article.metadata.journal),
        ("doi", article.doi),
        ("published", article.metadata.published),
    )
    for key, value in front_matter_fields:
        normalized_value = normalize_text(value)
        if normalized_value:
            lines.append(f'{key}: "{normalized_value.replace(chr(34), chr(39))}"')
    lines.extend(
        [
            f'source: "{article.source}"',
            f"has_fulltext: {str(article.quality.has_fulltext).lower()}",
            f"token_estimate: {article.quality.token_estimate}",
            "---",
            "",
            f"# {article.metadata.title or 'Untitled Article'}",
            "",
        ]
    )
    return build_rendered_block(lines)


def _build_markdown_render_plan(
    article: "ArticleModel",
    *,
    include_refs: str | None,
    include_figures: str | None,
    include_supplementary: bool | None,
    asset_profile: AssetProfile,
    max_tokens: MaxTokensMode,
) -> _MarkdownRenderPlan:
    token_budget, full_text_requested = normalize_token_budget(max_tokens)
    effective_include_refs = resolve_reference_mode(include_refs, full_text_requested=full_text_requested)
    effective_include_figures = resolve_figure_mode(include_figures, asset_profile=asset_profile)
    effective_include_supplementary = resolve_supplementary_mode(
        include_supplementary,
        asset_profile=asset_profile,
    )
    body_sections = tuple(
        section
        for section in article.sections
        if section.kind not in {"abstract", "references", "supplementary", "diagnostics"}
    )
    return _MarkdownRenderPlan(
        token_budget=token_budget,
        abstract_text=normalize_text(article.metadata.abstract),
        level_shift=compute_level_shift(article.sections),
        include_figures=effective_include_figures,
        reference_count=resolve_reference_limit(effective_include_refs, len(article.references)),
        body_sections=body_sections,
        figure_assets=tuple(selected_figure_assets(article.assets, asset_profile=asset_profile)),
        table_assets=tuple(selected_table_assets(article.assets, asset_profile=asset_profile)),
        supplementary_assets=tuple(
            selected_supplementary_assets(
                article.assets,
                asset_profile=asset_profile,
                include_supplementary=effective_include_supplementary,
            )
        ),
    )


def _append_abstract_with_budget(lines: list[str], *, abstract_text: str, context: RenderContext) -> None:
    if not abstract_text:
        return
    abstract_block = render_abstract_block(abstract_text)
    if context.append_if_fits(lines, abstract_block):
        return
    truncated_text = truncate_text_to_tokens(abstract_text, max(int(context.remaining_budget - 8), 0))
    if truncated_text:
        context.append_if_fits(lines, render_abstract_block(truncated_text))
    context.mark_truncated()


def _append_sections_with_budget(
    lines: list[str],
    *,
    sections: tuple["Section", ...],
    level_shift: int,
    context: RenderContext,
) -> None:
    selected_sections: list[tuple[int, RenderedBlock]] = []
    indexed_sections = list(enumerate(sections))
    for index, section in sorted(indexed_sections, key=lambda item: (section_priority(item[1]), item[0])):
        section_block = render_section_block(section, level_shift=level_shift)
        if section_block.token_estimate <= context.remaining_budget:
            selected_sections.append((index, section_block))
            context.remaining_budget -= section_block.token_estimate
            continue
        if not math.isinf(context.remaining_budget) and context.remaining_budget > 64:
            truncated_text = truncate_text_to_tokens(
                section.text,
                max(int(context.remaining_budget - estimate_tokens(section.heading) - 4), 0),
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
                        render_section_block(truncated_section, level_shift=level_shift),
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


def asset_in_body(asset: Asset) -> bool:
    return normalize_asset_section(asset) not in {"appendix", "supplementary"}


def selected_figure_assets(assets: list[Asset], *, asset_profile: AssetProfile) -> list[Asset]:
    figure_assets = [asset for asset in assets if asset.kind == "figure"]
    if asset_profile == "body":
        return [asset for asset in figure_assets if asset_in_body(asset)]
    return figure_assets


def selected_table_assets(assets: list[Asset], *, asset_profile: AssetProfile) -> list[Asset]:
    table_assets = [asset for asset in assets if asset.kind == "table"]
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


def build_rendered_block(lines: list[str], *, normalized_text: str | None = None) -> RenderedBlock:
    normalized = normalized_text if normalized_text is not None else normalize_markdown_text("\n".join(lines))
    return RenderedBlock(
        lines=tuple(lines),
        normalized_text=normalized,
        token_estimate=estimate_normalized_tokens(normalized),
    )


def render_abstract_block(abstract_text: str) -> RenderedBlock:
    return build_rendered_block([f"**Abstract.** {abstract_text}", ""])


def append_asset_block(lines: list[str], *, heading: str, item_groups: list[RenderedBlock]) -> None:
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


def append_reference_block(
    lines: list[str],
    *,
    references: list[Reference],
    total_references: int,
    shown_references: int,
) -> None:
    if not references:
        return
    lines.extend([f"## References ({total_references} total, showing {shown_references})", ""])
    for reference in references:
        lines.append(f"- {reference.raw}")
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

    header_block = build_rendered_block([f"## References ({total_references} total, showing {len(references)})", ""])
    if header_block.token_estimate > context.remaining_budget:
        context.mark_truncated()
        return

    selected_references: list[RenderedBlock] = []
    remaining_after_header = context.remaining_budget - header_block.token_estimate
    for reference in references:
        candidate_block = build_rendered_block([f"- {reference.raw}"])
        if candidate_block.token_estimate <= remaining_after_header:
            selected_references.append(candidate_block)
            remaining_after_header -= candidate_block.token_estimate
            continue
        if not math.isinf(remaining_after_header) and remaining_after_header > 16:
            truncated_reference = truncate_text_to_tokens(reference.raw, max(8, int(remaining_after_header - 2)))
            truncated_block = build_rendered_block([f"- {truncated_reference}"])
            if truncated_block.token_estimate <= remaining_after_header:
                selected_references.append(truncated_block)
                remaining_after_header -= truncated_block.token_estimate
        context.mark_truncated()
        break

    if not selected_references:
        return

    lines.extend(build_rendered_block([f"## References ({total_references} total, showing {len(selected_references)})", ""]).lines)
    for block in selected_references:
        lines.extend(block.lines)
    lines.append("")
    context.remaining_budget = remaining_after_header


def render_figure_asset_groups(assets: list[Asset], *, include_figures: str) -> list[RenderedBlock]:
    if include_figures not in {"captions_only", "inline"}:
        return []

    item_groups: list[RenderedBlock] = []
    for asset in assets:
        heading = normalize_text(asset.heading) or "Figure"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        if include_figures == "inline" and link:
            group = [f"![{heading}]({link})", ""]
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
            group = [f"![{heading}]({link})", ""]
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
    level = max(2, min(section.level - level_shift, 6))
    return f"{'#' * level} {section.heading}"


def render_section(section: Section, *, level_shift: int = 0) -> str:
    return f"{render_heading(section, level_shift=level_shift)}\n\n{section.text}".strip()


def render_section_block(section: Section, *, level_shift: int = 0) -> RenderedBlock:
    heading = render_heading(section, level_shift=level_shift)
    return build_rendered_block(
        [heading, section.text, ""],
        normalized_text=normalize_markdown_text(f"{heading}\n\n{section.text}".strip()),
    )


def compute_level_shift(sections: list[Section]) -> int:
    """Return how many heading levels to subtract so the shallowest body
    section renders at level 2 (right under the article title at level 1).

    Diagnostics / hardcoded level=2 sections are excluded so we don't anchor
    on them.
    """
    body_levels = [
        section.level
        for section in sections
        if section.kind not in {"diagnostics"} and section.level > 0
    ]
    if not body_levels:
        return 0
    return max(0, min(body_levels) - 2)


def lines_to_sections(lines: list[str], *, fallback_heading: str = "Full Text") -> list[Section]:
    sections: list[Section] = []
    current_heading = fallback_heading
    current_level = 2
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = strip_markdown_images("\n".join(buffer))
        if not text:
            return
        sections.append(
            Section(
                heading=current_heading,
                level=current_level,
                kind=section_kind_for_heading(current_heading),
                text=text,
            )
        )

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            buffer = []
            current_level = len(stripped) - len(stripped.lstrip("#"))
            current_heading = stripped[current_level:].strip() or fallback_heading
            continue
        if stripped or buffer:
            buffer.append(line.rstrip())
    flush()
    return sections


def normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [safe_text(item) for item in value if safe_text(item)]
    if isinstance(value, str):
        parts = [safe_text(part) for part in re.split(r"\s*;\s*|\s*,\s*", value)]
        return [part for part in parts if part]
    return []


def build_metadata(metadata: Mapping[str, Any]) -> Metadata:
    return Metadata(
        title=safe_text(metadata.get("title")) or None,
        authors=normalize_authors(metadata.get("authors")),
        abstract=safe_text(metadata.get("abstract")) or None,
        journal=safe_text(metadata.get("journal_title") or metadata.get("journal")) or None,
        published=safe_text(metadata.get("published")) or None,
        keywords=[
            safe_text(item)
            for item in (metadata.get("keywords") or [])
            if safe_text(item)
        ],
        license_urls=[
            safe_text(item)
            for item in (metadata.get("license_urls") or [])
            if safe_text(item)
        ],
        landing_page_url=safe_text(metadata.get("landing_page_url")) or None,
    )


def metadata_only_article(
    *,
    source: SourceKind,
    metadata: Mapping[str, Any],
    doi: str | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    article_metadata = build_metadata(metadata)
    references = build_references(metadata.get("references"))
    token_estimate_breakdown = build_token_estimate_breakdown(
        abstract_text=article_metadata.abstract,
        sections=[],
        references=references,
    )
    token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body
    return ArticleModel(
        doi=doi or safe_text(metadata.get("doi")) or None,
        source=source,
        metadata=article_metadata,
        sections=[],
        references=references,
        assets=[],
        quality=Quality(
            has_fulltext=False,
            token_estimate=token_estimate,
            warnings=list(warnings or []),
            source_trail=list(source_trail or []),
            token_estimate_breakdown=token_estimate_breakdown,
        ),
    )


def build_references(raw_references: Any) -> list[Reference]:
    references: list[Reference] = []
    if not isinstance(raw_references, list):
        return references
    for item in raw_references:
        if isinstance(item, Mapping):
            raw = safe_text(item.get("raw") or item.get("unstructured") or item.get("title"))
            if not raw:
                continue
            references.append(
                Reference(
                    raw=raw,
                    doi=safe_text(item.get("doi")) or None,
                    title=safe_text(item.get("title")) or None,
                    year=safe_text(item.get("year")) or None,
                )
            )
        else:
            raw = safe_text(item)
            if raw:
                references.append(Reference(raw=raw))
    return references


def article_from_structure(
    *,
    source: SourceKind,
    metadata: Mapping[str, Any],
    doi: str | None,
    abstract_lines: list[str],
    body_lines: list[str],
    figure_entries: list[Mapping[str, Any]],
    table_entries: list[Mapping[str, Any]],
    supplement_entries: list[Mapping[str, Any]],
    conversion_notes: list[str],
    references: list[Reference] | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    article_metadata = build_metadata(metadata)
    abstract_text = strip_markdown_images("\n".join(abstract_lines))
    if abstract_text and not article_metadata.abstract:
        article_metadata.abstract = abstract_text

    sections = lines_to_sections(body_lines)
    if conversion_notes:
        sections.append(
            Section(
                heading="Conversion Notes",
                level=2,
                kind="diagnostics",
                text=normalize_text("\n".join(conversion_notes)),
            )
        )

    assets: list[Asset] = []
    for entry in figure_entries:
        assets.append(
            Asset(
                kind="figure",
                heading=safe_text(entry.get("heading") or "Figure") or "Figure",
                caption=safe_text(entry.get("caption")) or None,
                url=local_asset_link(entry.get("link")),
                path=safe_text(entry.get("path")) or None,
                section=safe_text(entry.get("section")) or None,
            )
        )
    for entry in table_entries:
        assets.append(
            Asset(
                kind="table",
                heading=safe_text(entry.get("heading") or "Table") or "Table",
                caption=safe_text(entry.get("caption")) or None,
                url=local_asset_link(entry.get("link")),
                path=safe_text(entry.get("path")) or None,
                section=safe_text(entry.get("section")) or None,
            )
        )
    for entry in supplement_entries:
        assets.append(
            Asset(
                kind="supplementary",
                heading=safe_text(entry.get("heading") or "Supplementary Material") or "Supplementary Material",
                caption=safe_text(entry.get("caption")) or None,
                url=local_asset_link(entry.get("link")),
                path=safe_text(entry.get("path")) or None,
                section=safe_text(entry.get("section")) or None,
            )
        )

    fulltext_chunks = [article_metadata.abstract or ""]
    fulltext_chunks.extend(section.text for section in sections)
    normalized_references = list(references or build_references(metadata.get("references")))
    token_estimate_breakdown = build_token_estimate_breakdown(
        abstract_text=article_metadata.abstract,
        sections=sections,
        references=normalized_references,
    )
    token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body

    return ArticleModel(
        doi=doi or safe_text(metadata.get("doi")) or None,
        source=source,
        metadata=article_metadata,
        sections=sections,
        references=normalized_references,
        assets=assets,
        quality=Quality(
            has_fulltext=bool(sections or article_metadata.abstract),
            token_estimate=token_estimate,
            warnings=list(warnings or []),
            source_trail=list(source_trail or []),
            token_estimate_breakdown=token_estimate_breakdown,
        ),
    )


def article_from_markdown(
    *,
    source: SourceKind,
    metadata: Mapping[str, Any],
    doi: str | None,
    markdown_text: str,
    assets: list[Mapping[str, Any]] | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    article_metadata = build_metadata(metadata)
    normalized = normalize_markdown_text(markdown_text)
    sections = lines_to_sections(normalized.splitlines())
    extracted_abstract = None
    for section in sections:
        if section.kind == "abstract":
            extracted_abstract = section.text
            break
    article_metadata.abstract = extracted_abstract or article_metadata.abstract
    normalized_assets = [
        Asset(
            kind=safe_text(item.get("kind") or item.get("asset_type") or "asset") or "asset",
            heading=safe_text(item.get("heading") or "Asset") or "Asset",
            caption=safe_text(item.get("caption")) or None,
            url=local_asset_link(item.get("url") or item.get("source_url")),
            path=safe_text(item.get("path")) or None,
            section=safe_text(item.get("section")) or None,
        )
        for item in (assets or [])
    ]
    references = build_references(metadata.get("references"))
    token_estimate_breakdown = build_token_estimate_breakdown(
        abstract_text=article_metadata.abstract,
        sections=sections,
        references=references,
    )
    token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body
    return ArticleModel(
        doi=doi or safe_text(metadata.get("doi")) or None,
        source=source,
        metadata=article_metadata,
        sections=sections,
        references=references,
        assets=normalized_assets,
        quality=Quality(
            has_fulltext=bool(sections or article_metadata.abstract),
            token_estimate=token_estimate,
            warnings=list(warnings or []),
            source_trail=list(source_trail or []),
            token_estimate_breakdown=token_estimate_breakdown,
        ),
    )
