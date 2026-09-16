# illustration.expansion

Query expansion & refinement — the first node of the curation loop (R2 §1).

A narration *beat* (“a stormy harbour at dusk, fishermen hauling nets”) is not a
good stock-image query verbatim. This module turns a beat into a small set of
concrete, visual search queries, and — when a search round comes back empty or
off — refines a query given a short critique. These are the `generate_query`
and `refine_query` steps of the bounded CRAG loop.

The default generator is built on `aix.prompt_func()` (the multi-provider
LLM facade) and is imported **lazily**, so `import illustration` never requires
`aix`. Every entry point takes an injectable seam (a plain
`beat -> queries` / `(beat, critique) -> query` callable) so the loop is
fully testable offline with a stub — the same string-or-callable + lazy-LLM
idiom `ir` uses for its formulators.

```pycon
>>> # offline: inject a stub expander (no LLM, no network)
>>> expand_query("a stormy harbour", expander=lambda beat: ["harbour storm", "rough sea"])
['a stormy harbour', 'harbour storm', 'rough sea']
>>> refine_query("a stormy harbour", "too generic", refiner=lambda b, c: "harbour at dusk in a gale")
'harbour at dusk in a gale'
```

### Module Attributes

| [`Expander`](#illustration.expansion.Expander)          | An expander maps a beat to a list of candidate image-search queries.   |
|--------------------------------------------------------------------|------------------------------------------------------------------------|
| [`Refiner`](#illustration.expansion.Refiner)           | A refiner maps (beat, critique) to one improved query.                 |
| [`DFLT_N_EXPANSIONS`](#illustration.expansion.DFLT_N_EXPANSIONS) | Default number of expansions the LLM generator is asked for.           |

### Functions

| [`expand_query`](#illustration.expansion.expand_query)(beat, \*[, n, expander, model, ...])   | Expand a narration `beat` into a deduped list of image-search queries.   |
|------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`refine_query`](#illustration.expansion.refine_query)(beat, critique, \*[, refiner, model])  | Refine a query for `beat` given a short `critique` of the last round.    |
| [`make_query_expander`](#illustration.expansion.make_query_expander)(\*[, n, prompt, model])         | Build the default LLM expander on `aix` (lazy import on first call).     |
| [`make_query_refiner`](#illustration.expansion.make_query_refiner)(\*[, prompt, model])             | Build the default LLM refiner on `aix` (lazy import on first call).      |

### illustration.expansion.DFLT_N_EXPANSIONS *= 3*

Default number of expansions the LLM generator is asked for.

### illustration.expansion.Expander

An expander maps a beat to a list of candidate image-search queries.

alias of `Callable`[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### illustration.expansion.Refiner

A refiner maps (beat, critique) to one improved query.

alias of `Callable`[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.expansion.expand_query(beat, , n=3, expander=None, model=None, include_verbatim=True)

Expand a narration `beat` into a deduped list of image-search queries.

The verbatim beat is included first by default (so the literal phrasing is
never lost), followed by the expander’s suggestions. `expander` defaults to
an `aix.prompt_func()`-backed generator (built lazily); inject a
`beat -> [query, ...]` callable to override it or to test offline.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.expansion.make_query_expander(, n=3, prompt='You turn a narration beat into concrete, visual stock-image search queries.\\\\nBeat: {beat}\\\\n\\\\nWrite {n} short queries (3-7 words each), one per line, no numbering. Each must name concrete, depictable subjects/scenes/lighting a photographer could shoot — not abstract narration. Vary the angle (subject, setting, mood) across the lines.', model=None)

Build the default LLM expander on `aix` (lazy import on first call).

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### illustration.expansion.make_query_refiner(, prompt='A stock-image search for a narration beat did not return good matches.\\\\nBeat: {beat}\\\\nWhat went wrong: {critique}\\\\n\\\\nWrite ONE improved search query (3-7 words) that is more concrete and more likely to match real photographs. Output only the query, nothing else.', model=None)

Build the default LLM refiner on `aix` (lazy import on first call).

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.expansion.refine_query(beat, critique, , refiner=None, model=None)

Refine a query for `beat` given a short `critique` of the last round.

`refiner` defaults to an `aix.prompt_func()`-backed refiner (lazy);
inject a `(beat, critique) -> query` callable to override or test offline.
Falls back to the verbatim beat if the refiner errors or returns nothing.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
