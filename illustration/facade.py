"""The façade: :func:`search` — one call over any registered provider(s).

``search`` is the package's front door. The first argument is the query string;
everything else is keyword. It resolves which source(s) to query, translates the
canonical filters to each provider's native params, consults the SHA-256 cache,
fetches on a miss, normalizes, and returns :class:`~illustration.schema.ImageResult`
objects.

The escape hatch is the four-rung ladder from the design doc:

1. ``source=`` selects the provider(s);
2. canonical kwargs (``orientation``/``size``/``safe``/``license_type``) are
   translated per-provider;
3. ``provider_params={"pexels": {...}}`` (namespaced) and flat ``**provider_kwargs``
   pass native params straight through;
4. ``illustration.sources["pexels"]`` / ``ImageResult.raw`` reach the raw layer.

>>> # offline doctest with a stub source (no network)
>>> from illustration.base import RetrievalSource
>>> from illustration.schema import ImageResult
>>> from illustration import registry
>>> class _Stub(RetrievalSource):
...     name = "stub"
...     def _items(self, response): return []
...     def _normalize(self, item, *, query): ...  # unused
...     def search(self, query, *, n=10, **kw):
...         return [ImageResult(provider="stub", id=str(i), url=f"u{i}", query=query)
...                 for i in range(n)]
>>> registry.register_source(_Stub())                       # doctest: +ELLIPSIS
<...._Stub object at ...>
>>> hits = search("a stormy harbour at dusk", n=3, source="stub", cache=False)
>>> [h.id for h in hits]
['0', '1', '2']
>>> registry.unregister_source("stub")
"""

from __future__ import annotations

from typing import Any, Mapping

from illustration.caching import SearchCache
from illustration.config import DFLT_N
from illustration.registry import default_sources, get_source
from illustration.schema import ImageResult

__all__ = ["search"]

#: The formal canonical filter parameters (everything else is escape-hatch).
_CANONICAL_PARAMS = ("orientation", "size", "safe", "license_type")


def search(
    query: str,
    *,
    n: int = DFLT_N,
    source: "str | list[str] | None" = None,
    orientation: "str | None" = None,
    size: "str | None" = None,
    safe: bool = True,
    license_type: "str | None" = None,
    provider_params: "Mapping[str, Mapping[str, Any]] | None" = None,
    api_key: "str | None" = None,
    cache: "bool | SearchCache" = True,
    refresh: bool = False,
    **provider_kwargs: Any,
) -> list[ImageResult]:
    """Search for up to ``n`` images matching ``query`` from one or more sources.

    Args:
        query: The free-text query (first positional; required).
        n: Number of results wanted **per source** (default ``DFLT_N``).
        source: A source name, list of names, or ``None`` for the default set.
        orientation: ``landscape`` | ``portrait`` | ``square``.
        size: ``large`` | ``medium`` | ``small`` (minimum-size filter).
        safe: Exclude mature content where the provider supports it (default True).
        license_type: ``commercial`` | ``all-cc`` | ``modification`` | ``all``
            (honored by providers with license filtering, e.g. Openverse).
        provider_params: Per-source native params, e.g.
            ``{"pexels": {"color": "blue"}}`` — used when fanning out to multiple
            sources so each gets the right native overrides.
        api_key: An explicit API key (single-source convenience; usually prefer
            env vars or :func:`~illustration.credentials.using_credentials`).
        cache: ``True`` to use the default cache, ``False`` to bypass, or a
            :class:`~illustration.caching.SearchCache` instance to inject one.
        refresh: If True, ignore any cached entry and re-fetch (then re-store).
        **provider_kwargs: Flat native params for the single-source case
            (escape-hatch rung 3a), merged into the native call.

    Returns:
        A list of :class:`ImageResult`. For multiple sources, the per-source
        result lists are concatenated (Layer-2 adds rank fusion via ``ir``).

    >>> isinstance(search.__doc__, str)
    True
    """
    if not query or not isinstance(query, str):
        raise ValueError("query must be a non-empty string")
    if n <= 0:
        raise ValueError(f"n must be a positive integer, got {n}")

    names = _resolve_source_names(source)
    cache_obj = _resolve_cache(cache)
    provider_params = dict(provider_params or {})

    canonical = {
        "orientation": orientation,
        "size": size,
        "safe": safe,
        "license_type": license_type,
    }

    all_results: list[ImageResult] = []
    for name in names:
        src = get_source(name)
        # rung 3: native passthrough — namespaced per-source + flat (single-source)
        native = dict(provider_params.get(name, {}))
        if len(names) == 1:
            native.update(provider_kwargs)

        # the params that define the cache identity for this source
        key_params = {"n": n, **{k: v for k, v in canonical.items() if v is not None}}
        if native:
            key_params["native"] = dict(native)

        results = None
        if cache_obj is not None and not refresh:
            results = cache_obj.get(name, query, key_params)
        if results is None:
            results = src.search(
                query, n=n, api_key=api_key, native_params=native, **canonical
            )
            if cache_obj is not None:
                cache_obj.put(name, query, key_params, results)
        all_results.extend(results)
    return all_results


# --- internals --------------------------------------------------------------


def _resolve_source_names(source: "str | list[str] | None") -> list[str]:
    if source is None:
        return default_sources()
    if isinstance(source, str):
        return [source]
    names = list(source)
    if not names:
        raise ValueError("source list is empty; pass at least one source name")
    return names


def _resolve_cache(cache: "bool | SearchCache") -> "SearchCache | None":
    if cache is False:
        return None
    if cache is True:
        return SearchCache()
    return cache  # an injected SearchCache
