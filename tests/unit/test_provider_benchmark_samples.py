from __future__ import annotations

import paper_fetch.providers  # noqa: F401
from paper_fetch.provider_catalog import official_provider_names
from tests.provider_benchmark_samples import PROVIDER_BENCHMARK_SAMPLES


def test_provider_benchmark_samples_cover_official_live_smoke_providers() -> None:
    assert set(PROVIDER_BENCHMARK_SAMPLES) == set(official_provider_names())


def test_crossref_mailto_is_recommended_but_never_required() -> None:
    for sample in PROVIDER_BENCHMARK_SAMPLES.values():
        assert "CROSSREF_MAILTO" not in sample.required_env
        if sample.provider not in {"arxiv", "copernicus", "ieee"}:
            assert "CROSSREF_MAILTO" in sample.recommended_env
