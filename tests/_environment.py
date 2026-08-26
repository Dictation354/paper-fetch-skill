from __future__ import annotations

import importlib
import importlib.metadata
import inspect
from collections.abc import Callable
from types import ModuleType

from packaging.version import InvalidVersion, Version


PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR = "PAPER_FETCH_TEST_PRESERVED_CAMOUFOX_EXECUTABLE"
PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR = "PAPER_FETCH_TEST_PRESERVED_CAMOUFOX_CACHE_HOME"
PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR = "PAPER_FETCH_TEST_PRESERVED_FORMULA_TOOLS_DIR"

TEST_ENVIRONMENT_REPAIR = (
    "uv sync --frozen --extra dev --extra full && "
    "PYTHONPATH=src uv run python -m pytest tests/unit -q"
)
_TRAFILATURA_EXTRACT_PARAMETERS = frozenset(
    {"output_format", "include_links", "include_tables", "favor_precision"}
)


def locked_test_dependency_issues(
    *,
    version_of: Callable[[str], str] = importlib.metadata.version,
    import_module: Callable[[str], ModuleType] = importlib.import_module,
) -> list[str]:
    """Return actionable incompatibilities before the test suite is collected."""

    issues: list[str] = []
    for distribution in ("mcp", "trafilatura"):
        try:
            raw_version = version_of(distribution)
            version = Version(raw_version)
        except importlib.metadata.PackageNotFoundError:
            issues.append(f"missing required test dependency {distribution!r}")
            continue
        except InvalidVersion:
            issues.append(f"invalid {distribution} version metadata: {raw_version!r}")
            continue
        if version.major != 2:
            issues.append(
                f"incompatible {distribution} major {version.major}; expected >=2,<3"
            )

    if not any("trafilatura" in issue for issue in issues):
        try:
            extract = import_module("trafilatura").extract
            parameters = frozenset(inspect.signature(extract).parameters)
        except (AttributeError, ImportError, TypeError, ValueError) as error:
            issues.append(
                f"trafilatura.extract behavior probe failed: {error.__class__.__name__}"
            )
        else:
            missing = sorted(_TRAFILATURA_EXTRACT_PARAMETERS - parameters)
            if missing:
                issues.append(
                    "trafilatura.extract is missing locked behavior parameters: "
                    + ", ".join(missing)
                )
    return issues
