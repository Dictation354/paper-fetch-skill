from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from tests.script_modules import load_script_module


REPO_ROOT = Path(__file__).resolve().parents[2]


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "doi": "10.1234/example",
        "provider": "examplepub",
        "via": "http",
        "purpose": "structure",
        "from_manifest": None,
        "all": False,
        "retry_via": None,
        "auto_via": False,
        "fail_fast": False,
        "dry_run": False,
        "output_dir": str(tmp_path),
        "force": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _write_provider_manifest(
    path: Path,
    *,
    provider: str = "mdpi",
    doi: str | None = "10.3390/membranes15030093",
    requires_browser_runtime: bool = False,
) -> None:
    rendered_doi = "null" if doi is None else f'"{doi}"'
    rendered_browser = "true" if requires_browser_runtime else "false"
    path.write_text(
        f"""
name: {provider}
routing:
  primary: doi_prefix
  doi_prefixes:
    - "10.3390/"
probe:
  requires_browser_runtime: {rendered_browser}
fixtures:
  doi_samples:
    structure:
      doi: {rendered_doi}
      evidence_url: "https://example.test/article"
      evidence_reason: "Sample covers structure capture."
      observed_signals:
        - body_sections
      confidence: high
""",
        encoding="utf-8",
    )


def _write_access_review(path: Path, *, provider: str, runtimes: list[str]) -> None:
    rendered_runtimes = "\n".join(f"  - {runtime}" for runtime in runtimes)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
schema_version: 1
provider: {provider}
status: approved
allowed_runtimes:
{rendered_runtimes}
""",
        encoding="utf-8",
    )


def _write_pdf_fallback_manifest(
    path: Path,
    *,
    provider: str = "oxfordacademic",
    observed_signals: list[str] | None = None,
) -> str:
    pdf_url = "https://academic.oup.com/bioinformatics/article-pdf/36/11/3409/50670673/bioinformatics_36_11_3409.pdf"
    rendered_signals = "\n".join(
        f"        - {signal}" for signal in (observed_signals or ["pdf_link"])
    )
    path.write_text(
        f"""
name: {provider}
routing:
  primary: doi_prefix
  doi_prefixes:
    - "10.1093/"
probe:
  requires_browser_runtime: false
fixtures:
  doi_samples:
    pdf_fallback:
      doi: "10.1093/bioinformatics/btaa161"
      evidence_url: "{pdf_url}"
      evidence_reason: "Public article-pdf route."
      observed_signals:
{rendered_signals}
      confidence: medium
