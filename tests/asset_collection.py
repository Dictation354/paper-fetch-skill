"""Offline discovery of the fixed asset collection using existing provider owners."""

import json
from pathlib import Path
from paper_fetch.providers import (
    _annualreviews_html,
    _mdpi_assets,
    _springer_assets,
    elsevier,
)
from tests.golden_criteria import golden_criteria_sample_for_doi


def discover_assets(row):
    doi = row["doi"]
    raw = Path(row["source_input"]).read_text()
    source_url = row["source_url"]
    from paper_fetch.providers import (
        copernicus,
        frontiers,
        plos,
        _oxfordacademic_html,
        _royalsocietypublishing_html,
        _ieee_html,
    )
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml
    from paper_fetch.providers.browser_workflow.asset_download import (
        plan_browser_asset_download,
    )
    from paper_fetch.runtime import RuntimeContext
    from tests.support.acquired_article_assets import CLIENTS
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    s = golden_criteria_sample_for_doi(doi)
    provider = row["provider"]
    if provider == "elsevier":
        return [
            dict(
                a,
                kind=elsevier.elsevier_asset_result_kind(a["asset_type"]),
                url=a["source_url"],
                section=elsevier.elsevier_asset_result_section(a["asset_type"]),
            )
            for a in elsevier.extract_elsevier_asset_references(raw.encode())
        ]
    if provider in {"plos", "frontiers", "copernicus"}:
        parser = (
            copernicus.parse_copernicus_xml
            if provider == "copernicus"
            else parse_jats_xml
        )
        assets = parser(
            raw.encode(), source_url=source_url, base_metadata={"doi": doi}
        ).assets
        if provider == "frontiers":
            assets = frontiers._normalize_frontiers_extracted_assets(
                assets, doi=doi, landing_url=s.get("landing_url", source_url)
            )[0]
        if provider == "plos":
            for a in assets:
                url = a.get("url") or a.get("original_url") or ""
                aid = url.removeprefix("info:doi/")
                if not aid:
                    continue
                if a["kind"] == "supplementary":
                    a["url"] = plos._plos_supplementary_file_url(aid)
                elif a["kind"] == "formula":
                    a["url"] = plos._plos_formula_image_url(aid)
                elif a["kind"] in {"figure", "table"}:
                    a["url"] = plos._plos_figure_image_url(aid)
        for a in assets:
            if not a.get("url"):
                a["url"] = a.get("original_url") or a.get("link")
        return assets
    owner = {
        "annualreviews": _annualreviews_html,
        "mdpi": _mdpi_assets,
        "springer": _springer_assets,
    }.get(provider)
    if owner:
        return (
            owner.extract_html_assets
            if provider == "springer"
            else owner.extract_scoped_html_assets
        )(raw, source_url, asset_profile="all")
    if provider == "oxfordacademic":
        return _oxfordacademic_html.extract_markdown(
            raw, source_url, metadata={"doi": doi}, asset_profile="all"
        ).extracted_assets
    if provider == "royalsocietypublishing":
        return _royalsocietypublishing_html.extract_markdown(
            raw, source_url, asset_profile="all"
        ).extracted_assets
    if provider == "ieee":
        assets = _ieee_html._extract_ieee_html(
            raw, source_url, metadata={"doi": doi}
        ).extracted_assets
        if "multimedia.json" in s["assets"]:
            from paper_fetch.providers._ieee_supplementary import (
                _supplementary_assets_from_ieee_multimedia_payload,
            )

            assets += _supplementary_assets_from_ieee_multimedia_payload(
                json.loads(Path(s["assets"]["multimedia.json"]).read_text()),
                source_url=source_url,
            )
        return assets
    transport = FixtureHtmlTransport({})
    client = CLIENTS[provider](transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        plan = plan_browser_asset_download(
            article_id=doi,
            output_dir=Path("."),
            html_text=raw,
            source_url=source_url,
            profile={
                "client": client,
                "context": context,
                "asset_profile": "body" if provider == "iop" else "all",
            },
            deps=client.deps,
        )
    return plan.body_assets + plan.supplementary_assets


def source_markdown(row):
    """Use real source extraction; do not manufacture an asset-only article."""
    from paper_fetch.providers import (
        copernicus,
        frontiers,
        _springer_html,
        _oxfordacademic_html,
        _royalsocietypublishing_html,
        _ieee_html,
    )
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from tests.support.acquired_article_assets import CLIENTS
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    raw = Path(row["source_input"]).read_text()
    provider, doi, url = row["provider"], row["doi"], row["source_url"]
    metadata = {
        "doi": doi,
        "title": golden_criteria_sample_for_doi(doi).get("title", doi),
    }
    if provider == "elsevier":
        payload = RawFulltextPayload(
            provider=provider,
            content=ProviderContent(
                route_kind="xml",
                source_url=url,
                content_type="text/xml",
                body=raw.encode(),
                merged_metadata=metadata,
            ),
        )
        article = elsevier.ElsevierClient(
            FixtureHtmlTransport({}), {}
        ).to_article_model(metadata, payload)
        return article.to_ai_markdown(
            include_refs="none", max_tokens="full_text", asset_profile="all"
        )
    if provider in {"plos", "frontiers", "copernicus"}:
        parser = (
            copernicus.parse_copernicus_xml
            if provider == "copernicus"
            else parse_jats_xml
        )
        extraction = parser(raw.encode(), source_url=url, base_metadata=metadata)
        markdown = extraction.markdown_text
        if provider == "frontiers":
            _, replacements = frontiers._normalize_frontiers_extracted_assets(
                extraction.assets, doi=doi, landing_url=url
            )
            markdown = frontiers._replace_markdown_urls(markdown, replacements)
        return markdown
    if provider == "springer":
        return _springer_html.extract_html_payload(raw, url, title=metadata["title"])[
            "markdown_text"
        ]
    if provider == "oxfordacademic":
        return _oxfordacademic_html.extract_markdown(
            raw, url, metadata=metadata
        ).markdown_text
    if provider == "royalsocietypublishing":
        return _royalsocietypublishing_html.extract_markdown(raw, url).markdown_text
    if provider == "ieee":
        return _ieee_html._extract_ieee_html(raw, url, metadata=metadata).markdown_text
    return CLIENTS[provider](FixtureHtmlTransport({}), {}).extract_markdown(
        raw, url, metadata=metadata
    )[0]
