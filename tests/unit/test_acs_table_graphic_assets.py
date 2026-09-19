"""ACS table graphic discovery preserves publisher URLs and scope."""

from paper_fetch.providers._acs_html import scoped_asset_extractor


def test_table_graphic_is_discovered_without_inventing_original_or_signature():
    url = "https://acs.silverchair-cdn.com/article/m_chemical.png?Expires=1&Signature=old&Key-Pair-Id=key"
    markup = f'''<div class="table-wrap"><div class="fig-graphic" id="gr8">
    <img src="{url}" path-from-xml="chemical.tif" alt="Graphic" />
    </div><div class="table-modal"><img src="{url}" /></div></div>'''
    assets = scoped_asset_extractor(
        markup, "https://pubs.acs.org/article", asset_profile="body"
    )
    assert len(assets) == 1
    assert assets[0]["dom_id"] == "gr8"
    assert assets[0]["preview_url"] == url
    assert not assets[0].get("full_size_url")
    assert assets[0]["section"] == "body"


def test_navigation_graphic_is_not_promoted_to_a_body_asset():
    markup = '<div class="fig-graphic" id="logo"><img src="/logo.png" /></div>'
    assert (
        scoped_asset_extractor(
            markup, "https://pubs.acs.org/article", asset_profile="body"
        )
        == []
    )


def test_old_table_graphic_markdown_binds_to_captured_current_rendition(tmp_path):
    from paper_fetch.providers.acs import AcsClient
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    old_url = (
        "https://acs.silverchair-cdn.com/article/m_chemical.png?Expires=1&Signature=old"
    )
    new_url = (
        "https://acs.silverchair-cdn.com/article/m_chemical.png?Expires=2&Signature=new"
    )
    markup = f'<div class="table-wrap"><div class="fig-graphic" id="gr8"><img src="{new_url}" alt="Graphic" /></div></div>'
    asset = scoped_asset_extractor(
        markup, "https://pubs.acs.org/article", asset_profile="body"
    )[0]
    # This boundary mock proves link binding, not image availability or decoding.
    asset["path"] = str(tmp_path / "chemical.png")
    metadata = {"doi": "10.1021/example", "title": "Chemical study"}
    payload = RawFulltextPayload(
        provider="acs",
        content=ProviderContent(
            route_kind="html",
            source_url="https://pubs.acs.org/article",
            content_type="text/html",
            body=b"",
            markdown_text=f"# Chemical study\n\n## Results\n\n{'Measured result. ' * 100}\n\n![Graphic]({old_url})",
            merged_metadata=metadata,
        ),
    )
    article = AcsClient(FixtureHtmlTransport({}), {}).to_article_model(
        metadata, payload, downloaded_assets=[asset]
    )
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    assert asset["path"] in rendered
    assert old_url not in rendered
