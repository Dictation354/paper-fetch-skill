from __future__ import annotations


import pytest

from paper_fetch.extraction.html import provider_rules as provider_rules_module
from paper_fetch.extraction.html.provider_rules import (
    GENERIC_HTML_RULES,
    ProviderHtmlRules,
    _reset_provider_html_rules_cache,
    cleanup_policy_for_profile,
    provider_html_rules,
    require_provider_html_rules,
)


@pytest.fixture(autouse=True)
def _reset_provider_rule_caches() -> None:
    _reset_provider_html_rules_cache()
    yield
    _reset_provider_html_rules_cache()


def test_provider_html_rules_generic_returns_generic_rules() -> None:
    assert provider_html_rules("generic").name == GENERIC_HTML_RULES.name


@pytest.mark.parametrize("value", [None, "generic"])
def test_cleanup_policy_for_generic_profile_stays_provider_neutral(
    value: str | None,
) -> None:
    policy = cleanup_policy_for_profile(value)

    assert policy.name == "generic"
    assert "science" not in policy.front_matter_exact_texts
    assert "ams" not in policy.front_matter_publication_keywords
    assert "article type" not in policy.post_content_cutoff_tokens
    assert "citation-tools" not in policy.extraction_drop_keywords


def test_unknown_provider_html_rules_warns_and_falls_back_to_generic() -> None:
    with pytest.warns(RuntimeWarning, match="Unknown provider HTML rules provider"):
        assert provider_html_rules("missing-provider").name == GENERIC_HTML_RULES.name


def test_require_provider_html_rules_resolves_aliases_and_rejects_unknown() -> None:
    assert require_provider_html_rules("aaas").name == "science"

    with pytest.raises(KeyError, match="Unknown provider HTML rules provider"):
        require_provider_html_rules("missing-provider")


def test_provider_html_rules_rejects_alias_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = ProviderHtmlRules(name="first", aliases=("shared",))
    second = ProviderHtmlRules(name="second", aliases=("shared",))

    monkeypatch.setattr(
        provider_rules_module,
        "_build_provider_html_rules",
        lambda: {"first": first, "second": second},
    )
    _reset_provider_html_rules_cache()

    with pytest.raises(ValueError, match="provider lookup key conflict.*shared"):
        provider_html_rules("first")
