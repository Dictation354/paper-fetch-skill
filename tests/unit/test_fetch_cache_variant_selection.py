from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from paper_fetch.capability_scope import (
    BrowserStateCapabilityUse,
    CapabilityScopeBuilder,
    capability_scopes_for_query,
)
from paper_fetch.mcp.fetch_cache import FetchCache, PUBLIC_CREDENTIAL_SCOPE
from paper_fetch.mcp.cache_payloads import list_cached_payload
from paper_fetch.mcp.cache_index import (
    INDEX_VERSION,
    cache_index_path,
    read_cache_index,
    refresh_cache_index_for_doi,
    rescan_cache_index,
    scan_cached_files,
)
from paper_fetch.utils import sanitize_filename
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.runtime import RuntimeContext
from tests.unit._mcp_support import sample_envelope


DOI = "10.1000/variant-selection"


def _request(mode: str) -> FetchPaperRequest:
    return FetchPaperRequest(query=DOI, modes=[mode], prefer_cache=True)


def test_inspector_and_loader_select_compatible_rich_variant(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path)
    markdown_request = _request("markdown")
    metadata_request = _request("metadata")
    markdown = sample_envelope(modes={"markdown"}, doi=DOI)
    markdown.markdown = "# Older rich body\n"
    metadata = sample_envelope(modes={"metadata"}, doi=DOI)
    cache.write_fetch_envelope(markdown, markdown_request)
    cache.write_fetch_envelope(metadata, metadata_request)
    resolver = mock.Mock(side_effect=AssertionError("known DOI must stay offline"))

    inspection = cache.get_payload(DOI, request=markdown_request, detail="compact")
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = cache.load_fetch_envelope(
            markdown_request,
            resolve_paper_fn=resolver,
            context=context,
        )

    assert inspection["request_satisfied"] is True
    assert inspection["content_kind"] == "fulltext"
    assert loaded is not None
    assert loaded.markdown == "# Older rich body\n"
    resolver.assert_not_called()


def test_variant_selector_reads_each_candidate_once(
    tmp_path: Path, monkeypatch
) -> None:
    cache = FetchCache(tmp_path)
    cache.write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), _request("markdown")
    )
    cache.write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI), _request("metadata")
    )
    variants = set(tmp_path.glob("*.fetch-envelope.json"))
    real_read_text = Path.read_text
    reads: dict[Path, int] = {}

    def counted(path: Path, *args, **kwargs):
        if path in variants:
            reads[path] = reads.get(path, 0) + 1
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    cache._inspect_fetch_envelope_sidecar(DOI, _request("markdown"))

    assert reads == {path: 1 for path in variants}


def test_private_loader_falls_back_to_public_but_never_another_private(
    tmp_path: Path,
) -> None:
    public_dir = tmp_path / "public-fallback"
    public_cache = FetchCache(public_dir)
    public_cache.write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), _request("markdown")
    )
    private_scope = "credential:" + ("1" * 64)
    other_private_scope = "credential:" + ("2" * 64)
    with RuntimeContext(env={}, download_dir=public_dir) as context:
        public_fallback = FetchCache(
            public_dir,
            credential_scope=private_scope,
        ).load_fetch_envelope(
            _request("markdown"),
            resolve_paper_fn=mock.Mock(),
            context=context,
        )

    private_dir = tmp_path / "private-only"
    FetchCache(private_dir, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), _request("markdown")
    )
    with RuntimeContext(env={}, download_dir=private_dir) as context:
        other_private = FetchCache(
            private_dir,
            credential_scope=other_private_scope,
        ).load_fetch_envelope(
            _request("markdown"),
            resolve_paper_fn=mock.Mock(),
            context=context,
        )
        public_reader = FetchCache(
            private_dir,
            credential_scope=PUBLIC_CREDENTIAL_SCOPE,
        ).load_fetch_envelope(
            _request("markdown"),
            resolve_paper_fn=mock.Mock(),
            context=context,
        )

    assert public_fallback is not None
    assert other_private is None
    assert public_reader is None


def test_private_satisfying_variant_wins_before_exact_public_fallback(
    tmp_path: Path,
) -> None:
    private_scope = "credential:" + ("1" * 64)
    public_envelope = sample_envelope(modes={"markdown"}, doi=DOI)
    public_envelope.markdown = "# Public exact\n"
    private_envelope = sample_envelope(modes={"article", "markdown"}, doi=DOI)
    private_envelope.markdown = "# Private compatible\n"
    FetchCache(tmp_path).write_fetch_envelope(
        public_envelope,
        _request("markdown"),
    )
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        private_envelope,
        FetchPaperRequest(
            query=DOI,
            modes=["article", "markdown"],
            prefer_cache=True,
        ),
    )

    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = FetchCache(
            tmp_path,
            credential_scope=private_scope,
        ).load_fetch_envelope(
            _request("markdown"),
            resolve_paper_fn=mock.Mock(),
            context=context,
        )

    assert loaded is not None
    assert loaded.markdown == "# Private compatible\n"


