"""Offline acquisition replay; real source parsing and final model assembly."""

from dataclasses import replace
import json
from types import MethodType

from paper_fetch.providers import _elsevier_html
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import (
    ElsevierClient,
    extract_elsevier_asset_references,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.session_cache import CROSSREF_METADATA_KEY


class ReplayTransport:
    def __init__(self, xml_body):
        self.xml_body = xml_body

    def request(self, method, url, **kwargs):
        if url.startswith("https://api.elsevier.com/content/article/"):
            return {
                "url": url,
                "body": self.xml_body,
                "headers": {"content-type": "text/xml"},
                "status_code": 200,
            }
        if url == "https://api.crossref.org/works":
            message = {"items": []}
        elif url.startswith("https://api.crossref.org/works/"):
            from urllib.parse import unquote

            message = {"DOI": unquote(url.split("/works/", 1)[1])}
        else:
            raise AssertionError(f"Unexpected replay request: {url}")
        return {
            "url": url,
            "body": json.dumps({"message": message}).encode(),
            "headers": {"content-type": "application/json"},
            "status_code": 200,
        }


def replay_route(
    *, route, metadata, html_text, xml_body, output_dir, parent_crossref=None
):
    transport = ReplayTransport(xml_body)
    env = {"ELSEVIER_API_KEY": "replay"} if route == "xml" else {}
    client = ElsevierClient(transport, env)
    context = RuntimeContext(
        env={},
        transport=transport,
        download_dir=output_dir,
        clients={"crossref": CrossrefClient(transport, {})},
    )
    context.initialize_deadline(120)
    if parent_crossref is not None:
        context.set_session_cache(
            CROSSREF_METADATA_KEY.materialize(metadata["doi"]), parent_crossref
        )
    url = metadata["landing_page_url"]
    client.deps = replace(
        client.deps,
        load_runtime_config=lambda *a, **k: BrowserRuntimeConfig(
            provider="elsevier",
            doi=metadata["doi"],
            artifact_dir=output_dir,
            headless=True,
            user_agent=None,
            backend="byparr",
        ),
        ensure_runtime_ready=lambda config: None,
        fetch_html_with_browser=lambda *a, **k: BrowserFetchedHtml(
            url, url, html_text, 200, {}, metadata["title"], "", {}
        ),
    )

    def discover(
        self, doi, metadata, raw_payload, output_dir, *, asset_profile, context
    ):
        assets = (
            _elsevier_html.extract_assets(html_text, url, asset_profile=asset_profile)
            if route == "html"
            else extract_elsevier_asset_references(xml_body, xml_root=None)
        )
        return {"assets": assets, "asset_failures": []}

    client.download_related_assets = MethodType(discover, client)
    try:
        return client.fetch_result(
            metadata["doi"], metadata, output_dir, asset_profile="all", context=context
        )
    finally:
        context.close()
