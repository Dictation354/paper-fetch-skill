"""Wiley provider client backed by the local browser workflow."""

from __future__ import annotations

from ._science_pnas import BrowserWorkflowClient


class WileyClient(BrowserWorkflowClient):
    name = "wiley"
    article_source_name = "wiley_browser"
