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


@pytest.fixture(autouse=True)
def mock_browser_dependencies(monkeypatch):
    """Packages/runtime are explicit boundaries in ordinary unit scenarios."""
    from paper_fetch.providers.browser_runtime.backends import camoufox

    monkeypatch.setattr(
        camoufox,
        "_dependency_details",
        lambda: {
            "packages": {"camoufox": False, "playwright": False},
            "package_ready": False,
            "runtime_installed": False,
        },
    )
