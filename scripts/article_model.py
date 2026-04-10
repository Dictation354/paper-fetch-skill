"""Shared article model and AI-friendly serialization helpers."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping

SourceKind = Literal["elsevier_xml", "springer_xml", "wiley", "html_generic", "crossref_meta"]
MARKDOWN_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
MARKDOWN_TABLE_RULE_PATTERN = re.compile(r"^\s*[-+:| ]{3,}\s*$")
MARKDOWN_LIST_MARKER_PATTERN = re.compile(r"^(\s{0,3}(?:[-*+]|\d+[.)])\s+)(.*)$")

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


def normalize_text(value: str | None) -> str:
    text = (value or "").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
    if not normalized:
        return 0
    return max(1, math.ceil(len(normalized) / 4))


def strip_markdown_images(text: str) -> str:
    stripped = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    return normalize_markdown_text(stripped)


def truncate_text_to_tokens(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""
    normalized = normalize_markdown_text(text)
    if estimate_tokens(normalized) <= token_budget:
        return normalized
    max_chars = max(32, token_budget * 4)
    truncated = normalized[:max_chars].rstrip(" ,;:\n")
    if len(truncated) < len(normalized):
        truncated += "..."
    return truncated


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
    caption: str = ""
    url: str | None = None
    path: str | None = None


@dataclass
class Quality:
    has_fulltext: bool
    token_estimate: int
    warnings: list[str] = field(default_factory=list)
    source_trail: list[str] = field(default_factory=list)


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
        include_refs: str = "top10",
        include_figures: str = "captions_only",
        include_supplementary: bool = False,
        max_tokens: int = 8000,
    ) -> str:
        warnings = list(self.quality.warnings)
        lines = ["---"]
        front_matter_fields = (
            ("title", self.metadata.title),
            ("authors", ", ".join(self.metadata.authors) if self.metadata.authors else None),
            ("journal", self.metadata.journal),
            ("doi", self.doi),
            ("published", self.metadata.published),
        )
        for key, value in front_matter_fields:
            normalized_value = normalize_text(value)
            if normalized_value:
                lines.append(f'{key}: "{normalized_value.replace(chr(34), chr(39))}"')
        lines.extend(
            [
                f'source: "{self.source}"',
                f"has_fulltext: {str(self.quality.has_fulltext).lower()}",
                f"token_estimate: {self.quality.token_estimate}",
                "---",
                "",
                f"# {self.metadata.title or 'Untitled Article'}",
                "",
            ]
        )

        remaining_budget = max_tokens - estimate_tokens("\n".join(lines))
        if remaining_budget <= 0:
            if "Output truncated to satisfy token budget." not in warnings:
                warnings.append("Output truncated to satisfy token budget.")
            return "\n".join(lines).strip() + "\n"

        abstract_text = normalize_text(self.metadata.abstract)
        if abstract_text:
            heading_lines = ["**Abstract.** "]
            remaining_budget -= estimate_tokens("".join(heading_lines))
            abstract_text = truncate_text_to_tokens(abstract_text, max(remaining_budget, 0))
            abstract_tokens = estimate_tokens(abstract_text)
            remaining_budget -= abstract_tokens
            lines.extend([f"**Abstract.** {abstract_text}", ""])

        level_shift = compute_level_shift(self.sections)

        selected_sections: list[tuple[int, Section]] = []
        truncated_any = False
        indexed_sections = list(enumerate(self.sections))
        for index, section in sorted(indexed_sections, key=lambda item: (section_priority(item[1]), item[0])):
            if section.kind in {"abstract", "references", "supplementary", "diagnostics"}:
                continue
            rendered = render_section(section, level_shift=level_shift)
            section_tokens = estimate_tokens(rendered)
            if section_tokens <= remaining_budget:
                selected_sections.append((index, section))
                remaining_budget -= section_tokens
                continue
            if remaining_budget > 64:
                truncated_text = truncate_text_to_tokens(section.text, remaining_budget - estimate_tokens(section.heading) - 4)
                if truncated_text:
                    selected_sections.append(
                        (
                            index,
                            Section(
                                heading=section.heading,
                                level=section.level,
                                kind=section.kind,
                                text=truncated_text,
                            ),
                        )
                    )
                    remaining_budget = 0
            truncated_any = True
            break

        for _, section in sorted(selected_sections, key=lambda item: item[0]):
            lines.extend([render_heading(section, level_shift=level_shift), section.text, ""])

        figure_assets = [asset for asset in self.assets if asset.kind == "figure"]
        if include_figures == "captions_only" and figure_assets:
            caption_lines = []
            for asset in figure_assets:
                caption = normalize_text(asset.caption)
                if caption:
                    caption_lines.append(f"- {asset.heading}: {caption}")
            if caption_lines:
                rendered = "## Figures\n\n" + "\n".join(caption_lines) + "\n"
                if estimate_tokens(rendered) <= remaining_budget:
                    lines.extend(["## Figures", ""])
                    lines.extend(caption_lines)
                    lines.append("")

        if include_supplementary:
            supplement_lines = []
            for asset in self.assets:
                if asset.kind != "supplementary":
                    continue
                bullet = f"- {asset.heading}"
                if asset.caption:
                    bullet += f": {asset.caption}"
                supplement_lines.append(bullet)
            if supplement_lines:
                rendered = "## Supplementary Materials\n\n" + "\n".join(supplement_lines) + "\n"
                if estimate_tokens(rendered) <= remaining_budget:
                    lines.extend(["## Supplementary Materials", ""])
                    lines.extend(supplement_lines)
                    lines.append("")

        reference_count = resolve_reference_limit(include_refs, len(self.references))
        if reference_count:
            reference_lines = []
            for reference in self.references[:reference_count]:
                reference_lines.append(f"- {reference.raw}")
            rendered = "## References\n\n" + "\n".join(reference_lines) + "\n"
            if estimate_tokens(rendered) > remaining_budget and remaining_budget > 32:
                reference_lines = []
                for reference in self.references[:reference_count]:
                    candidate = f"- {truncate_text_to_tokens(reference.raw, max(8, remaining_budget // max(1, reference_count)))}"
                    if estimate_tokens(candidate) > remaining_budget:
                        break
                    reference_lines.append(candidate)
                rendered = "## References\n\n" + "\n".join(reference_lines) + "\n"
            if reference_lines and estimate_tokens(rendered) <= remaining_budget:
                lines.extend([f"## References ({len(self.references)} total, showing {len(reference_lines)})", ""])
                lines.extend(reference_lines)
                lines.append("")

        if truncated_any and "Output truncated to satisfy token budget." not in warnings:
            warnings.append("Output truncated to satisfy token budget.")
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


def render_heading(section: Section, *, level_shift: int = 0) -> str:
    level = max(2, min(section.level - level_shift, 6))
    return f"{'#' * level} {section.heading}"


def render_section(section: Section, *, level_shift: int = 0) -> str:
    return f"{render_heading(section, level_shift=level_shift)}\n\n{section.text}".strip()


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
        return [normalize_text(str(item)) for item in value if normalize_text(str(item))]
    if isinstance(value, str):
        parts = [normalize_text(part) for part in re.split(r"\s*;\s*|\s*,\s*", value)]
        return [part for part in parts if part]
    return []


def build_metadata(metadata: Mapping[str, Any]) -> Metadata:
    return Metadata(
        title=normalize_text(str(metadata.get("title") or "")) or None,
        authors=normalize_authors(metadata.get("authors")),
        abstract=normalize_text(str(metadata.get("abstract") or "")) or None,
        journal=normalize_text(str(metadata.get("journal_title") or metadata.get("journal") or "")) or None,
        published=normalize_text(str(metadata.get("published") or "")) or None,
        keywords=[
            normalize_text(str(item))
            for item in (metadata.get("keywords") or [])
            if normalize_text(str(item))
        ],
        license_urls=[
            normalize_text(str(item))
            for item in (metadata.get("license_urls") or [])
            if normalize_text(str(item))
        ],
        landing_page_url=normalize_text(str(metadata.get("landing_page_url") or "")) or None,
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
    token_estimate = estimate_tokens(
        "\n".join(
            [
                article_metadata.title or "",
                article_metadata.abstract or "",
            ]
        )
    )
    return ArticleModel(
        doi=doi or normalize_text(str(metadata.get("doi") or "")) or None,
        source=source,
        metadata=article_metadata,
        sections=[],
        references=build_references(metadata.get("references")),
        assets=[],
        quality=Quality(
            has_fulltext=False,
            token_estimate=token_estimate,
            warnings=list(warnings or []),
            source_trail=list(source_trail or []),
        ),
    )


def build_references(raw_references: Any) -> list[Reference]:
    references: list[Reference] = []
    if not isinstance(raw_references, list):
        return references
    for item in raw_references:
        if isinstance(item, Mapping):
            raw = normalize_text(str(item.get("raw") or item.get("unstructured") or item.get("title") or ""))
            if not raw:
                continue
            references.append(
                Reference(
                    raw=raw,
                    doi=normalize_text(str(item.get("doi") or "")) or None,
                    title=normalize_text(str(item.get("title") or "")) or None,
                    year=normalize_text(str(item.get("year") or "")) or None,
                )
            )
        else:
            raw = normalize_text(str(item))
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
                heading=normalize_text(str(entry.get("heading") or "Figure")) or "Figure",
                caption=normalize_text(str(entry.get("caption") or "")),
                url=normalize_text(str(entry.get("link") or "")) or None,
            )
        )
    for entry in table_entries:
        assets.append(
            Asset(
                kind="table",
                heading=normalize_text(str(entry.get("heading") or "Table")) or "Table",
                caption=normalize_text(str(entry.get("caption") or "")),
                url=normalize_text(str(entry.get("link") or "")) or None,
            )
        )
    for entry in supplement_entries:
        assets.append(
            Asset(
                kind="supplementary",
                heading=normalize_text(str(entry.get("heading") or "Supplementary Material")) or "Supplementary Material",
                caption=normalize_text(str(entry.get("caption") or "")),
                url=normalize_text(str(entry.get("link") or "")) or None,
            )
        )

    fulltext_chunks = [article_metadata.abstract or ""]
    fulltext_chunks.extend(section.text for section in sections)
    token_estimate = estimate_tokens("\n\n".join(fulltext_chunks))

    return ArticleModel(
        doi=doi or normalize_text(str(metadata.get("doi") or "")) or None,
        source=source,
        metadata=article_metadata,
        sections=sections,
        references=list(references or build_references(metadata.get("references"))),
        assets=assets,
        quality=Quality(
            has_fulltext=bool(sections or article_metadata.abstract),
            token_estimate=token_estimate,
            warnings=list(warnings or []),
            source_trail=list(source_trail or []),
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
            kind=normalize_text(str(item.get("kind") or item.get("asset_type") or "asset")) or "asset",
            heading=normalize_text(str(item.get("heading") or "Asset")) or "Asset",
            caption=normalize_text(str(item.get("caption") or "")),
            url=normalize_text(str(item.get("url") or item.get("source_url") or "")) or None,
            path=normalize_text(str(item.get("path") or "")) or None,
        )
        for item in (assets or [])
    ]
    token_estimate = estimate_tokens(
        "\n\n".join([article_metadata.abstract or ""] + [section.text for section in sections])
    )
    return ArticleModel(
        doi=doi or normalize_text(str(metadata.get("doi") or "")) or None,
        source=source,
        metadata=article_metadata,
        sections=sections,
        references=build_references(metadata.get("references")),
        assets=normalized_assets,
        quality=Quality(
            has_fulltext=bool(sections or article_metadata.abstract),
            token_estimate=token_estimate,
            warnings=list(warnings or []),
            source_trail=list(source_trail or []),
        ),
    )
