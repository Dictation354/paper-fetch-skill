from __future__ import annotations

import json
import socket
from pathlib import Path
from unittest import mock

import pytest

from paper_fetch.mcp import fetch_cache
from paper_fetch.mcp.server import build_server
from paper_fetch.utils import sanitize_filename
from tests.unit._mcp_support import (
    create_cached_downloads,
    create_cached_fetch_envelope,
    mcp_tools,
    assert_mcp_tool_omits_output_schema,
)


DOI = "10.1000/cache-compact"


def _sidecar_path(download_dir: Path, doi: str = DOI) -> Path:
    return download_dir / f"{sanitize_filename(doi)}.fetch-envelope.json"


def _prepared_cache(download_dir: Path) -> None:
    create_cached_downloads(download_dir, DOI)
    create_cached_fetch_envelope(download_dir, DOI)


def _rewrite_sidecar_credential_scope(
    download_dir: Path,
    credential_scope: str,
) -> None:
    sidecar_path = _sidecar_path(download_dir)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["credential_scope"] = credential_scope
    sidecar["request_fingerprint"] = fetch_cache.cache_request_fingerprint(
        DOI,
        sidecar["request"],
        credential_scope=credential_scope,
    )
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")


def test_get_cached_default_full_preserves_existing_fields(tmp_path: Path) -> None:
    _prepared_cache(tmp_path)

    default_payload = mcp_tools.get_cached_payload(doi=DOI, download_dir=tmp_path)
    explicit_payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="full",
        preferred_only=False,
    )

    assert default_payload == explicit_payload
    assert default_payload["status"] == "hit"
    assert default_payload["doi"] == DOI
    assert default_payload["download_dir"] == str(tmp_path)
    assert {entry["kind"] for entry in default_payload["entries"]} == {
        "asset",
        "fetch_envelope",
        "markdown",
        "primary_payload",
    }
    assert default_payload["preferred"]["markdown"] is not None
    assert default_payload["preferred"]["primary_payload"] is not None
    assert len(default_payload["preferred"]["assets"]) == 1


def test_get_cached_compact_returns_request_sensitive_quality_summary(
    tmp_path: Path,
) -> None:
    _prepared_cache(tmp_path)

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
    )

    assert payload["status"] == "hit"
    assert payload["detail"] == "compact"
    assert "entries" not in payload
    assert set(payload["preferred"]) == {"markdown", "primary_payload"}
    assert "assets" not in payload["preferred"]
    assert "payload" not in payload["sidecar"]
    assert payload["entry_summary"] == {
        "total": 4,
        "by_kind": {
            "asset": 1,
            "fetch_envelope": 1,
            "markdown": 1,
            "primary_payload": 1,
        },
    }
    assert payload["content_kind"] == "fulltext"
    assert payload["has_fulltext"] is True
    assert payload["confidence"] == "medium"
    assert payload["acceptance"]["status"] == "evaluated"
    assert payload["acceptance"]["content"] == "fulltext"
    assert payload["asset_summary"]["status"] == "not_requested"
    assert payload["warning_summary"]["warning_codes"] == ["weak_body_structure"]
    assert payload["request_status"] == "satisfied"
    assert payload["request_satisfied"] is True
    assert payload["cached_request"] == payload["requested_request"]
    assert (
        payload["cached_request_fingerprint"]
        == (payload["requested_request_fingerprint"])
    )
    assert len(payload["cached_request_fingerprint"]) == 64


def test_get_cached_preferred_only_omits_nonpreferred_entry_arrays(
    tmp_path: Path,
) -> None:
    _prepared_cache(tmp_path)

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        preferred_only=True,
    )

    assert payload["detail"] == "full"
    assert payload["preferred_only"] is True
    assert [entry["kind"] for entry in payload["entries"]] == [
        "markdown",
        "primary_payload",
    ]
    assert payload["preferred"]["assets"] == []
    assert payload["entry_summary"]["total"] == 4
    assert payload["entry_summary"]["by_kind"]["asset"] == 1


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"modes": ["metadata"]},
        {"strategy": {"asset_profile": "none"}},
        {"include_refs": "top10"},
        {"max_tokens": 512},
    ],
)
def test_get_cached_distinguishes_entries_from_request_mismatch(
    tmp_path: Path,
    request_overrides: dict[str, object],
) -> None:
    _prepared_cache(tmp_path)

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
        **request_overrides,
    )

    assert payload["status"] == "hit"
    assert payload["has_entries"] is True
    assert payload["request_status"] == "mismatch"
    assert payload["request_satisfied"] is False
    assert payload["sidecar"]["request_matches"] is False
    assert payload["sidecar"]["reason_code"] == "cached_request_mismatch"


