from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from paper_fetch.mcp.assets import fetch_assets_tool, inline_asset_images
from paper_fetch.mcp.content_delivery import content_snapshot
from paper_fetch.mcp.content_store import ContentSnapshot, ContentStore
from paper_fetch.mcp.schemas import (
    FetchAssetsRequest,
    FetchPaperRequest,
    InlineImageBudgetInput,
    ReadContentRequest,
)
from paper_fetch.providers.base import ProviderContent
from paper_fetch.runtime import RuntimeContext
from paper_fetch import targeted_assets as assets
from tests.support.asset_delivery_scenarios import (
    HTML,
    SOURCE,
    ImageTransport,
    asset_state,
)
from tests.support._mcp_support import sample_envelope


def runtime(transport):
    return RuntimeContext(env={}, transport=transport, clients={}, artifact_mode="none")


def test_html_index_formula_gif_deduplicates_and_ids_are_stable():
    state = asset_state()
    assert sorted(a["kind"] for a in state.assets) == ["figure", "formula", "formula"]
    assert len({a["asset_id"] for a in state.assets}) == 3
    assert state.assets == asset_state().assets


@pytest.mark.parametrize("route", ["xml", "official"])
def test_xml_index_uses_formula_ancestors_and_repeated_graphics(route):
    content = ProviderContent(
        route_kind=route,
        source_url=SOURCE,
        content_type="application/xml",
        body=b"""<article xmlns:xlink="http://www.w3.org/1999/xlink"><body><p><inline-formula><inline-graphic xlink:href="math-1.gif"/></inline-formula><inline-formula><inline-graphic xlink:href="math-1.gif"/></inline-formula></p><fig id="f"><label>Figure 1</label><graphic xlink:href="fig1.png"/></fig></body></article>""",
    )
    found = assets.discover_content_images(content, provider="")
    assert sorted(a["kind"] for a in found) == ["figure", "formula"]


@pytest.mark.parametrize("selector", ["id", "url", "formula"])
def test_only_selected_images_are_downloaded_and_repeated_fetch_reuses_files(selector):
    state, transport = asset_state(), ImageTransport()
    formula = next(a for a in state.assets if a["kind"] == "formula")
    selection = (
        {"asset_ids": [formula["asset_id"]]}
        if selector == "id"
        else {"urls": [formula["url"]]}
        if selector == "url"
        else {"kind": "formula"}
    )
    with runtime(transport) as context:
        first = assets.fetch_selected_assets(state, runtime=context, **selection)
        count = len(transport.requests)
        second = assets.fetch_selected_assets(state, runtime=context, **selection)
    assert first["status"] == second["status"] == "ok"
    assert all(result["kind"] == "formula" for result in first["results"])
    assert len(first["results"]) == (2 if selector == "formula" else 1)
    assert all(Path(result["path"]).is_file() for result in first["results"])
    assert len(transport.requests) == count
    assert not any("fig1" in url for url in transport.requests)
    state.close()
    assert not Path(first["results"][0]["path"]).exists()


def test_unknown_url_does_not_download_and_partial_failure_keeps_successes():
    state = asset_state()
    transport = ImageTransport(fail={"https://example.test/math-2.gif"})
    with runtime(transport) as context:
        result = assets.fetch_selected_assets(state, kind="formula", runtime=context)
        unknown = assets.fetch_selected_assets(
            state, urls=["https://unrelated.test/image.png"], runtime=context
        )
    assert result["status"] == "partial"
    assert [item["status"] for item in result["results"]] == ["ok", "failed"]
    assert result["results"][1]["failures"]
    assert unknown["results"][0]["reason"] == "asset_not_found"
    assert all(
        "unrelated" not in url and "fig1" not in url for url in transport.requests
    )


def test_missing_index_reads_source_only_and_never_fetches_body(monkeypatch):
    import paper_fetch.service as service

    monkeypatch.setattr(
        service, "fetch_paper", lambda *a, **kw: pytest.fail("full paper fetch")
    )
    state = assets.AssetContext(doi=None, provider="", source_url=SOURCE)
    transport = ImageTransport()
    with runtime(transport) as context:
        result = assets.fetch_selected_assets(
            state, urls=["https://example.test/math-1.gif"], runtime=context
        )
    assert result["status"] == "ok"
    assert transport.requests == [SOURCE, "https://example.test/math-1.gif"]


def test_missing_source_retains_actionable_failure():
    with (
        runtime(ImageTransport()) as context,
        pytest.raises(Exception, match="source URL") as error,
    ):
        assets.fetch_selected_assets(
            assets.AssetContext(None, "", ""), kind="formula", runtime=context
        )
    assert error.value.code == "asset_index_unavailable"


