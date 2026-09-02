"""Provider availability rule ownership for HTML full-text checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

if TYPE_CHECKING:
    from ...quality.html_signals import (
        AvailabilityOverrides,
        DatalayerSignalSet,
        TextMarkerSignalSet,
    )


@dataclass(frozen=True)
class AvailabilityContainerRules:
    remove_selectors: tuple[str, ...] = ()
    drop_keywords: tuple[str, ...] = ()
    drop_texts: tuple[str, ...] = ()
    drop_tags: tuple[str, ...] = ()
    browser_workflow_drop_tags: tuple[str, ...] = ()
    browser_workflow_short_text_patterns: tuple[str, ...] = ()

    def drop_tags_for(self, *, browser_workflow: bool = False) -> tuple[str, ...]:
        return self.browser_workflow_drop_tags if browser_workflow else self.drop_tags

    def short_text_patterns_for(
        self, *, browser_workflow: bool = False
    ) -> tuple[str, ...]:
        return self.browser_workflow_short_text_patterns if browser_workflow else ()


@dataclass(frozen=True)
class AvailabilityPolicy:
    """Provider-owned availability rules kept separate from cleanup policy."""

    name: str = ""
    container_rules: AvailabilityContainerRules = field(
        default_factory=AvailabilityContainerRules
    )
    site_rule_overrides: Mapping[str, Any] = field(default_factory=dict)
    datalayer_signal_set: DatalayerSignalSet | None = None
    text_marker_signal_set: TextMarkerSignalSet | None = None
    overrides: AvailabilityOverrides | None = None
    access_block_text_tokens: tuple[str, ...] = ()