def test_get_cached_uses_shared_cached_request_matcher(tmp_path: Path) -> None:
    _prepared_cache(tmp_path)

    with mock.patch.object(
        fetch_cache,
        "cached_request_matches",
        wraps=fetch_cache.cached_request_matches,
    ) as matcher:
        payload = mcp_tools.get_cached_payload(
            doi=DOI,
            download_dir=tmp_path,
            detail="compact",
        )

    assert payload["request_satisfied"] is True
    matcher.assert_called_once()


def test_get_cached_reports_cached_payload_missing_requested_mode(
    tmp_path: Path,
) -> None:
    _prepared_cache(tmp_path)
    sidecar_path = _sidecar_path(tmp_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["request"]["modes"] = ["article", "markdown", "metadata"]
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
        modes=["metadata"],
    )

    assert payload["status"] == "hit"
    assert payload["sidecar"]["request_matches"] is True
    assert payload["sidecar"]["payload_satisfies_request"] is False
    assert payload["request_satisfied"] is False
    assert payload["sidecar"]["reason_code"] == (
        "cached_payload_missing_requested_modes"
    )


@pytest.mark.parametrize(
    ("modes", "field", "value"),
    [
        (["markdown"], "markdown", ""),
        (["article"], "article", {}),
        (["metadata"], "metadata", {}),
    ],
)
def test_get_cached_rejects_semantically_empty_requested_outputs(
    tmp_path: Path,
    modes: list[str],
    field: str,
    value: object,
) -> None:
    create_cached_downloads(tmp_path, DOI)
    create_cached_fetch_envelope(tmp_path, DOI, modes=modes)
    sidecar_path = _sidecar_path(tmp_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["payload"][field] = value
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
        modes=modes,
    )

    assert payload["request_satisfied"] is False
    assert payload["sidecar"]["payload_satisfies_request"] is False


def test_get_cached_rejects_sidecar_content_flag_schema_conflict(
    tmp_path: Path,
) -> None:
    _prepared_cache(tmp_path)
    sidecar_path = _sidecar_path(tmp_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["payload"]["has_fulltext"] = False
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
    )

    assert payload["request_satisfied"] is False
    assert payload["sidecar"]["status"] == "invalid"
    assert payload["sidecar"]["reason_code"] == "cache_sidecar_schema_invalid"


def test_get_cached_reports_old_and_corrupt_sidecars_without_false_reuse(
    tmp_path: Path,
) -> None:
    old_scope = tmp_path / "old"
    corrupt_scope = tmp_path / "corrupt"
    _prepared_cache(old_scope)
    _prepared_cache(corrupt_scope)

    old_path = _sidecar_path(old_scope)
    old_payload = json.loads(old_path.read_text(encoding="utf-8"))
    old_payload["version"] = 4
    old_path.write_text(json.dumps(old_payload), encoding="utf-8")
    _sidecar_path(corrupt_scope).write_text("{broken", encoding="utf-8")

    old = mcp_tools.get_cached_payload(
        doi=DOI, download_dir=old_scope, detail="compact"
    )
    corrupt = mcp_tools.get_cached_payload(
        doi=DOI, download_dir=corrupt_scope, detail="compact"
    )

    assert old["status"] == "hit"
    assert old["sidecar"]["status"] == "version_mismatch"
    assert old["sidecar"]["reason_code"] == "cache_sidecar_version_mismatch"
    assert old["request_satisfied"] is False
    assert corrupt["status"] == "hit"
    assert corrupt["sidecar"]["status"] == "corrupt"
    assert corrupt["sidecar"]["reason_code"] == "cache_sidecar_invalid_json"
    assert corrupt["request_satisfied"] is False


