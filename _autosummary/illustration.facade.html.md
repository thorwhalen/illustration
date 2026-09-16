# illustration.facade

The façade: [`search()`](#illustration.facade.search) — one call over any registered provider(s).

`search` is the package’s front door. The first argument is the query string;
everything else is keyword. It resolves which source(s) to query, translates the
canonical filters to each provider’s native params, consults the SHA-256 cache,
fetches on a miss, normalizes, and returns [`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)
objects.

The escape hatch is the four-rung ladder from the design doc:

1. `source=` selects the provider(s);
2. canonical kwargs (`orientation`/`size`/`safe`/`license_type`) are
   translated per-provider;
3. `provider_params={"pexels": {...}}` (namespaced) and flat `**provider_kwargs`
   pass native params straight through;
4. `illustration.sources["pexels"]` / `ImageResult.raw` reach the raw layer.

```pycon
>>> # offline doctest: a stub source implementing the real hooks (no network)
>>> from illustration.base import RetrievalSource
>>> from illustration.schema import ImageResult
>>> from illustration import registry
>>> class _Resp:
...     status_code = 200
...     def __init__(self, payload): self._payload = payload
...     def json(self): return self._payload
>>> class _Sess:  # a minimal stand-in for requests.Session
...     def get(self, url, params=None, headers=None, timeout=None):
...         return _Resp({"items": [{"id": i} for i in range(params["pp"])]})
>>> class _Stub(RetrievalSource):
...     name = "stub"
...     per_page_param = "pp"
...     max_per_page = 10
...     def _items(self, response): return response["items"]
...     def _normalize(self, item, *, query):
...         return ImageResult(provider="stub", id=str(item["id"]),
...                            url=f"u{item['id']}", query=query)
>>> _ = registry.register_source(_Stub(session=_Sess()))
>>> [h.id for h in search("a stormy harbour at dusk", n=3, source="stub", cache=False)]
['0', '1', '2']
>>> registry.unregister_source("stub")
```

### Functions

| [`search`](#illustration.facade.search)(query, \*[, n, source, orientation, ...])   | Search for up to `n` images matching `query` from one or more sources.   |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|

### illustration.facade.search(query, , n=10, source=None, orientation=None, size=None, safe=True, license_type=None, color=None, content_type=None, license_allow=False, rerank=False, dedupe='auto', provider_params=None, api_key=None, cache=True, refresh=False, \*\*provider_kwargs)

Search for up to `n` images matching `query` from one or more sources.

* **Parameters:**
  * **query** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The free-text query (first positional; required).
  * **n** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of results wanted **per source** (default `DFLT_N`).
  * **source** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – A source name, list of names, or `None` for the default set.
  * **orientation** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `landscape` | `portrait` | `square`.
  * **size** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `large` | `medium` | `small` (minimum-size filter).
  * **safe** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Exclude mature content where the provider supports it (default True).
  * **license_type** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `commercial` | `all-cc` | `modification` | `all`
    (honored by providers with license filtering, e.g. Openverse).
  * **color** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – A named color or `#hex` (Pexels, Pixabay).
  * **content_type** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `photo` | `illustration` | `vector` (Openverse,
    Pixabay; providers map/skip values they don’t support).
  * **license_allow** (`Union`[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – License gate (R3). `False` (default) = no gate; `True`
    = keep only commercial-safe licenses (CC0/PD/BY/BY-SA + Pexels);
    an iterable of license codes = keep only those. Aggregators disclaim
    license accuracy, so gate when commercial use matters.
  * **dedupe** (`Union`[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – Collapse same-subject duplicates (R4), keeping the best image
    of each subject. `"auto"` (default) dedupes only when the call
    already fetches images — i.e. when `rerank` is on — so a bare
    metadata search stays offline. `True` forces it and accepts a
    thumbnail fetch per result; `False` switches it off; a strategy
    name (`"best"` | `"all"` | `"first"`) or a
    `DuplicateGroup -> [ImageResult]` callable chooses what to keep.
    See [`illustration.duplicates`](illustration.duplicates.html.md#module-illustration.duplicates).
  * **rerank** (`Union`[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – Local cross-modal precision rerank (R1). `False` (default) =
    off; `True` = SigLIP-2 (needs the `illustration[rerank]` extra);
    a `(query, results) -> scores` callable = a custom scorer. Applied
    to the assembled results, which it re-scores (populating `.score`)
    and sorts. Use the recall→rerank pattern: `search(q, n=50,
    rerank=True)[:10]`.
  * **provider_params** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]]) – Per-source native params, e.g.
    `{"pexels": {"color": "blue"}}` — used when fanning out to multiple
    sources so each gets the right native overrides.
  * **api_key** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – An explicit API key. **Single-source only** — raises if combined
    with multiple sources; use
    [`using_credentials()`](illustration.credentials.html.md#illustration.credentials.using_credentials) for keyed fan-out.
  * **cache** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool) | [`SearchCache`](illustration.caching.html.md#illustration.caching.SearchCache)) – `True` to use the default cache, `False` to bypass, or a
    [`SearchCache`](illustration.caching.html.md#illustration.caching.SearchCache) instance to inject one.
  * **refresh** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True, ignore any cached entry and re-fetch (then re-store).
  * **\*\*provider_kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Flat native params (escape-hatch rung 3a). \*\*Single-
    source only\*\* — raises if combined with multiple sources; use
    `provider_params={source: {...}}` for fan-out.
* **Returns:**
  for multiple
  sources the per-source lists are concatenated (up to `n × len(sources)`)
  and Layer-2 adds rank fusion via `ir`.
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)]

```pycon
>>> isinstance(search.__doc__, str)
True
```
