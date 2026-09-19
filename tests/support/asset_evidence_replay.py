"""Offline reassembly using the bounded 2026-09-18 official asset captures."""

from dataclasses import asdict, replace

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.extraction.html.assets import merge_extracted_and_downloaded_assets
from paper_fetch.models import FetchEnvelope
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.plos import (
    PlosClient,
    parse_plos_xml,
    _plos_figure_candidates,
)
from paper_fetch.quality.assets import build_asset_quality_summary
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.golden_criteria import source_selections
from tests.paths import REPO_ROOT
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import (
    captured_body,
    capture_records,
    _response,
)
from tests.support.arxiv_graphic_replay import GRAPHIC_IDS, graphic_payload
from tests.support.captured_images import download_captured_images
from tests.support.signed_image_replay import (
    extract_signed_fixture_payload,
    replay_royal_captured_viewer_assets,
)


def captured_asset_transport(doi):
    responses = {}
    records = []
    for candidate in capture_records(doi):
        if "acquisition/asset-evidence-2026-09-18/" not in candidate.get(
            "original_body_file", candidate["body_file"]
        ):
            continue
        record = candidate
        body = captured_body(doi, record)
        responses[record["requested_url"]] = _response(record, body)
        records.append(record)
    return FixtureHtmlTransport(responses), records


def finish_asset_replay(article, output_dir, *, discovered=None, downloaded=None):
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    store = ArtifactStore.from_download_dir(output_dir)
    if discovered is None:
        store.audit_article_assets(article, asset_profile="body", archive_enabled=True)
    else:
        # The existing arXiv ArticleModel contains only downloaded assets. Audit
        # all actual source candidates, so this task never shrinks its denominator.
        article.quality.asset_summary = build_asset_quality_summary(
            merge_extracted_and_downloaded_assets(discovered, downloaded),
            asset_profile="body",
            archive_enabled=True,
            base_dir=output_dir,
        )
    envelope = FetchEnvelope(
        doi=article.doi,
        source=article.source,
        has_fulltext=article.quality.has_fulltext,
        article=article,
        markdown=markdown,
    )
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="body", require_local_body_assets=True
    )
    return article, markdown, acceptance


def replay_arxiv_captured_graphics(arxiv_id, output_dir):
    client, extracted, payload = graphic_payload(arxiv_id)
    transport, records = captured_asset_transport("10.48550/arxiv." + arxiv_id)
    client.transport = transport
    selected = [
        a
        for a in extracted.extracted_assets
        if a.get("image_id") in GRAPHIC_IDS[arxiv_id]
    ]
    restricted = replace(
        payload, content=replace(payload.content, extracted_assets=selected)
    )
    result = client.download_related_assets(
        "", {}, restricted, output_dir, asset_profile="body"
    )
    assert not result["asset_failures"], result
    assert len(result["assets"]) == len(selected)
    article = client.to_article_model(
        extracted.merged_metadata, payload, downloaded_assets=result["assets"]
    )
    article, markdown, acceptance = finish_asset_replay(
        article,
        output_dir,
        discovered=extracted.extracted_assets,
        downloaded=result["assets"],
    )
    return (
        article,
        markdown,
        acceptance,
        result["assets"],
        records,
        extracted.extracted_assets,
    )


def replay_completed_signed_paper(doi, output_dir):
    row = golden_criteria_sample_for_doi(doi)["signed_asset_replay"]
    empty = FixtureHtmlTransport({})
    _, _, _, candidates, _ = extract_signed_fixture_payload(
        row, REPO_ROOT / row["current_source"], empty, output_dir
    )
    if doi == "10.1098/rsos.150470":
        _, _, captures, _ = replay_royal_captured_viewer_assets(output_dir)
        existing = {
            capture["asset"]["figure_page_url"]: capture["asset"]
            for capture in captures
        }
        remaining = [a for a in candidates if a.get("figure_page_url") not in existing]
        downloaded = [
            *existing.values(),
            *download_captured_images(doi, remaining, output_dir),
        ]
    else:
        downloaded = download_captured_images(doi, candidates, output_dir)
    client, metadata, payload, old_candidates, _ = extract_signed_fixture_payload(
        row, REPO_ROOT / row["old_source"], empty, output_dir
    )
    article = client.to_article_model(metadata, payload, downloaded_assets=downloaded)
    article, markdown, acceptance = finish_asset_replay(article, output_dir)
    return article, markdown, acceptance, downloaded, row, old_candidates


def replay_plos_captured_inline_formulas(doi, output_dir):
    rows = source_selections()
    row = next((r for r in rows if r["doi"] == doi), None)
    if row is None:
        sample = golden_criteria_sample_for_doi(doi)
        row = {
            "source_url": sample["source_url"],
            "source": str(golden_criteria_asset(doi, "original.xml")),
        }
    body = (REPO_ROOT / row["source"]).read_bytes()
    extraction = parse_plos_xml(
        body, source_url=row["source_url"], base_metadata={"doi": doi}
    )
    assert extraction is not None
    transport, records = captured_asset_transport(doi)
    payload = RawFulltextPayload(
        provider="plos",
        content=ProviderContent(
            route_kind="xml",
            source_url=row["source_url"],
            body=body,
            content_type="text/xml",
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.metadata,
            extracted_assets=extraction.assets,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "references": extraction.references,
                    "semantic_losses": asdict(extraction.semantic_losses),
                }
            },
        ),
    )
    wanted = {record["requested_url"] for record in records}
    selected = [
        asset
        for asset in extraction.assets
        if wanted.intersection(
            _plos_figure_candidates(
                transport, asset=asset, user_agent="offline captured replay"
            )
        )
    ]
    client = PlosClient(transport, {})
    restricted = replace(
        payload, content=replace(payload.content, extracted_assets=selected)
    )
    result = client.download_related_assets(
        doi, extraction.metadata, restricted, output_dir, asset_profile="body"
    )
    assert not result["asset_failures"], result
    assert len(result["assets"]) == len(records)
    article = client.to_article_model(
        extraction.metadata, payload, downloaded_assets=result["assets"]
    )
    article, markdown, acceptance = finish_asset_replay(article, output_dir)
    return article, markdown, acceptance, result["assets"], records, extraction.assets
