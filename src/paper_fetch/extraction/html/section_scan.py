"""Shared state machine for article section scanning."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

SectionStateName = Literal[
    "body",
    "abstract",
    "back_matter",
    "front_matter",
    "data_availability",
    "auxiliary",
]


@dataclass
class SectionScanState:
    in_abstract: bool = False
    in_back_matter: bool = False
    in_front_matter: bool = False
    in_data_availability: bool = False
    in_auxiliary: bool = False
    abstract_seen: bool = False
    body_heading_after_abstract: bool = False
    body_run_paragraph_count: int = 0
    body_run_char_count: int = 0
    body_paragraph_count: int = 0
    enabled_states: frozenset[SectionStateName] = field(
        default_factory=lambda: frozenset(
            {
                "body",
                "abstract",
                "back_matter",
                "front_matter",
                "data_availability",
            }
        )
    )
    _current_body_run_paragraph_count: int = field(default=0, init=False, repr=False)
    _current_body_run_char_count: int = field(default=0, init=False, repr=False)

    def in_skipped_section(self) -> bool:
        return any(
            [
                self.in_abstract,
                self.in_back_matter,
                self.in_front_matter,
                self.in_data_availability,
                self.in_auxiliary,
            ]
        )

    def transition(self, category: str, *, is_heading: bool) -> None:
        if category == "abstract":
            self.abstract_seen = True
            self._enter("abstract")
            return
        if category == "references_or_back_matter":
            self._enter("back_matter")
            return
        if category in {"data_availability", "code_availability"}:
            self._enter("data_availability")
            return
        if category == "front_matter":
            self._clear_sections()
            if is_heading and "front_matter" in self.enabled_states:
                self.in_front_matter = True
            return
        if category in {"ancillary", "auxiliary"}:
            self.in_front_matter = False
            self.in_data_availability = False
            if "auxiliary" in self.enabled_states:
                self._enter("auxiliary")
            return
        if category == "body_heading":
            self._clear_sections()
            if self.abstract_seen:
                self.body_heading_after_abstract = True

    def reset_body_run(self) -> None:
        self._current_body_run_paragraph_count = 0
        self._current_body_run_char_count = 0

    def record_body_paragraph(self, *, text_len: int) -> None:
        self.body_paragraph_count += 1
        self._current_body_run_paragraph_count += 1
        self._current_body_run_char_count += text_len
        self.body_run_paragraph_count = max(
            self.body_run_paragraph_count,
            self._current_body_run_paragraph_count,
        )
        self.body_run_char_count = max(
            self.body_run_char_count,
            self._current_body_run_char_count,
        )

    def _enter(self, state_name: SectionStateName) -> None:
        self._clear_sections()
        if state_name not in self.enabled_states:
            return
        if state_name == "abstract":
            self.in_abstract = True
        elif state_name == "back_matter":
            self.in_back_matter = True
        elif state_name == "front_matter":
            self.in_front_matter = True
        elif state_name == "data_availability":
            self.in_data_availability = True
        elif state_name == "auxiliary":
            self.in_auxiliary = True

    def _clear_sections(self, states: Iterable[SectionStateName] | None = None) -> None:
        target_states = set(
            states
            or (
                "abstract",
                "back_matter",
                "front_matter",
                "data_availability",
                "auxiliary",
            )
        )
        if "abstract" in target_states:
            self.in_abstract = False
        if "back_matter" in target_states:
            self.in_back_matter = False
        if "front_matter" in target_states:
            self.in_front_matter = False
        if "data_availability" in target_states:
            self.in_data_availability = False
        if "auxiliary" in target_states:
            self.in_auxiliary = False
