from __future__ import annotations

from paper_fetch.extraction.html.renderer import (
    render_html_markdown,
    render_provider_html_fragment,
)


def test_render_html_markdown_applies_shared_cleaning_and_postprocess() -> None:
    markdown = render_html_markdown(
        "<article><h1>Example</h1><p>Body text.</p></article>",
        "https://example.test/article",
        trafilatura_backend=None,
        postprocessors=(
            lambda value: f"{value}\n\n## Data availability\n\nAvailable on request.",
        ),
    )

    assert "# Example" in markdown
    assert "Body text." in markdown
    assert "## Data availability" in markdown


def test_render_provider_html_fragment_returns_markdown_and_sidecars() -> None:
    rendered = render_provider_html_fragment(
        """
        <section class="abstract"><h2>Abstract</h2><p>Short summary.</p></section>
        <section><h2>Results</h2><p>Body text with enough structure.</p></section>
        """,
        "https://example.test/article",
        title="Example Article",
        trafilatura_backend=None,
    )

    payload = rendered.to_payload()

    assert "## Results" in rendered.markdown_text
    assert payload["markdown_text"] == rendered.markdown_text
    assert rendered.container_tag == "article"
    assert rendered.container_text_length and rendered.container_text_length > 0
    assert any(item["heading"] == "Results" for item in rendered.section_hints)
    assert any(item["heading"] == "Abstract" for item in rendered.abstract_sections)
