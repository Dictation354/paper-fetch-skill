"""Captured stamp wrapper and PDF prove source identity, not PDF formatting."""

import hashlib
import json
from types import SimpleNamespace
from urllib.parse import urlsplit

from paper_fetch.providers import _pdf_common, _pdf_fallback
from paper_fetch.providers._ieee_pdf import iframe_pdf_candidates
from tests.paths import REPO_ROOT
from tests.support.verified_source_inputs import inspect_original


def test_real_ieee_wrapper_maps_to_identity_verified_pdf(tmp_path, monkeypatch):
    base = REPO_ROOT / "tests/fixtures/golden_criteria/10.1109_MPER.1985.5526567"
    folder = base / "acquisition/source-completion-2026-09-18"
    wrapper = folder / "010-user-followup-browser_iframe_no_click_result_dom.html"
    pdf = folder / "009-user-followup-browser_iframe_no_click_pdf_response.pdf"
    records = json.loads((base / "acquisition/provenance.json").read_text())["records"]
    captured = {}
    for path in (wrapper, pdf):
        record = next(
            r for r in records if r["body_file"] == str(path.relative_to(base))
        )
        assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert record["doi"] == "10.1109/MPER.1985.5526567"
        captured[path] = record
    # Capture diagnostics redact query strings. Restore only the known article
    # number for wrapper matching; the iframe URL itself comes from raw HTML.
    wrapper_url = captured[wrapper]["final_url"] + "?arnumber=5526567"
    candidates = iframe_pdf_candidates(wrapper.read_text(), wrapper_url)
    assert len(candidates) == 1
    pdf_url = candidates[0]
    assert urlsplit(pdf_url)._replace(query="").geturl() == captured[pdf]["final_url"]
    identity = inspect_original(
        pdf.read_bytes(), "ieee", "10.1109/MPER.1985.5526567", pdf_url
    )
    assert identity and identity["identity"] == "matched"
    assert identity["pages"] == 1
    assert identity["title"] == (
        "Network Observability: Identification of Observable Islands and Measurement Placement"
    )
    monkeypatch.setattr(
        _pdf_common,
        "render_pdf_markdown_result",
        lambda *a, **kw: _pdf_common.PdfMarkdownRenderResult(
            markdown_text="Opaque converter result", assets=[]
        ),
    )
    result = _pdf_fallback._response_to_pdf_result(
        SimpleNamespace(
            headers={"content-type": "application/pdf"}, body=pdf.read_bytes
        ),
        artifact_dir=tmp_path,
        source_url=pdf_url,
        final_url=pdf_url,
        request=_pdf_fallback.PdfRequestContext(
            expected_identity={"doi": "10.1109/MPER.1985.5526567"}, provider_name="ieee"
        ),
    )
    assert result is not None
    assert result.pdf_bytes == pdf.read_bytes()
    assert result.final_url == pdf_url
    assert result.diagnostics["identity"]["status"] == "match"
    assert result.diagnostics["pdf_pages"] == 1
    assert result.markdown_text == "Opaque converter result"