""",
        encoding="utf-8",
    )
    return pdf_url


def test_capture_fixture_writes_fixture_manifest_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script_module("capture_fixture")

    class FakeTransport:
        def request(self, method: str, url: str, **kwargs: object) -> dict[str, object]:
            assert method == "GET"
            assert url == "https://doi.org/10.1234/example"
            headers = kwargs.get("headers")
            assert isinstance(headers, dict)
            assert "Chrome/" in headers["User-Agent"]
            return {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": b"<html><title>Fixture</title></html>",
                "url": "https://publisher.test/article",
                "status_code": 200,
            }

    monkeypatch.setattr(module, "HttpTransport", FakeTransport)

    summary = module.capture_fixture(_args(tmp_path))

    fixture_path = (
        tmp_path
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / "10.1234_example"
        / "original.html"
    )
    manifest_path = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert fixture_path.read_bytes() == b"<html><title>Fixture</title></html>"
    assert (
        summary["fixture_path"]
        == "tests/fixtures/golden_criteria/10.1234_example/original.html"
    )
    assert summary["content_type"] == "text/html; charset=utf-8"
    assert summary["bytes"] == len(b"<html><title>Fixture</title></html>")
    assert manifest["samples"]["10.1234_example"]["expected_outcome"] == "pending"
    assert manifest["samples"]["10.1234_example"]["purpose"] == "structure"
    assert (
        manifest["samples"]["10.1234_example"]["assets"]["original.html"]
        == summary["fixture_path"]
    )


def test_capture_fixture_http_follows_location_redirects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    seen_urls: list[str] = []

    class RedirectTransport:
        def request(self, method: str, url: str, **kwargs: object) -> dict[str, object]:
            assert method == "GET"
            seen_urls.append(url)
            if url == "https://doi.org/10.1234/example":
                return {
                    "headers": {"Location": "/article"},
                    "body": b"<html>moved</html>",
                    "url": "https://publisher.test/doi/10.1234/example",
                    "status_code": 302,
                }
            assert url == "https://publisher.test/article"
            return {
                "headers": {"content-type": "text/html"},
                "body": b"<html><title>Fixture</title></html>",
                "url": "",
                "status_code": 200,
            }

    monkeypatch.setattr(module, "HttpTransport", RedirectTransport)

    summary = module.capture_fixture(_args(tmp_path))

    assert seen_urls == [
        "https://doi.org/10.1234/example",
        "https://publisher.test/article",
    ]
    assert summary["manifest_entry"]["source_url"] == "https://publisher.test/article"


def test_capture_fixture_dry_run_does_not_fetch_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script_module("capture_fixture")

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("dry-run must not fetch")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(_args(tmp_path, doi="10.0000/probe", dry_run=True))

    assert summary["dry_run"] is True
    assert summary["bytes"] == 0
    assert summary["would_write"]
    assert not (tmp_path / "tests").exists()


def test_capture_fixture_refuses_to_overwrite_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script_module("capture_fixture")

    fixture_dir = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "10.1234_example"
    )
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "original.html").write_text("old", encoding="utf-8")

    class FakeTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"new",
                "url": "https://example.test",
            }

    monkeypatch.setattr(module, "HttpTransport", FakeTransport)

    with pytest.raises(module.CaptureFixtureError) as exc_info:
        module.capture_fixture(_args(tmp_path))
    assert exc_info.value.code == "UNSUITABLE_DOI_SAMPLE"


def test_capture_fixture_reuses_existing_manifest_sample_for_duplicate_purpose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    fixture_path = (
        tmp_path
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / "10.1234_example"
        / "original.html"
    )
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text("<html>existing article</html>", encoding="utf-8")
    manifest_path = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            {
                "samples": {
                    "10.1234_example": {
                        "doi": "10.1234/example",
                        "publisher": "examplepub",
                        "content_type": "text/html",
                        "route_kind": "html",
                        "assets": {
                            "original.html": str(fixture_path.relative_to(tmp_path))
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError(
                "existing duplicate fixture must be reused without fetching"
            )

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(_args(tmp_path))

    assert summary["status"] == "OK"
    assert summary["reused"] is True
    assert summary["capture_route"] == "reused"
    assert summary["bytes"] == len("<html>existing article</html>")


def test_capture_fixture_rejects_existing_route_mismatch_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    fixture_path = (
        tmp_path
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / "10.1234_example"
        / "original.html"
    )
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text("<html>existing article</html>", encoding="utf-8")
    manifest_path = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            {
                "samples": {
                    "10.1234_example": {
                        "doi": "10.1234/example",
                        "publisher": "examplepub",
                        "content_type": "text/html",
                        "route_kind": "html",
                        "assets": {
                            "original.html": str(fixture_path.relative_to(tmp_path))
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("route mismatch must fail before fetching")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    with pytest.raises(module.CaptureFixtureError) as exc_info:
        module.capture_fixture(_args(tmp_path, purpose="pdf_fallback"))

    assert exc_info.value.code == "UNSUITABLE_DOI_SAMPLE"
    assert "route_kind='html'" in exc_info.value.message


def test_capture_fixture_routes_block_purpose_to_block_fixture_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script_module("capture_fixture")

    class FakeTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"<html>gate</html>",
                "url": "https://example.test",
            }

    monkeypatch.setattr(module, "HttpTransport", FakeTransport)

    summary = module.capture_fixture(_args(tmp_path, purpose="access-gate"))

    assert summary["route"] == "block"
    assert (
        tmp_path / "tests" / "fixtures" / "block" / "10.1234_example" / "raw.html"
    ).is_file()
    manifest = json.loads(
        (
            tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
        ).read_text()
    )
    assert manifest["samples"]["10.1234_example"]["fixture_family"] == "block"


def test_capture_fixture_reads_doi_and_evidence_from_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "mdpi.yml"
    _write_provider_manifest(manifest_path)

    class FakeTransport:
        def request(self, method: str, url: str, **kwargs: object) -> dict[str, object]:
            assert method == "GET"
            assert url == "https://example.test/article"
            return {
                "headers": {"content-type": "text/html"},
                "body": b"<html><body><article>Full article body</article></body></html>",
                "url": "https://www.mdpi.com/10.3390/membranes15030093",
                "status_code": 200,
            }

    monkeypatch.setattr(module, "HttpTransport", FakeTransport)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            from_manifest=str(manifest_path),
            purpose="structure",
        ),
    )

    assert summary["doi"] == "10.3390/membranes15030093"
    assert summary["provider"] == "mdpi"
    assert summary["manifest_sample"]["evidence_url"] == "https://example.test/article"
    assert summary["evidence_confidence"] == "high"
    assert summary["provider_routing"]["primary"] == "doi_prefix"


def test_capture_fixture_auto_via_selects_browser_for_browser_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "mdpi.yml"
    _write_provider_manifest(manifest_path, requires_browser_runtime=True)

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("dry-run must not fetch")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            from_manifest=str(manifest_path),
            purpose="structure",
            dry_run=True,
            auto_via=True,
        ),
    )

    assert summary["capture_route"] == "browser"


def test_capture_fixture_auto_via_defaults_to_http_for_non_browser_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "newpub.yml"
    _write_provider_manifest(
        manifest_path,
        provider="newpub",
        doi="10.1234/example",
        requires_browser_runtime=False,
    )

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("dry-run must not fetch")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            from_manifest=str(manifest_path),
            purpose="structure",
            dry_run=True,
            auto_via=True,
        ),
    )

    assert summary["capture_route"] == "http"


def test_capture_fixture_auto_via_selects_browser_for_pdf_fallback_http_403_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    access_dir = tmp_path / "access-reviews"
    _write_access_review(
        access_dir / "oxfordacademic.yml",
        provider="oxfordacademic",
        runtimes=["http", "browser"],
    )
    monkeypatch.setattr(module, "ACCESS_REVIEW_DIR", access_dir)
    manifest_path = tmp_path / "oxfordacademic.yml"
    _write_pdf_fallback_manifest(
        manifest_path,
        observed_signals=["pdf_link", "http_403", "browser_public_pdf"],
    )

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            purpose="pdf_fallback",
            from_manifest=str(manifest_path),
            dry_run=True,
            auto_via=True,
        )
    )

    assert summary["capture_route"] == "browser"
    assert summary["content_type"] == "application/pdf"
    assert summary["manifest_entry"]["content_type"] == "application/pdf"
    assert summary["fixture_path"] == (
        "tests/fixtures/golden_criteria/10.1093_bioinformatics_btaa161/original.pdf"
    )


def test_capture_fixture_auto_via_retries_403_with_browser_pdf_and_keeps_stable_source_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    access_dir = tmp_path / "access-reviews"
    _write_access_review(
        access_dir / "oxfordacademic.yml",
        provider="oxfordacademic",
        runtimes=["http", "browser"],
    )
    monkeypatch.setattr(module, "ACCESS_REVIEW_DIR", access_dir)
    manifest_path = tmp_path / "oxfordacademic.yml"
    pdf_url = _write_pdf_fallback_manifest(manifest_path, observed_signals=["pdf_link"])
    final_token_url = (
        "https://watermark02.silverchair.com/tokenized.pdf?token=short-lived"
    )

    class ForbiddenTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"<html><body>Forbidden</body></html>",
                "url": pdf_url,
                "status_code": 403,
            }

    def fake_capture_browser(*_args: object, **kwargs: object) -> dict[str, object]:
        assert kwargs["url"] == pdf_url
        assert kwargs["purpose"] == "pdf_fallback"
        return {
            "headers": {"content-type": "application/pdf"},
            "body": b"%PDF-1.4\n%%EOF\n",
            "url": final_token_url,
            "status_code": 200,
        }

    monkeypatch.setattr(module, "HttpTransport", ForbiddenTransport)
    monkeypatch.setattr(module, "_capture_browser", fake_capture_browser)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            purpose="pdf_fallback",
            from_manifest=str(manifest_path),
            auto_via=True,
        )
    )

    fixture_path = (
        tmp_path
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / "10.1093_bioinformatics_btaa161"
        / "original.pdf"
    )
    manifest = json.loads(
        (
            tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
        ).read_text()
    )
    entry = manifest["samples"]["10.1093_bioinformatics_btaa161"]

    assert summary["capture_route"] == "browser"
    assert summary["capture_final_url"] == final_token_url
    assert fixture_path.read_bytes().startswith(b"%PDF-")
    assert entry["route_kind"] == "pdf_fallback"
    assert entry["assets"]["original.pdf"] == summary["fixture_path"]
    assert entry["source_url"] == pdf_url
    assert (
        entry["diagnostics"]["browser_final_url"]
        == "https://watermark02.silverchair.com/tokenized.pdf"
    )
    assert entry["diagnostics"]["browser_final_url_redacted"] is True


def test_capture_fixture_skips_manifest_null_doi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "mdpi.yml"
    _write_provider_manifest(manifest_path, doi=None)

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("null DOI sample must skip without fetching")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            from_manifest=str(manifest_path),
            purpose="structure",
        ),
    )

    assert summary["status"] == "SKIPPED"
    assert summary["skipped"] is True
    assert summary["reason"] == "fixtures.doi_samples.structure.doi is null"
    assert not (tmp_path / "tests").exists()


def test_capture_fixture_from_manifest_all_dry_run_plans_non_null_and_skips_null(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "mdpi.yml"
    manifest_path.write_text(
        """
