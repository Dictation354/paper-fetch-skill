from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tests._environment import (
    TEST_ENVIRONMENT_REPAIR,
    locked_test_dependency_issues,
)


def _extract(
    _content: Any,
    *,
    output_format: str = "txt",
    include_links: bool = False,
    include_tables: bool = True,
    favor_precision: bool = False,
) -> None:
    del output_format, include_links, include_tables, favor_precision


def test_locked_test_dependency_probe_accepts_supported_contract() -> None:
    issues = locked_test_dependency_issues(
        version_of=lambda name: {"mcp": "2.0.0", "trafilatura": "2.2.0"}[name],
        import_module=lambda _name: SimpleNamespace(extract=_extract),  # type: ignore[arg-type,return-value]
    )

    assert issues == []


def test_locked_test_dependency_probe_reports_ambient_major_and_behavior() -> None:
    issues = locked_test_dependency_issues(
        version_of=lambda name: {"mcp": "1.28.0", "trafilatura": "2.0.0"}[name],
        import_module=lambda _name: SimpleNamespace(extract=lambda _content: None),  # type: ignore[arg-type,return-value]
    )

    assert "incompatible mcp major 1; expected >=2,<3" in issues
    assert any("locked behavior parameters" in issue for issue in issues)
    assert "uv sync --frozen" in TEST_ENVIRONMENT_REPAIR
    assert "PYTHONPATH=src uv run python -m pytest" in TEST_ENVIRONMENT_REPAIR
