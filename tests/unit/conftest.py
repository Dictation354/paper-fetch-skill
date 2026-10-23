"""Unit rendering uses a boundary mock; real MathJax runs in integration."""

import pytest


@pytest.fixture(autouse=True)
def mock_tex_validation(monkeypatch):
    from paper_fetch.formula.validation import TexValidation, TexValidationSession

    monkeypatch.setattr(
        TexValidationSession,
        "validate",
        lambda self, expression, display_mode: TexValidation(True),
    )
