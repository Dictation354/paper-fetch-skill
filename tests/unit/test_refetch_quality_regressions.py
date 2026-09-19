"""Small scenarios for the N1–N6 refetch findings."""

from pathlib import Path

from markdown_it import MarkdownIt
import pytest

from paper_fetch.models import FetchEnvelope, article_from_markdown
from paper_fetch.providers._arxiv_metadata import _merge_arxiv_metadata_layers
from paper_fetch.providers._acs_html import scoped_asset_extractor
from paper_fetch.providers._springer_markdown import extract_html_payload
from paper_fetch.providers.acs import AcsClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow.assets import (
    _merge_download_attempt_results,
)
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.quality.assets import build_asset_quality_summary
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._paper_fetch_support import FixtureHtmlTransport


def headings(markdown):
    if markdown.startswith("---\n"):
        markdown = markdown.split("\n---\n", 1)[1]
    tokens = MarkdownIt().parse(markdown)
    return [
        tokens[i + 1].content
        for i, token in enumerate(tokens)
        if token.type == "heading_open"
    ]


@pytest.mark.parametrize(
    "html, api, expected",
    [
        (["A. Author"], ["Alice Author", "Bob Writer"], ["Alice Author", "Bob Writer"]),
        (
            ["A. Author", "B. Writer"],
            ["Alice Author", "Bob Writer"],
            ["A. Author", "B. Writer"],
        ),
        (["A. Author", "B. Writer"], ["Alice Author"], ["A. Author", "B. Writer"]),
        ([], ["Alice Author"], ["Alice Author"]),
        (["A. Author"], [], ["A. Author"]),
    ],
)
def test_arxiv_author_lists_are_complete_without_combining_spellings(
    html, api, expected
):
    merged = _merge_arxiv_metadata_layers(
        {"arxiv_id": "1406.2661v1"},
        html_metadata={"authors": html},
        api_metadata={"authors": api},
    )
    assert merged["authors"] == expected


@pytest.mark.parametrize("profile", ["none", "body"])
@pytest.mark.parametrize("outside_main", [False, True])
def test_springer_excluded_table_survives_prepare_and_final_render(
    profile, outside_main
):
    table = '<figure class="c-article-table"><figcaption class="c-article-table__figcaption">Extended Data Table 1 Observed water yield</figcaption><a data-test="table-link" href="/articles/example/tables/1">Full size table</a></figure>'
    html = '<article><div class="c-article-body"><div class="main-content"><p>Measured result.</p>'
    html += (
        "</div><section>" + table + "</section>" if outside_main else table + "</div>"
    )
    html += "</div></article>"
    url = "https://www.nature.com/articles/example"
    transport = FixtureHtmlTransport({})  # Any table download is unexpected.
    with RuntimeContext(env={}, transport=transport) as context:
        client = SpringerClient(transport, {})
        prepared, entries, warnings, assets = client._prepare_html_with_inline_tables(
            html,
            url,
            context=context,
            asset_profile=profile,
        )
    assert not entries and not warnings and not assets
    extraction = extract_html_payload(prepared, url)
    article = article_from_markdown(
        source="springer_html",
        doi=None,
        metadata={"title": "Study"},
        markdown_text=extraction["markdown_text"],
        section_hints=extraction["section_hints"],
    )
    md = article.to_ai_markdown(asset_profile=profile, max_tokens="full_text")
    assert md.count("Extended Data Table 1 Observed water yield") == 1
    assert (
        "[Extended Data Table 1 Observed water yield](https://www.nature.com/articles/example/tables/1)"
        in md
    )


@pytest.mark.parametrize(
    "title",
    [
        "First report of\n<i>Species name</i>\nin the region",
        "Effects of\n<i>Species name</i>\noil",
        "Decoupling\nthe Responses at an Interface",
    ],
)
def test_html_multiline_metadata_title_is_one_final_heading(title):
    client = AcsClient(FixtureHtmlTransport({}), {})
    metadata = {"doi": "10.1021/example", "title": title}
    payload = RawFulltextPayload(
        provider="acs",
        content=ProviderContent(
            route_kind="html",
            content_type="text/html",
            source_url="https://pubs.acs.org/article",
            body=b"",
            markdown_text="## Results\n\nMeasured result.",
            merged_metadata=metadata,
        ),
    )
    article = client.to_article_model(metadata, payload)
    assert headings(article.to_ai_markdown(max_tokens="full_text"))[0] == " ".join(
        title.split()
    )


def test_acs_multiline_heading_keeps_complete_text():
    title = "4.1. C–N\nCoupling Using <i>Carbon</i>\nNanomaterials"
    html = f'<html><head><meta name="citation_title" content="Catalyst study"></head><body><div class="article-body"><h3>{title}</h3><p>{"Measured reaction yield. " * 90}</p></div></body></html>'
    client = AcsClient(FixtureHtmlTransport({}), {})
    md, _ = client.extract_markdown(
        html, "https://pubs.acs.org/article", metadata={"title": "Catalyst study"}
    )
    heading = next(h for h in headings(md) if h.startswith("4.1."))
    assert "Nanomaterials" in heading
    assert "C–N Coupling Using Carbon Nanomaterials" in heading


