from dataclasses import fields

from paper_fetch.providers.browser_runtime.types import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)


def test_native_profile_contract_excludes_json_state():
    names = {field.name for field in fields(BrowserRuntimeConfig)}
    assert not names & {
        "storage_state_path",
        "persist_storage_state",
        "state_mode",
        "capability_storage_state_path",
    }
    assert "staged_storage_state" not in {
        field.name for field in fields(BrowserFetchedHtml)
    }
