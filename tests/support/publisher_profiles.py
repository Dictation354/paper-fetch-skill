"""Small native profile boundary double; never launches a real browser."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path


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