name: mdpi
routing:
  primary: doi_prefix
  doi_prefixes:
    - "10.3390/"
probe:
  requires_browser_runtime: false
fixtures:
  doi_samples:
    structure:
      doi: "10.3390/membranes15030093"
      evidence_url: "https://example.test/structure"
      evidence_reason: "Structure sample."
      observed_signals:
        - html_body
      confidence: high
    figure:
      doi: null
      evidence_url: "https://example.test/figure"
      evidence_reason: "No figure sample selected."
      observed_signals: []
      confidence: low
extra_fixtures:
  - purpose: structure
    doi: "10.3390/foods10081757"
    evidence_url: "https://example.test/extra"
    evidence_reason: "Extra structure sample."
    observed_signals:
      - html_body
    confidence: high
""",
        encoding="utf-8",
    )

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("dry-run --all must not fetch")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_all_from_manifest(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            purpose=None,
            from_manifest=str(manifest_path),
            all=True,
            dry_run=True,
        )
    )

    assert summary["status"] == "OK"
    assert summary["target_count"] == 3
    assert summary["captured_count"] == 2
    assert summary["skipped_count"] == 1
    reasons = [item.get("reason") for item in summary["results"]]
    assert "fixtures.doi_samples.figure.doi is null" in reasons
    planned = [item for item in summary["results"] if item.get("status") == "OK"]
    assert {item["manifest_sample_path"] for item in planned} == {
        "fixtures.doi_samples.structure",
        "extra_fixtures[0]",
    }
    assert not (tmp_path / "tests").exists()


def test_capture_fixture_manifest_dry_run_infers_xml_from_jats_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "plos.yml"
    manifest_path.write_text(
        """
