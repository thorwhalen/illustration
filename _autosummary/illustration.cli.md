# illustration.cli

Command-line surface (thin `cw` wrappers over the library functions).

Business logic lives in the library; these functions only adapt it to the shell
and format output — the dispatch-to-interface pattern. Examples:

```default
illustration search "a stormy harbour at dusk" --n 10
illustration search "rusty bicycle" --source openverse --size large --json
illustration sources
illustration info openverse
```

### Functions

| [`search`](#illustration.cli.search)(query, \*[, n, source, orientation, ...])   | Search for images and print the results (one per line, or `--json`).     |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`curate`](#illustration.cli.curate)(beat, \*[, source, n, max_iter, ...])       | Curate the best image for a narration BEAT via the bounded CRAG loop.    |
| [`curate_sequence`](#illustration.cli.curate_sequence)(\*beats[, source, n, json])        | Choose the best image per narration BEAT across a sequence (cross-shot). |
| [`sources`](#illustration.cli.sources)()                                          | List the registered image sources.                                       |
| [`info`](#illustration.cli.info)(name)                                         | Show metadata for one source.                                            |
| [`export_schema`](#illustration.cli.export_schema)(\*[, out_dir])                       | Write the JSON contract the TypeScript twin (`ts/`) is generated from.   |

### illustration.cli.curate(beat, , source=None, n=12, max_iter=3, model=None, json=False)

Curate the best image for a narration BEAT via the bounded CRAG loop.

Needs the optional `[curate]` extra (aix + ir) and provider/LLM API keys;
see the agentic-curation docs. Prints the accepted candidate (or the
best-so-far) and a one-line spend summary, or the full result with `--json`.

### illustration.cli.curate_sequence(\*beats, source=None, n=12, json=False)

Choose the best image per narration BEAT across a sequence (cross-shot).

Pass one quoted beat per argument. Optimizes relevance + cross-shot coherence
− redundancy with near-duplicate suppression (the M4 selection layer); needs
the [curate]/[rerank] extras for the full signal. Prints the chosen image per
beat, or the full result with –json.

### illustration.cli.export_schema(, out_dir=None)

Write the JSON contract the TypeScript twin (`ts/`) is generated from.

Re-run after changing [`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), a provider’s
declared vocabulary, the licence tables or a canned payload; commit the
result. `tests/test_schema_export.py` fails until you do. `out_dir`
defaults to this checkout’s `schema/`; outside a checkout it refuses.

### illustration.cli.info(name)

Show metadata for one source.

### illustration.cli.search(query, , n=10, source=None, orientation=None, size=None, safe=True, license_type=None, json=False)

Search for images and print the results (one per line, or `--json`).

### illustration.cli.sources()

List the registered image sources.
