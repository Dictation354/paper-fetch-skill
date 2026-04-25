"""Compatibility alias for the canonical browser workflow runtime.

New code should import :mod:`paper_fetch.providers.browser_workflow`.  This
module intentionally resolves to that module object so legacy monkeypatches on
``_science_pnas`` still affect the canonical runtime.
"""

from __future__ import annotations

import sys
import types

from . import browser_workflow as _browser_workflow


class _SciencePnasCompatModule(types.ModuleType):
    def __getattr__(self, name: str):
        return getattr(_browser_workflow, name)

    def __setattr__(self, name: str, value):
        if hasattr(_browser_workflow, name):
            setattr(_browser_workflow, name, value)
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)


__all__ = list(getattr(_browser_workflow, "__all__", ()))
for _name, _value in _browser_workflow.__dict__.items():
    if _name not in {
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
    }:
        globals()[_name] = _value

sys.modules[__name__].__class__ = _SciencePnasCompatModule
