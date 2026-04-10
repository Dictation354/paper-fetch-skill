"""Public package surface for paper-fetch."""

from .models import ArticleModel, FetchEnvelope, Metadata, Quality, RenderOptions, Section
from .service import FetchStrategy, PaperFetchFailure, fetch_paper, resolve_paper

__all__ = [
    "ArticleModel",
    "FetchEnvelope",
    "FetchStrategy",
    "Metadata",
    "PaperFetchFailure",
    "Quality",
    "RenderOptions",
    "Section",
    "fetch_paper",
    "resolve_paper",
]
