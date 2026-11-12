"""Replay the reviewed current captures through extraction and persistence.

Run from the repository root with PYTHONPATH=src:. .venv/bin/python
scripts/refresh_full_read_baselines.py. Original captures and the three historical
minimal artifacts are never written.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
    expected_summary_from_article,
)
from tests.support.replay import persisted_fixture_markdown
from tests.golden_criteria import golden_criteria_asset
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
    expected_path = golden_criteria_asset(fixture.doi, "expected.json")
    expected = json.loads(expected_path.read_text())
    summary = expected_summary_from_article(article)
    if any(expected.get(key) != value for key, value in summary.items()):
        for key, value in summary.items():
            if isinstance(value, dict) and isinstance(expected.get(key), dict):
                expected[key].update(value)
            else:
                expected[key] = value
        expected_path.write_text(
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n"
        )
    return {
        "sample_id": record["sample_id"],
        "changed": old != body,
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", action="append", help="Limit replay to registered sample IDs"
    )
    args = parser.parse_args()
    contracts = json.loads(CONTRACTS.read_text())
    current = [r for r in contracts["files"] if r["scope"] == "current"]
    if args.sample:
        selected = set(args.sample)
        current = [r for r in current if r["sample_id"] in selected]
        if selected != {r["sample_id"] for r in current}:
            parser.error("--sample must name current registered samples")
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
    for result in results:
        sample = contracts["samples"].get(result["sample_id"])
        if sample and "current" in sample:
            sample["current"]["baseline_sha256"] = result["sha256"]
    CONTRACTS.write_text(json.dumps(contracts, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Replayed {len(results)} captures; updated {sum(r['changed'] for r in results)} baselines."
    )


if __name__ == "__main__":
    main()