name: plos
routing:
  primary: doi_prefix
  doi_prefixes:
    - "10.1371/"
probe:
  requires_browser_runtime: false
fixtures:
  doi_samples:
    structure:
      doi: "10.1371/journal.pone.0263725"
      evidence_url: "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0263725&type=manuscript"
      evidence_reason: "JATS XML sample."
      observed_signals:
        - jats_xml
        - xml_body_sections
      confidence: high
""",
        encoding="utf-8",
    )

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("dry-run must not fetch")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            purpose="structure",
            from_manifest=str(manifest_path),
            dry_run=True,
            auto_via=True,
        )
    )

    assert summary["content_type"] == "application/xml"
    assert summary["route_kind"] == "xml"
    assert summary["fixture_path"] == (
        "tests/fixtures/golden_criteria/10.1371_journal.pone.0263725/original.xml"
    )


def test_capture_fixture_reuses_existing_xml_manifest_asset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")
    manifest_path = tmp_path / "plos.yml"
    doi = "10.1371/journal.pone.0263725"
    slug = "10.1371_journal.pone.0263725"
    fixture_path = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / slug / "original.xml"
    )
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text("<article />", encoding="utf-8")
    manifest_path.write_text(
        f"""
name: plos
routing:
  primary: doi_prefix
  doi_prefixes:
    - "10.1371/"
