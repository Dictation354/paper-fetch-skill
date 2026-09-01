"""Small Playwright helpers shared by Camoufox browser paths."""

from __future__ import annotations

from typing import Any


def browser_page_user_agent(page: Any) -> str | None:
    try:
        user_agent = page.evaluate("() => navigator.userAgent")
    except Exception:
        return None
    normalized = str(user_agent or "").strip()
    return normalized or None


__all__ = ["browser_page_user_agent"]
