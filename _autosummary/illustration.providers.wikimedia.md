# illustration.providers.wikimedia

Wikimedia Commons source — 140M+ free media, **no key**, deep file metadata.

Wikimedia Commons (the MediaWiki Action API at
`https://commons.wikimedia.org/w/api.php`) adds breadth and historical /
editorial / fine-art / scientific reference imagery to the no-key default set.
It uses a `generator=search` query feeding `prop=imageinfo` so each hit
carries the full image URL, a thumbnail, and `extmetadata` (license, license
URL, artist, attribution).

This adapter exercises the base’s general extension hooks (no per-provider hacks
in the façade): `fixed_params` (the constant `action=query` / `format`
/ `generator` / `gsrnamespace` / `prop` / `iiprop` params) and
`_page_params()` (Wikimedia paginates by `gsroffset`, not page number).

Quirks handled here: the response’s `query.pages` is a \*\*dict keyed by
pageid\*\* (sorted here by the search `index` to preserve relevance order);
licenses **vary per file** (so pair with the `license_allow` gate for
commercial use); the `Artist` field is **HTML** (stripped for `author`,
with the first `href` lifted into `author_url`); the File namespace includes
non-images (PDF/audio/video) which are dropped during normalization by MIME.

It supports **none** of the canonical search-time filters (orientation/size/
safe/license_type/color/content_type) — they degrade gracefully.

### Classes

| [`WikimediaSource`](#illustration.providers.wikimedia.WikimediaSource)(\*[, session])   | Pure-search adapter for Wikimedia Commons (MediaWiki Action API).   |
|-----------------------------------------------------------------------------------|---------------------------------------------------------------------|

### *class* illustration.providers.wikimedia.WikimediaSource(, session=None)

Bases: [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

Pure-search adapter for Wikimedia Commons (MediaWiki Action API).

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'https://commons.wikimedia.org/w/api.php'*

Search endpoint URL. Required.

#### fixed_params *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= {'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': '6', 'iiprop': 'url|extmetadata|size|mime|user', 'iiurlwidth': '320', 'prop': 'imageinfo'}*

Constant native params sent on every request (e.g. an API mode/format).

#### info *: [SourceInfo](illustration.base.md#illustration.base.SourceInfo)* *= SourceInfo(name='wikimedia', description='140M+ free media files with deep per-file metadata; no key.', requires_key=False, homepage='https://commons.wikimedia.org', default_cacheable=True, license_note='Per-file license varies (CC/PD; some share-alike) — gate for commercial use.', rate_limit='etiquette-bound (descriptive User-Agent required)', tags=('open', 'historical', 'editorial', 'breadth', 'no-key'))*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 50*

Hard cap on results per page this provider allows.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'wikimedia'*

Registry key, e.g. `"openverse"`. Required.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'gsrsearch'*

Native name of the free-text query parameter.
