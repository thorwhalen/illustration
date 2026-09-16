# illustration.caching

SHA-256 content-addressed caching of search results (the `falaw` recipe).

The cache key is a SHA-256 over the canonicalized JSON of
`(source, query, params, schema-version)`. Canonicalization
(`sort_keys=True`, `default=str`) makes the key invariant to dict order and
value types, so logically identical queries collapse to one entry. The
schema-version token ([`SEARCH_CACHE_SCHEMA`](illustration.config.html.md#illustration.config.SEARCH_CACHE_SCHEMA)) makes
invalidation *structural* — bump it and every old key is simply never hit again.

The store is an injectable `MutableMapping` (a `dol` store), defaulting to a
`JsonFiles` directory under the cache dir; swap it for S3/Redis/Mongo without
touching call sites.

```pycon
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
```

### Functions

| [`search_cache_key`](#illustration.caching.search_cache_key)(source, query, params)   | Content-addressed SHA-256 key for `(source, query, params)`.        |
|--------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| [`default_search_store`](#illustration.caching.default_search_store)()                    | A `JsonFiles` store under `<cache_dir>/search` (created on demand). |

### Classes

| [`SearchCache`](#illustration.caching.SearchCache)([store])   | A thin read/write facade over an injectable `MutableMapping` store.   |
|-------------------------------------------------------------------------|-----------------------------------------------------------------------|

### *class* illustration.caching.SearchCache(store=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A thin read/write facade over an injectable `MutableMapping` store.

Values are stored as a small JSON envelope
`{schema, source, query, stored_at, results: [ImageResult.model_dump(), ...]}`.

#### get(source, query, params)

Return cached results for the key, or `None` on a miss.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### put(source, query, params, results)

Store `results` under the key; return the key.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### illustration.caching.default_search_store()

A `JsonFiles` store under `<cache_dir>/search` (created on demand).

* **Return type:**
  [`MutableMapping`](https://docs.python.org/3/library/typing.html#typing.MutableMapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### illustration.caching.search_cache_key(source, query, params)

Content-addressed SHA-256 key for `(source, query, params)`.

`params` should be the *normalized* request parameters (the canonical args
actually sent, including `n`), so two calls that differ only cosmetically
share a key.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
