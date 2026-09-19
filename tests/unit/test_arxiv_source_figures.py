"""Minimum source-environment contracts, independent of image byte fidelity."""

import pytest
from paper_fetch.providers._arxiv_source_archive import (
    _extract_arxiv_source_figure_references,
)


@pytest.mark.parametrize(
    "environment,command",
    [
        ("figure", "caption"),
        ("figure*", "caption"),
        ("extdatafigure", "extdatacaption"),
    ],
)
def test_source_figure_environment_keeps_its_caption_and_label(environment, command):
    tex = (
        rf"\begin{{{environment}}}\includegraphics{{image.png}}"
        rf"\{command}{{Source caption}}\label{{fig:test}}\end{{{environment}}}"
    )
    figures = _extract_arxiv_source_figure_references(
        {"main.tex": tex.encode(), "image.png": b"injected bytes"}
    )
    assert figures == [
        {
            "source_path": "image.png",
            "body": b"injected bytes",
            "caption": "Source caption",
            "label": "fig:test",
        }
    ]


def test_unrelated_or_mismatched_environments_are_not_figures():
    tex = rb"\begin{table}\includegraphics{image.png}\end{table} \begin{extdatafigure}\includegraphics{image.png}\end{figure}"
    assert (
        _extract_arxiv_source_figure_references(
            {"main.tex": tex, "image.png": b"injected bytes"}
        )
        == []
    )
