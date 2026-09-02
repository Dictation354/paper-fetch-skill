"""Intermediate records for shared Markdown block rendering."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarkdownTable:
    label: str
    caption: str
    headers: list[str]
    rows: list[list[str]]
    footnotes: tuple[str, ...] = ()
    image_fallback_url: str | None = None
    fallback_message: str = ""


@dataclass(frozen=True)
class MarkdownFigure:
    label: str
    caption: str
    asset_url: str
    alt: str = ""


@dataclass(frozen=True)
class MarkdownFormula:
    label: str
    latex: str
    display_mode: bool
    fallback_image_url: str | None = None


@dataclass(frozen=True)
class MarkdownCaption:
    label: str
    text: str


@dataclass(frozen=True)
class MarkdownList:
    items: list[str] = field(default_factory=list)
    ordered: bool = False
