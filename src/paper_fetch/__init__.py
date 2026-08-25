"""Public package surface for paper-fetch."""

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
