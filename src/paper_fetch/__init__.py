"""Public package surface for paper-fetch, loaded on first access."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import (
        AcquisitionProvenance,
        ArticleModel,
        FetchEnvelope,
        Metadata,
        Quality,
        RenderOptions,
        Section,
        TokenEstimateBreakdown,
    )
    from .service import FetchStrategy, PaperFetchFailure, fetch_paper, resolve_paper
    from .version import __version__

__all__ = [
    "AcquisitionProvenance",
    "ArticleModel",
    "FetchEnvelope",
    "FetchStrategy",
    "Metadata",
    "PaperFetchFailure",
    "Quality",
    "RenderOptions",
    "Section",
    "TokenEstimateBreakdown",
    "__version__",
    "fetch_paper",
    "resolve_paper",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = (
        ".version"
        if name == "__version__"
        else (
            ".service"
            if name
            in {"FetchStrategy", "PaperFetchFailure", "fetch_paper", "resolve_paper"}
            else ".models"
        )
    )
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
