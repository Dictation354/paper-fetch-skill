from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

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


def test_provider_specific_hooks_have_neutral_defaults() -> None:
    from paper_fetch.extraction.html.provider_rules import DomHooks, MarkdownHooks

    assert DomHooks().before_inline_formula_normalization is None
    assert DomHooks().render_table is None
    assert MarkdownHooks().keep_leading_auxiliary_block is None
    for provider in ("pnas", "ams", "acs", "aip", "wiley"):
        rules = provider_html_rules(provider)
        assert rules.dom_hooks.before_inline_formula_normalization is None
        assert rules.dom_hooks.render_table is None
        assert rules.markdown_hooks.keep_leading_auxiliary_block is None
    assert provider_html_rules("science").dom_hooks.render_table is not None
    assert (
        provider_html_rules("iop").dom_hooks.before_inline_formula_normalization
        is not None
    )


def test_inline_and_table_hooks_run_at_existing_normalization_stages(
    monkeypatch,
) -> None:
    from dataclasses import replace
    from paper_fetch.providers.atypon_browser_workflow import normalization

    profile = normalization._publisher_profile("pnas")
    events = []
    soup = BeautifulSoup(
        '<article><div class="display-eqn"><script type="math/tex">y=1</script></div>'
        '<table><tr><th>Value</th></tr><tr><td><math alttext="x"><mi>x</mi></math></td></tr></table></article>',
        "html.parser",
    )

    def before_inline(container):
        assert container.select_one(".display-eqn") is None
        assert "$$" in container.get_text()
        assert container.find("math") is not None
        events.append("before_inline")

    def render_table(node, *, label, caption):
        assert node.find("math") is None
        assert "$x$" in node.get_text()
        assert label == "Table"
        assert caption == ""
        events.append("table")
        return "Custom table"

    def after(container):
        assert container.find("table") is None
        events.append("after")

    profile = replace(
        profile,
        dom_hooks=replace(
            profile.dom_hooks,
            before_inline_formula_normalization=before_inline,
            render_table=render_table,
            after_block_normalization=after,
        ),
    )
    monkeypatch.setattr(normalization, "_publisher_profile", lambda _: profile)
    entries = normalization._normalize_special_blocks(soup.article, "pnas")
    assert events == ["before_inline", "table", "after"]
    assert entries[0]["markdown"] == "Custom table"


def test_table_hook_none_uses_shared_rendering(monkeypatch) -> None:
    from dataclasses import replace
    from paper_fetch.providers.atypon_browser_workflow import normalization

    profile = normalization._publisher_profile("pnas")
    calls = []

    def decline(node, *, label, caption):
        calls.append(label)
        return None

    def source():
        return BeautifulSoup(
            "<article><table><tr><th>Parameter</th></tr><tr><td>42</td></tr></table></article>",
            "html.parser",
        ).article

    expected = normalization._normalize_table_blocks(source(), "pnas")
    profile = replace(
        profile, dom_hooks=replace(profile.dom_hooks, render_table=decline)
    )
    monkeypatch.setattr(normalization, "_publisher_profile", lambda _: profile)
    assert normalization._normalize_table_blocks(source(), "pnas") == expected
    assert calls == ["Table"]


def test_iop_inline_hook_keeps_tex_precedence_and_formula_order() -> None:
    from paper_fetch.providers.atypon_browser_workflow.normalization import (
        _normalize_special_blocks,
    )

    soup = BeautifulSoup(
        '<article><p>First <span class="inline-eqn"><script type="math/tex">a+b</script>'
        '<math alttext="wrong"><mi>z</mi></math><img src="formula.gif"/></span> then '
        '<span class="inline-eqn"><script type="math/tex">c+d</script></span>.</p>'
        '<div class="display-eqn"><script type="math/tex">e=f</script></div></article>',
        "html.parser",
    )
    _normalize_special_blocks(soup.article, "iop")
    text = soup.get_text()
    assert "$a+b$" in text and "$c+d$" in text
    assert text.index("$a+b$") < text.index("$c+d$") < text.index("e=f")
    assert "wrong" not in text
    assert soup.find(["math", "script", "img"]) is None


