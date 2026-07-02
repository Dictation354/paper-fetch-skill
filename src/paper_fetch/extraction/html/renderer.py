"""Shared HTML-to-Markdown rendering pipeline helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

from bs4 import BeautifulSoup, Tag

from .language import collect_html_abstract_blocks
from .parsing import choose_parser
from .semantics import collect_html_section_hints
from ._runtime import (
    clean_markdown,
    extract_article_markdown,
    extract_article_markdown_from_cleaned_html,
)

HtmlMarkdownRenderFn = Callable[[str, str], str]
MarkdownPostprocessor = Callable[[str], str]

_DEFAULT_TRAFILATURA = object()


@dataclass(frozen=True)
class HtmlMarkdownRenderer:
    """Render raw or provider-cleaned HTML through a shared cleanup pipeline."""

    noise_profile: str | None = None
    trafilatura_backend: Any = _DEFAULT_TRAFILATURA
    cleaned_html: bool = False
    renderer: HtmlMarkdownRenderFn | None = None
    postprocessors: tuple[MarkdownPostprocessor, ...] = field(default_factory=tuple)

    def render(self, html_text: str, source_url: str) -> str:
        raw_markdown = self._render_raw(str(html_text or ""), source_url)
        return clean_rendered_markdown(
            raw_markdown,
            noise_profile=self.noise_profile,
            postprocessors=self.postprocessors,
        )

    def _render_raw(self, html_text: str, source_url: str) -> str:
        if self.renderer is not None:
            return str(self.renderer(html_text, source_url) or "")
        kwargs = {}
        if self.trafilatura_backend is not _DEFAULT_TRAFILATURA:
            kwargs["trafilatura_backend"] = self.trafilatura_backend
        if self.noise_profile is not None:
            kwargs["noise_profile"] = self.noise_profile
        if self.cleaned_html:
            return extract_article_markdown_from_cleaned_html(
                html_text, source_url, **kwargs
            )
        return extract_article_markdown(html_text, source_url, **kwargs)


def clean_rendered_markdown(
    markdown_text: str,
    *,
    noise_profile: str | None = None,
    postprocessors: tuple[MarkdownPostprocessor, ...] = (),
) -> str:
    cleaned = clean_markdown(str(markdown_text or ""), noise_profile=noise_profile)
    for postprocess in postprocessors:
        cleaned = str(postprocess(cleaned) or "")
    return cleaned


def render_html_markdown(
    html_text: str,
    source_url: str,
    *,
    noise_profile: str | None = None,
    trafilatura_backend: Any = _DEFAULT_TRAFILATURA,
    cleaned_html: bool = False,
    renderer: HtmlMarkdownRenderFn | None = None,
    postprocessors: tuple[MarkdownPostprocessor, ...] = (),
) -> str:
    return HtmlMarkdownRenderer(
        noise_profile=noise_profile,
        trafilatura_backend=trafilatura_backend,
        cleaned_html=cleaned_html,
        renderer=renderer,
        postprocessors=postprocessors,
    ).render(html_text, source_url)


@dataclass(frozen=True)
class RenderedHtmlFragment:
    markdown_text: str
    section_hints: list[dict[str, Any]]
    abstract_sections: list[dict[str, Any]]
    container_tag: str | None = None
    container_text_length: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "markdown_text": self.markdown_text,
            "section_hints": [dict(item) for item in self.section_hints],
            "abstract_sections": [dict(item) for item in self.abstract_sections],
            "container_tag": self.container_tag,
            "container_text_length": self.container_text_length,
        }


def _fragment_root(html_fragment: str):
    soup = BeautifulSoup(
        f"<article data-paper-fetch-renderer-root='1'>{html_fragment}</article>",
        choose_parser(),
    )
    root = soup.select_one("[data-paper-fetch-renderer-root='1']")
    return root if isinstance(root, Tag) else None


def render_provider_html_fragment(
    html_fragment: str,
    source_url: str,
    *,
    title: str | None = None,
    noise_profile: str | None = None,
    trafilatura_backend: Any = _DEFAULT_TRAFILATURA,
    renderer: HtmlMarkdownRenderFn | None = None,
    postprocessors: tuple[MarkdownPostprocessor, ...] = (),
    language_hint_resolver: Callable[[Any], str | None] | None = None,
) -> RenderedHtmlFragment:
    root = _fragment_root(str(html_fragment or ""))
    section_hints = (
        collect_html_section_hints(
            root, title=title, language_hint_resolver=language_hint_resolver
        )
        if root is not None
        else []
    )
    abstract_sections = collect_html_abstract_blocks(root) if root is not None else []
    return RenderedHtmlFragment(
        markdown_text=render_html_markdown(
            html_fragment,
            source_url,
            noise_profile=noise_profile,
            trafilatura_backend=trafilatura_backend,
            cleaned_html=True,
            renderer=renderer,
            postprocessors=postprocessors,
        ),
        section_hints=[dict(item) for item in section_hints],
        abstract_sections=[dict(item) for item in abstract_sections],
        container_tag=str(getattr(root, "name", "") or "") or None,
        container_text_length=len(" ".join(root.stripped_strings))
        if root is not None
        else None,
    )


__all__ = [
    "HtmlMarkdownRenderFn",
    "HtmlMarkdownRenderer",
    "MarkdownPostprocessor",
    "RenderedHtmlFragment",
    "clean_rendered_markdown",
    "render_html_markdown",
    "render_provider_html_fragment",
]
