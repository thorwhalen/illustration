# illustration.providers

Built-in provider sources, registered on import.

Importing [`illustration`](illustration.md#module-illustration) imports this package, which instantiates and
registers each built-in [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource). A
third-party provider registers itself the same way:
`illustration.register_source(MySource())`.

(This subpackage is named `providers` rather than `sources` so it does not
shadow the public `illustration.sources` registry view.)

### Classes

| [`OpenverseSource`](#illustration.providers.OpenverseSource)(\*[, session])   | Pure-search adapter for the Openverse image API (anonymous tier).   |
|-----------------------------------------------------------------------------------|---------------------------------------------------------------------|
| [`PexelsSource`](#illustration.providers.PexelsSource)(\*[, session])      | Pure-search adapter for the Pexels photo API.                       |
| [`PixabaySource`](#illustration.providers.PixabaySource)(\*[, session])     | Pure-search adapter for the Pixabay image API.                      |
| [`WikimediaSource`](#illustration.providers.WikimediaSource)(\*[, session])   | Pure-search adapter for Wikimedia Commons (MediaWiki Action API).   |

### *class* illustration.providers.OpenverseSource(, session=None)

Bases: [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

Pure-search adapter for the Openverse image API (anonymous tier).

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://api.openverse.org/v1/images/'*

Search endpoint URL. Required.

#### info *: [SourceInfo](illustration.base.md#illustration.base.SourceInfo)* *= SourceInfo(name='openverse', description='800M+ CC / public-domain images aggregated from 50+ sources.', requires_key=False, homepage='https://openverse.org', default_cacheable=True, license_note='Per-result CC/PD license; preserve attribution for BY-family.', rate_limit='anonymous: 20/min, 200/day', tags=('open', 'cc', 'public-domain', 'breadth'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 20*

Hard cap on results per page this provider allows.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'openverse'*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'color': None, 'content_type': {'choices': {'illustration', 'photo'}, 'coerce': <function OpenverseSource.<lambda>>, 'name': 'category'}, 'license_type': 'license_type', 'orientation': {'coerce': <function OpenverseSource.<lambda>>, 'name': 'aspect_ratio'}, 'safe': {'coerce': <function OpenverseSource.<lambda>>, 'name': 'mature'}, 'size': {'choices': {'large', 'medium', 'small'}, 'name': 'size'}}*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page_size'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'q'*

Native name of the free-text query parameter.

### *class* illustration.providers.PexelsSource(, session=None)

Bases: [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

Pure-search adapter for the Pexels photo API.

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://api.pexels.com/v1/search'*

Search endpoint URL. Required.

#### info *: [SourceInfo](illustration.base.md#illustration.base.SourceInfo)* *= SourceInfo(name='pexels', description='Curated high-quality stock photos under the Pexels License.', requires_key=True, homepage='https://www.pexels.com', default_cacheable=True, license_note='Single Pexels License (commercial OK); credit photographer + backlink.', rate_limit='200/hour, 20,000/month', tags=('stock', 'photos', 'keyed'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 80*

Hard cap on results per page this provider allows.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'pexels'*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'color': 'color', 'content_type': None, 'license_type': None, 'orientation': {'choices': {'landscape', 'portrait', 'square'}, 'name': 'orientation'}, 'safe': None, 'size': {'choices': {'large', 'medium', 'small'}, 'name': 'size'}}*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'per_page'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'query'*

Native name of the free-text query parameter.

### *class* illustration.providers.PixabaySource(, session=None)

Bases: [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

Pure-search adapter for the Pixabay image API.

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://pixabay.com/api/'*

Search endpoint URL. Required.

#### info *: [SourceInfo](illustration.base.md#illustration.base.SourceInfo)* *= SourceInfo(name='pixabay', description='Free commercial-use images; license permits caching + self-hosting.', requires_key=True, homepage='https://pixabay.com', default_cacheable=True, license_note='Single Pixabay Content License; download-to-own-server (no hotlink).', rate_limit='100/60s (raisable); responses must be cached 24h', tags=('stock', 'free-commercial', 'keyed', 'cacheable'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 200*

Hard cap on results per page this provider allows.

#### min_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 3*

Floor on results per page this provider allows. Default 1 (no floor);
raise it for a provider that *rejects* a small page (Pixabay’s documented
minimum is 3), so `search(q, n=1)` asks for a page the API accepts and
the extra rows are trimmed by the `n` slice rather than 400-ing.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'pixabay'*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'color': 'colors', 'content_type': {'choices': {'illustration', 'photo', 'vector'}, 'name': 'image_type'}, 'license_type': None, 'orientation': {'choices': {'landscape', 'portrait', 'square'}, 'coerce': <function PixabaySource.<lambda>>, 'name': 'orientation'}, 'safe': {'coerce': <function PixabaySource.<lambda>>, 'name': 'safesearch'}, 'size': {'choices': {'large', 'medium', 'small'}, 'coerce': <function PixabaySource.<lambda>>, 'name': 'min_width'}}*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'per_page'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'q'*

Native name of the free-text query parameter.

### *class* illustration.providers.WikimediaSource(, session=None)

Bases: [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

Pure-search adapter for Wikimedia Commons (MediaWiki Action API).

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://commons.wikimedia.org/w/api.php'*

Search endpoint URL. Required.

#### fixed_params *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'action': 'query', 'format': 'json', 'formatversion': '2', 'generator': 'search', 'gsrnamespace': '6', 'iiprop': 'url|extmetadata|size|mime|user', 'iiurlwidth': '320', 'prop': 'imageinfo'}*

Constant native params sent on every request (e.g. an API mode/format).

#### info *: [SourceInfo](illustration.base.md#illustration.base.SourceInfo)* *= SourceInfo(name='wikimedia', description='140M+ free media files with deep per-file metadata; no key.', requires_key=False, homepage='https://commons.wikimedia.org', default_cacheable=True, license_note='Per-file license varies (CC/PD; some share-alike) — gate for commercial use.', rate_limit='etiquette-bound (descriptive User-Agent required)', tags=('open', 'historical', 'editorial', 'breadth', 'no-key'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 50*

Hard cap on results per page this provider allows.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'wikimedia'*

Registry key, e.g. `"openverse"`. Required.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'gsrsearch'*

Native name of the free-text query parameter.

### Modules

| [`openverse`](illustration.providers.openverse.md#module-illustration.providers.openverse)   | Openverse source — 800M+ openly-licensed / public-domain images, **no key**.     |
|------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`pexels`](illustration.providers.pexels.md#module-illustration.providers.pexels)         | Pexels source — high-quality stock photos, **API key required**.                 |
| [`pixabay`](illustration.providers.pixabay.md#module-illustration.providers.pixabay)       | Pixabay source — free commercial-use images, **API key required (query param)**. |
| [`wikimedia`](illustration.providers.wikimedia.md#module-illustration.providers.wikimedia)   | Wikimedia Commons source — 140M+ free media, **no key**, deep file metadata.     |