def test_science_leading_figure_hook_preserves_caption_and_label_matching() -> None:
    from paper_fetch.providers.atypon_browser_workflow.postprocess import (
        _postprocess_browser_workflow_markdown,
    )

    block = "**Figure 1.** A manuscript photograph."
    assets = [{"kind": "figure", "heading": "Figure 1", "section": "body"}]
    hook = provider_html_rules("science").markdown_hooks.keep_leading_auxiliary_block
    assert hook is not None
    assert hook(block, publisher="science", figure_assets=assets)
    assert not hook(block, publisher="Science", figure_assets=assets)
    assert not hook("**Fig. 1.** Caption", publisher="science", figure_assets=assets)
    assert not hook(
        block,
        publisher="science",
        figure_assets=[dict(assets[0], section="supplementary")],
    )
    assert not hook(block, publisher="science", figure_assets=[])
    text = (
        block + "\n\n" + "This paragraph explains the scientific result in detail. " * 6
    )
    for publisher, figures, kept in (
        ("science", assets, True),
        ("science", [], False),
        ("pnas", assets, False),
    ):
        rendered = _postprocess_browser_workflow_markdown(
            text, title=None, publisher=publisher, figure_assets=figures
        )
        assert (block in rendered) == kept


def test_post_content_policy_injects_provider_tokens_once() -> None:
    from paper_fetch.providers.atypon_browser_workflow.profile import (
        POST_CONTENT_BREAK_TOKENS,
        _cleanup_policy_for_publisher,
        _post_content_cleanup_policy,
    )

    for publisher in ("science", "ams", "acs", "iop", "aip"):
        policy = _post_content_cleanup_policy(publisher)
        assert policy.post_content_cutoff_tokens == (
            *_cleanup_policy_for_publisher(publisher).post_content_cutoff_tokens,
            *POST_CONTENT_BREAK_TOKENS,
        )
        for token in provider_html_rules(publisher).cleanup.post_content_break_tokens:
            assert policy.post_content_cutoff_tokens.count(token) == 1


def test_iop_formula_registration_only_extends_shared_defaults() -> None:
    from paper_fetch.extraction.html.formula_rules import (
        GENERIC_FORMULA_CONTAINER_TOKENS,
        GENERIC_DISPLAY_FORMULA_SELECTORS,
        display_formula_nodes,
        display_formula_selectors_for_profile,
        formula_container_tokens_for_profile,
    )

    assert formula_container_tokens_for_profile("iop") == (
        *GENERIC_FORMULA_CONTAINER_TOKENS,
        "tex",
    )
    assert (
        display_formula_selectors_for_profile("iop")
        == GENERIC_DISPLAY_FORMULA_SELECTORS
    )
    soup = BeautifulSoup(
        '<article><div class="display-eqn" id="a"></div>'
        '<div class="disp-formula" id="b"></div><div class="display-eqn" id="c"></div></article>',
        "html.parser",
    )
    assert [n["id"] for n in display_formula_nodes(soup, noise_profile="iop")] == [
        "a",
        "c",
        "b",
    ]


@pytest.mark.parametrize("provider", ["science", "pnas"])
def test_science_and_pnas_asset_scopes_preserve_mutation_and_render_order(
    provider,
) -> None:
    from paper_fetch.providers import _pnas_html, _science_html

    callback = {"science": _science_html, "pnas": _pnas_html}[
        provider
    ].extract_asset_html_scopes
    body = BeautifulSoup(
        "<article><p>Body</p><section>Body supplement</section></article>",
        "html.parser",
    ).article
    supplementary = BeautifulSoup(
        "<article><section>First supplement</section><section> </section><section>Last supplement</section></article>",
        "html.parser",
    ).article
    events = []

    def sections(container):
        events.append("body" if container is body else "supplementary")
        if container is supplementary:
            assert body.find("section") is None
        return container.find_all("section")

    def fragment(container, *, publisher):
        assert publisher == provider
        assert events == ["body", "supplementary"]
        assert container is body
        events.append("render")
        return str(container)

    result = callback(
        body,
        supplementary,
        publisher=provider,
        content_fragment_html=fragment,
        atypon_browser_workflow_supplementary_sections=sections,
    )
    assert result == (
        "<article><p>Body</p></article>",
        "<section>First supplement</section>\n<section>Last supplement</section>",
    )
    assert events == ["body", "supplementary", "render"]
