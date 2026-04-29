"""Public article model API."""

from __future__ import annotations

from ..utils import normalize_text as normalize_text, safe_text as safe_text
from . import builders as _builders
from . import markdown as _markdown
from . import quality as _quality
from . import render as _render
from . import schema as _schema
from . import sections as _sections
from . import tokens as _tokens

_PUBLIC_MODULES = (_schema, _markdown, _tokens, _sections, _quality, _render, _builders)

for _module in _PUBLIC_MODULES:
    globals().update({name: getattr(_module, name) for name in _module.__all__})

_EXTRA_EXPORTS = {"normalize_text": normalize_text, "safe_text": safe_text}
globals().update(_EXTRA_EXPORTS)

__all__ = list(
    dict.fromkeys(
        [
            *(name for module in _PUBLIC_MODULES for name in module.__all__),
            *_EXTRA_EXPORTS,
        ]
    )
)
