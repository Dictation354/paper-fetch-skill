"""Document-scoped TeX validation and same-node MathML selection (never PDF)."""

from __future__ import annotations

from contextlib import contextmanager, suppress
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from functools import wraps
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
from typing import Any
from uuid import uuid4
import xml.etree.ElementTree as ET

from . import convert
from .paths import formula_tools_subpaths


@dataclass
class TexValidation:
    valid: bool
    error: str | None = None
    available: bool = True


@dataclass
class FormulaSelection:
    node_id: str
    source_tex: str
    final_latex: str
    valid: bool
    validation_errors: list[str] = field(default_factory=list)
    backend: str | None = None
    style_degradations: list[str] = field(default_factory=list)


class TexValidationSession:
    def __init__(self) -> None:
        self.session_id = uuid4().hex
        self.worker: convert.MathMLToLatexWorker | None = None
        self.unavailable: str | None = None
        self.selections: dict[tuple, FormulaSelection] = {}

    def validate(self, expression: str, display_mode: bool) -> TexValidation:
        if self.unavailable:
            return TexValidation(False, self.unavailable, available=False)
        try:
            if self.worker is None:
                env = dict(convert._FORMULA_RUNTIME_ENV.get() or os.environ)
                node = env.get("MATHML_TO_LATEX_NODE_BIN") or shutil.which("node")
                candidates = formula_tools_subpaths("tex_validation_worker.mjs", env)
                candidates.append(
                    Path(__file__).parents[1]
                    / "resources/formula/tex_validation_worker.mjs"
                )
                script = next((p for p in candidates if p.is_file()), candidates[-1])
                if not node:
                    raise RuntimeError(
                        "MathJax validator unavailable: node executable not found"
                    )
                self.worker = convert._mathml_worker_for(
                    node_bin=node,
                    script_path=str(script),
                    cwd=script.parent,
                    env=env,
                )
            result = self.worker.request(
                {
                    "session": self.session_id,
                    "expression": expression,
                    "displayMode": display_mode,
                },
                timeout_seconds=convert.DEFAULT_TIMEOUT_SECONDS,
            )
            error = result.get("error")
            return TexValidation(
                bool(result.get("valid")),
                error.get("message") if isinstance(error, dict) else error,
            )
        except (
            OSError,
            RuntimeError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ) as exc:
            self.unavailable = f"MathJax validator unavailable: {exc}"
            return TexValidation(False, self.unavailable, available=False)

    def close(self) -> None:
        if self.worker is not None and not self.unavailable:
            with suppress(
                OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError
            ):
                self.worker.request(
                    {"operation": "close", "session": self.session_id},
                    timeout_seconds=5,
                )


_SESSION: ContextVar[TexValidationSession | None] = ContextVar(
    "formula_document", default=None
)


@contextmanager
def formula_validation_session(*, new_document: bool = False):
    """Nested rendering shares a document; the owner always releases its macros."""
    active = _SESSION.get()
    if active is not None and not new_document:
        yield active
        return
    session = TexValidationSession()
    token = _SESSION.set(session)
    try:
        yield session
        if active is not None:
            # A fetch can try several representations. Publish diagnostics only
            # from a completed extraction, without sharing that document's macros.
            active.selections = session.selections
    finally:
        session.close()
        _SESSION.reset(token)


