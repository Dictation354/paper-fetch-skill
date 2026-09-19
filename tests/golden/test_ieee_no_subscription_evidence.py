"""Real current subscription landings, distinct from REST/PDF denial samples."""

import json
from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup

from paper_fetch.quality.access_boundary import html_paywall_diagnostics
from tests.golden_criteria import golden_criteria_asset
from tests.support.acquired_publisher_inputs import _record

PREFIX = "acquisition/no-subscription-2026-09-16/"


@pytest.mark.parametrize(
    "doi,number",
    [
        ("10.1109/PGEC.1967.264619", "4038993"),
        ("10.1109/TBME.2024.3434477", "10612240"),
    ],
)
def test_unsubscribed_landing_is_same_paper_gate_without_downstream_denial_claim(
    doi, number
):
    capture = json.loads(
        golden_criteria_asset(doi, PREFIX + "collection.json").read_text()
    )
    record, dom = _record(doi, capture["dom_file"])
    assert record["capture_kind"] == "browser_rendered_dom"
    assert record["status_code"] is None
    response, _ = _record(doi, PREFIX + "001-http_response_entity.bin")
    assert response["status_code"] == 200
    soup = BeautifulSoup(dom, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    visible = soup.get_text(" ", strip=True)
    assert "Sign In or Purchase" in visible
    assert "Access provided by:" not in visible
    assert soup.select_one("#article") is None
    gate = html_paywall_diagnostics(
        dom, metadata={"doi": doi}, source_url=capture["final_url"], provider="ieee"
    )
    assert gate["confirmed_article_paywall"]["doi"] == doi.lower()
    assert gate["confirmed_article_paywall"]["basis"] == "Sign In or Purchase"
    assert gate["content_kind"] == "abstract_only"
    assert gate["received_metadata"]["abstract"]
    assert capture["stop_reason"] == "confirmed_article_paywall"
    assert capture["explicit_followup_requests"] == []
    requests = [urlsplit(item["url"]).path for item in capture["browser_requests"]]
    assert not any(
        "/stamp/" in path or path.endswith("/references") for path in requests
    )
    rest_paths = {path for path in requests if "/rest/document/" in path}
    expected = {f"/rest/document/{number}/toc", f"/rest/document/{number}/similar"}
    if number == "10612240":
        expected.add(f"/rest/document/{number}/snippet")
    assert rest_paths == expected
    assert not any(path.rstrip("/") == f"/rest/document/{number}" for path in requests)
    # The older institutional-access observation remains a separate counterexample.
    old, old_dom = _record(
        doi, "acquisition/known-gaps-2026-09-16/000-browser_rendered_dom.html"
    )
    assert not html_paywall_diagnostics(
        old_dom, metadata={"doi": doi}, source_url=old["final_url"], provider="ieee"
    )
