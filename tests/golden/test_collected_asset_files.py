"""Captured source -> discovered collection -> real byte download -> article links.

This is an offline asset replay, not a claim of live fulltext CLI success.
Real-download acceptance covers body and body images only. Supplementary
discovery and final remote links remain required. Supplementary payloads have
been removed at user request; only their acquisition metadata is retained.
Historical local reuse with unknown HTTP status receives an explicitly injected
200 envelope. Missing HTTP responses are injected as 404; actual capture failures are retained
separately in provenance and never counted as downloaded files.
"""

import hashlib
import json
from pathlib import Path
import pytest
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
)
from paper_fetch.models import article_from_markdown
from paper_fetch.provider_catalog import SOURCE_PROVIDER_MAP
from tests.asset_collection import discover_assets, source_markdown
from tests.support.acquired_publisher_inputs import (
    capture_url_identity,
    _record,
    _response,
)
from tests.paths import REPO_ROOT
from tests.support._paper_fetch_support import FixtureHtmlTransport


from tests.golden_criteria import golden_criteria_manifest, golden_criteria_asset

ROWS = [
    sample["asset_collection"]
    for sample in golden_criteria_manifest()["samples"].values()
    if "asset_collection" in sample
]


def test_fixed_scope_and_independent_collection_counts():
    assert len({r["provider"] for r in ROWS if r["include_supplementary"]}) == 16
    assert len({r["doi"] for r in ROWS}) == len(ROWS)
    for row in ROWS:
        assert (
            hashlib.sha256((REPO_ROOT / row["source_input"]).read_bytes()).hexdigest()
            == row["source_sha256"]
        )
        identities = [
            capture_url_identity(t["download_url"], provider=row["provider"])
            for t in row["targets"]
        ]
        assert len(identities) == len(set(identities)) == row["counts"]["unique_files"]
        assert (
            sum(t["state"] == "file_verified" for t in row["targets"])
            == row["counts"]["verified_files"]
        )


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["doi"])
def test_original_source_contains_the_complete_discovered_collection(row):
    discovered = discover_assets(row)
    selected = [
        a
        for a in discovered
        if a.get("url")
        and (
            row["include_supplementary"]
            if a["kind"] == "supplementary"
            else row["include_body"]
        )
    ]
    expected = {
        capture_url_identity(
            a.get("download_url") or a.get("full_size_url") or a["url"],
            provider=row["provider"],
        )
        for a in selected
    }
    actual = {
        capture_url_identity(
            t["asset"].get("download_url")
            or t["asset"].get("full_size_url")
            or t["asset"]["url"],
            provider=row["provider"],
        )
        for t in row["targets"]
    }
    assert actual == expected


