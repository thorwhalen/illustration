# illustration.providers.openverse

Openverse source — 800M+ openly-licensed / public-domain images, **no key**.

Openverse (`https://api.openverse.org/v1/images/`) aggregates Creative-Commons
and public-domain media from Flickr, Wikimedia, museums, and more. The anonymous
tier needs no credentials, which makes it the package’s out-of-the-box default
(`illustration.search("...")` works with zero setup). Every result carries a
license code, a canonical license URL (except CC0/PDM, where it is `None`), and
a ready-to-render attribution sentence — so licensing is populated from day one.

Quirks handled here (from the live-API survey): `tags` are *objects*
(`{"name": ...}`), `url` is the real image while `thumbnail` is an
Openverse proxy, and the anonymous tier caps `page_size` at 20.

### Classes

| [`OpenverseSource`](#illustration.providers.openverse.OpenverseSource)(\*[, session])   | Pure-search adapter for the Openverse image API (anonymous tier).   |
|-----------------------------------------------------------------------------------|---------------------------------------------------------------------|

### *class* illustration.providers.openverse.OpenverseSource(, session=None)

Bases: [`RetrievalSource`](illustration.base.html.md#illustration.base.RetrievalSource)

Pure-search adapter for the Openverse image API (anonymous tier).

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://api.openverse.org/v1/images/'*

Search endpoint URL. Required.

#### info *: [SourceInfo](illustration.base.html.md#illustration.base.SourceInfo)* *= SourceInfo(name='openverse', description='800M+ CC / public-domain images aggregated from 50+ sources.', requires_key=False, homepage='https://openverse.org', default_cacheable=True, license_note='Per-result CC/PD license; preserve attribution for BY-family.', rate_limit='anonymous: 20/min, 200/day', tags=('open', 'cc', 'public-domain', 'breadth'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 20*

Hard cap on results per page this provider allows.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'openverse'*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'color': None, 'content_type': {'choices': {'illustration', 'photo'}, 'coerce': <function OpenverseSource.<lambda>>, 'name': 'category'}, 'license_type': 'license_type', 'orientation': {'coerce': <function OpenverseSource.<lambda>>, 'name': 'aspect_ratio'}, 'safe': {'coerce': <function OpenverseSource.<lambda>>, 'name': 'mature'}, 'size': {'choices': {'large', 'medium', 'small'}, 'name': 'size'}}*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.html.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page_size'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'q'*

Native name of the free-text query parameter.