def formula_document(function=None, *, new_document: bool = False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with formula_validation_session(new_document=new_document):
                return function(*args, **kwargs)

        return wrapped

    return decorate(function) if function is not None else decorate


def formula_diagnostics() -> list[dict[str, Any]]:
    session = _SESSION.get()
    return [asdict(s) for s in session.selections.values()] if session else []


def capture_formula_diagnostics(losses, *, count_fallbacks: bool = False) -> None:
    previous = {
        (d["node_id"], d["source_tex"], d["final_latex"])
        for d in losses.formula_diagnostics
    }
    losses.formula_diagnostics = formula_diagnostics()
    if count_fallbacks:
        losses.formula_fallback_count += sum(
            bool(item["source_tex"])
            and (bool(item["backend"]) or not item["valid"])
            and (item["node_id"], item["source_tex"], item["final_latex"])
            not in previous
            for item in losses.formula_diagnostics
        )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def same_node_mathml(element: ET.Element | None) -> ET.Element | None:
    if element is None:
        return None
    candidates = [
        n
        for n in element.iter()
        if isinstance(n.tag, str) and _local_name(n.tag) == "math"
    ]
    return candidates[0] if len(candidates) == 1 else None


def conversion_mathml(element: ET.Element) -> ET.Element:
    """Discard converter TeX hints only on a copy, retaining captured source."""
    clone = deepcopy(element)
    for parent in clone.iter():
        for key in list(parent.attrib):
            if _local_name(key).lower() in {
                "alttext",
                "alt-text",
                "tex",
                "latex",
                "data-tex",
                "data-latex",
            }:
                del parent.attrib[key]
        for child in list(parent):
            if isinstance(child.tag, str) and _local_name(child.tag) in {
                "annotation",
                "annotation-xml",
                "tex-math",
            }:
                parent.remove(child)
    return clone


def select_formula_latex(
    source_tex: str,
    mathml: ET.Element | None,
    *,
    display_mode: bool,
    node_id: str = "",
) -> FormulaSelection:
    with formula_validation_session() as session:
        raw = convert.stringify_mathml(mathml)
        key = (source_tex, raw, display_mode, node_id)
        if key in session.selections:
            return session.selections[key]
        selected = FormulaSelection(
            node_id or f"formula-{len(session.selections) + 1}",
            source_tex,
            source_tex,
            False,
        )
        session.selections[key] = selected
        if source_tex:
            validation = session.validate(source_tex, display_mode)
            if validation.valid:
                selected.valid = True
                return selected
            selected.validation_errors.append(
                validation.error or "Source TeX validation failed"
            )
            if not validation.available:
                return selected
        if mathml is None:
            selected.validation_errors.append("No unambiguous same-node MathML")
            return selected
        prepared = conversion_mathml(mathml)
        env = dict(convert._FORMULA_RUNTIME_ENV.get() or os.environ)
        backend = convert.resolve_backend(env=env)
        strategy = convert.backend_strategy(backend)
        # Preserve the configured order, including the default external fallback.
        explicit = bool(env.get("MATHML_CONVERTER_BACKEND", "").strip())
        backends = (
            strategy.fallback_backends
            if backend == convert.BACKEND_AUTO
            else (
                backend,
                *(strategy.fallback_backends if not explicit else ()),
            )
        )
        for name in backends:
            result = convert.convert_mathml_element_to_latex(
                prepared, display_mode=display_mode, backend=name
            )
            if result.status == "ok" and result.latex:
                validation = session.validate(result.latex, display_mode)
                if validation.valid:
                    selected.backend, selected.final_latex, selected.valid = (
                        name,
                        result.latex,
                        True,
                    )
                    break
                selected.validation_errors.append(f"{name}: {validation.error}")
                if not validation.available:
                    return selected
            else:
                selected.validation_errors.append(f"{name}: {result.error}")
        if not selected.valid:
            from ..providers._article_markdown_math import render_mathml_expression

            expression = render_mathml_expression(prepared)
            if expression:
                validation = session.validate(expression, display_mode)
                if validation.valid:
                    selected.backend, selected.final_latex, selected.valid = (
                        "internal_mathml",
                        expression,
                        True,
                    )
                else:
                    selected.validation_errors.append(
                        f"internal_mathml: {validation.error}"
                    )
        if selected.valid and selected.backend:
            # Converters cannot represent every publisher font variant. Report
            # this loss instead of altering commands in the captured source TeX.
            variants = {n.get("mathvariant", "") for n in prepared.iter()}
            if re.search(r"\\sc(?![A-Za-z])", source_tex) or any(
                "small-caps" in v for v in variants
            ):
                selected.style_degradations.append("small-caps")
            if source_tex:
                selected.style_degradations.append(
                    "MathML font styling may differ from source TeX"
                )
        return selected
