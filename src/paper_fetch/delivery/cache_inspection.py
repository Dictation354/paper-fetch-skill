"""Internal cache inspection using the same visibility rules as acquisition."""

from pathlib import Path
from ..capability_scope import capability_scopes_for_query
from ..config import build_runtime_env
from .cache_index import cache_entry_visible_for_scopes
from .fetch_cache import FetchCache
from .requests import FetchPaperRequest


def list_cached_payload(*, env=None, download_dir: Path):
    runtime_env = build_runtime_env(env)
    payload = FetchCache(download_dir).list_payload(_filter_entries=False)
    payload["entries"] = [
        entry
        for entry in payload.get("entries", [])
        if cache_entry_visible_for_scopes(
            entry, capability_scopes_for_query(runtime_env, entry.get("doi", ""))
        )
    ]
    return payload


def get_cached_payload(
    *,
    doi,
    download_dir: Path,
    env=None,
    detail="full",
    preferred_only=False,
    modes=None,
    strategy=None,
    include_refs="all",
    max_tokens="full_text",
):
    scopes = capability_scopes_for_query(build_runtime_env(env), doi)
    request = FetchPaperRequest(
        query=doi,
        modes=modes or ["markdown"],
        strategy=strategy or {},
        include_refs=include_refs,
        max_tokens=max_tokens,
        prefer_cache=True,
    )
    return FetchCache(
        download_dir, credential_scope=scopes[0], read_credential_scopes=scopes
    ).get_payload(doi, request=request, detail=detail, preferred_only=preferred_only)
