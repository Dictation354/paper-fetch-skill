"""Real worker protocol, offline font layout and per-document macro lifecycle."""

import shutil

from bs4 import BeautifulSoup
import pytest

from paper_fetch.formula.validation import (
    TexValidationSession,
    formula_validation_session,
    formula_document,
    select_formula_latex,
)
from paper_fetch.formula.convert import formula_runtime_env
from paper_fetch.extraction.markdown_render.formulas import (
    render_html_formula_container,
)
from tests.paths import REPO_ROOT


@pytest.fixture
def validator():
    if not (REPO_ROOT / ".formula-tools/node_modules/@mathjax/src").exists():
        pytest.skip("requires prepared formula-tools MathJax dependencies")
    with (
        formula_runtime_env(
            {
                "PAPER_FETCH_FORMULA_TOOLS_DIR": str(REPO_ROOT / ".formula-tools"),
                "MATHML_TO_LATEX_NODE_BIN": shutil.which("node"),
                "TEXMATH_BIN": shutil.which("texmath") or "texmath",
            }
        ),
        formula_validation_session() as session,
    ):
        yield session


def test_mathjax_worker_reuses_process_but_isolates_document_macros(validator):
    assert validator.validate(r"\newcommand{\isolated}{x}", False).valid
    assert validator.validate(r"\isolated", False).valid
    process = validator.worker._process
    assert validator.validate(r"\mathbbm{1}+\textdegree+\ce{H2O}", True).valid
    assert validator.worker._process is process
    other = TexValidationSession()
    try:
        result = other.validate(r"\isolated", False)
        assert not result.valid and "Undefined control sequence" in result.error
        assert other.worker._process is process
    finally:
        other.close()


def test_html_fallback_compiles_and_original_failure_stays_visible(validator):
    payload = r'<span id="eq1" class="inline-formula"><tex-math>\bm{x}</tex-math><math alttext="\bm{x}"><mi mathvariant="bold">x</mi><annotation encoding="application/x-tex">\bm{x}</annotation></math></span>'
    node = BeautifulSoup(payload, "html.parser").span
    before = str(node)
    rendered = render_html_formula_container(node)
    assert r"\bm" not in rendered
    assert str(node) == before
    selection = next(iter(validator.selections.values()))
    assert selection.valid and selection.backend and selection.style_degradations
    failed = BeautifulSoup(
        r'<span class="inline-formula"><tex-math>\unavailableMacro{x}</tex-math></span>',
        "html.parser",
    ).span
    assert render_html_formula_container(failed) == r"$\unavailableMacro{x}$"
    assert not validator.validate(r"\unavailableMacro{x}", False).valid


def test_extraction_documents_isolate_macros_inside_one_fetch_session(validator):
    @formula_document(new_document=True)
    def extract(expression):
        return select_formula_latex(expression, None, display_mode=False)

    assert extract(r"\newcommand{\documentOnly}{x}").valid
    assert not extract(r"\documentOnly").valid
    assert validator.worker is None  # Parent fetch only collects diagnostics.
