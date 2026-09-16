# illustration.reranking

Local cross-modal rerank — the precision stage (research report R1 §3).

Provider lexical/tag search is a cheap, high-recall *recall* stage; this module
is the expensive, high-precision *rerank* stage that re-scores the candidates by
true cross-modal (text↔image) similarity using a local CLIP-family model. The
default is **SigLIP 2** (Apache-2.0, commercially safe; R1’s recommended open
encoder).

The design is a clean seam: [`rerank()`](#illustration.reranking.rerank) is a torch-free orchestrator over an
injectable [`Scorer`](#illustration.reranking.Scorer) (`(query, results) -> per-result scores`). The
default scorer ([`make_siglip_scorer()`](#illustration.reranking.make_siglip_scorer)) loads SigLIP via `transformers` +
`torch` + `pillow` — all behind the optional `illustration[rerank]` extra
and imported lazily, so `import illustration` (and this module) stay light and
the scorer can later be swapped for an `ef`-hosted embedder with no call-site
change.

Typical recall→rerank→top-k use:

```default
hits = illustration.search("a stormy harbour at dusk", n=50)   # recall
top = illustration.rerank("a stormy harbour at dusk", hits)[:10]  # precision
```

or the convenience `illustration.search("...", n=50, rerank=True)[:10]`.

```pycon
>>> # orchestration is testable with a stub scorer (no model needed)
>>> from illustration.schema import ImageResult
>>> rs = [ImageResult(provider="p", id=str(i), url=f"u{i}") for i in range(3)]
>>> ranked = rerank("q", rs, scorer=lambda q, results: [0.1, 0.9, 0.5])
>>> [r.id for r in ranked], [round(r.score, 1) for r in ranked]
(['1', '2', '0'], [0.9, 0.5, 0.1])
```

### Module Attributes

| [`Scorer`](#illustration.reranking.Scorer)            | A scorer maps (query, results) -> one relevance score per result (parallel).   |
|--------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`DFLT_RERANK_MODEL`](#illustration.reranking.DFLT_RERANK_MODEL) | SigLIP 2 base (Apache-2.0).                                                    |

### Functions

| [`rerank`](#illustration.reranking.rerank)(query, results, \*[, scorer, descending])   | Re-score `results` against `query` and return them sorted by score.                                            |
|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| [`make_siglip_scorer`](#illustration.reranking.make_siglip_scorer)(\*[, model, cache, ...])        | Build a SigLIP [`SiglipScorer`](#illustration.reranking.SiglipScorer) (raises if the extra is missing). |
| [`default_scorer`](#illustration.reranking.default_scorer)([model])                            | The default (cached) SigLIP scorer for `model` — built once per model.                                         |
| [`embed_images`](#illustration.reranking.embed_images)(results, \*[, model])                 | L2-normalized SigLIP image embeddings for `results` (`None` per unfetchable).                                  |
| [`check_rerank_requirements`](#illustration.reranking.check_rerank_requirements)()                        | Raise `RerankDependencyError` if the rerank extra isn't installed.                                             |

### Classes

| [`SiglipScorer`](#illustration.reranking.SiglipScorer)(\*[, model, cache, device, ...])   | Scores (query, image) pairs by SigLIP cross-modal cosine similarity.   |
|--------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|

### illustration.reranking.DFLT_RERANK_MODEL *= 'google/siglip2-base-patch16-224'*

SigLIP 2 base (Apache-2.0). Smaller/faster than So400m; set a
larger model (e.g. `google/siglip2-so400m-patch16-384`) for higher quality.

* **Type:**
  Default encoder

### illustration.reranking.Scorer

A scorer maps (query, results) -> one relevance score per result (parallel).

alias of `Callable`[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)]], [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]]

### *class* illustration.reranking.SiglipScorer(, model='google/siglip2-base-patch16-224', cache=None, device=None, image_field='thumbnail_url')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Scores (query, image) pairs by SigLIP cross-modal cosine similarity.

The model is loaded lazily on first call; image embeddings are content-
addressed (keyed by model + image URL) in an injectable `dol` store, so a
re-rank of overlapping candidates is cheap. A candidate whose image can’t be
fetched/embedded scores `-1.0` (sorted to the bottom) rather than failing.

#### image_embeddings(results)

L2-normalized image embeddings (cached) for `results`; `None` per failure.

The image half of `__call__()`, exposed so Layer-2 sequence selection
can reuse the cached embeddings for cross-shot coherence/redundancy
without re-fetching or re-embedding.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)

### illustration.reranking.check_rerank_requirements()

Raise `RerankDependencyError` if the rerank extra isn’t installed.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.reranking.default_scorer(model='google/siglip2-base-patch16-224')

The default (cached) SigLIP scorer for `model` — built once per model.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)]], [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]]

### illustration.reranking.embed_images(results, , model='google/siglip2-base-patch16-224')

L2-normalized SigLIP image embeddings for `results` (`None` per unfetchable).

Reuses the same content-addressed embedding cache the reranker populates, so
embedding candidates a second time (e.g. for Layer-2 sequence coherence) is
cheap. Needs the `[rerank]` extra; raises `RerankDependencyError` if
it’s missing. The returned list is aligned 1:1 with `results`.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)

### illustration.reranking.make_siglip_scorer(, model='google/siglip2-base-patch16-224', cache=None, device=None, image_field='thumbnail_url')

Build a SigLIP [`SiglipScorer`](#illustration.reranking.SiglipScorer) (raises if the extra is missing).

* **Return type:**
  [`SiglipScorer`](#illustration.reranking.SiglipScorer)

### illustration.reranking.rerank(query, results, , scorer=None, descending=True)

Re-score `results` against `query` and return them sorted by score.

Each returned `ImageResult` is a copy with `.score` populated.
`scorer` defaults to the SigLIP scorer (needs the `[rerank]` extra);
inject any `(query, results) -> scores` callable to use a different model
or a test double. An empty `results` returns `[]` without loading a model.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)]
