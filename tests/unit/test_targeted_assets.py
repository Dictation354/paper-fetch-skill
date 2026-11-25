from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from paper_fetch import targeted_assets as assets
from paper_fetch.cli.subcommands import _compact_asset_receipt
from paper_fetch.delivery.receipts import _image_body_positions
from paper_fetch.providers.base import ProviderContent
from paper_fetch.runtime import RuntimeContext
from tests.support.asset_delivery_scenarios import (
    HTML,
    SOURCE,
    ImageTransport,
    asset_state,
)
from tests.support.fetch_fixtures import sample_envelope


def runtime(transport):
    return RuntimeContext(env={}, transport=transport, clients={}, artifact_mode="none")


def test_html_index_formula_gif_deduplicates_and_ids_are_stable():
    state = asset_state()
    assert sorted(a["kind"] for a in state.assets) == ["figure", "formula", "formula"]
    assert len({a["asset_id"] for a in state.assets}) == 3
    assert state.assets == asset_state().assets


@pytest.mark.parametrize("kind", ["formula", "figure", "table"])
def test_body_positions_index_all_image_kinds(kind, tmp_path):
    body = tmp_path / "body.md"
    image = tmp_path / "image.png"
    image.touch()
    (indexed,) = _image_body_positions(
        [{"kind": kind, "path": str(image), "url": "https://example.test/image.png"}],
        "# Body\n\nAn ![image](image.png) and ![copy](https://example.test/image.png)\n",
        body=body,
    )
    assert indexed["body_positions"] == [
        {"line": 3, "column": 4},
        {"line": 3, "column": 28},
    ]
    state = asset_state()
    state.assets = assets.image_index([indexed])
    try:
        with runtime(ImageTransport()) as context:
            result = assets.fetch_selected_assets(state, kind=kind, runtime=context)
        (selected,) = result["results"]
        assert selected["status"] == "ok" and selected["kind"] == kind
        assert selected["body_positions"] == indexed["body_positions"]
    finally:
        state.close()


def test_body_positions_skip_fences_and_escaped_images_and_normalize_unreserved_urls(
    tmp_path,
):
    reference = "https://example.test/~reader/image%2Fone.png"
    markdown = "\n".join(
        [
            "```md",
            f"![code]({reference})",
            "```",
            "~~~~",
            f"![code]({reference})",
            "~~~",
            f"![still fenced]({reference})",
            "~~~~",
            rf"\![escaped]({reference})",
            "![reserved slash](https://example.test/~reader/image/one.png)",
            r"\\![real](https://example.test/%7ereader/image%2fone.png)",
            f"![real]({reference})",
        ]
    )
    (asset,) = _image_body_positions(
        [{"kind": "figure", "url": reference}], markdown, body=tmp_path / "body.md"
    )
    assert asset["body_positions"] == [
        {"line": 11, "column": 3},
        {"line": 12, "column": 1},
    ]


@pytest.mark.parametrize(
    ("positions", "lines"),
    [
        (True, []),
        (b"invalid", []),
        ("invalid", []),
        ({"line": 1}, []),
        ([{"line": True}, {"line": 0}, {"line": -3}, {"line": "2"}, None], []),
        (({"line": 3}, {"line": 2}, {"line": 3}, {"line": False}, []), [2, 3]),
    ],
)
def test_compact_asset_receipt_only_emits_valid_body_lines(tmp_path, positions, lines):
    result = {"status": "ok", "asset_id": "img_1", "path": "figure.png"}
    payload = {
        "status": "ok",
        "doi": "10.1000/example",
        "results": [{**result, "kind": "figure", "body_positions": positions}],
    }
    receipt = _compact_asset_receipt(payload, output_dir=str(tmp_path), state=None)
    if lines:
        result.update(kind="figure", lines=lines)
    assert receipt["results"] == [result]


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


def test_context_from_manifest_reads_acceptance_identity_doi(tmp_path):
    from paper_fetch.delivery.receipts import save_reading_artifacts
    from paper_fetch.manifest import build_manifest_record
    from paper_fetch.manifest_writer import write_manifest_record

    envelope = sample_envelope(modes={"article", "markdown"}, doi="10.1000/example")
    envelope.__dict__["_asset_context"] = asset_state()
    delivery_dir = tmp_path / "delivery"
    artifacts = save_reading_artifacts(delivery_dir, envelope=envelope)
    record = build_manifest_record(
        tool_version="8.0.0",
        index=1,
        attempt=1,
        query="10.1000/example",
        request_parameters={},
        asset_profile="none",
        envelope=envelope,
        output_artifacts=artifacts,
    )
    manifest_path = write_manifest_record(delivery_dir / "manifest.json", record)
    restored = assets.context_from_manifest(manifest_path)
    assert restored.doi == "10.1000/example"
    assert restored.source_url == SOURCE
    assert len(restored.assets) == 3


def test_default_none_captures_index_without_download(monkeypatch):
    from paper_fetch.providers._result import assemble_provider_result
    from paper_fetch.providers.base import (
        PreparedFetchResultPayload,
        ProviderClient,
        RawFulltextPayload,
    )
    from tests.support.fetch_fixtures import sample_article

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
