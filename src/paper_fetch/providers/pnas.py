"""PNAS provider client."""

from __future__ import annotations

from ._science_pnas import SciencePnasClient


class PnasClient(SciencePnasClient):
    name = "pnas"