def test_private_index_entries_are_hidden_from_public_get_and_list(
    tmp_path: Path,
) -> None:
    env = {"ELSEVIER_API_KEY": "private-index-secret"}
    private_scope = CapabilityScopeBuilder(env).build()
    request = _request("markdown")
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), request
    )

    public_get = FetchCache(tmp_path).get_payload(DOI, request=request)
    private_get = FetchCache(
        tmp_path,
        credential_scope=private_scope,
    ).get_payload(DOI, request=request)
    public_list = list_cached_payload(env={}, download_dir=tmp_path)
    private_list = list_cached_payload(env=env, download_dir=tmp_path)

    assert public_get["status"] == "miss"
    assert public_get["entries"] == []
    assert public_get["sidecar"]["reason_code"] == (
        "cache_sidecar_credential_scope_mismatch"
    )
    assert private_get["status"] == "hit"
    assert private_get["entries"]
    assert public_list["entries"] == []
    assert private_list["entries"]
    assert all(
        entry["credential_scope"] == private_scope for entry in private_list["entries"]
    )


def test_legacy_index_entry_without_scope_fails_closed_until_refresh(
    tmp_path: Path,
) -> None:
    env = {"ELSEVIER_API_KEY": "legacy-private-secret"}
    private_scope = CapabilityScopeBuilder(env).build()
    request = _request("markdown")
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), request
    )
    index_path = tmp_path / ".paper-fetch-mcp-cache.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index["entries"]:
        entry.pop("credential_scope", None)
    index_path.write_text(json.dumps(index), encoding="utf-8")

    listed = list_cached_payload(env={}, download_dir=tmp_path)
    refreshed = FetchCache(tmp_path).get_payload(DOI, request=request)

    assert listed["entries"] == []
    assert refreshed["entries"] == []
    assert refreshed["status"] == "miss"


def test_public_metadata_write_preserves_unchanged_private_artifact_scope(
    tmp_path: Path,
) -> None:
    private_scope = "credential:" + ("3" * 64)
    xml_path = tmp_path / f"{sanitize_filename(DOI)}.xml"
    xml_path.write_text("<article>licensed</article>", encoding="utf-8")
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"article"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["article"]),
    )

    FetchCache(tmp_path).write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["metadata"]),
    )

    def xml_entry() -> dict[str, object]:
        return next(
            entry
            for entry in read_cache_index(tmp_path).entries
            if Path(str(entry["path"])) == xml_path.resolve()
        )

    assert xml_entry()["credential_scope"] == private_scope
    assert all(
        Path(str(entry["path"])) != xml_path.resolve()
        for entry in FetchCache(tmp_path).list_payload()["entries"]
    )
    refresh_cache_index_for_doi(tmp_path, DOI)
    assert xml_entry()["credential_scope"] == private_scope
    rescan_cache_index(tmp_path)
    assert xml_entry()["credential_scope"] == private_scope


def test_private_metadata_write_keeps_unchanged_public_artifact_reusable(
    tmp_path: Path,
) -> None:
    private_scope = "credential:" + ("4" * 64)
    xml_path = tmp_path / f"{sanitize_filename(DOI)}.xml"
    xml_path.write_text("<article>public</article>", encoding="utf-8")
    FetchCache(tmp_path).write_fetch_envelope(
        sample_envelope(modes={"article"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["article"]),
    )
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["metadata"]),
    )

    raw_xml = next(
        entry
        for entry in read_cache_index(tmp_path).entries
        if Path(str(entry["path"])) == xml_path.resolve()
    )
    private_entries = FetchCache(
        tmp_path,
        credential_scope=private_scope,
    ).list_payload()["entries"]
    public_entries = FetchCache(tmp_path).list_payload()["entries"]

    assert raw_xml["credential_scope"] == PUBLIC_CREDENTIAL_SCOPE
    assert any(
        Path(str(entry["path"])) == xml_path.resolve() for entry in private_entries
    )
    assert any(
        Path(str(entry["path"])) == xml_path.resolve() for entry in public_entries
    )


