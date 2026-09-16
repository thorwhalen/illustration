# illustration.config

Configuration: XDG directories and package-wide defaults (the SSOT).

All tunable constants live here so the rest of the package never hardcodes a
magic number. Directories follow the XDG base-directory convention with
per-package environment overrides, mirroring the ecosystem’s `ir`/`aix`
idiom:

| Purpose        | Environment override      | Fallback                        |
|----------------|---------------------------|---------------------------------|
| config         | `ILLUSTRATION_CONFIG_DIR` | `$XDG_CONFIG_HOME`/illustration |
| data (durable) | `ILLUSTRATION_DATA_DIR`   | `$XDG_DATA_HOME`/illustration   |
| cache (regen.) | `ILLUSTRATION_CACHE_DIR`  | `$XDG_CACHE_HOME`/illustration  |
```pycon
>>> p = cache_dir()
>>> p.name
'illustration'
```

### Module Attributes

| [`DFLT_N`](#illustration.config.DFLT_N)                 | Default number of results requested *per source*.                                                                                              |
|-------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| [`DFLT_DEDUPE`](#illustration.config.DFLT_DEDUPE)            | Collapse same-subject duplicates in `search()`.                                                                                                |
| [`DFLT_DEDUPE_STRATEGY`](#illustration.config.DFLT_DEDUPE_STRATEGY)   | the largest reproduction.                                                                                                                      |
| [`DFLT_SOURCES`](#illustration.config.DFLT_SOURCES)           | Default source set used when `search(..., source=None)`.                                                                                       |
| [`DFLT_LICENSE_ALLOWLIST`](#illustration.config.DFLT_LICENSE_ALLOWLIST) | Conservative default license allowlist for the (opt-in) license gate.                                                                          |
| [`HTTP_TIMEOUT`](#illustration.config.HTTP_TIMEOUT)           | HTTP request timeout, seconds.                                                                                                                 |
| [`MAX_PAGES`](#illustration.config.MAX_PAGES)              | Hard safety cap on how many pages a single `search` will fetch, so an unbounded `n` (or a misbehaving provider) can never loop forever.        |
| [`SEARCH_CACHE_SCHEMA`](#illustration.config.SEARCH_CACHE_SCHEMA)    | Version token folded into every cache key, so a result-schema change invalidates the cache *structurally* (a new key) rather than by deletion. |

### Functions

| [`config_dir`](#illustration.config.config_dir)(\*[, ensure])   | Directory for durable configuration (e.g. registered sources).         |
|-----------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`data_dir`](#illustration.config.data_dir)(\*[, ensure])     | Directory for durable data.                                            |
| [`cache_dir`](#illustration.config.cache_dir)(\*[, ensure])    | Directory for regenerable caches (the default search-result store).    |
| [`package_version`](#illustration.config.package_version)()          | The installed package version, or `'0+unknown'` if not installed.      |
| [`user_agent`](#illustration.config.user_agent)()               | A descriptive User-Agent string (some providers throttle default UAs). |

### illustration.config.DFLT_DEDUPE *= 'auto'*

Collapse same-subject duplicates in `search()`. A search for one person
routinely returns several reproductions of the same portrait, and a consumer
asking for N images wants N *subjects*, not N files.

The default is `"auto"`, not `True`, and the distinction is the whole
design: telling two engravings of one sitter apart requires \*looking at the
pixels\*, which a bare `search()` deliberately never does — it is a metadata
call with an offline contract. So dedup rides along with image work already
being paid for: `"auto"` means “dedupe when this call fetches images anyway”
(i.e. when reranking). Pass `dedupe=True` to force it and accept the
fetches, or `False` to switch it off. The curation layer, which always
fetches, dedupes unconditionally.

### illustration.config.DFLT_DEDUPE_STRATEGY *= 'best'*

the largest reproduction.

* **Type:**
  What to keep from each duplicate group

### illustration.config.DFLT_LICENSE_ALLOWLIST *= frozenset({'by', 'by-sa', 'cc0', 'pdm', 'pexels-license', 'pixabay-license'})*

Conservative default license allowlist for the (opt-in) license gate.
CC0 / public-domain / CC-BY / CC-BY-SA are commercial-safe (BY-SA imposes
share-alike — flagged, not rejected). NC/ND and unknowns are excluded.
Entries are compared *after* [`illustration.licensing.normalize_license()`](illustration.licensing.html.md#illustration.licensing.normalize_license)
runs over both sides, so a provider’s own spelling (`cc-by-sa-4.0`,
`Pixabay License`) matches the canonical code written here.

### illustration.config.DFLT_N *= 10*

Default number of results requested *per source*.

### illustration.config.DFLT_SOURCES *= ('openverse',)*

Default source set used when `search(..., source=None)`. Openverse first
because it needs no API key (works out of the box).

### illustration.config.HTTP_TIMEOUT *= 30*

HTTP request timeout, seconds.

### illustration.config.MAX_PAGES *= 25*

Hard safety cap on how many pages a single `search` will fetch, so an
unbounded `n` (or a misbehaving provider) can never loop forever.

### illustration.config.SEARCH_CACHE_SCHEMA *= 'illustration.search/v1'*

Version token folded into every cache key, so a result-schema change
invalidates the cache *structurally* (a new key) rather than by deletion.

### illustration.config.cache_dir(, ensure=False)

Directory for regenerable caches (the default search-result store).

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### illustration.config.config_dir(, ensure=False)

Directory for durable configuration (e.g. registered sources).

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### illustration.config.data_dir(, ensure=False)

Directory for durable data.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### illustration.config.package_version()

The installed package version, or `'0+unknown'` if not installed.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> isinstance(package_version(), str)
True
```

### illustration.config.user_agent()

A descriptive User-Agent string (some providers throttle default UAs).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> user_agent().startswith('illustration/')
True
```
