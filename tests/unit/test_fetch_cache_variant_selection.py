from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest import mock

import paper_fetch.delivery.fetch_cache as fetch_cache_module
from paper_fetch.capability_scope import (
    BrowserStateCapabilityUse,
    CapabilityScopeBuilder,
    capability_scopes_for_query,
)
from paper_fetch.delivery.fetch_cache import (
    FETCH_ENVELOPE_SIDECAR_VERSION,
    PUBLIC_CREDENTIAL_SCOPE,
    FetchCache,
)
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.runtime import RuntimeContext
from tests.support.fetch_fixtures import sample_envelope

DOI = "10.1000/variant-selection"


def _request(*modes: str) -> FetchPaperRequest:
    return FetchPaperRequest(
        query=DOI, modes=list(modes or ("markdown",)), prefer_cache=True
    )


def test_modern_nature_url_reuses_doi_cache_without_a_resolver(tmp_path: Path) -> None:
    doi = "10.1038/s41586-026-12345-x"
    cache = FetchCache(tmp_path)
    request = FetchPaperRequest(query=doi, modes=["markdown"], prefer_cache=True)
    cache.write_fetch_envelope(sample_envelope(modes={"markdown"}, doi=doi), request)
    resolver = mock.Mock(side_effect=AssertionError("known DOI must stay offline"))
    url_request = request.model_copy(
        update={"query": "https://nature.com/articles/s41586-026-12345-x"}
    )
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = cache.load_fetch_envelope(
            url_request, resolve_paper_fn=resolver, context=context
        )
    assert loaded is not None and loaded.doi == doi
    resolver.assert_not_called()


def test_single_sidecar_write_without_index_or_canonical_duplicate(
    tmp_path: Path,
) -> None:
    cache = FetchCache(tmp_path)
    request = _request("markdown")
    cache.write_fetch_envelope(sample_envelope(modes={"markdown"}, doi=DOI), request)

    sidecars = list(tmp_path.glob("*.fetch-envelope.json"))
    assert len(sidecars) == 1
    assert not (tmp_path / "10.1000_variant-selection.fetch-envelope.json").exists()
    assert not (tmp_path / ".paper-fetch-cache.json").exists()
    stored = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert stored["version"] == FETCH_ENVELOPE_SIDECAR_VERSION == 8
    assert "schema_version" not in stored["payload"]


def test_loader_reuses_superset_variant_and_projects_requested_modes(
    tmp_path: Path,
) -> None:
    cache = FetchCache(tmp_path)
    rich_request = _request("article", "markdown", "metadata")
    rich = sample_envelope(modes={"article", "markdown", "metadata"}, doi=DOI)
    rich.markdown = "# Superset body\n"
    cache.write_fetch_envelope(rich, rich_request)
    cache.write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI), _request("metadata")
    )
    resolver = mock.Mock(side_effect=AssertionError("known DOI must stay offline"))

    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = cache.load_fetch_envelope(
            _request("markdown"),
            resolve_paper_fn=resolver,
            context=context,
        )

    assert loaded is not None
    assert loaded.markdown == "# Superset body\n"
    assert loaded.article is None
    assert loaded.metadata is None
    resolver.assert_not_called()


def test_malformed_exact_sidecar_does_not_hide_valid_superset(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path)
    request = _request("markdown")
    cache.write_fetch_envelope(sample_envelope(modes={"markdown"}, doi=DOI), request)
    (exact_path,) = tmp_path.glob("*.fetch-envelope.json")
    payload = json.loads(exact_path.read_text(encoding="utf-8"))
    payload["payload"]["quality"]["content_kind"] = []
    exact_path.write_text(json.dumps(payload), encoding="utf-8")

    rich = sample_envelope(modes={"article", "markdown"}, doi=DOI)
    rich.markdown = "# Verified fallback\n"
    cache.write_fetch_envelope(rich, _request("article", "markdown"))
    resolver = mock.Mock(side_effect=AssertionError("known DOI must stay offline"))
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = cache.load_fetch_envelope(
            request, resolve_paper_fn=resolver, context=context
        )

    assert loaded is not None and loaded.markdown == rich.markdown
    resolver.assert_not_called()


def test_lightweight_header_filter_skips_envelope_deserialization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache = FetchCache(tmp_path)
    private_scope = "credential:" + ("9" * 64)
    # Write incompatible variants (wrong mode, wrong scope, and stale version)
    # with deliberately broken payload bodies that would fail deserialization.
    FetchCache(tmp_path, credential_scope=private_scope).write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), _request("markdown")
    )
    cache.write_fetch_envelope(
        sample_envelope(modes={"metadata"}, doi=DOI), _request("metadata")
    )
    for bad_path in tmp_path.glob("*.fetch-envelope.json"):
        raw = json.loads(bad_path.read_text(encoding="utf-8"))
        raw["payload"] = {"broken": True}
        bad_path.write_text(json.dumps(raw), encoding="utf-8")

    stale = tmp_path / f"10.1000_variant-selection.{'f' * 64}.fetch-envelope.json"
    stale.write_text(
        json.dumps(
            {
                "version": 7,
                "extraction_revision": 12,
                "credential_scope": "public",
                "request_fingerprint": "f" * 64,
                "request": {},
                "payload": {"broken": True},
            }
        ),
        encoding="utf-8",
    )

    decode_spy = mock.Mock(wraps=fetch_cache_module.envelope_from_payload)
    monkeypatch.setattr(fetch_cache_module, "envelope_from_payload", decode_spy)

    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = cache.load_fetch_envelope(
            _request("markdown"),
            resolve_paper_fn=mock.Mock(),
            context=context,
        )

    assert loaded is None
    decode_spy.assert_not_called()


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


def test_private_reader_prefers_exact_public_match_before_superset_scan(
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
        _request("article", "markdown"),
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
    assert loaded.markdown == "# Public exact\n"


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
        profile_dir=state.parent,
    )
    use = replace(use, content_sha256="1" * 64)
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
