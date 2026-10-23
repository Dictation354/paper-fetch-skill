"""Replay the reviewed current captures through extraction and persistence.

Run from the repository root with PYTHONPATH=src:. uv run python
scripts/refresh_full_read_baselines.py. Original captures and the three historical
minimal artifacts are never written.
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
)
from tests.support.replay import persisted_fixture_markdown
from tests.support.formula_runtime import captured_formula_environment
from paper_fetch.formula.convert import formula_runtime_env

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = (
    ROOT / "tests/fixtures/golden_criteria/_scenarios/review_contracts/expected.json"
)


def refresh(record):
    fixture = golden_corpus_fixture_for_doi(record["doi"])
    with formula_runtime_env(captured_formula_environment()):
        article = build_article_from_fixture(fixture)
    text = persisted_fixture_markdown(fixture, article)
    path = ROOT / record["path"]
    old = path.read_bytes()
    body = text.encode()
    if old != body:
        path.write_bytes(body)
    return {
        "sample_id": record["sample_id"],
        "changed": old != body,
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def main():
    contracts = json.loads(CONTRACTS.read_text())
    current = [r for r in contracts["files"] if r["scope"] == "current"]
    results = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for future in as_completed(
            [pool.submit(refresh, record) for record in current]
        ):
            result = future.result()
            results.append(result)
            print(
                result["sample_id"],
                "updated" if result["changed"] else "unchanged",
                flush=True,
            )
    print(
        f"Replayed {len(results)} captures; updated {sum(r['changed'] for r in results)} baselines."
    )


if __name__ == "__main__":
    main()