def test_lost_index_with_multiple_sidecar_scopes_makes_artifact_ambiguous(
    tmp_path: Path,
) -> None:
    private_scope = "credential:" + ("5" * 64)
    xml_path = tmp_path / f"{sanitize_filename(DOI)}.xml"
    xml_path.write_text("<article>private</article>", encoding="utf-8")
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"article"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["article"]),
    )
    cache_index_path(tmp_path).unlink()

    FetchCache(tmp_path).write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["metadata"]),
    )

    raw_xml = next(
        entry
        for entry in read_cache_index(tmp_path).entries
        if Path(str(entry["path"])) == xml_path.resolve()
    )
    assert "credential_scope" not in raw_xml
    assert all(
        Path(str(entry["path"])) != xml_path.resolve()
        for entry in FetchCache(tmp_path).list_payload()["entries"]
    )
    assert all(
        Path(str(entry["path"])) != xml_path.resolve()
        for entry in FetchCache(
            tmp_path, credential_scope=private_scope
        ).list_payload()["entries"]
    )
    rescan_cache_index(tmp_path)
    rescanned_xml = next(
        entry
        for entry in read_cache_index(tmp_path).entries
        if Path(str(entry["path"])) == xml_path.resolve()
    )
    assert "credential_scope" not in rescanned_xml


def test_true_legacy_v2_private_entry_without_stat_or_scope_stays_ambiguous(
    tmp_path: Path,
) -> None:
    xml_path = tmp_path / f"{sanitize_filename(DOI)}.xml"
    xml_path.write_text("<article>legacy licensed content</article>", encoding="utf-8")
    [legacy_entry] = scan_cached_files(tmp_path, DOI)
    for key in ("device", "inode", "mtime_ns", "credential_scope"):
        legacy_entry.pop(key, None)
    cache_index_path(tmp_path).write_text(
        json.dumps({"version": INDEX_VERSION, "entries": [legacy_entry]}),
        encoding="utf-8",
    )

    refresh_cache_index_for_doi(tmp_path, DOI)
    [refreshed_entry] = read_cache_index(tmp_path).entries

    assert "credential_scope" not in refreshed_entry
    assert "device" in refreshed_entry
    assert FetchCache(tmp_path).list_payload()["entries"] == []

    FetchCache(tmp_path).write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI),
        FetchPaperRequest(query=DOI, modes=["metadata"]),
    )
    xml_after_public_write = next(
        entry
        for entry in read_cache_index(tmp_path).entries
        if Path(str(entry["path"])) == xml_path.resolve()
    )
    assert "credential_scope" not in xml_after_public_write


def test_constructor_cannot_widen_public_or_private_reader_scopes() -> None:
    private_scope = "credential:" + ("1" * 64)
    other_private_scope = "credential:" + ("2" * 64)

    public_reader = FetchCache(
        None,
        credential_scope=PUBLIC_CREDENTIAL_SCOPE,
        read_credential_scopes=(private_scope, PUBLIC_CREDENTIAL_SCOPE),
    )
    private_reader = FetchCache(
        None,
        credential_scope=private_scope,
        read_credential_scopes=(other_private_scope, private_scope),
    )

    assert public_reader.read_credential_scopes == (PUBLIC_CREDENTIAL_SCOPE,)
    assert private_reader.read_credential_scopes == (
        private_scope,
        PUBLIC_CREDENTIAL_SCOPE,
    )


def test_deleted_browser_state_cannot_read_state_backed_sidecar(tmp_path: Path) -> None:
    state = tmp_path / "profile" / "storage-state.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    env = {"PAPER_FETCH_BROWSER_PROFILE_DIR": str(state.parent)}
    use = BrowserStateCapabilityUse.from_path(
        provider="wiley",
        backend="camoufox",
        storage_state_path=state,
    )
    private_scope = CapabilityScopeBuilder(env).add_browser_state_use(use).build()
    cache = FetchCache(tmp_path / "downloads", credential_scope=private_scope)
    request = FetchPaperRequest(
        query="10.1002/state-backed", modes=["markdown"], prefer_cache=True
    )
    cache.write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=request.query), request
    )
    state.unlink()
    reader_scopes = capability_scopes_for_query(env, request.query)

    with RuntimeContext(env=env, download_dir=cache.download_dir) as context:
        loaded = FetchCache(
            cache.download_dir,
            credential_scope=reader_scopes[0],
            read_credential_scopes=reader_scopes,
        ).load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(),
            context=context,
        )

    assert reader_scopes == (PUBLIC_CREDENTIAL_SCOPE,)
    assert loaded is None


def test_known_doi_cache_miss_does_not_run_enrichment_resolver(tmp_path: Path) -> None:
    resolver = mock.Mock(
        side_effect=AssertionError("enrichment must follow cache miss")
    )
    request = FetchPaperRequest(query=DOI, modes=["markdown"], prefer_cache=True)

    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = FetchCache(tmp_path).load_fetch_envelope(
            request,
            resolve_paper_fn=resolver,
            context=context,
        )

    assert loaded is None
    resolver.assert_not_called()
