from __future__ import annotations

import json
import socket
from pathlib import Path
from unittest import mock

import pytest

from paper_fetch.delivery.acceptance_payloads import compact_acceptance_payload
from paper_fetch.delivery.fetch_cache import FetchCache, cache_request_fingerprint
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support.fetch_fixtures import sample_envelope
from tests.support.workflow_acceptance import _envelope

DOI = "10.1000/cache-compact"


def _write_sidecar(download_dir: Path, *, modes: list[str] | None = None) -> Path:
    request = FetchPaperRequest(
        query=DOI,
        modes=list(modes or ["markdown"]),
        prefer_cache=True,
    )
    cache = FetchCache(download_dir)
    cache.write_fetch_envelope(
        sample_envelope(modes=set(request.modes), doi=DOI), request
    )
    return next(download_dir.glob("*.fetch-envelope.json"))


def test_compact_acceptance_payload_projects_unrequested_asset_summary() -> None:
    unrequested = evaluate_fetch_acceptance(_envelope(), asset_profile="none")
    assert compact_acceptance_payload(unrequested)["asset_summary"] == {
        "requested": False,
        "profile": "none",
    }


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"modes": ["metadata"]},
        {"strategy": {"asset_profile": "body"}},
        {"include_refs": "top10"},
        {"max_tokens": 512},
    ],
)
def test_cache_loader_rejects_mismatched_request_parameters(
    tmp_path: Path,
    request_overrides: dict[str, object],
) -> None:
    _write_sidecar(tmp_path)
    request = FetchPaperRequest.model_validate(
        {
            "query": DOI,
            "prefer_cache": True,
            **request_overrides,
        }
    )
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = FetchCache(tmp_path).load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(),
            context=context,
        )
    assert loaded is None


@pytest.mark.parametrize(
    ("modes", "field", "value"),
    [
        (["markdown"], "markdown", ""),
        (["article"], "article", {}),
        (["metadata"], "metadata", {}),
    ],
)
def test_cache_loader_rejects_semantically_empty_requested_outputs(
    tmp_path: Path,
    modes: list[str],
    field: str,
    value: object,
) -> None:
    sidecar_path = _write_sidecar(tmp_path, modes=modes)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["payload"][field] = value
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    request = FetchPaperRequest(query=DOI, modes=modes, prefer_cache=True)
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = FetchCache(tmp_path).load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(),
            context=context,
        )
    assert loaded is None


def test_cache_loader_rejects_old_corrupt_and_doi_mismatched_sidecars(
    tmp_path: Path,
) -> None:
    for case in (
        "old_version",
        "corrupt_json",
        "doi_mismatch",
        "content_flag_conflict",
    ):
        scope = tmp_path / case
        sidecar_path = _write_sidecar(scope)
        if case == "corrupt_json":
            sidecar_path.write_text("{broken", encoding="utf-8")
        else:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if case == "old_version":
                sidecar["version"] = 7
            elif case == "doi_mismatch":
                sidecar["payload"]["doi"] = "10.1000/other"
            else:
                sidecar["payload"]["quality"]["has_fulltext"] = False
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

        request = FetchPaperRequest(query=DOI, modes=["markdown"], prefer_cache=True)
        with RuntimeContext(env={}, download_dir=scope) as context:
            loaded = FetchCache(scope).load_fetch_envelope(
                request,
                resolve_paper_fn=mock.Mock(),
                context=context,
            )
        assert loaded is None


def test_cache_wrong_scope_is_miss_and_never_uses_network(tmp_path: Path) -> None:
    correct_scope = tmp_path / "correct"
    wrong_scope = tmp_path / "wrong"
    wrong_scope.mkdir(parents=True)
    _write_sidecar(correct_scope)

    request = FetchPaperRequest(query=DOI, modes=["markdown"], prefer_cache=True)
    with (
        mock.patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("cache lookup must stay offline"),
        ) as create_connection,
        RuntimeContext(env={}, download_dir=wrong_scope) as context,
    ):
        loaded = FetchCache(wrong_scope).load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(),
            context=context,
        )

    assert loaded is None
    create_connection.assert_not_called()


def test_cache_request_fingerprint_is_stable_across_json_key_order() -> None:
    request = {
        "target": "paper",
        "modes": ["markdown"],
        "strategy": {"asset_profile": "none"},
        "include_refs": "all",
        "max_tokens": "full_text",
    }
    reordered = dict(reversed(list(request.items())))
    assert cache_request_fingerprint(DOI, request) == cache_request_fingerprint(
        DOI, reordered
    )
