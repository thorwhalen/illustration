"""Tests for the SHA-256 content-addressed search cache."""

from illustration.caching import SearchCache, search_cache_key
from illustration.schema import ImageResult


def test_key_is_order_invariant():
    k1 = search_cache_key("openverse", "q", {"a": 1, "b": 2})
    k2 = search_cache_key("openverse", "q", {"b": 2, "a": 1})
    assert k1 == k2


def test_key_varies_by_source_query_params():
    base = search_cache_key("openverse", "q", {"n": 10})
    assert base != search_cache_key("pexels", "q", {"n": 10})
    assert base != search_cache_key("openverse", "other", {"n": 10})
    assert base != search_cache_key("openverse", "q", {"n": 5})


def test_put_get_roundtrip():
    cache = SearchCache({})
    results = [ImageResult(provider="openverse", id="1", url="u1", license="cc0")]
    cache.put("openverse", "q", {"n": 10}, results)
    got = cache.get("openverse", "q", {"n": 10})
    assert [r.id for r in got] == ["1"]
    assert got[0].license == "cc0"


def test_miss_returns_none():
    cache = SearchCache({})
    assert cache.get("openverse", "absent", {"n": 10}) is None


def test_corrupt_entry_is_a_miss():
    store = {}
    cache = SearchCache(store)
    key = search_cache_key("openverse", "q", {"n": 10})
    store[key] = {"results": [{"not": "a valid ImageResult"}]}
    assert cache.get("openverse", "q", {"n": 10}) is None
