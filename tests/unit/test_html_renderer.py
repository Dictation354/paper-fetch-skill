from __future__ import annotations

import pytest

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


@pytest.mark.parametrize(
    "sentence,expected",
    [
        (
            "The measured response follows $V_i = B V^h$, with $k_{on}$ and $x_i^2$ as model parameters.",
            ("$V_i = B V^h$", "$k_{on}$", "$x_i^2$"),
        ),
        (
            'The measured response is listed in <a href="#table_1">Table 1</a>, with [Table 2] as an additional comparison.',
            ("Table 1", "[Table 2]"),
        ),
    ],
    ids=["inline-latex", "table-reference"],
)
def test_render_html_markdown_preserves_formula_and_table_tokens(
    sentence, expected
) -> None:
    trafilatura = pytest.importorskip("trafilatura")
    html = (
        "<article><h1>Measured response</h1><p>"
        + sentence
        + " Each parameter is estimated from independent measurements to describe "
        "the observed biological process and its quantitative response.</p></article>"
    )
    markdown = render_html_markdown(
        html,
        "https://example.test/article",
        trafilatura_backend=trafilatura,
    )
    for token in expected:
        assert token in markdown
