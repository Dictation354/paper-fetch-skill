"""Reuse immutable canonical builds across golden assertions and xdist workers.

Only unmodified canonical adapter builds opt in. Cache/retry/isolation tests use
``tests.golden_corpus.build_article_from_fixture`` directly. Every caller gets an
independent copy; the shared pickle is a trusted, session-local test artifact.
"""

from copy import deepcopy
from functools import cache
import hashlib
import json
from pathlib import Path
import pickle
from filelock import FileLock
from tests.support.layer_policy import reject
from tests.support.test_evidence import capture_reads, observe


ROOT: Path | None = None


@cache
def _build(key: str):
    from tests.golden_corpus import GoldenCorpusFixture, build_article_from_fixture

    sample = json.loads(key)
    fixture = GoldenCorpusFixture(sample["sample_id"], sample)
    if ROOT is None:
        raise RuntimeError("canonical reuse requires the golden session fixture")
    path = ROOT / (hashlib.sha256(key.encode()).hexdigest() + ".pickle")
    with FileLock(str(path) + ".lock"):
        if path.exists():
            return pickle.loads(path.read_bytes())
        with capture_reads() as reads:
            article = build_article_from_fixture(fixture)
        envelope = (article, frozenset(reads))
        path.write_bytes(pickle.dumps(envelope))
        return envelope


def build_article_from_fixture(fixture):
    reject("full-paper replay builder")
    article, reads = _build(json.dumps(fixture.sample, sort_keys=True))
    observe(reads)
    return deepcopy(article)
