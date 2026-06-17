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


def test_on_disk_jsonfiles_roundtrip(monkeypatch, tmp_path):
    """Round-trip through the real default JsonFiles store (actual JSON on disk)."""
    monkeypatch.setenv("ILLUSTRATION_CACHE_DIR", str(tmp_path))
    from illustration.caching import default_search_store

    cache = SearchCache(default_search_store())
    full = ImageResult(
        provider="openverse", id="1", url="u", thumbnail_url="t", width=10, height=20,
        title="T", description="d", tags=["a", "b"], license="cc0", license_url=None,
        attribution="by x", source_page_url="sp", author="x", cacheable=True,
        avg_color="#fff", raw={"nested": {"k": [1, 2, 3]}},
    )
    cache.put("openverse", "q", {"n": 1}, [full])
    got = cache.get("openverse", "q", {"n": 1})
    assert got == [full]  # survives JSON serialization on disk
