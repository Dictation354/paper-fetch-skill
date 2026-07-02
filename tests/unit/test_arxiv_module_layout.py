from __future__ import annotations

from pathlib import Path

from paper_fetch.providers import arxiv as arxiv_provider


PROVIDER_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "paper_fetch" / "providers"
)


def test_arxiv_provider_module_line_counts_stay_split() -> None:
    assert (
        len((PROVIDER_ROOT / "arxiv.py").read_text(encoding="utf-8").splitlines())
        <= 800
    )
    limits = {
        "_arxiv_atom.py": 700,
        # arXiv assets also owns source archive figure recovery and diagnostics.
        "_arxiv_assets.py": 1200,
        "_arxiv_authors.py": 500,
        "_arxiv_html.py": 600,
        "_arxiv_metadata.py": 500,
        "_arxiv_references.py": 500,
    }
    for filename, limit in limits.items():
        path = PROVIDER_ROOT / filename
        assert len(path.read_text(encoding="utf-8").splitlines()) <= limit, filename


def test_arxiv_client_declares_only_client_public_export() -> None:
    assert arxiv_provider.__all__ == ["ArxivClient"]
    assert not hasattr(arxiv_provider, "ArxivHtmlExtraction")
    assert not hasattr(arxiv_provider, "ArxivSearch")
    assert not hasattr(arxiv_provider, "InternalArxivApiClient")
    assert not hasattr(arxiv_provider, "arxiv_metadata_probe_short_circuit")
    assert not hasattr(arxiv_provider, "metadata_from_arxiv_result")
    assert not hasattr(arxiv_provider, "minimal_arxiv_metadata")

    lines = (PROVIDER_ROOT / "arxiv.py").read_text(encoding="utf-8").splitlines()
    direct_private_imports = [
        line for line in lines if line.startswith("from ._arxiv_")
    ]
    assert len(direct_private_imports) <= 5
