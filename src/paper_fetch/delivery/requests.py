"""Protocol-independent fetch and persistent cache request semantics."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..models import RenderOptions
from ..workflow.types import FetchStrategy


class FetchStrategyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None
    asset_profile: Literal["none", "body", "all"] | None = "none"
    require_local_body_assets: bool = False
    require_full_size_body_assets: bool = False

    @model_validator(mode="after")
    def imply_local_assets(self):
        if self.require_full_size_body_assets:
            self.require_local_body_assets = True
        return self

    def cache_request_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_service_strategy(self) -> FetchStrategy:
        return FetchStrategy(**self.model_dump())


class FetchPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    target: Literal["paper", "supplementary"] = "paper"
    modes: list[str] = Field(default_factory=lambda: ["markdown"])
    strategy: FetchStrategyInput = Field(default_factory=FetchStrategyInput)
    include_refs: Literal["none", "top10", "all"] | None = "all"
    max_tokens: int | Literal["full_text"] = "full_text"
    prefer_cache: bool = False
    save_markdown: bool = False

    def requested_modes(self) -> set[str]:
        modes = set(self.modes)
        if self.save_markdown:
            modes.update({"markdown", "article"})
        if self.target == "supplementary":
            modes.discard("article")
        return modes

    def to_render_options(self) -> RenderOptions:
        return RenderOptions(
            include_refs=self.include_refs,
            max_tokens=self.max_tokens,
            asset_profile=self.strategy.asset_profile,
        )
