# illustration.sequence

Sequence-level selection — the M4 domain core (research report R2 §5).

M3’s [`illustration.curate()`](illustration.html.md#illustration.curate) picks the best image for *one* beat in isolation.
A storyboard is a *sequence*, so the right image for beat *i* depends on its
neighbours: consecutive shots should cohere visually, the set should stay
diverse, and no two beats should land on near-duplicate images. This module adds
that cross-shot layer — the one piece of M4 the ecosystem doesn’t already own
(`burns` renders, `walkthru` orchestrates time + narration, `lacing`
persists; none of them *choose* images).

The objective, greedily optimized left-to-right (an MMR-style pass, R2 §5):

```default
J(s) = Σ_i  rel(s_i)                          # per-beat relevance
     + α Σ_i  coherence(s_i, s_{i-1})         # consecutive-shot visual coherence
     − β Σ_i  redundancy(s_i, {s_j : j<i})    # diversity / anti-repetition
  subject to  phash_distance(s_i, s_j) ≥ τ    # hard near-duplicate constraint
```

Everything heavy is an **injectable seam**, and the defaults stay dependency-light
on purpose (the no-bloat directive): relevance defaults to the candidate’s
existing rerank `.score`; coherence/redundancy reuse the \*\*SigLIP image
embeddings illustration already caches in M2b\*\* (via
[`illustration.reranking.embed_images()`](illustration.reranking.html.md#illustration.reranking.embed_images), behind the `[rerank]` extra);
near-duplicate detection is an **in-house NumPy DCT perceptual hash** (no new
dep). When the embedding deps are absent the loop degrades gracefully to
relevance + dedup. Optional upgrades — `apricot` (submodular shortlisting) and
`imagededup` (CNN dedup) — plug in through the `shortlist` / `hasher` seams,
exactly like M3’s `Scorer` seam.

```pycon
>>> # offline: pure relevance, no embeddings, no dedup -> highest score per beat
>>> from illustration.schema import ImageResult
>>> beats = [
...     [ImageResult(provider="p", id="a", url="ua", score=0.9),
...      ImageResult(provider="p", id="b", url="ub", score=0.3)],
...     [ImageResult(provider="p", id="c", url="uc", score=0.2),
...      ImageResult(provider="p", id="d", url="ud", score=0.8)],
... ]
>>> sel = select_sequence(beats, embed=lambda rs: [None] * len(rs), hasher=lambda r: None)
>>> [bs.chosen.id for bs in sel.selections]
['a', 'd']
```

### Module Attributes

| [`DFLT_ALPHA`](#illustration.sequence.DFLT_ALPHA)           | Coherence reward weight (α) — how much consecutive-shot similarity is favored.                                         |
|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| [`DFLT_BETA`](#illustration.sequence.DFLT_BETA)            | Redundancy penalty weight (β) — how much repetition across the set is punished.                                        |
| [`DFLT_PHASH_THRESHOLD`](#illustration.sequence.DFLT_PHASH_THRESHOLD) | Perceptual-hash Hamming distance below which two images are "near-duplicate".                                          |
| [`DFLT_SEQUENCE_N`](#illustration.sequence.DFLT_SEQUENCE_N)      | Default candidate-pool width requested per beat by [`curate_sequence()`](#illustration.sequence.curate_sequence). |

### Functions

| [`select_sequence`](#illustration.sequence.select_sequence)(per_beat_candidates, \*[, ...])    | Choose one image per beat optimizing relevance + coherence − redundancy.    |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`curate_sequence`](#illustration.sequence.curate_sequence)(beats, \*[, sources, n, per_beat]) | Curate a whole sequence: gather a candidate pool per beat, then select.     |
| [`phash`](#illustration.sequence.phash)(image, \*[, hash_size, highfreq_factor])     | A DCT perceptual hash of a PIL image, as a `hash_size**2`-bit integer.      |
| [`hamming_distance`](#illustration.sequence.hamming_distance)(a, b)                             | Number of differing bits between two perceptual hashes.                     |
| [`make_phash_hasher`](#illustration.sequence.make_phash_hasher)(\*[, field, fetch])              | A pHash hasher that fetches each result's image once (cached for the pass). |

### Classes

| [`SequenceSelection`](#illustration.sequence.SequenceSelection)(\*\*data)   | One image chosen per beat, optimized for the cross-shot objective.   |
|--------------------------------------------------------------------------------|----------------------------------------------------------------------|
| [`BeatSelection`](#illustration.sequence.BeatSelection)(\*\*data)       | The chosen image (and why) for one beat in a sequence.               |
| [`SequenceResult`](#illustration.sequence.SequenceResult)(\*\*data)      | The result of curating a whole sequence of beats.                    |

### *class* illustration.sequence.BeatSelection(\*\*data)

Bases: `BaseModel`

The chosen image (and why) for one beat in a sequence.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### illustration.sequence.DFLT_ALPHA *= 0.3*

Coherence reward weight (α) — how much consecutive-shot similarity is favored.

### illustration.sequence.DFLT_BETA *= 0.5*

Redundancy penalty weight (β) — how much repetition across the set is punished.

### illustration.sequence.DFLT_PHASH_THRESHOLD *= 6*

Perceptual-hash Hamming distance below which two images are “near-duplicate”.

### illustration.sequence.DFLT_SEQUENCE_N *= 12*

Default candidate-pool width requested per beat by [`curate_sequence()`](#illustration.sequence.curate_sequence).

### *class* illustration.sequence.SequenceResult(\*\*data)

Bases: `BaseModel`

The result of curating a whole sequence of beats.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.sequence.SequenceSelection(\*\*data)

Bases: `BaseModel`

One image chosen per beat, optimized for the cross-shot objective.

#### *property* chosen *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[ImageResult](illustration.schema.html.md#illustration.schema.ImageResult) | [None](https://docs.python.org/3/builtins/constants.html#None)]*

The chosen image per beat, in order (`None` where a beat was empty).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### illustration.sequence.curate_sequence(beats, , sources=None, n=12, per_beat=None, \*\*select_kwargs)

Curate a whole sequence: gather a candidate pool per beat, then select.

`per_beat` produces the candidate pool for one beat — a sequence of
[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult) (default: a recall + SigLIP rerank
via [`illustration.search()`](illustration.html.md#illustration.search), so pools carry relevance `.score`). For
the full per-beat CRAG loop, unwrap the loop’s `Candidate` envelopes:
`per_beat=lambda b: [c.result for c in illustration.curate(b).candidates]`.
Remaining keyword args pass through to [`select_sequence()`](#illustration.sequence.select_sequence).

* **Return type:**
  [`SequenceResult`](#illustration.sequence.SequenceResult)

### illustration.sequence.hamming_distance(a, b)

Number of differing bits between two perceptual hashes.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### illustration.sequence.make_phash_hasher(, field='thumbnail_url', fetch=None)

A pHash hasher that fetches each result’s image once (cached for the pass).

Returns `result -> int | None` (None when the image can’t be fetched or
Pillow/NumPy aren’t installed), suitable as [`select_sequence()`](#illustration.sequence.select_sequence)’s
`hasher` seam. The fetch is content-deduped within the pass.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)], [`int`](https://docs.python.org/3/builtins/functions.html#int) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]

### illustration.sequence.phash(image, , hash_size=8, highfreq_factor=4)

A DCT perceptual hash of a PIL image, as a `hash_size**2`-bit integer.

The standard pHash: resize to grayscale, take the low-frequency DCT block,
threshold against its median (excluding the DC term), pack into bits.
Implemented with a NumPy DCT matrix so it needs only Pillow + NumPy.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### illustration.sequence.select_sequence(per_beat_candidates, , relevance=None, embed=None, hasher=None, shortlist=None, alpha=0.3, beta=0.5, phash_threshold=6, signature=None)

Choose one image per beat optimizing relevance + coherence − redundancy.

A greedy left-to-right pass: at each beat, pick the candidate maximizing
`rel + α·coherence(prev) − β·max_redundancy(chosen)`, excluding any
near-duplicate (pHash Hamming < `phash_threshold`) of an already-chosen
image. If *every* candidate for a beat is a near-duplicate, the constraint is
relaxed for that beat and the choice is flagged `forced_duplicate`.

Seams (all default to the lean in-house / M2b path, injectable for tests or
upgrades): `relevance` (default: candidate `.score` or 0), `embed`
(default: cached SigLIP embeddings via `[rerank]`; coherence/redundancy are
skipped when unavailable), `hasher` (default: in-house DCT pHash; dedup is
skipped when Pillow/NumPy are unavailable), `shortlist` (optional per-beat
pre-filter, e.g. an `apricot` submodular representative set).

`signature` upgrades the duplicate constraint from *same raster* to \*same
subject\* ([`illustration.duplicates`](illustration.duplicates.html.md#module-illustration.duplicates)). pHash cannot tell that four
nineteenth-century engravings after one portrait are one picture, and a
sequence that spends four beats on them is the failure this guards. When
given, it replaces the pHash test entirely — it strictly subsumes it.

* **Return type:**
  [`SequenceSelection`](#illustration.sequence.SequenceSelection)
