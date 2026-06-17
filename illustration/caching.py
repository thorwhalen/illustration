"""SHA-256 content-addressed caching of search results (the ``falaw`` recipe).

The cache key is a SHA-256 over the canonicalized JSON of
``(source, query, params, schema-version)``. Canonicalization
(``sort_keys=True``, ``default=str``) makes the key invariant to dict order and
value types, so logically identical queries collapse to one entry. The
schema-version token (:data:`~illustration.config.SEARCH_CACHE_SCHEMA`) makes
invalidation *structural* — bump it and every old key is simply never hit again.

The store is an injectable ``MutableMapping`` (a ``dol`` store), defaulting to a
``JsonFiles`` directory under the cache dir; swap it for S3/Redis/Mongo without
touching call sites.

>>> store = {}                              # any MutableMapping works
>>> cache = SearchCache(store)
>>> k1 = search_cache_key("openverse", "dusk harbour", {"size": "large", "n": 10})
>>> k2 = search_cache_key("openverse", "dusk harbour", {"n": 10, "size": "large"})
>>> k1 == k2                                # dict order does not matter
True
>>> from illustration.schema import ImageResult
>>> _ = cache.put("openverse", "dusk harbour", {"n": 10},
...               [ImageResult(provider="openverse", id="1", url="u")])
>>> [r.id for r in cache.get("openverse", "dusk harbour", {"n": 10})]
['1']
>>> cache.get("openverse", "other", {"n": 10}) is None
True
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Iterable, Mapping, MutableMapping

from illustration.config import SEARCH_CACHE_SCHEMA, cache_dir
from illustration.schema import ImageResult, _coerce_results

__all__ = ["search_cache_key", "SearchCache", "default_search_store"]


def search_cache_key(source: str, query: str, params: Mapping[str, Any]) -> str:
    """Content-addressed SHA-256 key for ``(source, query, params)``.

    ``params`` should be the *normalized* request parameters (the canonical args
    actually sent, including ``n``), so two calls that differ only cosmetically
    share a key.
    """
    blob = json.dumps(
        {
            "schema": SEARCH_CACHE_SCHEMA,
            "source": source,
            "query": query,
            "params": dict(params),
        },
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class SearchCache:
    """A thin read/write facade over an injectable ``MutableMapping`` store.

    Values are stored as a small JSON envelope
    ``{schema, source, query, stored_at, results: [ImageResult.model_dump(), ...]}``.
    """

    def __init__(self, store: "MutableMapping[str, Any] | None" = None):
        self.store = store if store is not None else default_search_store()

    def get(
        self, source: str, query: str, params: Mapping[str, Any]
    ) -> "list[ImageResult] | None":
        """Return cached results for the key, or ``None`` on a miss."""
        key = search_cache_key(source, query, params)
        try:
            envelope = self.store[key]
        except KeyError:
            return None
        try:
            return _coerce_results(envelope["results"])
        except Exception:  # corrupt entry -> treat as a miss
            return None

    def put(
        self,
        source: str,
        query: str,
        params: Mapping[str, Any],
        results: Iterable[ImageResult],
    ) -> str:
        """Store ``results`` under the key; return the key."""
        key = search_cache_key(source, query, params)
        self.store[key] = {
            "schema": SEARCH_CACHE_SCHEMA,
            "source": source,
            "query": query,
            "stored_at": time.time(),
            "results": [r.model_dump() for r in results],
        }
        return key


def default_search_store() -> "MutableMapping[str, Any]":
    """A ``JsonFiles`` store under ``<cache_dir>/search`` (created on demand)."""
    from dol import JsonFiles  # local ecosystem package

    root = cache_dir(ensure=True) / "search"
    root.mkdir(parents=True, exist_ok=True)
    return JsonFiles(str(root))