probe:
  requires_browser_runtime: false
fixtures:
  doi_samples:
    structure:
      doi: "{doi}"
      evidence_url: "https://journals.plos.org/plosone/article/file?id={doi}&type=manuscript"
      evidence_reason: "JATS XML sample."
      observed_signals:
        - jats_xml
      confidence: high
""",
        encoding="utf-8",
    )
    fixture_manifest_path = (
        tmp_path / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    )
    fixture_manifest_path.write_text(
        json.dumps(
            {
                "samples": {
                    slug: {
                        "doi": doi,
                        "publisher": "plos",
                        "content_type": "text/xml",
                        "route_kind": "xml",
                        "assets": {
                            "original.xml": fixture_path.relative_to(
                                tmp_path
                            ).as_posix()
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    class FailingTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise AssertionError("existing XML fixture should be reused")

    monkeypatch.setattr(module, "HttpTransport", FailingTransport)

    summary = module.capture_fixture(
        _args(
            tmp_path,
            doi=None,
            provider=None,
            purpose="structure",
            from_manifest=str(manifest_path),
        )
    )

    assert summary["reused"] is True
    assert summary["content_type"] == "text/xml"
    assert summary["route_kind"] == "xml"
    assert summary["fixture_path"] == fixture_path.relative_to(tmp_path).as_posix()


def test_capture_fixture_retries_403_with_browser_placeholder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")

    class ForbiddenTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"forbidden",
                "status_code": 403,
            }

    monkeypatch.setattr(module, "HttpTransport", ForbiddenTransport)
    monkeypatch.setattr(
        module,
        "_capture_browser",
        lambda *_args, **kwargs: (_ for _ in ()).throw(
            module.CaptureFixtureError(
                "BROWSER_RUNTIME_REQUIRED",
                "browser fixture capture requires an interactive browser runtime",
                retryable=False,
                route=kwargs["route"],
            )
        ),
    )

    with pytest.raises(module.CaptureFixtureError) as exc_info:
        module.capture_fixture(_args(tmp_path, retry_via="browser"))

    assert exc_info.value.code == "BROWSER_RUNTIME_REQUIRED"
    assert exc_info.value.previous_code == "HTTP_FORBIDDEN"
    assert exc_info.value.route == "browser"
    assert not (tmp_path / "tests").exists()


def test_capture_fixture_maps_challenge_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_script_module("capture_fixture")

    class ChallengeTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"<html><title>Just a moment</title><body>verify you are human captcha</body></html>",
                "status_code": 200,
            }

    monkeypatch.setattr(module, "HttpTransport", ChallengeTransport)

    with pytest.raises(module.CaptureFixtureError) as exc_info:
        module.capture_fixture(_args(tmp_path))

    assert exc_info.value.code == "CHALLENGE_DETECTED"


def test_capture_fixture_validation_allows_annualreviews_access_provided_by_fulltext() -> (
    None
):
    module = load_script_module("capture_fixture")
    body_text = "Annual Reviews full article section text with enough substance. " * 8
    html = (
        "<html><head><title>Annual Reviews Article</title></head><body>"
        "<div>Access provided by: Peking University</div>"
        f"<div id='itemFullTextId'><h2>Introduction</h2><p>{body_text}</p><p>{body_text}</p></div>"
        "</body></html>"
    )

    content_type, body, final_url = module._validate_capture_response(
        response={
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": html.encode("utf-8"),
            "url": "https://www.annualreviews.org/content/journals/10.1146/example",
            "status_code": 200,
        },
        purpose="structure",
        route="browser",
    )

    assert content_type == "text/html; charset=utf-8"
    assert body == html.encode("utf-8")
    assert final_url == "https://www.annualreviews.org/content/journals/10.1146/example"


def test_capture_fixture_validation_allows_access_ui_when_fulltext_container_is_populated() -> (
    None
):
    module = load_script_module("capture_fixture")
    body_text = "Annual Reviews full article section text with enough substance. " * 80
    html = (
        "<html><head><title>Annual Reviews Article</title></head><body>"
        "<aside>Sign in to access your institutional or personal subscription.</aside>"
        f"<main id='html_fulltext'><section class='articleSection'><h2>Introduction</h2><p>{body_text}</p></section></main>"
        "</body></html>"
    )

    content_type, body, _final_url = module._validate_capture_response(
        response={
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": html.encode("utf-8"),
            "url": "https://www.annualreviews.org/content/journals/10.1146/example",
            "status_code": 200,
        },
        purpose="references",
        route="browser",
    )

    assert content_type == "text/html; charset=utf-8"
    assert body == html.encode("utf-8")


def test_capture_fixture_maps_non_pdf_fallback_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")

    class HtmlTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"<html><body>PDF wrapper page</body></html>",
                "status_code": 200,
            }

    monkeypatch.setattr(module, "HttpTransport", HtmlTransport)

    with pytest.raises(module.CaptureFixtureError) as exc_info:
        module.capture_fixture(_args(tmp_path, purpose="pdf_fallback"))

    assert exc_info.value.code == "NON_PDF_FALLBACK_CONTENT"
    assert exc_info.value.retryable is True


def test_capture_fixture_maps_browser_pdf_non_pdf_failure_to_non_pdf_content() -> None:
    module = load_script_module("capture_fixture")

    class BrowserPdfFailure(Exception):
        kind = "downloaded_file_not_pdf"
        message = "PDF fallback did not produce a PDF file."

    error = module._browser_capture_error(BrowserPdfFailure(), route="browser")

    assert error.code == "NON_PDF_FALLBACK_CONTENT"
    assert error.retryable is True
    assert error.route == "browser"


def test_capture_fixture_maps_timeout_to_network_transient(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script_module("capture_fixture")

    class TimeoutTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            raise TimeoutError("read timed out")

    monkeypatch.setattr(module, "HttpTransport", TimeoutTransport)

    with pytest.raises(module.CaptureFixtureError) as exc_info:
        module.capture_fixture(_args(tmp_path))

    assert exc_info.value.code == "NETWORK_TRANSIENT"
    assert exc_info.value.retryable is True
    assert exc_info.value.route == "http"


def test_capture_fixture_fail_fast_writes_json_stderr_without_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_script_module("capture_fixture")

    class RateLimitedTransport:
        def request(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "headers": {"content-type": "text/html"},
                "body": b"slow down",
                "status_code": 429,
            }

    monkeypatch.setattr(module, "HttpTransport", RateLimitedTransport)

    rc = module.main(
        [
            "--doi",
            "10.1234/example",
            "--provider",
            "examplepub",
            "--purpose",
            "structure",
            "--fail-fast",
            "--output-dir",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    error = json.loads(captured.err)

    assert rc == 1
    assert captured.out == ""
    assert error["code"] == "HTTP_RATE_LIMITED"
    assert error["provider"] == "examplepub"
    assert error["purpose"] == "structure"
