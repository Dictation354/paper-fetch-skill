"""Provider-owned HTML payload and asset planning for captured signed-image replay."""

from paper_fetch.providers import (
    acs,
    aip,
    royalsocietypublishing,
    oxfordacademic,
    _oxfordacademic_html,
)
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow.asset_download import (
    plan_browser_asset_download,
)
from paper_fetch.runtime import RuntimeContext

CLIENTS = {
    "acs": acs.AcsClient,
    "aip": aip.AipClient,
    "royalsocietypublishing": royalsocietypublishing.RoyalsocietypublishingClient,
    "oxfordacademic": oxfordacademic.OxfordAcademicClient,
}


def extract_signed_fixture_payload(row, path, transport, output_dir):
    provider = row["provider"]
    client = CLIENTS[provider](transport, {})
    text = path.read_text()
    metadata = {"doi": row["doi"], "landing_page_url": row["source_url"]}
    if provider == "oxfordacademic":
        e = _oxfordacademic_html.extract_markdown(
            text, row["source_url"], metadata=metadata, asset_profile="body"
        )
        md = e.markdown_text
        assets = e.extracted_assets
        metadata = e.metadata
        diagnostics = {
            "abstract_sections": e.abstract_sections,
            "section_hints": e.section_hints,
        }
        cb = None
    else:
        md, diagnostics = client.extract_markdown(
            text, row["source_url"], metadata=metadata
        )
        metadata = diagnostics.get("metadata") or metadata
        with RuntimeContext(env={}, transport=transport) as context:
            profile = {"client": client, "context": context, "asset_profile": "body"}
            if diagnostics.get("extracted_assets"):
                profile["assets"] = diagnostics["extracted_assets"]
            plan = plan_browser_asset_download(
                article_id=row["doi"],
                output_dir=output_dir,
                html_text=text,
                source_url=row["source_url"],
                profile=profile,
                deps=client.deps,
            )
        assets = plan.body_assets
        cb = plan.candidate_builder
    payload = RawFulltextPayload(
        provider=provider,
        content=ProviderContent(
            route_kind="html",
            source_url=row["source_url"],
            content_type="text/html",
            body=text.encode(),
            markdown_text=md,
            merged_metadata=metadata,
            diagnostics={"extraction": diagnostics},
            extracted_assets=assets,
        ),
    )
    return client, metadata, payload, assets, cb


def replay_royal_captured_viewer_assets(output_dir):
    """Two real viewer/image captures in a five-figure historical article.

    The image provenance masks its signature. Match the full object path and
    rendition to the signed URL in its captured viewer; this is offline response
    binding, not a fresh request or evidence that an old signature still works.
    """
    from pathlib import Path
    from paper_fetch.extraction.html.assets import (
        AssetDownloadOptions,
        FIGURE_KIND,
        download_assets,
    )
    from paper_fetch.extraction.html.assets.figures import (
        extract_full_size_figure_image_url,
    )
    from paper_fetch.providers.browser_workflow.assets import (
        _discover_browser_workflow_figure_originals,
    )
    from tests.golden_criteria import golden_criteria_asset
    from tests.support._paper_fetch_support import FixtureHtmlTransport
    from tests.support.acquired_publisher_inputs import _record, _response
    from functools import partial
    from tests.support.acquired_publisher_inputs import capture_url_identity

    _identity = partial(capture_url_identity, provider="royalsocietypublishing")

    doi = "10.1098/rsos.150470"
    captures = [
        "acquisition/requested-viewer-2026-09-16/",
        "acquisition/requested-viewer-missing-2026-09-16/",
    ]
    article_record, _ = _record(doi, captures[0] + "000-browser_rendered_dom.html")
    row = {
        "provider": "royalsocietypublishing",
        "doi": doi,
        "source_url": article_record["requested_url"],
    }
    transport = FixtureHtmlTransport({})
    _, _, _, current_assets, candidate_builder = extract_signed_fixture_payload(
        row,
        golden_criteria_asset(doi, captures[0] + "000-browser_rendered_dom.html"),
        transport,
        output_dir,
    )
    pages = {}
    image_records = []
    for prefix in captures:
        viewer_record, viewer = _record(doi, prefix + "001-browser_rendered_dom.html")
        image_record, image = _record(doi, prefix + "002-direct_http.jpeg")
        candidate = extract_full_size_figure_image_url(
            viewer.decode(), viewer_record["final_url"]
        )
        assert _identity(candidate) == _identity(image_record["requested_url"])
        assert image_record["status_code"] == 200
        transport.responses[candidate] = _response(image_record, image)
        pages[viewer_record["requested_url"]] = (
            viewer.decode(),
            viewer_record["final_url"],
        )
        selected = [
            a
            for a in current_assets
            if a.get("figure_page_url") == viewer_record["requested_url"]
        ]
        assert len(selected) == 1
        # Figure 1 already declares a direct original in the article; its
        # provider policy correctly does not revisit the viewer. Both captures
        # bind to that identical full-size object despite different signatures.
        requested_candidate = selected[0].get("full_size_url") or candidate
        assert _identity(requested_candidate) == _identity(candidate)
        transport.responses[requested_candidate] = _response(image_record, image)
        image_records.append(
            {
                "record": image_record,
                "viewer_record": viewer_record,
                "candidate": candidate,
                "requested_candidate": requested_candidate,
                "source_dom_id": selected[0]["dom_id"],
                "image": image,
            }
        )
    selected = [a for a in current_assets if a.get("figure_page_url") in pages]
    assert len(selected) == 2
    resolved = _discover_browser_workflow_figure_originals(
        selected, figure_page_fetcher=pages.get
    )
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=doi,
        assets=resolved,
        output_dir=output_dir,
        user_agent="offline captured viewer replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=candidate_builder,
            asset_download_concurrency=1,
            provider_name="royalsocietypublishing",
        ),
    )
    assert not result["asset_failures"], result["asset_failures"]
    assert len(result["assets"]) == 2
    by_viewer = {a["figure_page_url"]: a for a in result["assets"]}
    for capture in image_records:
        asset = by_viewer[capture["viewer_record"]["requested_url"]]
        assert Path(asset["path"]).read_bytes() == capture["image"]
        assert asset["download_tier"] == "full_size"
        capture["asset"] = asset
    assembled = [by_viewer.get(a.get("figure_page_url"), a) for a in current_assets]
    client, metadata, old_payload, _, _ = extract_signed_fixture_payload(
        row, golden_criteria_asset(doi, "original.html"), transport, output_dir
    )
    article = client.to_article_model(
        metadata, old_payload, downloaded_assets=assembled
    )
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    return article, markdown, image_records, transport.calls
