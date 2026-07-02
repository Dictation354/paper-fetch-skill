from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from paper_fetch.extraction.html.availability_policy import (
    AvailabilityContainerRules,
    AvailabilityPolicy,
)
from paper_fetch.extraction.html.cleanup_policy import (
    AVAILABILITY_DROP_TAGS,
    BROWSER_WORKFLOW_DROP_TAGS,
    BROWSER_WORKFLOW_SHORT_TEXT_PATTERNS,
)
from paper_fetch.extraction.html.provider_rules import (
    ProviderHtmlRules,
    _availability_container_rules_from_rules,
    availability_rules_for_provider,
    merged_site_rule,
)


def test_availability_container_rules_round_trip_from_site_rule_overrides() -> None:
    rules = ProviderHtmlRules(
        name="custom",
        availability=AvailabilityPolicy(
            name="custom",
            site_rule_overrides={
                "candidate_selectors": ["article", ".custom-article"],
                "remove_selectors": [".custom-remove"],
                "drop_keywords": {"custom-chrome"},
                "drop_text": {"Custom action"},
            },
        ),
    )

    merged = merged_site_rule(rules)
    container_rules = _availability_container_rules_from_rules(rules)

    assert isinstance(container_rules, AvailabilityContainerRules)
    assert container_rules.candidate_selectors == tuple(merged["candidate_selectors"])
    assert container_rules.remove_selectors == tuple(merged["remove_selectors"])
    assert set(container_rules.drop_keywords) == merged["drop_keywords"]
    assert set(container_rules.drop_texts) == merged["drop_text"]
    assert container_rules.drop_tags == AVAILABILITY_DROP_TAGS
    assert container_rules.browser_workflow_drop_tags == BROWSER_WORKFLOW_DROP_TAGS
    assert (
        container_rules.browser_workflow_short_text_patterns
        == BROWSER_WORKFLOW_SHORT_TEXT_PATTERNS
    )


def test_availability_container_rules_are_frozen_and_cleanup_policy_has_no_copy() -> (
    None
):
    container_rules = availability_rules_for_provider("ieee").container_rules

    assert "document-actions" in container_rules.drop_keywords
    assert ".document-actions" in container_rules.remove_selectors
    with pytest.raises(FrozenInstanceError):
        container_rules.drop_keywords = ()
