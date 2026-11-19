from __future__ import annotations

from paper_fetch.providers import _html_authors as html_authors
from paper_fetch.providers._html_authors import (
    AuthorExtractionPipeline,
    AuthorStep,
)


def test_author_extraction_pipeline_accepts_callables_and_named_steps() -> None:
    calls: list[str] = []

    def empty_step(html_text: str) -> list[str]:
        calls.append("empty")
        assert html_text == "<html></html>"
        return []

    def author_step(html_text: str) -> list[str]:
        calls.append("authors")
        assert html_text == "<html></html>"
        return ["Ada Lovelace", "Ada Lovelace", "Grace Hopper"]

    def late_step(_: str) -> list[str]:
        calls.append("late")
        return ["Ignored Author"]

    pipeline = AuthorExtractionPipeline(
        empty_step,
        AuthorStep("author-step", author_step),
        AuthorStep("late-step", late_step),
    )

    assert [step.name for step in pipeline.steps] == [
        "empty_step",
        "author-step",
        "late-step",
    ]
    assert pipeline.extractors[0] is empty_step
    assert pipeline("<html></html>") == ["Ada Lovelace", "Grace Hopper"]
    assert calls == ["empty", "authors"]


def test_author_extraction_pipeline_returns_empty_when_all_steps_miss() -> None:
    pipeline = AuthorExtractionPipeline(
        AuthorStep("empty", lambda _: []),
        AuthorStep("also-empty", lambda _: []),
    )

    assert pipeline("<html></html>") == []


def test_author_extraction_pipeline_reuses_soup_between_html_steps(monkeypatch) -> None:
    html_text = """
<html>
  <head><meta name="citation_author" content=""></head>
  <body><span class="author-name">Ada Lovelace</span></body>
</html>
"""
    real_beautiful_soup = html_authors.BeautifulSoup
    parse_count = 0

    def counting_beautiful_soup(*args, **kwargs):
        nonlocal parse_count
        parse_count += 1
        return real_beautiful_soup(*args, **kwargs)

    monkeypatch.setattr(html_authors, "BeautifulSoup", counting_beautiful_soup)

    pipeline = AuthorExtractionPipeline(
        AuthorStep(
            "meta",
            lambda html: html_authors.extract_meta_authors(
                html,
                keys={"citation_author"},
            ),
        ),
        AuthorStep(
            "selector",
            lambda html: html_authors.extract_selector_authors(
                html,
                selectors=(".author-name",),
                ignored_text=set(),
                node_text=lambda node: node.get_text(" ", strip=True),
            ),
        ),
    )

    assert pipeline(html_text) == ["Ada Lovelace"]
    assert parse_count == 1
