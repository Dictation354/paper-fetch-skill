"""Internal compatibility aggregator for split HTML asset helpers."""

from __future__ import annotations

from . import dom as _dom
from . import download as _download
from . import figures as _figures
from . import formulas as _formulas
from . import identity as _identity
from . import supplementary as _supplementary

_PUBLIC_MODULES = (_dom, _figures, _formulas, _supplementary, _identity, _download)

for _module in _PUBLIC_MODULES:
    globals().update({name: getattr(_module, name) for name in _module.__all__})

__all__ = list(dict.fromkeys(name for module in _PUBLIC_MODULES for name in module.__all__))
