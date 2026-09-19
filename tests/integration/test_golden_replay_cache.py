"""Canonical build reuse preserves caller isolation and route distinctions."""

from tests.golden_corpus import GoldenCorpusFixture
from tests.support import replay


def test_canonical_build_reuse_is_session_local_and_returns_independent_copies(
    tmp_path, monkeypatch
):
    calls = []

    def build(fixture):
        calls.append(fixture.sample)
        return {"sections": [{"text": "opaque output"}]}

    monkeypatch.setattr("tests.golden_corpus.build_article_from_fixture", build)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    replay._build.cache_clear()
    fixture = GoldenCorpusFixture(
        "controlled", {"sample_id": "controlled", "route": "html"}
    )
    try:
        first = replay.build_article_from_fixture(fixture)
        first["sections"][0]["text"] = "caller mutation"
        assert (
            replay.build_article_from_fixture(fixture)["sections"][0]["text"]
            == "opaque output"
        )
        assert len(calls) == 1
        # A fresh worker has no in-memory cache and reads the shared session artifact.
        replay._build.cache_clear()
        assert (
            replay.build_article_from_fixture(fixture)["sections"][0]["text"]
            == "opaque output"
        )
        assert len(calls) == 1
        replay.build_article_from_fixture(
            GoldenCorpusFixture(
                "controlled", {"sample_id": "controlled", "route": "pdf_fallback"}
            )
        )
        assert len(calls) == 2
    finally:
        replay._build.cache_clear()
