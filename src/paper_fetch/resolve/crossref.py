"""Resolve-layer adapter around the Crossref metadata client."""

from __future__ import annotations

from ..providers.crossref import CrossrefClient as CrossrefLookupClient

__all__ = ["CrossrefLookupClient"]