def test_get_cached_wrong_scope_is_explicit_miss_and_never_uses_network(
    tmp_path: Path,
) -> None:
    correct_scope = tmp_path / "correct"
    wrong_scope = tmp_path / "wrong"
    _prepared_cache(correct_scope)

    with mock.patch.object(
        socket,
        "create_connection",
        side_effect=AssertionError("cache lookup must stay offline"),
    ) as create_connection:
        payload = mcp_tools.get_cached_payload(
            doi=DOI,
            download_dir=wrong_scope,
            detail="compact",
        )

    assert payload["status"] == "miss"
    assert payload["scope_status"] == "missing"
    assert payload["identity_status"] == "no_proven_entries"
    assert payload["sidecar"]["status"] == "missing"
    assert payload["request_satisfied"] is False
    assert str(correct_scope) not in json.dumps(payload)
    create_connection.assert_not_called()


def test_get_cached_uses_runtime_credential_scope(tmp_path: Path) -> None:
    _prepared_cache(tmp_path)
    runtime_env = mcp_tools.build_runtime_env({"ELSEVIER_API_KEY": "unit-test-secret"})
    credential_scope = fetch_cache.credential_scope_from_env(runtime_env)
    _rewrite_sidecar_credential_scope(tmp_path, credential_scope)

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
        env={"ELSEVIER_API_KEY": "unit-test-secret"},
    )

    assert payload["request_satisfied"] is True
    assert payload["sidecar"]["status"] == "ready"


def test_get_cached_credential_scope_fallback_is_one_way(tmp_path: Path) -> None:
    public_cache = tmp_path / "public"
    private_cache = tmp_path / "private"
    _prepared_cache(public_cache)
    _prepared_cache(private_cache)
    runtime_env = mcp_tools.build_runtime_env({"ELSEVIER_API_KEY": "unit-test-secret"})
    private_scope = fetch_cache.credential_scope_from_env(runtime_env)
    _rewrite_sidecar_credential_scope(private_cache, private_scope)

    credentialed_reader = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=public_cache,
        detail="compact",
        env={"ELSEVIER_API_KEY": "unit-test-secret"},
    )
    public_reader = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=private_cache,
        detail="compact",
        env={"ELSEVIER_API_KEY": ""},
    )

    assert credentialed_reader["request_satisfied"] is True
    assert credentialed_reader["sidecar"]["status"] == "ready"
    assert public_reader["request_satisfied"] is False
    assert public_reader["sidecar"]["status"] == "credential_scope_mismatch"


def test_get_cached_does_not_treat_unproven_markdown_as_doi_hit(
    tmp_path: Path,
) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "notes.md").write_text(
        f"# Notes\n\nMentioned DOI: {DOI}\n",
        encoding="utf-8",
    )

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
    )

    assert payload["status"] == "miss"
    assert payload["has_entries"] is False
    assert payload["identity_status"] == "no_proven_entries"
    assert payload["entry_summary"] == {"total": 0, "by_kind": {}}
    assert payload["sidecar"]["status"] == "missing"
    assert payload["request_satisfied"] is False


def test_get_cached_reports_sidecar_doi_mismatch(tmp_path: Path) -> None:
    _prepared_cache(tmp_path)
    sidecar_path = _sidecar_path(tmp_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["payload"]["doi"] = "10.1000/other"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    payload = mcp_tools.get_cached_payload(
        doi=DOI,
        download_dir=tmp_path,
        detail="compact",
    )

    assert payload["status"] == "hit"
    assert payload["sidecar"]["status"] == "doi_mismatch"
    assert payload["sidecar"]["reason_code"] == "cache_sidecar_doi_mismatch"
    assert payload["request_satisfied"] is False


def test_cache_request_fingerprint_is_stable_across_json_key_order(
    tmp_path: Path,
) -> None:
    _prepared_cache(tmp_path)
    first = mcp_tools.get_cached_payload(
        doi=DOI, download_dir=tmp_path, detail="compact"
    )
    sidecar_path = _sidecar_path(tmp_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["request"] = dict(reversed(list(sidecar["request"].items())))
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    second = mcp_tools.get_cached_payload(
        doi=DOI, download_dir=tmp_path, detail="compact"
    )

    assert first["cached_request_fingerprint"] == second["cached_request_fingerprint"]


def test_get_cached_compact_payload_keeps_asset_summary_without_output_schema(
    tmp_path: Path,
) -> None:
    _prepared_cache(tmp_path)
    payload = mcp_tools.get_cached_payload(
        doi=DOI, download_dir=tmp_path, detail="compact"
    )
    assert_mcp_tool_omits_output_schema(build_server(), "get_cached", payload)
    assert isinstance(payload["asset_summary"], dict)
