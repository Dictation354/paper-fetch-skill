from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup

from paper_fetch.page_diagnostics import (
    PageDiagnosticRequest,
    capture_page_diagnostic,
    is_empty_article_shell,
    page_shape_diagnostics,
    sanitize_page_html,
)
from paper_fetch.runtime import RuntimeContext


def test_page_diagnostic_persists_only_sanitized_html(tmp_path) -> None:
    raw = """
    <html onload="steal()">
      <head><script>token=super-secret</script><style>.x{}</style></head>
      <body class="article">
        <!-- private comment -->
        <form><input value="account@example.com"><button>Submit</button></form>
        <a href="https://user:pass@example.test/article?token=secret#private">
          Contact account@example.com
        </a>
        <img src="https://cdn.example.test/figure.png?signature=secret">
        <section data-extent="bodymatter" data-private="secret">Body</section>
      </body>
    </html>
    """
    context = RuntimeContext(
        env={},
        download_dir=tmp_path,
        artifact_mode="all",
    )
    try:
        result = capture_page_diagnostic(
            context,
            PageDiagnosticRequest(
                provider="aip",
                route="html",
                attempt=2,
                failure_code="article_container_not_found",
                stage="html_extraction",
                html_text=raw,
                doi="10.1000/example",
                target_url="https://user:pass@example.test/article?token=secret",
                final_url="https://example.test/article?code=private",
                backend="camoufox",
                response_status=200,
                title="Contact account@example.com",
                details={
                    "browser_runtime_trace": {
                        "backend": "camoufox",
                        "candidates": [
                            {
                                "status": 200,
                                "dom_readiness_ready": False,
                                "dom_readiness_text_length": 0,
                            }
                        ],
                    }
                },
            ),
        )
    finally:
        context.close()

    diagnostic_path = (
        tmp_path / "diagnostics/aip/10.1000_example/html-2/diagnostic.json"
    )
    page_path = diagnostic_path.with_name("page-sanitized.html")
    assert result["diagnostic_path"] == str(diagnostic_path)
    assert diagnostic_path.is_file()
    assert page_path.is_file()
    page = page_path.read_text(encoding="utf-8")
    combined = diagnostic_path.read_text(encoding="utf-8") + page
    assert "super-secret" not in combined
    assert "account@example.com" not in combined
    assert "user:pass@" not in combined
    assert "?token=" not in combined
    assert "?signature=" not in combined
    assert "<script" not in page
    assert "<form" not in page
    assert "onload" not in page
    assert "data-private" not in page
    assert "[redacted-email]" in page
    assert 'data-extent="bodymatter"' in page

    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["response_status"] == 200
    assert payload["page"]["html_shape"]["has_body"] is True
    assert payload["page"]["browser_runtime"]["candidates"][0] == {
        "status": 200,
        "dom_readiness_ready": False,
        "dom_readiness_text_length": 0,
    }
    assert (
        payload["raw_html"]["sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    )
    assert (
        payload["sanitized_html"]["sha256"]
        == hashlib.sha256(page.encode("utf-8")).hexdigest()
    )
    assert {item["kind"] for item in context.diagnostic_artifacts} == {"diagnostic"}


def test_sanitized_html_truncates_at_dom_boundaries() -> None:
    raw = (
        "<html><body>"
        + "".join(f"<p id='p-{index}'>{'x' * 80}</p>" for index in range(200))
        + "</body></html>"
    )
    sanitized, truncated = sanitize_page_html(raw, maximum_bytes=1024)

    assert truncated is True
    assert len(sanitized.encode("utf-8")) <= 1024
    assert "paper-fetch diagnostic truncated" in sanitized
    parsed = BeautifulSoup(sanitized, "html.parser")
    assert parsed.html is not None
    assert parsed.body is not None


def test_non_all_mode_keeps_memory_summary_without_writing(tmp_path) -> None:
    context = RuntimeContext(
        env={},
        download_dir=tmp_path,
        artifact_mode="markdown-assets",
    )
    try:
        result = capture_page_diagnostic(
            context,
            PageDiagnosticRequest(
                provider="springer",
                route="html",
                attempt=1,
                failure_code="publisher_paywall",
                stage="availability",
                html_text="<html><body>Preview</body></html>",
            ),
        )
    finally:
        context.close()

    assert result["raw_html"]["byte_count"] > 0
    assert result["sanitized_html"] is None
    assert "diagnostic_path" not in result
    assert not (tmp_path / "diagnostics").exists()


def test_wiley_http_access_status_review_is_allowlisted_and_secret_safe(
    tmp_path,
) -> None:
    context = RuntimeContext(
        env={},
        download_dir=tmp_path,
        artifact_mode="markdown-assets",
    )
    try:
        result = capture_page_diagnostic(
            context,
            PageDiagnosticRequest(
                provider="wiley",
                route="html",
                attempt=1,
                failure_code="publisher_access_denied",
                stage="block_detection",
                html_text="<html><body>Access denied</body></html>",
                response_status=403,
                details={
                    "browser_runtime_trace": {
                        "candidates": [
                            {
                                "status": 403,
                                "http_access_status_review": {
                                    "status": 403,
                                    "body_ready": True,
                                    "doi_evidence_present": True,
                                    "doi_evidence_sources": ["citation_meta"],
                                    "doi_match": True,
                                    "doi_match_sources": ["citation_meta"],
                                    "blocking_signals": ["publisher_access_denied"],
                                    "candidate_confirmed": False,
                                    "status_override_applied": False,
                                    "fulltext_acceptance": "not_attempted",
                                    "accepted": False,
                                    "reason": "blocking_signal",
                                    "authorization": "Bearer private-secret",
                                    "raw_failure_html": "private-secret",
                                    "storage_state": {"cookie": "private-secret"},
                                },
                            }
                        ]
                    }
                },
            ),
        )
    finally:
        context.close()

    review = result["page"]["browser_runtime"]["candidates"][0][
        "http_access_status_review"
    ]
    assert review == {
        "status": 403,
        "body_ready": True,
        "doi_evidence_present": True,
        "doi_evidence_sources": ["citation_meta"],
        "doi_match": True,
        "doi_match_sources": ["citation_meta"],
        "blocking_signals": ["publisher_access_denied"],
        "candidate_confirmed": False,
        "status_override_applied": False,
        "fulltext_acceptance": "not_attempted",
        "accepted": False,
        "reason": "blocking_signal",
    }
    assert "private-secret" not in json.dumps(result, sort_keys=True)
    assert not (tmp_path / "diagnostics").exists()


def test_failure_before_page_load_persists_json_without_fake_html(tmp_path) -> None:
    context = RuntimeContext(
        env={},
        download_dir=tmp_path,
        artifact_mode="all",
    )
    try:
        result = capture_page_diagnostic(
            context,
            PageDiagnosticRequest(
                provider="science",
                route="preflight",
                attempt=1,
                failure_code="browser_connect_timeout",
                stage="browser_connect",
                html_text=None,
                doi="10.1000/example",
                target_url="https://example.test/article?token=secret",
                backend="camoufox",
                details={"browser_runtime_trace": {"deadline_exhausted": True}},
            ),
        )
    finally:
        context.close()

    diagnostic_path = Path(result["diagnostic_path"])
    assert diagnostic_path.is_file()
    assert result["raw_html"] is None
    assert result["sanitized_html"] is None
    assert result["page"]["html_shape"] is None
    assert not diagnostic_path.with_name("page-sanitized.html").exists()
    assert [item["path"] for item in context.diagnostic_artifacts] == [
        str(diagnostic_path)
    ]


def test_empty_article_shell_requires_small_http_200_document_without_body() -> None:
    head_only = "<html><head><title>AIP article</title></head></html>"

    assert is_empty_article_shell(head_only, response_status=200) is True
    assert is_empty_article_shell(head_only, response_status=503) is False
    assert (
        is_empty_article_shell(
            "<html><body><main>Article</main></body></html>",
            response_status=200,
        )
        is False
    )
    assert page_shape_diagnostics(head_only) == {
        "byte_count": len(head_only.encode("utf-8")),
        "has_html": True,
        "has_head": True,
        "has_body": False,
        "body_text_length": 0,
        "body_element_count": 0,
        "article_container_count": 0,
    }


def test_observed_734_byte_http_200_head_only_shell_is_classified() -> None:
    prefix = "<html><head><title>ACS article</title>"
    suffix = "</head></html>"
    padding = " " * (734 - len((prefix + suffix).encode("utf-8")))
    shell = f"{prefix}{padding}{suffix}"

    assert len(shell.encode("utf-8")) == 734
    assert is_empty_article_shell(shell, response_status=200) is True
