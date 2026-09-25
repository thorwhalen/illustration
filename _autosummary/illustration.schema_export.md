# illustration.schema_export

Export the Python SSOT as committed JSON for the TypeScript twin (`ts/`).

`illustration` ships twice: as this Python package and as the npm package
`illustration-search` (`ts/`), which runs the same `search()` in a browser.
The two must agree on the result schema, the rights record, the licence
vocabulary, every provider’s request vocabulary, and what each provider’s
payload normalises into. None of that is re-authored on the TypeScript side:
this module writes it out as JSON, the TS build generates its types from the
schema and reads the registries as data, and its parity tests replay the
fixtures below and assert the same output byte for byte.

What lands in `<out_dir>`:

- `image-result.schema.json` — [`ImageResult`](illustration.schema.md#illustration.schema.ImageResult) as
  JSON Schema (the codegen input for the Zod type).
- `sources.json` — one record per registered source: endpoint, parameter
  names, paging caps, fixed params, auth style, canonical→native parameter
  names, and its [`SourceInfo`](illustration.base.md#illustration.base.SourceInfo).
- `constants.json` — `RIGHTS_FIELDS`, the licence alias table, the default
  allowlist, façade defaults, credential lookups, and licence-normalisation
  cases (input → canonical code) the TS port must reproduce.
- `fixtures/<source>.expected.json` — derived from the hand-authored
  `fixtures/<source>.payload.json` (shared with `conftest.py`): the
  normalised results, canonical→native translations for a fixed set of filter
  combinations, query/paging params, and the per-page clamp.

`tests/test_schema_export.py` pins the committed directory to a fresh export,
so a schema or provider change that forgets to run `illustration export-schema`
fails CI here, before the TS side can drift.

```pycon
>>> from illustration.schema_export import CANONICAL_REQUEST_CASES
>>> all(isinstance(case, dict) for case in CANONICAL_REQUEST_CASES)
True
```

### Module Attributes

| [`FIXTURE_QUERY`](#illustration.schema_export.FIXTURE_QUERY)           | The query every fixture is normalised under (it lands in `ImageResult.query`).   |
|--------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`CANONICAL_REQUEST_CASES`](#illustration.schema_export.CANONICAL_REQUEST_CASES) | Filter combinations every source translates in its fixture.                      |
| [`QUERY_CASES`](#illustration.schema_export.QUERY_CASES)             | `(query, page, per_page)` triples every source builds query params for.          |
| [`LICENSE_CASES`](#illustration.schema_export.LICENSE_CASES)           | Licence spellings the TS `normalizeLicense` must fold identically.               |

### Functions

| [`export_schema`](#illustration.schema_export.export_schema)([out_dir, sources])   | Write the JSON contract under `out_dir`; return the paths written.   |
|--------------------------------------------------------------------------------------|----------------------------------------------------------------------|

### illustration.schema_export.CANONICAL_REQUEST_CASES *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)], ...]* *= ({}, {'color': 'blue', 'content_type': 'photo', 'license_type': 'commercial', 'orientation': 'landscape', 'safe': True, 'size': 'large'}, {'content_type': 'illustration', 'orientation': 'portrait', 'size': 'medium'}, {'content_type': 'vector', 'orientation': 'square', 'size': 'small'}, {'safe': False}, {'content_type': 'hologram', 'orientation': 'diagonal', 'size': 'huge'}, {'color': '#ff0000', 'license_type': 'all-cc'})*

Filter combinations every source translates in its fixture. Chosen to hit
every canonical parameter, every `choices` guard (a valid and an invalid
value), a boolean coercion in both states, and the empty case.

### illustration.schema_export.FIXTURE_QUERY *= 'stormy harbour'*

The query every fixture is normalised under (it lands in `ImageResult.query`).

### illustration.schema_export.LICENSE_CASES *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str) | [None](https://docs.python.org/3/builtins/constants.html#None), ...]* *= (None, '', '   ', 'by-sa', 'BY', '  BY  ', 'cc0', 'CC0 1.0', 'cc-0', 'cc-zero', 'cc-by-sa-4.0', 'CC BY-SA 4.0', 'cc-by-nc-nd-2.0', 'cc_by_3.0', 'Pexels License', 'Pixabay License', 'public domain', 'Public Domain Mark', 'pdm', 'cc-pdm', 'sampling+', 'by-nc', 'CC-BY-SA-v2.5')*

Licence spellings the TS `normalizeLicense` must fold identically.

### illustration.schema_export.QUERY_CASES *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [int](https://docs.python.org/3/builtins/functions.html#int), [int](https://docs.python.org/3/builtins/functions.html#int)], ...]* *= (('stormy harbour', 1, 10), ('stormy harbour', 3, 5), ('Category:Ships at dusk', 1, 20), ('File:Stormy Harbour.jpg|File:Dusk Pier.jpg', 1, 10))*

`(query, page, per_page)` triples every source builds query params for.
The `Category:` and `File:` forms exercise Wikimedia’s routing; the
others are plain paging.

### illustration.schema_export.export_schema(out_dir=None, , sources=None)

Write the JSON contract under `out_dir`; return the paths written.

`out_dir` defaults to the `schema/` directory of *this checkout* (the
one holding the hand-authored `fixtures/*.payload.json`). This is
repository tooling: with no checkout — an installed wheel, or a directory
with no payload fixtures — it refuses rather than scattering a partial
`schema/` tree wherever the shell happens to be.

`sources` defaults to every registered source. A source with no
`fixtures/<name>.payload.json` gets no expected-fixture file (its
registry record is still written), so a provider can be registered before
its canned payload exists, but the TS parity suite will then have nothing
to replay for it.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)]
