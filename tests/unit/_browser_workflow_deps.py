from __future__ import annotations

from dataclasses import replace
from typing import Any

from paper_fetch.providers.browser_workflow.shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
)


def browser_workflow_deps(**overrides: Any) -> BrowserWorkflowDeps:
    return replace(default_browser_workflow_deps(), **overrides)


def install_browser_workflow_deps(client: Any, **overrides: Any) -> BrowserWorkflowDeps:
    deps = browser_workflow_deps(**overrides)
    client.deps = deps
    return deps
