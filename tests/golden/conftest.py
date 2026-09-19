"""One session-local canonical result per source, route and adapter options."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def canonical_builds(tmp_path_factory):
    from tests.support import replay

    # xdist worker base directories have a shared parent owned by this invocation.
    base = tmp_path_factory.getbasetemp()
    if base.name.startswith("popen-gw"):
        base = base.parent
    replay.ROOT = base / "canonical-builds"
    replay.ROOT.mkdir(exist_ok=True)
    yield
    replay._build.cache_clear()
    replay.ROOT = None
