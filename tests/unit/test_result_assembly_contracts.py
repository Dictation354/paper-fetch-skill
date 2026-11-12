from pathlib import Path

import pytest

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.models import article_from_markdown
from paper_fetch.providers.base import (
    ProviderClient,
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.providers.raw_adapter import RawProviderAdapter
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_event


class RawRecorder:
    name = "pnas"

    def __init__(self, *, failure=False, pdf=False):
        self.failure = failure
        self.calls = []
        self.articles = []
        self.payload = RawFulltextPayload(
            provider="pnas",
            content=ProviderContent(
                route_kind="pdf_fallback" if pdf else "raw",
                source_url="https://example.test/article",
                content_type="text/plain",
                body=b"Article",
                extracted_assets=[{"kind": "figure", "path": "extracted.png"}]
                if pdf
                else [],
            ),
        )

    def fetch_raw_fulltext(self, doi, metadata, *, context=None):
        self.calls.append(("raw", context, context.artifact_store))
        return self.payload

    def to_article_model(
        self,
        metadata,
        raw_payload,
        *,
        downloaded_assets=None,
        asset_failures=None,
        context=None,
    ):
        self.calls.append(("article", context, context.artifact_store))
        self.articles.append((downloaded_assets, asset_failures))
        return article_from_markdown(
            source="pnas",
            metadata=metadata,
            doi=metadata["doi"],
            markdown_text="# Contract\n\n## Results\n\n" + "Body text. " * 100,
        )

    def download_related_assets(
        self,
        doi,
        metadata,
        raw_payload,
        output_dir,
        *,
        asset_profile="all",
        context=None,
    ):
        self.calls.append(("assets", context, context.artifact_store))
        if self.failure:
            raise ProviderFailure("error", "asset failed")
        self.payload.warnings.append("asset-stage warning")
        self.payload.trace.append(trace_event("download", "pnas", "ok"))
        return {"assets": [], "asset_failures": []}

    def asset_download_failure_warning(self, exc):
        return "asset warning"


class MainRecorder(RawRecorder, ProviderClient):
    def finalize_fetch_result_article(self, article, **kwargs):
        self.finalized = article
        return article


@pytest.mark.parametrize("raw", [False, True])
def test_single_assembly_preserves_interface_calls_and_restores_context(
    tmp_path: Path, raw
):
    recorder = RawRecorder(pdf=True) if raw else MainRecorder()
    client = RawProviderAdapter(recorder) if raw else recorder
    store = ArtifactStore.from_download_dir(tmp_path)
    with RuntimeContext(env={}, asset_profile="none") as context:
        previous_store = context.artifact_store
        result = client.fetch_result(
            "10.1073/example",
            {"doi": "10.1073/example", "title": "Contract"},
            tmp_path,
            asset_profile="all",
            artifact_store=store,
            context=context,
        )
        assert all(
            seen_context is context and seen_store is store
            for _, seen_context, seen_store in recorder.calls
        )
        assert context.asset_profile == "none"
        assert context.artifact_store is previous_store
    if raw:
        assert [stage for stage, *_ in recorder.calls] == [
            "raw",
            "article",
            "assets",
            "article",
        ]
        assert recorder.articles == [([], []), ([], [])]
        assert result.artifacts.assets == [{"kind": "figure", "path": "extracted.png"}]
        assert result.warnings == ["asset-stage warning"]
        assert result.trace == recorder.payload.trace
    else:
        assert [stage for stage, *_ in recorder.calls] == ["raw", "article", "assets"]
        assert recorder.articles == [(None, None)]
        assert result.article is recorder.finalized


@pytest.mark.parametrize("raw", [False, True])
def test_asset_exception_contract_and_request_restoration(tmp_path, raw):
    recorder = RawRecorder(failure=True) if raw else MainRecorder(failure=True)
    client = RawProviderAdapter(recorder) if raw else recorder
    with RuntimeContext(env={}, asset_profile="body") as context:
        original_store = context.artifact_store
        if raw:
            with pytest.raises(ProviderFailure, match="asset failed"):
                client.fetch_result(
                    "10.1073/example",
                    {"doi": "10.1073/example"},
                    tmp_path,
                    asset_profile="all",
                    context=context,
                )
        else:
            result = client.fetch_result(
                "10.1073/example",
                {"doi": "10.1073/example"},
                tmp_path,
                asset_profile="all",
                context=context,
            )
            assert result.warnings == ["asset warning"]
        assert context.asset_profile == "body"
        assert context.artifact_store is original_store


def test_direct_entry_keeps_explicit_no_output_even_with_context_directory(tmp_path):
    recorder = MainRecorder()
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        store = context.artifact_store
        recorder.fetch_result(
            "10.1073/example",
            {"doi": "10.1073/example"},
            None,
            asset_profile="all",
            context=context,
        )
        assert context.artifact_store is store
    assert [stage for stage, *_ in recorder.calls] == ["raw", "article"]
