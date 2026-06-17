"""Tests for the search() façade: dispatch, caching, multi-source, escape hatch."""

import pytest

from illustration import facade
from illustration.base import RetrievalSource
from illustration.caching import SearchCache
from illustration.registry import register_source, unregister_source
from illustration.schema import ImageResult


class _Counter(RetrievalSource):
    """A source that records calls and returns n synthetic results."""

    def __init__(self, name, **kw):
        super().__init__(**kw)
        self.name = name
        self.calls = []

    def _items(self, response):  # pragma: no cover - unused (search overridden)
        return []

    def _normalize(self, item, *, query):  # pragma: no cover - unused
        ...

    def search(self, query, *, n=10, api_key=None, native_params=None, **canonical):
        self.calls.append({"query": query, "n": n, "native": native_params, "canonical": canonical})
        return [
            ImageResult(provider=self.name, id=f"{self.name}-{i}", url=f"u{i}", query=query)
            for i in range(n)
        ]


@pytest.fixture
def counter_sources():
    a, b = _Counter("srcA"), _Counter("srcB")
    register_source(a)
    register_source(b)
    try:
        yield a, b
    finally:
        unregister_source("srcA")
        unregister_source("srcB")


def test_single_source_returns_n(counter_sources):
    a, _ = counter_sources
    results = facade.search("q", n=3, source="srcA", cache=False)
    assert [r.id for r in results] == ["srcA-0", "srcA-1", "srcA-2"]


def test_multi_source_concatenates(counter_sources):
    results = facade.search("q", n=2, source=["srcA", "srcB"], cache=False)
    providers = [r.provider for r in results]
    assert providers == ["srcA", "srcA", "srcB", "srcB"]


def test_cache_hit_avoids_second_call(counter_sources):
    a, _ = counter_sources
    cache = SearchCache({})
    facade.search("q", n=2, source="srcA", cache=cache)
    facade.search("q", n=2, source="srcA", cache=cache)
    assert len(a.calls) == 1  # second call served from cache


def test_refresh_bypasses_cache(counter_sources):
    a, _ = counter_sources
    cache = SearchCache({})
    facade.search("q", n=2, source="srcA", cache=cache)
    facade.search("q", n=2, source="srcA", cache=cache, refresh=True)
    assert len(a.calls) == 2


def test_different_params_are_different_cache_keys(counter_sources):
    a, _ = counter_sources
    cache = SearchCache({})
    facade.search("q", n=2, source="srcA", cache=cache, size="large")
    facade.search("q", n=2, source="srcA", cache=cache, size="small")
    assert len(a.calls) == 2


def test_flat_provider_kwargs_passed_as_native_single_source(counter_sources):
    a, _ = counter_sources
    facade.search("q", n=1, source="srcA", cache=False, color="blue")
    assert a.calls[0]["native"] == {"color": "blue"}


def test_namespaced_provider_params_multi_source(counter_sources):
    a, b = counter_sources
    facade.search(
        "q", n=1, source=["srcA", "srcB"], cache=False,
        provider_params={"srcB": {"color": "blue"}},
    )
    assert a.calls[0]["native"] == {}
    assert b.calls[0]["native"] == {"color": "blue"}


def test_canonical_params_forwarded(counter_sources):
    a, _ = counter_sources
    facade.search("q", n=1, source="srcA", cache=False, orientation="landscape", size="large")
    assert a.calls[0]["canonical"]["orientation"] == "landscape"
    assert a.calls[0]["canonical"]["size"] == "large"


def test_default_source_is_openverse():
    # default_sources resolves to the configured default (openverse) when no
    # source is given; we don't call the network — just check resolution.
    from illustration.facade import _resolve_source_names

    assert _resolve_source_names(None) == ["openverse"]


def test_invalid_args():
    with pytest.raises(ValueError):
        facade.search("", source="srcA")
    with pytest.raises(ValueError):
        facade.search("q", n=0, source="srcA")


def test_empty_source_list_rejected():
    with pytest.raises(ValueError):
        facade.search("q", source=[])


def test_multi_source_flat_kwargs_rejected(counter_sources):
    with pytest.raises(ValueError, match="single-source"):
        facade.search("q", source=["srcA", "srcB"], cache=False, color="blue")


def test_multi_source_api_key_rejected(counter_sources):
    with pytest.raises(ValueError, match="single-source"):
        facade.search("q", source=["srcA", "srcB"], cache=False, api_key="k")


def test_empty_results_not_cached(counter_sources):
    """A zero-hit response must not be negatively cached."""
    class _Empty(RetrievalSource):
        name = "emptysrc"

        def _items(self, response):  # pragma: no cover
            return []

        def _normalize(self, item, *, query):  # pragma: no cover
            ...

        def search(self, query, *, n=10, api_key=None, native_params=None, **canonical):
            self.calls = getattr(self, "calls", 0) + 1
            return []

    src = _Empty()
    register_source(src)
    cache = SearchCache({})
    try:
        facade.search("q", source="emptysrc", cache=cache)
        facade.search("q", source="emptysrc", cache=cache)
    finally:
        unregister_source("emptysrc")
    assert src.calls == 2  # not served from cache (empties aren't pinned)


def test_multi_source_namespaced_native_caches(counter_sources):
    a, _ = counter_sources
    cache = SearchCache({})
    pp = {"srcA": {"color": "blue"}}
    facade.search("q", n=1, source=["srcA"], cache=cache, provider_params=pp)
    facade.search("q", n=1, source=["srcA"], cache=cache, provider_params=pp)
    assert len(a.calls) == 1  # the native-param cache key round-trips
    # a different native param is a different key (cache miss)
    facade.search("q", n=1, source=["srcA"], cache=cache, provider_params={"srcA": {"color": "red"}})
    assert len(a.calls) == 2
