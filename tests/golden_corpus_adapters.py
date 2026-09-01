"""Provider adapters for offline golden corpus replay tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderGoldenContract:
    route_kind: str
    content_prefix: str | tuple[str, ...]
    source: str
    primary_marker: str


@dataclass(frozen=True)
class GoldenCorpusAdapter:
    provider: str
    build_article: Callable[[Any], Any]
    lightweight_summary: Callable[[Any], dict[str, Any]]
    primary_contract: ProviderGoldenContract
    fallback_contracts: Mapping[str, ProviderGoldenContract] = field(
        default_factory=dict
    )

    def contract_for_fixture(self, fixture: Any) -> ProviderGoldenContract:
        route_kind = str(getattr(fixture, "route_kind", "") or "")
        if route_kind == self.primary_contract.route_kind:
            return self.primary_contract
        try:
            return self.fallback_contracts[route_kind]
        except KeyError as exc:
            raise ValueError(
                f"Golden corpus adapter for {self.provider!r} does not declare route_kind "
                f"{route_kind!r}. Register a provider adapter contract for new golden routes."
            ) from exc


_GOLDEN_CORPUS_ADAPTERS: dict[str, GoldenCorpusAdapter] = {}


def register_golden_corpus_adapter(adapter: GoldenCorpusAdapter) -> None:
    provider = adapter.provider.strip().lower()
    if not provider:
        raise ValueError("Golden corpus adapter provider name is required.")
    existing = _GOLDEN_CORPUS_ADAPTERS.get(provider)
    if existing is not None:
        if existing == adapter:
            return
        raise ValueError(f"Golden corpus adapter is already registered: {provider}")
    _GOLDEN_CORPUS_ADAPTERS[provider] = adapter


def golden_corpus_adapter(provider: str) -> GoldenCorpusAdapter:
    normalized = str(provider or "").strip().lower()
    try:
        return _GOLDEN_CORPUS_ADAPTERS[normalized]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported golden fixture provider: {provider}. "
            "Register tests.golden_corpus_adapters.GoldenCorpusAdapter for new providers."
        ) from exc


def iter_golden_corpus_adapters() -> tuple[GoldenCorpusAdapter, ...]:
    return tuple(_GOLDEN_CORPUS_ADAPTERS.values())


def adapter_provider_names(
    adapters: Iterable[GoldenCorpusAdapter] | None = None,
) -> tuple[str, ...]:
    return tuple(
        adapter.provider for adapter in (adapters or iter_golden_corpus_adapters())
    )
