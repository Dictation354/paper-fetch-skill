"""Small native profile boundary double; never launches a real browser."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path


def write_verified_ams_profile(path: Path) -> None:
    """Write the credential-free summary/marker produced by successful auth."""
    import json

    from paper_fetch.providers.browser_runtime.profile import METADATA_FILENAME

    path.mkdir(parents=True, exist_ok=True)
    (path / METADATA_FILENAME).write_text(
        json.dumps(
            {
                "provider": "ams",
                "native_initialized": True,
                "state_sha256": "a" * 64,
                "auth": {
                    "native_profile_verified": True,
                    "state_replay_verified": True,
                    "state_sha256": "b" * 64,
                },
            }
        ),
        encoding="utf-8",
    )


class ProfilePage:
    def __init__(self, context):
        self.context = context
        self.url = "about:blank"
        self.closed = False

    def goto(self, url, **kwargs):
        self.url = url

    def evaluate(self, script, items=None):
        if items is not None:
            self.context.state["origins"].append(
                {"origin": self.url, "localStorage": items}
            )

    def close(self):
        self.closed = True


class ProfileContext:
    def __init__(self):
        self.state = {"cookies": [], "origins": []}
        self.closed = False
        self.pages = []

    def new_page(self):
        page = ProfilePage(self)
        self.pages.append(page)
        return page

    def storage_state(self):
        return deepcopy(self.state)

    def add_cookies(self, cookies):
        self.state["cookies"].extend(cookies)

    def close(self):
        self.closed = True


class NativeProfileDouble:
    instances = []

    def __init__(self, config, *, native_profile, runtime_context=None):
        user_data_dir, headless = native_profile, config.headless
        self.path = Path(user_data_dir)
        self.headless = headless
        self.context = ProfileContext()
        self.instances.append(self)

    def new_context(self):
        (self.path / "prefs.js").touch()
        return self.context

    def close(self):
        self.context.close()
