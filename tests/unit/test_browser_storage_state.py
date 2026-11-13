from dataclasses import fields
import pytest
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
    BrowserFetchedHtml,
)
from paper_fetch.mcp.schemas import BrowserPreflightRequest


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
    with pytest.raises(ValueError):
        BrowserPreflightRequest(provider="wiley", storage_state_path="state.json")
    with pytest.raises(ValueError):
        BrowserPreflightRequest(provider="wiley", save_storage_state=False)
