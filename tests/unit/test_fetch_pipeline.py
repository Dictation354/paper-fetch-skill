from __future__ import annotations

import unittest

from paper_fetch.models import RenderOptions
from paper_fetch.workflow.pipeline import FetchPipeline, FetchPipelineRequest
from paper_fetch.workflow.types import FetchStrategy

from ._paper_fetch_support import build_envelope, sample_article


class FetchPipelineTests(unittest.TestCase):
    def test_run_forwards_shared_fetch_inputs_with_explicit_context(self) -> None:
        captured: dict[str, object] = {}
        context = object()

        def fake_fetch_paper(query, **kwargs):
            captured["query"] = query
            captured.update(kwargs)
            return build_envelope(sample_article())

        request = FetchPipelineRequest(
            query="10.1016/test",
            modes={"article", "markdown"},
            strategy=FetchStrategy(asset_profile="body"),
            render=RenderOptions(asset_profile="body"),
        )
        envelope = FetchPipeline(fake_fetch_paper).run(
            request,
            context=context,  # type: ignore[arg-type]
        )

        self.assertEqual(envelope.doi, "10.1016/test")
        self.assertEqual(captured["query"], request.query)
        self.assertIs(captured["modes"], request.modes)
        self.assertIs(captured["strategy"], request.strategy)
        self.assertIs(captured["render"], request.render)
        self.assertIs(captured["context"], context)


if __name__ == "__main__":
    unittest.main()