@pytest.mark.parametrize(
    "row",
    [r for r in ROWS if any(t["file_role"] != "supplementary" for t in r["targets"])],
    ids=lambda r: r["doi"],
)
def test_captured_collection_download_and_final_article_links(row, tmp_path):
    targets = [t for t in row["targets"] if t["state"] == "file_verified"]
    if not targets:
        pytest.skip("No verified binary; actual failures remain in provenance")
    responses = {}
    for target in targets:
        record, body = _record(row["doi"], target["record"])
        responses[target["download_url"]] = {
            "status_code": record["status_code"]
            if record["status_code"] is not None
            else 200,
            "headers": record["response_headers"] or {},
            "url": record["final_url"] or target["download_url"],
            "body": body,
        }
    transport = FixtureHtmlTransport(responses)
    downloaded = []
    for kind in (FIGURE_KIND, SUPPLEMENTARY_KIND):
        group = [
            t
            for t in targets
            if (t["asset"]["kind"] == "supplementary") == (kind == SUPPLEMENTARY_KIND)
        ]
        if not group:
            continue
        assets = [dict(t["asset"], download_url=t["download_url"]) for t in group]
        result = download_assets(
            kind,
            transport,
            article_id=row["doi"],
            assets=assets,
            output_dir=tmp_path,
            user_agent="offline captured collection replay",
            asset_profile="all",
            options=AssetDownloadOptions(
                asset_download_concurrency=1, provider_name=row["provider"]
            ),
        )
        assert not result["asset_failures"], result["asset_failures"]
        assert len(result["assets"]) == len(group)
        downloaded.extend(result["assets"])
    assert len(downloaded) == len(targets)
    hashes = {
        hashlib.sha256(
            golden_criteria_asset(row["doi"], t["record"]).read_bytes()
        ).hexdigest()
        for t in targets
    }
    assert {
        hashlib.sha256(Path(a["path"]).read_bytes()).hexdigest() for a in downloaded
    } == hashes
    markdown = source_markdown(row)
    article = article_from_markdown(
        source=next(
            s
            for s, owner in SOURCE_PROVIDER_MAP.items()
            if owner == row["provider"] and not s.endswith("_pdf")
        ),
        doi=row["doi"],
        metadata={"title": row["doi"]},
        markdown_text=markdown,
        assets=downloaded,
    )
    rendered = article.to_ai_markdown(
        include_refs="none", max_tokens="full_text", asset_profile="all"
    )
    article_path = tmp_path / "article.md"
    article_path.write_text(rendered, encoding="utf-8")
    persisted = article_path.read_text(encoding="utf-8")
    for asset in downloaded:
        assert asset["path"] in persisted
    receipt = {
        "doi": row["doi"],
        "source_input": row["source_input"],
        "source_sha256": row["source_sha256"],
        "scope": "Offline source discovery, captured-byte download, article assembly and Markdown write/read; not a live CLI claim",
        "rendered_article_sha256": hashlib.sha256(persisted.encode()).hexdigest(),
        "files": [
            {
                "filename": Path(a["path"]).name,
                "download_url": a.get("download_url"),
                "source_url": a.get("source_url"),
                "sha256": hashlib.sha256(Path(a["path"]).read_bytes()).hexdigest(),
                "size": Path(a["path"]).stat().st_size,
                "kind": a["kind"],
                "download_tier": a.get("download_tier"),
                "width": a.get("width"),
                "height": a.get("height"),
                "final_article_link_verified": a["path"] in persisted,
            }
            for a in downloaded
        ],
    }
    (tmp_path / "replay-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    if row["doi"] == "10.1093/bioinformatics/btaa823":
        assert len(downloaded) == 9
        assert all(a["download_tier"] == "full_size" for a in downloaded)


@pytest.mark.parametrize(
    "doi",
    [
        "10.3389/fmars.2023.1101972",
        "10.1371/journal.pone.0015338",
        "10.1016/j.envres.2018.12.059",
        "10.1016/j.agrformet.2024.109975",
        "10.1016/j.ecolind.2024.112140",
    ],
)
def test_xml_provider_owns_the_complete_download_and_article_chain(doi, tmp_path):
    from paper_fetch.providers import frontiers, plos, elsevier
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.runtime import RuntimeContext

    row = next(r for r in ROWS if r["doi"] == doi)
    provider = row["provider"]
    targets = [
        t
        for t in row["targets"]
        if t["state"] == "file_verified" and t["asset"]["kind"] != "supplementary"
    ]
    responses = {}
    for target in targets:
        record, body = _record(doi, target["record"])
        responses[target["download_url"]] = _response(record, body)
    transport = FixtureHtmlTransport(responses)
    raw = (REPO_ROOT / row["source_input"]).read_bytes()
    metadata = {"doi": doi}
    client_type = {
        "frontiers": frontiers.FrontiersClient,
        "plos": plos.PlosClient,
        "elsevier": elsevier.ElsevierClient,
    }[provider]
    client = client_type(transport, {"ELSEVIER_API_KEY": "offline-placeholder"})
    extracted = []
    markdown = None
    if provider != "elsevier":
        extraction = parse_jats_xml(
            raw, source_url=row["source_url"], base_metadata=metadata
        )
        metadata = extraction.metadata
        extracted = extraction.assets
        markdown = extraction.markdown_text
        if provider == "frontiers":
            extracted, replacements = frontiers._normalize_frontiers_extracted_assets(
                extracted, doi=doi, landing_url=row["source_url"]
            )
            markdown = frontiers._replace_markdown_urls(markdown, replacements)
    payload = RawFulltextPayload(
        provider=provider,
        content=ProviderContent(
            route_kind="xml",
            source_url=row["source_url"],
            content_type="text/xml",
            body=raw,
            merged_metadata=metadata,
            markdown_text=markdown,
            extracted_assets=extracted,
        ),
    )
    with RuntimeContext(
        env={"ELSEVIER_API_KEY": "offline-placeholder"}, transport=transport
    ) as context:
        result = client.download_related_assets(
            doi,
            metadata,
            payload,
            tmp_path,
            asset_profile="body",
            context=context,
        )
    assert not result["asset_failures"], result["asset_failures"]
    assert len(result["assets"]) == len(targets)
    expected_hashes = {_record(doi, t["record"])[0]["sha256"] for t in targets}
    assert {
        hashlib.sha256(Path(a["path"]).read_bytes()).hexdigest()
        for a in result["assets"]
    } == expected_hashes
    article = client.to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    rendered = article.to_ai_markdown(
        include_refs="none", max_tokens="full_text", asset_profile="all"
    )
    for a in result["assets"]:
        assert a["path"] in rendered
    if provider == "plos":
        assert len([a for a in result["assets"] if a["kind"] == "formula"]) == 4
        assert len([a for a in result["assets"] if a["kind"] == "table"]) == 5
    if provider == "elsevier":
        assert all(
            call["headers"].get("X-ELS-APIKey") == "offline-placeholder"
            for call in transport.calls
        )


@pytest.mark.parametrize(
    "row", [r for r in ROWS if r["include_supplementary"]], ids=lambda r: r["doi"]
)
def test_supplementary_indexes_keep_article_link_metadata_without_payloads(row):
    targets = [t for t in row["targets"] if t["file_role"] == "supplementary"]
    assert targets
    assert all(t["state"] == "index_only" and "record" not in t for t in targets)
    article = article_from_markdown(
        source=next(
            s
            for s, owner in SOURCE_PROVIDER_MAP.items()
            if owner == row["provider"] and not s.endswith("_pdf")
        ),
        doi=row["doi"],
        metadata={"title": row["doi"]},
        markdown_text="",
        assets=[t["asset"] for t in targets],
    )
    # Remote asset URLs are stored as provenance by the existing Article
    # contract; only downloaded paths become local Markdown links.
    links = {
        url
        for a in article.assets
        for url in (a.original_url, a.download_url, a.source_url)
    }
    for target in targets:
        assert (target["asset"].get("original_url") or target["asset"]["url"]) in links
    assert all(a.path is None for a in article.assets)


def test_removed_supplementary_files_are_absent_from_fixture_catalog():
    from tests.fixture_catalog import fixture_catalog

    catalog = fixture_catalog()
    for record in golden_criteria_manifest()["withdrawn_assets"]:
        path = Path(record["former_path"])
        if path.is_absolute():
            continue  # Scratch directories are not part of the portable fixture contract.
        assert record["former_path"] not in catalog
        assert not (REPO_ROOT / path).exists()
