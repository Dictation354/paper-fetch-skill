from __future__ import annotations

from bs4 import BeautifulSoup

from paper_fetch.extraction.html.provider_rules import (
    provider_html_rules,
)


def test_provider_markdown_hooks_preserve_key_behaviour() -> None:
    pnas_hooks = provider_html_rules("pnas").markdown_hooks
    science_hooks = provider_html_rules("science").markdown_hooks
    ams_hooks = provider_html_rules("ams").markdown_hooks

    assert pnas_hooks.suppress_missing_abstract is not None
    assert pnas_hooks.suppress_missing_abstract(
        "# Title\n\n## Significance\n\nText\n\n## Abstract\n\nText"
    )
    assert not pnas_hooks.suppress_missing_abstract("# Title\n\n## Abstract\n\nText")

    assert science_hooks.normalize_markdown is not None
    assert science_hooks.normalize_markdown("*A1*, *B2*") == "*A1, B2*"
    assert science_hooks.keep_unknown_abstract_block is not None
    assert science_hooks.keep_unknown_abstract_block("A substantial abstract block.")

    assert ams_hooks.classify_heading is not None
    assert ams_hooks.classify_heading("Acknowledgments", None) == "body_heading"
    assert ams_hooks.classify_heading("References", None) is None

    assert ams_hooks.normalize_markdown is not None
    normalized = ams_hooks.normalize_markdown(
        "\n\n".join(
            [
                "# Title",
                "## Acknowledgments",
                "Thanks.",
                "## APPENDIX A",
                "Appendix text.",
                "## Data availability statement",
                "Data are archived.",
            ]
        )
    )
    assert normalized.index("## Acknowledgments") < normalized.index(
        "## Data availability statement"
    )
    assert normalized.index("## Data availability statement") < normalized.index(
        "## APPENDIX A"
    )


def test_provider_dom_hooks_preserve_key_behaviour() -> None:
    pnas_hook = provider_html_rules("pnas").dom_hooks.before_block_normalization
    assert pnas_hook is not None
    body_text = "Body text. " * 80
    pnas_soup = BeautifulSoup(
        f"<article><section><p>Sign up for PNAS alerts</p></section><p>{body_text}</p></article>",
        "html.parser",
    )
    pnas_hook(pnas_soup.article)
    assert "Sign up for PNAS alerts" not in pnas_soup.get_text(" ", strip=True)
    assert "Body text." in pnas_soup.get_text(" ", strip=True)

    ams_hook = provider_html_rules("ams").dom_hooks.before_block_normalization
    assert ams_hook is not None
    ams_soup = BeautifulSoup(
        "<article><button class='download-figure'>PowerPoint</button><p>Body text.</p></article>",
        "html.parser",
    )
    ams_hook(ams_soup.article)
    assert "PowerPoint" not in ams_soup.get_text(" ", strip=True)
    assert "Body text." in ams_soup.get_text(" ", strip=True)
