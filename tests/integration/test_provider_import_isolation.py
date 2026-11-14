"""Independent-process contracts for static discovery and first-use loading."""

import subprocess
import sys
import textwrap

import pytest


def run_script(script):
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_catalog_and_public_names_do_not_load_execution_dependencies():
    run_script("""
        import sys
        import paper_fetch
        from paper_fetch.providers._definitions import PROVIDER_DEFINITIONS
        execution = {d.implementation.split(":")[0] for d in PROVIDER_DEFINITIONS.values()}
        assert not execution.intersection(sys.modules)
        assert not any(name.startswith(("paper_fetch.extraction", "paper_fetch.providers.browser_runtime")) for name in sys.modules)
        class BlockExecution:
            def find_spec(self, name, path=None, target=None):
                if name in execution or name.startswith(("paper_fetch.extraction", "paper_fetch.providers.browser_runtime")):
                    raise AssertionError("Unexpected implementation import: " + name)
        sys.meta_path.insert(0, BlockExecution())
        from paper_fetch.provider_catalog import provider_names, SOURCE_PROVIDER_MAP, PROVIDER_CATALOG
        from paper_fetch.catalog_payload import provider_catalog_payload
        assert set(provider_names()) == set(PROVIDER_DEFINITIONS)
        assert SOURCE_PROVIDER_MAP and PROVIDER_CATALOG
        assert provider_catalog_payload()["providers"]
        assert set(paper_fetch.__all__).issubset(dir(paper_fetch))
    """)


@pytest.mark.parametrize("name, query", [("science", "aaas"), ("springer", "nature")])
def test_rule_alias_loads_only_the_selected_provider(name, query):
    run_script(f"""
        import sys
        from paper_fetch.providers._definitions import PROVIDER_DEFINITIONS
        blocked = {{d.implementation.split(":")[0] for n, d in PROVIDER_DEFINITIONS.items() if n != {name!r}}}
        class BlockUnselected:
            def find_spec(self, name, path=None, target=None):
                if name in blocked:
                    raise AssertionError("Unexpected provider import: " + name)
        sys.meta_path.insert(0, BlockUnselected())
        from paper_fetch.extraction.html.provider_rules import provider_html_rules, cleanup_policy_for_profile, PROVIDER_HTML_RULES, REGISTERED_NOISE_PROFILES
        rules = provider_html_rules({query!r})
        assert rules.name == PROVIDER_DEFINITIONS[{name!r}].rules_name
        assert PROVIDER_HTML_RULES[rules.name] is rules
        assert cleanup_policy_for_profile(rules.noise_profile)
        assert set(REGISTERED_NOISE_PROFILES)
        assert not blocked.intersection(sys.modules)
    """)


def test_concurrent_first_load_keeps_original_factory_and_bundle_identity():
    run_script("""
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from paper_fetch.providers._registry import provider_bundle
        from paper_fetch.providers.registry import LazyProviderClients
        barrier = threading.Barrier(8)
        clients = LazyProviderClients(object(), {})
        def load(_):
            barrier.wait()
            return provider_bundle("crossref"), clients["crossref"]
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(load, range(8)))
        from paper_fetch.providers.crossref import CrossrefClient, PROVIDER_BUNDLE
        assert all(bundle is PROVIDER_BUNDLE and client is results[0][1] for bundle, client in results)
        assert type(results[0][1]) is CrossrefClient
    """)