def test_archive_survives_handle_cleanup_and_overwrite_is_explicit(tmp_path):
    state = asset_state()
    formula = next(a for a in state.assets if a["kind"] == "formula")
    with runtime(ImageTransport()) as context:
        result = assets.fetch_selected_assets(
            state,
            asset_ids=[formula["asset_id"]],
            output_dir=str(tmp_path),
            runtime=context,
        )
        path = Path(result["results"][0]["path"])
        path.write_bytes(b"existing")
        refused = assets.fetch_selected_assets(
            state,
            asset_ids=[formula["asset_id"]],
            output_dir=str(tmp_path),
            runtime=context,
        )
        assert refused["results"][0]["reason"] == "output_exists"
        assert path.read_bytes() == b"existing"
        replaced = assets.fetch_selected_assets(
            state,
            asset_ids=[formula["asset_id"]],
            output_dir=str(tmp_path),
            overwrite=True,
            runtime=context,
        )
    state.close()
    assert path.is_file() and path.read_bytes().startswith(b"GIF")
    assert replaced["results"][0]["path"] == str(path)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"asset_ids": []},
        {"urls": [""]},
        {"kind": "figure"},
        {"kind": "formula", "urls": [SOURCE]},
        {"asset_ids": ["x"], "output_dir": ""},
        {"kind": "formula", "unknown": True},
    ],
)
def test_mcp_selector_validation(options):
    with pytest.raises(ValidationError):
        FetchAssetsRequest(content_id="id", **options)


def test_mcp_expired_handle_returns_error():
    result = asyncio.run(
        fetch_assets_tool(ContentStore(), content_id="expired", kind="formula")
    )
    assert result.is_error
    assert result.structured_content["code"] == "content_handle_expired"


@pytest.mark.parametrize("cleanup", ["expire", "evict", "close"])
def test_handle_resource_cleanup_including_seed(cleanup):
    now = [0]
    state = asset_state()
    state.browser_context_seed = {
        "browser_cookies": [{"name": "session", "value": "secret"}]
    }
    size = ContentSnapshot({"markdown": "text"}, asset_context=state).size
    store = ContentStore(max_bytes=size + 1, idle_ttl=2, timer=lambda: now[0])
    ref = store.register_many(
        [ContentSnapshot({"markdown": "text"}, asset_context=state)]
    )[0]
    local = state.temporary_dir() / "image.gif"
    local.write_bytes(b"gif")
    if cleanup == "expire":
        now[0] = 3
        assert store.get_asset_context(ref["content_id"]) is None
    elif cleanup == "evict":
        store.register_many([ContentSnapshot({"markdown": "x" * size})])
    else:
        store.close()
    assert not local.exists()
    assert state.browser_context_seed == {}


def test_supplement_does_not_change_body_or_offsets_and_seed_is_private(monkeypatch):
    state = asset_state()
    state.browser_context_seed = {"browser_cookies": [{"value": "private-cookie"}]}
    envelope = sample_envelope(modes={"markdown"})
    envelope.__dict__["_asset_context"] = state
    envelope.markdown = "😀 Chinese 中文 ![Formula](https://example.test/math-1.gif)\n"
    snapshot = content_snapshot(envelope, FetchPaperRequest(query=envelope.doi))
    assert "private-cookie" not in json.dumps(snapshot.views)
    store = ContentStore()
    ref = store.register_many([snapshot])[0]
    monkeypatch.setattr(
        assets, "RuntimeContext", lambda **kw: runtime(ImageTransport())
    )
    before = store.read(
        ReadContentRequest(content_id=ref["content_id"], offset=2, max_chars=9)
    )
    fetched = asyncio.run(
        fetch_assets_tool(store, content_id=ref["content_id"], kind="formula")
    )
    after = store.read(
        ReadContentRequest(content_id=ref["content_id"], offset=2, max_chars=9)
    )
    assert before == after
    assert fetched.structured_content["image_delivery"]["returned_images"] == 2
    assert all(content.type == "image" for content in fetched.content)
    details = store.read(
        ReadContentRequest(
            content_id=ref["content_id"], view="diagnostics", max_chars=20000
        )
    )
    assert json.loads(details["text"])["asset_fetches"]
    assert "private-cookie" not in details["text"]
    store.close()


def test_inline_limits_include_paths_and_reasons(tmp_path):
    small, large = tmp_path / "small.png", tmp_path / "large.png"
    small.write_bytes(b"png")
    large.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    payload = {
        "discovery_complete": True,
        "results": [
            {"status": "ok", "path": str(small), "kind": "formula"} for _ in range(4)
        ],
    }
    assert len(inline_asset_images(payload)) == 3
    assert payload["results"][-1]["inline_reason"] == "image_count_limit"
    payload["results"] = [{"status": "ok", "path": str(large)}]
    assert (
        inline_asset_images(
            payload, InlineImageBudgetInput(max_bytes_per_image=9999999)
        )
        == []
    )
    assert payload["results"][0]["path"] == str(large)
    assert payload["results"][0]["inline_reason"] == "byte_limit_or_unreadable"
    payload["results"] = [{"status": "ok", "path": str(small)}]
    assert inline_asset_images(payload, InlineImageBudgetInput(max_total_bytes=2)) == []


def test_formula_image_summary_uses_final_markdown_references():
    state = asset_state()
    envelope = sample_envelope(modes={"markdown"})
    envelope.__dict__["_asset_context"] = state
    envelope.markdown = "Text ![Formula](https://example.test/math-1.gif)"
    assert assets.image_delivery(envelope)["formula_images"] == 1
    assert assets.image_delivery(envelope)["discovery_complete"] is True
    envelope.markdown += " ![Formula](https://example.test/unknown.gif)"
    assert assets.image_delivery(envelope)["discovery_complete"] is False
    assert assets.image_delivery(envelope)["returned_images"] == 0


