"""Shared parser choice for arXiv/ar5iv HTML."""

from __future__ import annotations

from ..extraction.html.parsing import choose_parser

ARXIV_HTML_PARSER = choose_parser()
