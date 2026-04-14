"""Science provider client."""

from __future__ import annotations

from ._science_pnas import SciencePnasClient


class ScienceClient(SciencePnasClient):
    name = "science"