def test_default_none_captures_index_without_download(monkeypatch):
    from paper_fetch.providers._result import assemble_provider_result
    from paper_fetch.providers.base import ProviderClient
    from paper_fetch.providers.base import (
        PreparedFetchResultPayload,
        RawFulltextPayload,
    )
    from tests.support._mcp_support import sample_article

    article = sample_article()
    content = ProviderContent(
        route_kind="html",
        source_url=SOURCE,
        content_type="text/html",
        body=HTML,
        browser_context_seed={"browser_cookies": [{"value": "secret"}]},
    )
    client = ProviderClient()
    client.name = "plos"
    client.transport = ImageTransport()
    client.env = {}
    monkeypatch.setattr(
        client,
        "prepare_fetch_result_payload",
        lambda *a, **kw: PreparedFetchResultPayload(
            raw_payload=RawFulltextPayload(provider="test", content=content),
            provisional_article=article,
        ),
    )
    monkeypatch.setattr(
        client,
        "maybe_recover_fetch_result_payload",
        lambda doi, metadata, prepared, **kw: prepared,
    )
    monkeypatch.setattr(client, "ensure_html_markdown", lambda raw, *a, **kw: raw)
    monkeypatch.setattr(
        client, "validate_raw_payload_identity", lambda doi, metadata, raw: raw
    )
    monkeypatch.setattr(
        client,
        "download_related_assets",
        lambda *a, **kw: pytest.fail("unrequested download"),
    )
    with runtime(ImageTransport()) as context:
        result = assemble_provider_result(
            client,
            article.doi,
            asdict(article.metadata),
            None,
            asset_profile="none",
            context=context,
        )
    assert len(result.article.diagnostics["image_index"]) == 3
    assert "secret" not in result.article.to_json()


def test_cached_envelope_without_private_context_reuses_index_and_file(
    tmp_path, monkeypatch
):
    from paper_fetch.models.codec import envelope_from_payload
    from paper_fetch.models import Asset

    local = tmp_path / "formula.gif"
    local.write_bytes(b"GIF89a")
    envelope = sample_envelope(modes={"article", "markdown"})
    envelope.article.assets = [
        Asset(
            kind="formula",
            heading="Equation 1",
            url=SOURCE + "/math-1.gif",
            path=str(local),
        )
    ]
    envelope.diagnostics.update(
        image_source_url=SOURCE, image_provider="", image_discovery_complete=True
    )
    envelope.markdown = f"![Formula]({local})"
    cached = envelope_from_payload(envelope.to_dict())
    assert not hasattr(cached, "_asset_context")
    snapshot = content_snapshot(cached, FetchPaperRequest(query=cached.doi))
    state = snapshot.asset_context
    monkeypatch.setattr(
        assets,
        "_download_selected",
        lambda *a, **kw: pytest.fail("local file must be reused"),
    )
    with runtime(ImageTransport()) as context:
        result = assets.fetch_selected_assets(
            state, asset_ids=[state.assets[0]["asset_id"]], runtime=context
        )
    assert result["results"][0]["path"] == str(local)
    state.close()
    assert local.is_file()
    assert assets.image_delivery(cached)["formula_images"] == 1


def test_source_recovery_uses_serializable_seed_without_public_credentials(monkeypatch):
    from types import SimpleNamespace
    from paper_fetch.providers import browser_runtime

    class Blocked(ImageTransport):
        def request(self, method, url, **kwargs):
            self.requests.append(url)
            return {
                "status_code": 403,
                "url": url,
                "headers": {"content-type": "text/html"},
                "body": b"<title>challenge</title>",
            }

    state = assets.AssetContext(
        None,
        "wiley",
        SOURCE,
        browser_context_seed={"browser_cookies": [{"value": "secret"}]},
    )
    calls = []
    monkeypatch.setattr(
        browser_runtime, "load_runtime_config", lambda *a, **kw: "runtime-config"
    )

    def recover(urls, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            html=HTML.decode(),
            final_url=SOURCE,
            browser_context_seed={"browser_cookies": [{"value": "restored-secret"}]},
        )

    monkeypatch.setattr(browser_runtime, "fetch_html_with_browser", recover)
    with runtime(Blocked()) as context:
        assets._load_source(state, context)
    assert calls[0]["browser_context_seed"]["browser_cookies"][0]["value"] == "secret"
    assert len(state.assets) == 3
    assert "secret" not in json.dumps(state.assets)
    assert (
        state.browser_context_seed["browser_cookies"][0]["value"] == "restored-secret"
    )


@pytest.mark.parametrize(
    "url", ["file:///tmp/formula.gif", "https://user:secret@example.test/formula.gif"]
)
def test_mcp_image_urls_reject_nonremote_or_embedded_credentials(url):
    with pytest.raises(ValidationError):
        FetchAssetsRequest(content_id="id", urls=[url])
