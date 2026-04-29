"""Canonical provider-neutral HTML asset extraction and download API."""

from __future__ import annotations

from . import dom as _dom
from . import download as download
from . import figures as _figures
from . import formulas as _formulas
from . import identity as _identity
from . import supplementary as _supplementary

_PUBLIC_MODULES = (_dom, _figures, _formulas, _supplementary, _identity, download)

for _module in _PUBLIC_MODULES:
    globals().update({name: getattr(_module, name) for name in _module.__all__})

_build_cookie_seeded_opener = download._build_cookie_seeded_opener
_request_with_opener = download._request_with_opener


def download_figure_assets(*args, **kwargs):
    kwargs.setdefault("cookie_opener_builder", _build_cookie_seeded_opener)
    kwargs.setdefault("opener_requester", _request_with_opener)
    return download.download_figure_assets(*args, **kwargs)


def download_supplementary_assets(*args, **kwargs):
    kwargs.setdefault("cookie_opener_builder", _build_cookie_seeded_opener)
    kwargs.setdefault("opener_requester", _request_with_opener)
    return download.download_supplementary_assets(*args, **kwargs)


__all__ = list(
    dict.fromkeys(
        [
            *(name for module in _PUBLIC_MODULES for name in module.__all__),
            "download_figure_assets",
            "download_supplementary_assets",
        ]
    )
)
