# illustration.persistence

Persist curation/selection decisions as `lacing` standoff annotations (R2 §6).

Per R2 §6, a director’s curation decisions should be **standoff annotations**, not
destructive edits: a beat → its chosen image, layered so a human override is a
*new* annotation that supersedes (never overwrites) the machine’s choice, with
full provenance. The ecosystem already has exactly this — `lacing` (the
standoff annotation system: typed `Annotation` envelope, W3C PROV-O provenance,
append-only, OTIO export). This module is the thin adapter that maps an
illustration [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult) onto lacing — it does
**not** reinvent an annotation store.

A stored selection carries the **rights record** — `license`, `license_url`,
`attribution`, `source_page_url`, `author`, `author_url`, `cacheable`
([`illustration.schema.RIGHTS_FIELDS`](illustration.schema.md#illustration.schema.RIGHTS_FIELDS)) — alongside the candidate’s identity,
under the same field names [`ImageResult`](illustration.schema.md#illustration.schema.ImageResult) uses. The
annotation is the durable artifact; a URL alone stops being able to answer “may
we ship this, and whom must we credit?” the moment the link rots or the
aggregator re-tags the file, and that is the one field set no later step can
reconstruct.

One deliberate modeling choice: a “best image for beat *i*” selection is a *graph*
relation (beat → candidate), not inherently time-keyed — but `lacing` is
interval-keyed, and at selection time the storyboard has no rendered timeline
yet. So selections are keyed on an **ordinal beat-index timeline**
(`RationalTime(i, rate=1)` = “beat *i*”), which is honest (a storyboard *is* an
ordered sequence) and lets the real render timeline stay a separate concern. If a
general “selection track” facade proves worth sharing, it belongs upstream in
`lacing`; this stays a domain-specific adapter.

Behind the optional `[persist]` extra (`lacing`); imported lazily so base
`illustration` never requires it.

```pycon
>>> # offline doctest needs lacing; skipped if the extra isn't installed
>>> import importlib.util
>>> if importlib.util.find_spec("lacing"):
...     from illustration.sequence import SequenceResult, SequenceSelection, BeatSelection
...     from illustration.schema import ImageResult
...     r = SequenceResult(beats=["dawn harbour"], selection=SequenceSelection(
...         selections=[BeatSelection(beat_index=0,
...             chosen=ImageResult(provider="p", id="x", url="u", score=0.9))]))
...     store = persist_sequence(r)
...     resolve_selection(store, 0)["selected"]["id"]
```

### Module Attributes

| [`SELECTION_SCHEMA_URI`](#illustration.persistence.SELECTION_SCHEMA_URI)   | The lacing body-schema URI for an illustration selection annotation.   |
|-------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`SELECTIONS_TIER`](#illustration.persistence.SELECTIONS_TIER)        | The lacing tier selections live on.                                    |

### Functions

| [`persist_sequence`](#illustration.persistence.persist_sequence)(result, \*[, store, actor, ...])   | Persist a [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult) as lacing annotations.   |
|------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| [`record_override`](#illustration.persistence.record_override)(store, beat_index, chosen, \*)      | Append a director override for `beat_index` (a new, superseding annotation).                                                            |
| [`resolve_selection`](#illustration.persistence.resolve_selection)(store, beat_index)                | The *active* selection body for a beat — the latest annotation wins.                                                                    |
| [`resolved_selections`](#illustration.persistence.resolved_selections)(store)                          | The active selection body per beat index (resolved over all overrides).                                                                 |
| [`export_otio`](#illustration.persistence.export_otio)(store[, target])                        | Export the annotation store to OpenTimelineIO (needs `lacing[otio]`).                                                                   |

### Classes

| [`SelectionBody`](#illustration.persistence.SelectionBody)(\*\*data)   | The typed body of an illustration selection annotation (lacing body schema).   |
|----------------------------------------------------------------------------|--------------------------------------------------------------------------------|

### illustration.persistence.SELECTIONS_TIER *= 'selections'*

The lacing tier selections live on.

### illustration.persistence.SELECTION_SCHEMA_URI *= 'annot://schema/illustration-selection/v1'*

The lacing body-schema URI for an illustration selection annotation.

### *class* illustration.persistence.SelectionBody(\*\*data)

Bases: `BaseModel`

The typed body of an illustration selection annotation (lacing body schema).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### illustration.persistence.export_otio(store, target=None)

Export the annotation store to OpenTimelineIO (needs `lacing[otio]`).

Thin passthrough to lacing’s OTIO adapter, so selections can flow into video
tools. Returns the bytes when `target` is None, else writes the file.

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.persistence.persist_sequence(result, , store=None, actor='agent:illustration-curate', activity='infer', at_time=None)

Persist a [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult) as lacing annotations.

One `selections`-tier annotation per beat (machine choices), keyed on the
ordinal beat timeline. Returns the store (a fresh `lacing.MemoryStore` when
`store` is None). `at_time` (a `lacing.RationalTime`) overrides the
provenance timestamp — pass it for deterministic ordering in tests; defaults
to wall-clock `RationalTime.now()`.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.persistence.record_override(store, beat_index, chosen, , beat=None, actor='user:director', reason=None, at_time=None)

Append a director override for `beat_index` (a new, superseding annotation).

Never mutates the machine’s annotation — the override is a fresh annotation on
the same beat, with `provenance.was_derived_from` pointing at the most-recent
prior selection (STAM-style append-only layering). Returns the new annotation.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.persistence.resolve_selection(store, beat_index)

The *active* selection body for a beat — the latest annotation wins.

Resolves machine choice vs. director override by provenance timestamp, so a
later override supersedes the machine’s choice without deleting it.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.persistence.resolved_selections(store)

The active selection body per beat index (resolved over all overrides).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]
