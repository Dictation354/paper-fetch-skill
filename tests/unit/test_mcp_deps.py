from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from paper_fetch.config import build_runtime_env, resolve_mcp_download_dir
from paper_fetch.mcp._deps import MCPDeps, default_mcp_deps
from paper_fetch.mcp.cache_index import (
    find_cached_entry,
    list_cache_entries,
    preferred_cached_entries,
    refresh_cache_index_for_doi,
)
from paper_fetch.providers.registry import build_clients
from paper_fetch.service import fetch_paper, probe_has_fulltext, resolve_paper


class McpDepsTests(unittest.TestCase):
    def test_default_mcp_deps_points_to_production_dependencies(self) -> None:
        deps = default_mcp_deps()

        self.assertIs(deps.build_runtime_env, build_runtime_env)
        self.assertIs(deps.service_fetch_paper, fetch_paper)
        self.assertIs(deps.service_probe_has_fulltext, probe_has_fulltext)
        self.assertIs(deps.service_resolve_paper, resolve_paper)
        self.assertIs(deps.build_clients, build_clients)
        self.assertIs(deps.refresh_cache_index_for_doi, refresh_cache_index_for_doi)
        self.assertIs(deps.resolve_mcp_download_dir, resolve_mcp_download_dir)
        self.assertIs(deps.find_cached_entry, find_cached_entry)
        self.assertIs(deps.list_cache_entries, list_cache_entries)
        self.assertIs(deps.preferred_cached_entries, preferred_cached_entries)
        self.assertEqual(deps.fetch_paper_envelope.__name__, "_fetch_paper_envelope")
        self.assertEqual(
            deps.write_cached_fetch_envelope.__name__, "_write_cached_fetch_envelope"
        )

    def test_mcp_deps_round_trips_and_protects_fields(self) -> None:
        deps = default_mcp_deps()
        round_trip = MCPDeps(**deps.__dict__)

        self.assertEqual(round_trip, deps)
        with self.assertRaises(FrozenInstanceError):
            deps.build_runtime_env = lambda: {}  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
