# illustration.providers.pexels

Pexels source — high-quality stock photos, **API key required**.

Pexels (`https://api.pexels.com/v1/search`) is the package’s reference *keyed*
provider: it proves the registry is a true drop-in and exercises the credentials
/ `check_requirements` path. The key is sent as the **raw** value of the
`Authorization` header (no `Bearer` prefix — a prefix yields 401).

Quirks handled here (from the live-API survey): `photos[].url` is the Pexels
web *page*, not the image (the image is under `photos[].src.*`); there are no
tags and no per-result license (all content is the single Pexels License).

### Classes

| [`PexelsSource`](#illustration.providers.pexels.PexelsSource)(\*[, session])   | Pure-search adapter for the Pexels photo API.   |
|--------------------------------------------------------------------------------|-------------------------------------------------|

### *class* illustration.providers.pexels.PexelsSource(, session=None)

Bases: [`RetrievalSource`](illustration.base.html.md#illustration.base.RetrievalSource)

Pure-search adapter for the Pexels photo API.

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://api.pexels.com/v1/search'*

Search endpoint URL. Required.

#### info *: [SourceInfo](illustration.base.html.md#illustration.base.SourceInfo)* *= SourceInfo(name='pexels', description='Curated high-quality stock photos under the Pexels License.', requires_key=True, homepage='https://www.pexels.com', default_cacheable=True, license_note='Single Pexels License (commercial OK); credit photographer + backlink.', rate_limit='200/hour, 20,000/month', tags=('stock', 'photos', 'keyed'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 80*

Hard cap on results per page this provider allows.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'pexels'*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'color': 'color', 'content_type': None, 'license_type': None, 'orientation': {'choices': {'landscape', 'portrait', 'square'}, 'name': 'orientation'}, 'safe': None, 'size': {'choices': {'large', 'medium', 'small'}, 'name': 'size'}}*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.html.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'per_page'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'query'*

Native name of the free-text query parameter.