@pytest.mark.parametrize("missing_table", [False, True])
def test_acs_distinct_table_downloads_survive_merging_and_strict_acceptance(
    tmp_path, missing_table
):
    url = "https://pubs.acs.org/article"
    markup = "".join(
        f'<div class="table-wrap"><div class="table-wrap-title"><span class="label">Table {i}.</span><div class="caption">Reaction {i}</div></div><div class="fig-graphic" id="gr{i}"><img src="https://acs.silverchair-cdn.com/article/m_{i}.png?Signature=old" alt="Graphic"/></div></div>'
        for i in (2, 3)
    )
    assets = scoped_asset_extractor(markup, url, asset_profile="body")
    assert len(assets) == 2
    for i, asset in enumerate(assets):
        asset["path"] = str(tmp_path / f"{i}.png")
        Path(asset["path"]).write_bytes(b"local asset boundary")
    result = _merge_download_attempt_results({"assets": assets}, {"assets": []})
    assert len(result["assets"]) == 2
    if missing_table:
        result["assets"][0].pop("path")
    metadata = {"doi": "10.1021/example", "title": "Study"}
    md = (
        "## Results\n\n"
        + "Measured result. " * 100
        + "\n\n"
        + "\n\n".join(f"![Graphic]({asset['preview_url']})" for asset in assets)
    )
    client = AcsClient(FixtureHtmlTransport({}), {})
    article = client.to_article_model(
        metadata,
        RawFulltextPayload(
            provider="acs",
            content=ProviderContent(
                route_kind="html",
                source_url=url,
                content_type="text/html",
                body=b"",
                markdown_text=md,
                merged_metadata=metadata,
            ),
        ),
        downloaded_assets=result["assets"],
    )
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    assert len(article.assets) == 2
    if not missing_table:
        assert "silverchair-cdn.com" not in rendered
        assert all(asset["path"] in rendered for asset in result["assets"])
    article.quality.asset_summary = build_asset_quality_summary(
        article.assets, asset_profile="body", archive_enabled=True
    )
    acceptance = evaluate_fetch_acceptance(
        FetchEnvelope(
            doi=metadata["doi"],
            source=article.source,
            article=article,
            has_fulltext=True,
        ),
        asset_profile="body",
        require_local_body_assets=True,
    )
    assert acceptance.asset.body_discovered == 2
    assert acceptance.asset.body_local == (1 if missing_table else 2)
    assert acceptance.asset.local_body_assets_satisfied is (not missing_table)
    if missing_table:
        assert acceptance.overall != "complete"


@pytest.mark.parametrize("number", ["5526567", "4038993"])
def test_ieee_bad_gateway_reaches_existing_browser_pdf_route(monkeypatch, number):
    from paper_fetch.providers import ieee, _ieee_metadata
    from paper_fetch.providers._pdf_fallback import PdfFetchFailure, PdfFetchResult
    from unittest.mock import Mock

    doi = "10.1109/example." + number
    url = "https://ieeexplore.ieee.org/document/" + number + "/"
    transport = FixtureHtmlTransport({})
    client = ieee.IeeeClient(transport, {})
    failure = PdfFetchFailure(
        "pdf_download_failed", "HTTP 502", details={"status": 502}
    )
    direct = Mock(side_effect=failure)
    recovered = Mock(
        return_value=PdfFetchResult(
            source_url=url,
            final_url=url,
            pdf_bytes=b"opaque provider boundary",
            markdown_text="Opaque converter output",
            suggested_filename="article.pdf",
            diagnostics={
                "identity": {"status": "match"},
                "browser_pdf_response": "ieee_article_click",
            },
        )
    )
    monkeypatch.setattr(ieee, "fetch_pdf_over_http", direct)
    monkeypatch.setattr(ieee, "fetch_pdf_with_browser", recovered)
    attempt = _ieee_metadata.IeeeLandingAttempt(
        normalized_doi=doi,
        landing_url=url,
        response_url=url,
        html_text="",
        merged_metadata={"doi": doi, "article_number": number},
        article_number=number,
        landing_metadata={},
    )
    with RuntimeContext(env={}, transport=transport) as context:
        payload = client._fetch_pdf_payload(
            attempt,
            html_failure_message="HTML unavailable",
            warnings=[],
            context=context,
        )
    recovered.assert_called_once()
    assert recovered.call_args.kwargs["request"].expected_identity == {"doi": doi}
    assert payload.content.route_kind == "pdf_fallback"
    assert (
        payload.content.diagnostics["pdf_fallback"]["browser_pdf_response"]
        == "ieee_article_click"
    )
    assert (
        payload.content.diagnostics["pdf_fallback"]["direct_failure"]["details"][
            "status"
        ]
        == 502
    )
