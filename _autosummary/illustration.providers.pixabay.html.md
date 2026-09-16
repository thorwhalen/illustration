# illustration.providers.pixabay

Pixabay source — free commercial-use images, **API key required (query param)**.

Pixabay (`https://pixabay.com/api/`) is a second keyed provider whose license
explicitly permits **downloading, caching, and self-hosting** the files — the
download-to-your-own-server model a production pipeline wants (so `cacheable`
is `True`). Its key is sent as a **query parameter** (`key=`), not a header
— exercised here via the base `_auth_params` hook.

It is also the second provider for two canonical params: it supports `color`
(native `colors`, alongside Pexels) and `content_type` (native `image_type`
= photo/illustration/vector, alongside Openverse’s `category`), which is what
promotes both to first-class façade arguments under the ≥2-provider rule.

Quirks handled here: `tags` is a comma-separated string; the usable image URLs
are `largeImageURL` / `webformatURL` (`imageURL` needs full API access);
there is no per-result license (the single Pixabay Content License).

### Classes

| [`PixabaySource`](#illustration.providers.pixabay.PixabaySource)(\*[, session])   | Pure-search adapter for the Pixabay image API.   |
|---------------------------------------------------------------------------------|--------------------------------------------------|

### *class* illustration.providers.pixabay.PixabaySource(, session=None)

Bases: [`RetrievalSource`](illustration.base.html.md#illustration.base.RetrievalSource)

Pure-search adapter for the Pixabay image API.

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://pixabay.com/api/'*

Search endpoint URL. Required.

#### info *: [SourceInfo](illustration.base.html.md#illustration.base.SourceInfo)* *= SourceInfo(name='pixabay', description='Free commercial-use images; license permits caching + self-hosting.', requires_key=True, homepage='https://pixabay.com', default_cacheable=True, license_note='Single Pixabay Content License; download-to-own-server (no hotlink).', rate_limit='100/60s (raisable); responses must be cached 24h', tags=('stock', 'free-commercial', 'keyed', 'cacheable'))*

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

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.html.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'per_page'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'q'*

Native name of the free-text query parameter.
