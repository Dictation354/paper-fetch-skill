from __future__ import annotations

from dataclasses import replace
import socket
from typing import Any

from paper_fetch.http import SafeRemoteUrlPolicy
from paper_fetch.providers.browser_workflow.shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
)


def public_test_url_policy() -> SafeRemoteUrlPolicy:
    """Return a deterministic policy that resolves fixture hosts publicly."""

    def resolver(_host: str, port: int, *, type: int):
        return [(socket.AF_INET, type, 6, "", ("8.8.8.8", port))]

    return SafeRemoteUrlPolicy(resolver=resolver)


def browser_workflow_deps(**overrides: Any) -> BrowserWorkflowDeps:
    return replace(default_browser_workflow_deps(), **overrides)


def install_browser_workflow_deps(client: Any, **overrides: Any) -> BrowserWorkflowDeps:
    deps = browser_workflow_deps(**overrides)
    client.deps = deps
    return deps
