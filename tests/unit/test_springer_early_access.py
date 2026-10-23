"""Minimal access-grant and accepted-manuscript landing contracts."""

import pytest

from paper_fetch.providers import _springer_dom
from paper_fetch.providers.springer import _raise_for_springer_paywall
from paper_fetch.providers.base import ProviderFailure


@pytest.mark.parametrize("granted", [False, True])
def test_residual_preview_needs_explicit_article_access_grant(granted):
    html = '<meta name="citation_doi" content="10.1038/example">'
    html += '<p data-test="institution-access-preview">This is a preview of subscription content</p>'
    if granted:
        html += '<p data-test="access-message">You have full access to this article via <strong>Peking University</strong>.</p>'
        _raise_for_springer_paywall(
            html,
            provider="springer",
            source_url="https://www.nature.com/articles/example",
        )
    else:
        with pytest.raises(ProviderFailure):
            _raise_for_springer_paywall(
                html,
                provider="springer",
                source_url="https://www.nature.com/articles/example",
            )


@pytest.mark.parametrize("main", [False, True])
def test_early_access_attachment_description_is_not_article_body(main):
    html = '<p class="c-status-message">We’re sharing this article early</p><div class="c-article-body">'
    html += '<section data-title="Abstract"><p>Abstract</p></section>'
    html += '<section data-title="Supplementary information"><p>Supplementary Notes and Figs.</p></section>'
    if main:
        html += '<section data-title="Main"><p>Actual main article.</p></section>'
    html += "</div>"
    assert _springer_dom.early_access_without_body(html) is not main
