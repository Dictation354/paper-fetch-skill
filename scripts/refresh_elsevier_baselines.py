"""Rebuild only the derived Elsevier outputs from the saved source captures.

PYTHONPATH=src:. uv run python scripts/refresh_elsevier_baselines.py
Original sources, assets, acquisition facts and historical api-fetch files remain
unchanged. Existing final HTML articles retain their asset request and options.
"""

from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/golden_criteria"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def refresh_xml(sample):
    from paper_fetch.formula.convert import formula_runtime_env
    from tests.support.formula_runtime import captured_formula_environment
    from tests.golden_corpus import (
        build_article_from_fixture,
        golden_corpus_fixture_for_doi,
        expected_summary_from_article,
    )
    from tests.support.replay import persisted_fixture_markdown

    fixture = golden_corpus_fixture_for_doi(sample["doi"])
    with formula_runtime_env(captured_formula_environment()):
        article = build_article_from_fixture(fixture)
    (ROOT / sample["assets"]["extracted.md"]).write_text(
        persisted_fixture_markdown(fixture, article)
    )
    expected_path = ROOT / sample["assets"]["expected.json"]
    expected = json.loads(expected_path.read_text())
    expected.update(expected_summary_from_article(article))
    write_json(expected_path, expected)
    return sample["doi"]


def refresh_html(path):
    from paper_fetch.formula.convert import formula_runtime_env
    from tests.support.formula_runtime import captured_formula_environment
    from paper_fetch.providers import _elsevier_html
    from paper_fetch.providers._payloads import build_provider_payload
    from paper_fetch.providers.elsevier import ElsevierClient
    from paper_fetch.models import FetchEnvelope
    from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
    from paper_fetch.models.schema import coerce_acquisition_provenance

    path = Path(path)
    source = path.with_name("original.html")
    provenance_path = path.with_name("provenance.json")
    provenance = json.loads(provenance_path.read_text())
    article_path = path.with_name("article.json")
    old = json.loads(article_path.read_text()) if article_path.exists() else None
    doi = (
        old["doi"]
        if old
        else provenance.get("doi") or source.parents[2].name.replace("_", "/", 1)
    )
    metadata = dict(old["metadata"]) if old else {"doi": doi}
    url = provenance["final_url"]
    with formula_runtime_env(captured_formula_environment()):
        markdown, extraction = _elsevier_html.extract_markdown(
            source.read_text(), url, metadata=metadata
        )
        path.write_text(markdown)
        if old is not None:
            metadata.update(title=extraction["title"])
            payload = build_provider_payload(
                provider="elsevier",
                route_kind="html",
                source_url=url,
                content_type="text/html",
                body=source.read_bytes(),
                markdown_text=markdown,
                merged_metadata=metadata,
                diagnostics={"extraction": extraction},
                warnings=old["quality"]["warnings"],
                trace_markers=old["quality"]["source_trail"],
            )
            # These thirteen captures requested no assets; do not discover or
            # download new assets while refreshing derived text.
            assert not old["assets"]
            profile = old["quality"]["asset_summary"]["profile"]
            article = ElsevierClient(None, {}).to_article_model(metadata, payload)
            article.acquisition = coerce_acquisition_provenance(old["acquisition"])
            write_json(article_path, article.to_dict())
            final = article.to_ai_markdown(
                include_refs="all",
                max_tokens="full_text",
                asset_profile=profile,
            )
            path.with_name("article.md").write_text(final)
            envelope = FetchEnvelope(
                doi=doi,
                source=article.source,
                article=article,
                markdown=final,
                has_fulltext=article.quality.has_fulltext,
                quality=article.quality,
                acquisition=article.acquisition,
            )
            old_acceptance = json.loads(path.with_name("acceptance.json").read_text())
            acceptance = evaluate_fetch_acceptance(
                envelope,
                asset_profile=profile,
                expected_doi=doi,
                requested_outputs=old_acceptance["output"]["requested"],
            ).model_dump(mode="json")
            write_json(path.with_name("acceptance.json"), acceptance)
    for record in provenance.get("outputs", []):
        target = ROOT / record["path"]
        if target in {path, path.with_name("article.md")}:
            data = target.read_bytes()
            record["size"] = len(data)
            record["sha256"] = hashlib.sha256(data).hexdigest()
    # Only the output records change; timings, response status and source hashes
    # describe the original acquisition and remain historical facts.
    write_json(provenance_path, provenance)
    return str(path.relative_to(ROOT))


def main():
    from tests.golden_criteria import iter_manifest_samples

    samples = [
        s
        for s in iter_manifest_samples(fixture_family="golden")
        if "sciencedirect.html" in s.get("assets", {})
    ]
    html_paths = sorted(CORPUS.glob("10.1016*/acquisition/sciencedirect*/extracted.md"))
    with tempfile.TemporaryDirectory(prefix="elsevier-refresh-") as temporary:
        os.environ["XDG_DATA_HOME"] = temporary
        os.environ["XDG_CACHE_HOME"] = temporary
        with ProcessPoolExecutor(max_workers=8) as pool:
            for result in pool.map(refresh_xml, samples):
                print("XML", result, flush=True)
            for result in pool.map(refresh_html, html_paths):
                print("HTML", result, flush=True)
    print(f"Refreshed {len(samples)} XML and {len(html_paths)} HTML captures.")


if __name__ == "__main__":
    main()
