"""Internal compatibility aggregator for split Science/PNAS helpers."""

from __future__ import annotations

from . import asset_scopes as _asset_scopes
from . import markdown as _markdown
from . import normalization as _normalization
from . import postprocess as _postprocess
from . import profile as _profile

_PUBLIC_MODULES = (_profile, _normalization, _asset_scopes, _postprocess, _markdown)

for _module in _PUBLIC_MODULES:
    globals().update({name: getattr(_module, name) for name in _module.__all__})

__all__ = list(dict.fromkeys(name for module in _PUBLIC_MODULES for name in module.__all__))
