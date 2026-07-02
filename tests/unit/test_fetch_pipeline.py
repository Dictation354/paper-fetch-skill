from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from paper_fetch.models import RenderOptions
from paper_fetch.workflow import pipeline as pipeline_module
from paper_fetch.workflow.pipeline import (
    FetchPipeline,
    FetchPipelineCacheHooks,
    FetchPipelineRequest,
    MarkdownSaveSpec,
)
from paper_fetch.workflow.request_builder import build_fetch_pipeline_request
from paper_fetch.workflow.types import FetchStrategy

from ._paper_fetch_support import build_envelope, sample_article


def _request(**overrides) -> FetchPipelineRequest:
    values = {
        "query": "10.1016/test",
        "modes": {"article", "markdown"},
        "strategy": FetchStrategy(),
        "render": RenderOptions(),
        "env": {},
    }
    values.update(overrides)
    return FetchPipelineRequest(**values)


class FetchPipelineTests(unittest.TestCase):
    def test_run_passes_none_env_to_runtime_context_and_closes_it(self) -> None:
        captured: dict[str, object] = {}

        class FakeContext:
            def __init__(self, **kwargs) -> None:
                captured["runtime_kwargs"] = kwargs

            def close(self) -> None:
                captured["closed"] = True

        def fake_fetch_paper(query, **kwargs):
            captured["fetch_query"] = query
            captured["fetch_context"] = kwargs["context"]
            return build_envelope(sample_article())

        with mock.patch.object(pipeline_module, "RuntimeContext", FakeContext):
            result = FetchPipeline(fake_fetch_paper).run(_request(env=None))

        self.assertEqual(result.envelope.doi, "10.1016/test")
        self.assertEqual(captured["fetch_query"], "10.1016/test")
        self.assertIsNone(captured["runtime_kwargs"]["env"])
        self.assertTrue(captured["closed"])

    def test_run_passes_no_download_and_fetch_cache_to_context(self) -> None:
        captured: dict[str, object] = {}
        fetch_cache = object()

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return build_envelope(sample_article())

        with tempfile.TemporaryDirectory() as tmpdir:
            FetchPipeline(fake_fetch_paper).run(
                _request(
                    download_dir=Path(tmpdir),
                    no_download=True,
                    fetch_cache=fetch_cache,
                )
            )

        context = captured["context"]
        self.assertIsNone(context.download_dir)
        self.assertEqual(context.artifact_mode, "none")
        self.assertIs(context.fetch_cache, fetch_cache)

    def test_request_builder_keeps_artifact_mode_when_no_download(self) -> None:
        request = build_fetch_pipeline_request(
            query="10.1016/test",
            modes={"article"},
            strategy=FetchStrategy(),
            render=RenderOptions(),
            download_dir=Path("/tmp/downloads"),
            artifact_mode="all",
            no_download=True,
        )

        self.assertEqual(request.artifact_mode, "all")
        self.assertTrue(request.no_download)

    def test_run_passes_artifact_mode_to_context(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return build_envelope(sample_article())

        with tempfile.TemporaryDirectory() as tmpdir:
            FetchPipeline(fake_fetch_paper).run(
                _request(
                    download_dir=Path(tmpdir),
                    artifact_mode="markdown-assets",
                )
            )

        context = captured["context"]
        self.assertEqual(context.download_dir, Path(tmpdir))
        self.assertEqual(context.artifact_mode, "markdown-assets")
        self.assertIsNone(context.transport.disk_cache_dir)

    def test_cache_hit_short_circuits_service_and_write_hook(self) -> None:
        cached = build_envelope(sample_article())
        called: list[str] = []

        def fail_fetch(*args, **kwargs):
            raise AssertionError("service should not be called on cache hit")

        result = FetchPipeline(fail_fetch).run(
            _request(
                cache_hooks=FetchPipelineCacheHooks(
                    load=lambda context: cached,
                    write=lambda envelope: called.append("write"),
                )
            )
        )

        self.assertIs(result.envelope, cached)
        self.assertTrue(result.cache_hit)
        self.assertEqual(called, [])

    def test_cache_miss_calls_service_and_write_hook(self) -> None:
        written: list[object] = []

        def fake_fetch_paper(query, **kwargs):
            return build_envelope(sample_article())

        result = FetchPipeline(fake_fetch_paper).run(
            _request(
                cache_hooks=FetchPipelineCacheHooks(
                    load=lambda context: None,
                    write=written.append,
                )
            )
        )

        self.assertFalse(result.cache_hit)
        self.assertEqual(written, [result.envelope])

    def test_cache_hit_still_runs_markdown_save_spec(self) -> None:
        cached = build_envelope(sample_article())

        def fail_fetch(*args, **kwargs):
            raise AssertionError("service should not be called on cache hit")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = FetchPipeline(fail_fetch).run(
                _request(
                    cache_hooks=FetchPipelineCacheHooks(load=lambda context: cached),
                    markdown_save=MarkdownSaveSpec(
                        output_dir=output_dir,
                        render=RenderOptions(),
                        filename="cached.md",
                    ),
                )
            )

            self.assertTrue(result.cache_hit)
            self.assertEqual(result.saved_markdown_path, output_dir / "cached.md")
            self.assertTrue((output_dir / "cached.md").exists())

    def test_markdown_save_spec_writes_file_and_calls_hook(self) -> None:
        saved: list[tuple[object, Path]] = []

        def fake_fetch_paper(query, **kwargs):
            return build_envelope(sample_article())

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = FetchPipeline(fake_fetch_paper).run(
                _request(
                    markdown_save=MarkdownSaveSpec(
                        output_dir=output_dir,
                        render=RenderOptions(),
                        filename="paper.md",
                        request_label="--save-markdown",
                        on_saved=lambda envelope, path: saved.append((envelope, path)),
                    )
                )
            )

            saved_path = output_dir / "paper.md"
            self.assertEqual(result.saved_markdown_path, saved_path)
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved, [(result.envelope, saved_path)])
            self.assertIn("download:markdown_saved", result.envelope.source_trail)

    def test_request_builder_applies_context_runtime_resources_without_context_download_dir(
        self,
    ) -> None:
        transport = object()
        clients = {"crossref": object()}
        explicit_transport = object()
        explicit_clients = {"elsevier": object()}

        def cancel_check() -> bool:
            return False

        request = build_fetch_pipeline_request(
            query="10.1016/test",
            modes=["markdown"],
            strategy=FetchStrategy(asset_profile="body"),
            render=RenderOptions(asset_profile="body"),
            env={"IGNORED": "1"},
            download_dir=Path("/tmp/request-downloads"),
            transport=explicit_transport,
            clients=explicit_clients,
            context=SimpleNamespace(
                env={"CROSSREF_MAILTO": "unit@example.test"},
                transport=transport,
                clients=clients,
                cancel_check=cancel_check,
                download_dir=Path("/tmp/context-downloads"),
            ),
        )

        self.assertEqual(request.env, {"CROSSREF_MAILTO": "unit@example.test"})
        self.assertIs(request.transport, transport)
        self.assertIs(request.clients, clients)
        self.assertIs(request.cancel_check, cancel_check)
        self.assertEqual(request.download_dir, Path("/tmp/request-downloads"))
        self.assertEqual(request.artifact_mode, "all")
        self.assertEqual(request.modes, {"markdown"})


if __name__ == "__main__":
    unittest.main()
