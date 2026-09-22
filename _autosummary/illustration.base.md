# illustration.base

The provider plugin contract: [`RetrievalSource`](#illustration.base.RetrievalSource).

Each image-search provider is a small subclass implementing a few hooks; the
base class supplies the uniform behaviour (canonical→native translation,
pagination to satisfy `n`, HTTP with a descriptive User-Agent, credential
checking, per-item normalization that never lets one bad item fail the search).
Adding a provider touches only a new subclass + one registration — never the
façade (open-closed).

A subclass declares class attributes (`name`, `endpoint`, `query_param`,
`page_param`, `per_page_param`, `max_per_page`, `min_per_page`,
`param_map`, `info`)
and implements three hooks: `_items()`, `_normalize()`, and
(if the provider needs a key) `_auth_headers()`.

See `illustration/providers/openverse.py` for the canonical example.

### Classes

| [`RetrievalSource`](#illustration.base.RetrievalSource)(\*[, session])       | Abstract base for a pure image-search provider.                          |
|---------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`SourceInfo`](#illustration.base.SourceInfo)(name[, description, ...]) | Static, human-facing metadata about a source (for discovery + the gate). |

### *class* illustration.base.RetrievalSource(, session=None)

Bases: [`ABC`](https://docs.python.org/3/library/abc.html#abc.ABC)

Abstract base for a pure image-search provider.

Subclasses set the class attributes below and implement `_items()` and
`_normalize()` (and `_auth_headers()` if the provider needs a key).
[`search()`](#illustration.base.RetrievalSource.search) and [`raw_search()`](#illustration.base.RetrievalSource.raw_search) are \*\*template methods — do not
override them\*\*: they enforce credential checks, canonical→native
translation, pagination (capped by `MAX_PAGES`), and per-item normalization
that skips rather than fails on a malformed item. Override a hook, not the
template, so a provider can never silently lose those guarantees.

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= ''*

Search endpoint URL. Required.

#### fixed_params *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= mappingproxy({})*

Constant native params sent on every request (e.g. an API mode/format).

#### info *: [SourceInfo](#illustration.base.SourceInfo)* *= SourceInfo(name='', description='', requires_key=False, homepage=None, default_cacheable=True, license_note='', rate_limit='', tags=())*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 20*

Hard cap on results per page this provider allows.

#### min_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 1*

Floor on results per page this provider allows. Default 1 (no floor);
raise it for a provider that *rejects* a small page (Pixabay’s documented
minimum is 3), so `search(q, n=1)` asks for a page the API accepts and
the extra rows are trimmed by the `n` slice rather than 400-ing.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= ''*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= mappingproxy({})*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page_size'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'q'*

Native name of the free-text query parameter.

#### raw_search(, api_key=None, \*\*native_params)

Hit the endpoint with zero translation — the deepest escape hatch.

`native_params` are passed through verbatim as the provider’s own
query parameters; the raw decoded JSON response is returned.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

#### search(query, , n=10, api_key=None, native_params=None, \*\*canonical)

Search `query` and return up to `n` normalized `ImageResult`.

`canonical` are façade-canonical filters (see the façade `search` and
the design doc §2); each is translated to the provider’s native param via
`param_map`, degrading gracefully where unsupported. `native_params`
are raw provider-native params (the escape hatch) merged last, overriding
translated ones.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

### *class* illustration.base.SourceInfo(name, description='', requires_key=False, homepage=None, default_cacheable=True, license_note='', rate_limit='', tags=<factory>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Static, human-facing metadata about a source (for discovery + the gate).
