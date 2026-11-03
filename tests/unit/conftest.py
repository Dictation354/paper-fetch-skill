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
def mock_system_chrome_probe(monkeypatch):
    """System Chrome version processes are a unit boundary, like browser launch."""
    from paper_fetch.providers.browser_runtime.backends import flaresolverr

    def missing(*args, **kwargs):
        raise ValueError("System Chrome is unavailable in the unit boundary")

    monkeypatch.setattr(flaresolverr, "discover_chrome", missing)
