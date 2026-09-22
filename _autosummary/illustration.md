# illustration

illustration — find existing images to illustrate narrated video.

A façade + (future) agentic layer for **cross-modal text-to-image retrieval**:
given narration text, retrieve fitting images from stock / open-media corpora.
It is *not* an image generator.

Quick start (no API key needed — Openverse is the default source):

```pycon
>>> import illustration
>>> hits = illustration.search("a stormy harbour at dusk", n=10)
>>> hits[0].url, hits[0].license, hits[0].cacheable
('https://...', 'by-sa', True)
```

The first argument is the query; everything else is keyword. `search` returns
a list of [`ImageResult`](illustration.schema.md#illustration.schema.ImageResult) (the normalized,
license-carrying result schema). Results are cached (SHA-256 content-addressed),
so an identical second call is free.

Adding a provider is open-closed — subclass
[`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource) and
[`register_source()`](#illustration.register_source) it; the façade is untouched.

See `misc/docs/design/illustration_design.md` for the full design.

### Functions

| [`search`](#illustration.search)(query, \*[, n, source, orientation, ...])   | Search for up to `n` images matching `query` from one or more sources.                                                                |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| [`license_allowlist`](#illustration.license_allowlist)(results, \*[, allow])            | Keep only results whose license is on the allowlist (R3's license gate).                                                              |
| [`check_attributions`](#illustration.check_attributions)(results)                        | Return the results whose `attribution` does not visibly name a licence.                                                               |
| [`normalize_license`](#illustration.normalize_license)(value)                           | Fold a provider's licence spelling onto one canonical, comparable code.                                                               |
| [`display_license`](#illustration.display_license)(value)                             | The conventional human spelling of a licence, for on-screen credit.                                                                   |
| [`to_search_hit`](#illustration.to_search_hit)(result)                              | Map an [`ImageResult`](#illustration.ImageResult) to an `ir.SearchHit` for Layer-2 fusion.                          |
| [`register_source`](#illustration.register_source)(source, \*[, name])                | Register a source instance under `name` (default `source.name`).                                                                      |
| [`unregister_source`](#illustration.unregister_source)(name)                            | Remove a source from the registry (no error if absent).                                                                               |
| [`get_source`](#illustration.get_source)(name)                                   | Return the registered source named `name` (raises if unknown).                                                                        |
| [`list_sources`](#illustration.list_sources)()                                     | Sorted names of all registered sources.                                                                                               |
| [`default_sources`](#illustration.default_sources)()                                  | The default source set (config `DFLT_SOURCES`), filtered to registered.                                                               |
| [`search_cache_key`](#illustration.search_cache_key)(source, query, params)            | Content-addressed SHA-256 key for `(source, query, params)`.                                                                          |
| [`default_search_store`](#illustration.default_search_store)()                             | A `JsonFiles` store under `<cache_dir>/search` (created on demand).                                                                   |
| [`using_credentials`](#illustration.using_credentials)(\*\*provider_keys)               | Bind per-request provider API keys for the duration of the `with` block.                                                              |
| [`resolve_api_key`](#illustration.resolve_api_key)(provider, \*[, api_key])           | Resolve the API key for `provider` by precedence, or `None` if absent.                                                                |
| [`check_requirements`](#illustration.check_requirements)(provider, \*[, api_key])        | Return the key for `provider`, raising if a *required* key is missing.                                                                |
| [`requires_credentials`](#illustration.requires_credentials)(provider)                     | Decorator separating credential-checking from a function's business logic.                                                            |
| [`make_param_translator`](#illustration.make_param_translator)(param_map, \*[, ...])        | Build a translator from a `param_map` (see module docstring).                                                                         |
| [`cache_dir`](#illustration.cache_dir)(\*[, ensure])                            | Directory for regenerable caches (the default search-result store).                                                                   |
| [`package_version`](#illustration.package_version)()                                  | The installed package version, or `'0+unknown'` if not installed.                                                                     |
| [`rerank`](#illustration.rerank)(query, results, \*[, scorer, descending])   | Re-score `results` against `query` and return them sorted by score.                                                                   |
| [`make_siglip_scorer`](#illustration.make_siglip_scorer)(\*[, model, cache, ...])        | Build a SigLIP `SiglipScorer` (raises if the extra is missing).                                                                       |
| [`check_rerank_requirements`](#illustration.check_rerank_requirements)()                        | Raise [`RerankDependencyError`](#illustration.RerankDependencyError) if the rerank extra isn't installed.                     |
| [`curate`](#illustration.curate)(beat, \*[, sources, n, budget, ...])        | Curate the single best image for a narration `beat` via the CRAG loop.                                                                |
| [`score_grade`](#illustration.score_grade)(results, selection)                    | The default, model-free grader — scale-robust via `ir.select` structure.                                                              |
| [`expand_query`](#illustration.expand_query)(beat, \*[, n, expander, model, ...])  | Expand a narration `beat` into a deduped list of image-search queries.                                                                |
| [`refine_query`](#illustration.refine_query)(beat, critique, \*[, refiner, model]) | Refine a query for `beat` given a short `critique` of the last round.                                                                 |
| [`prefilter`](#illustration.prefilter)(results, \*[, checks, field, fetch])     | Run `checks` over `results`, keeping only candidates that pass all.                                                                   |
| [`blur_check`](#illustration.blur_check)(\*[, min_variance])                     | Reject blurry images via variance of the Laplacian (R2 §3; OpenCV-free).                                                              |
| [`brightness_check`](#illustration.brightness_check)(\*[, min_brightness, ...])        | Reject near-black / blown-out images.                                                                                                 |
| [`nsfw_check`](#illustration.nsfw_check)(\*[, max_prob, classifier])             | Hard-drop unsafe images (R2: NSFW is a non-negotiable drop).                                                                          |
| [`inspect_candidate`](#illustration.inspect_candidate)(query, result, \*[, mode, ...])  | Inspect one candidate: a cheap caption (default) or a full rubric judge.                                                              |
| [`judge_candidate`](#illustration.judge_candidate)(query, result, \*[, ...])          | Score one candidate against `query` with a pointwise VLM rubric.                                                                      |
| [`select_sequence`](#illustration.select_sequence)(per_beat_candidates, \*[, ...])    | Choose one image per beat optimizing relevance + coherence − redundancy.                                                              |
| [`curate_sequence`](#illustration.curate_sequence)(beats, \*[, sources, n, per_beat]) | Curate a whole sequence: gather a candidate pool per beat, then select.                                                               |
| [`phash`](#illustration.phash)(image, \*[, hash_size, highfreq_factor])     | A DCT perceptual hash of a PIL image, as a `hash_size**2`-bit integer.                                                                |
| [`dedupe`](#illustration.dedupe)(results, \*[, strategy, signature, ...])    | `results` with same-subject duplicates collapsed, original order kept.                                                                |
| [`dedupe_paths`](#illustration.dedupe_paths)(paths, \*[, strategy, ...])           | The paths in `paths` with same-subject duplicates collapsed, order kept.                                                              |
| [`group_duplicates`](#illustration.group_duplicates)(results, \*[, signature, ...])    | Partition `results` into groups of the same subject.                                                                                  |
| [`group_duplicate_paths`](#illustration.group_duplicate_paths)(paths, \*[, signature, ...]) | Partition image files on disk into groups of the same subject.                                                                        |
| [`default_signature`](#illustration.default_signature)(\*\*kwargs)                      | The strongest signature whose dependencies are installed.                                                                             |
| [`local_signature`](#illustration.local_signature)([tier])                            | A signature that reads its pixels off the filesystem instead of the network.                                                          |
| [`dinov2_signature`](#illustration.dinov2_signature)([model, field, fetch])            | DINOv2 embeddings — the preferred tier for "is this the same thing?".                                                                 |
| [`siglip_signature`](#illustration.siglip_signature)([model])                          | SigLIP image embeddings, reusing the reranker's on-disk embedding cache.                                                              |
| [`phash_signature`](#illustration.phash_signature)(\*[, field, fetch])                | Perceptual hash as ±1 bits — the always-available tier.                                                                               |
| [`hamming_distance`](#illustration.hamming_distance)(a, b)                             | Number of differing bits between two perceptual hashes.                                                                               |
| [`make_phash_hasher`](#illustration.make_phash_hasher)(\*[, field, fetch])              | A pHash hasher that fetches each result's image once (cached for the pass).                                                           |
| [`persist_sequence`](#illustration.persist_sequence)(result, \*[, store, actor, ...])  | Persist a [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult) as lacing annotations. |
| [`record_override`](#illustration.record_override)(store, beat_index, chosen, \*)     | Append a director override for `beat_index` (a new, superseding annotation).                                                          |
| [`resolve_selection`](#illustration.resolve_selection)(store, beat_index)               | The *active* selection body for a beat — the latest annotation wins.                                                                  |
| [`resolved_selections`](#illustration.resolved_selections)(store)                         | The active selection body per beat index (resolved over all overrides).                                                               |
| [`export_otio`](#illustration.export_otio)(store[, target])                       | Export the annotation store to OpenTimelineIO (needs `lacing[otio]`).                                                                 |
| [`render_sequence_video`](#illustration.render_sequence_video)(selections, \*, saveas)      | Render chosen images into a single Ken-Burns film via `burns`.                                                                        |
| [`to_walkthru_document`](#illustration.to_walkthru_document)(selections, \*[, ...])        | Build a `walkthru.DemoDocument` from the selections (pure data, no render).                                                           |

### Classes

| [`ImageResult`](#illustration.ImageResult)(\*\*data)                     | One normalized image hit from any provider.                                  |
|--------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| [`RetrievalSource`](#illustration.RetrievalSource)(\*[, session])            | Abstract base for a pure image-search provider.                              |
| [`SourceInfo`](#illustration.SourceInfo)(name[, description, ...])      | Static, human-facing metadata about a source (for discovery + the gate).     |
| [`SourcesView`](#illustration.SourcesView)()                             | A live `Mapping` over the registry with dict- *and* attribute-access.        |
| [`SearchCache`](#illustration.SearchCache)([store])                      | A thin read/write facade over an injectable `MutableMapping` store.          |
| [`CurationResult`](#illustration.CurationResult)(\*\*data)                  | The outcome of curating one beat.                                            |
| [`Candidate`](#illustration.Candidate)(\*\*data)                       | One scored (and optionally inspected) candidate.                             |
| [`Budget`](#illustration.Budget)([max_iter, max_search_calls, ...]) | Hard loop bounds — the safety net, enforced in controller code (R2).         |
| [`Grade`](#illustration.Grade)(\*values)                           | CRAG's three-way retrieval grade (R2 §1).                                    |
| [`IterationRecord`](#illustration.IterationRecord)(\*\*data)                 | One iteration of the loop — the run-log R2 requires for observability.       |
| [`PrefilterResult`](#illustration.PrefilterResult)(passed, reports)          | The outcome of pre-filtering a candidate set.                                |
| [`PrefilterReport`](#illustration.PrefilterReport)(\*\*data)                 | Per-candidate pre-filter verdict (the R2 PREFILTER stage record).            |
| [`InspectReport`](#illustration.InspectReport)(\*\*data)                   | A VLM inspection of one candidate (caption or judge mode; R2 INSPECT).       |
| [`RubricScore`](#illustration.RubricScore)(\*\*data)                     | A pointwise VLM judgement of one candidate (R2 §4 rubric dimensions).        |
| [`SequenceSelection`](#illustration.SequenceSelection)(\*\*data)               | One image chosen per beat, optimized for the cross-shot objective.           |
| [`SequenceResult`](#illustration.SequenceResult)(\*\*data)                  | The result of curating a whole sequence of beats.                            |
| [`BeatSelection`](#illustration.BeatSelection)(\*\*data)                   | The chosen image (and why) for one beat in a sequence.                       |
| [`DuplicateGroup`](#illustration.DuplicateGroup)(members[, signature])      | Images judged to be the same subject, best first.                            |
| [`DuplicateSignature`](#illustration.DuplicateSignature)                        |                                                                              |
| [`SelectionBody`](#illustration.SelectionBody)(\*\*data)                   | The typed body of an illustration selection annotation (lacing body schema). |

### Exceptions

| [`IllustrationError`](#illustration.IllustrationError)                                | Base class for every error raised by [`illustration`](#module-illustration).   |
|---------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| [`UnknownSourceError`](#illustration.UnknownSourceError)(name[, known])                | A source name was requested that is not in the registry.                                              |
| [`MissingCredentialError`](#illustration.MissingCredentialError)(provider, \*[, ...])      | A source needs an API key that could not be resolved.                                                 |
| [`ProviderError`](#illustration.ProviderError)(provider, message, \*[, status])   | A provider's HTTP API returned an error or an unusable response.                                      |
| [`RateLimitError`](#illustration.RateLimitError)(provider, message, \*[, status])  | A provider returned HTTP 429 (rate limit exceeded).                                                   |
| [`RerankDependencyError`](#illustration.RerankDependencyError)([missing])                 | The optional local-rerank dependencies are not installed.                                             |
| [`CurateDependencyError`](#illustration.CurateDependencyError)([missing, extra, purpose]) | An optional Layer-2 (agentic curation) dependency is not installed.                                   |

### *class* illustration.BeatSelection(\*\*data)

Bases: `BaseModel`

The chosen image (and why) for one beat in a sequence.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.Budget(max_iter=3, max_search_calls=8, max_caption_calls=12, max_judge_calls=8, accept_threshold=0.62, correct_min_score=None, select_max_k=3, select_rel=0.9, min_score=None, max_cost=None, cost_estimator=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Hard loop bounds — the safety net, enforced in controller code (R2).

Counts and iterations are the deterministic, provider-independent caps. The
optional `cost_estimator` / `max_cost` overlay lets a caller add a money
ceiling on top; with no estimator the call/iteration caps alone bound spend.

#### accept_threshold *: [float](https://docs.python.org/3/builtins/functions.html#float)* *= 0.62*

Rubric `overall` (0-1) at/above which a judged candidate is accepted.

#### correct_min_score *: [float](https://docs.python.org/3/builtins/functions.html#float) | [None](https://docs.python.org/3/builtins/constants.html#None)* *= None*

Optional absolute relevance floor below which a *Correct*-graded dominant
candidate is escalated to the VLM judge instead of auto-accepted. `None`
(default) keeps the cheap fast-path; set it (on the reranker’s score scale)
when a dominant-but-weak top must still be rubric-verified.

#### cost_estimator *: [Callable](https://docs.python.org/3/library/typing.html#typing.Callable)[[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)], [float](https://docs.python.org/3/builtins/functions.html#float)] | [None](https://docs.python.org/3/builtins/constants.html#None)* *= None*

`(call_type, info) -> cost` estimate; `call_type` in
{“search”, “caption”, “judge”}.

#### max_cost *: [float](https://docs.python.org/3/builtins/functions.html#float) | [None](https://docs.python.org/3/builtins/constants.html#None)* *= None*

Optional money ceiling overlay. The count/iteration caps above are the
strict hard bound; `max_cost` is a *soft* ceiling — the run halts once
accrued `est_cost` reaches it, so the one call already decided upon may
push the total slightly past `max_cost` (effective bound ≈ `max_cost` +
one call’s estimate).

#### max_search_calls *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 8*

Cap on individual `(query, source)` search requests across the whole run.

#### min_score *: [float](https://docs.python.org/3/builtins/functions.html#float) | [None](https://docs.python.org/3/builtins/constants.html#None)* *= None*

Optional absolute relevance floor for `ir.select` abstention. `None` =
relative-only (the loop’s quality bar lives in the rubric, which is 0-1).

#### select_max_k *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 3*

`ir.select` tuning for the grade (conservative selector).

### *class* illustration.Candidate(\*\*data)

Bases: `BaseModel`

One scored (and optionally inspected) candidate.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### *property* quality *: [float](https://docs.python.org/3/builtins/functions.html#float)*

the rubric overall if judged, else 0.

* **Type:**
  A 0-1 comparable quality

### *exception* illustration.CurateDependencyError(missing=None, , extra='curate', purpose='agentic curation')

Bases: [`IllustrationError`](illustration.errors.md#illustration.errors.IllustrationError), [`ImportError`](https://docs.python.org/3/builtins/exceptions.html#ImportError)

An optional Layer-2 (agentic curation) dependency is not installed.

The message names the missing packages and the extra that provides them,
so the failure is actionable (e.g. `pip install 'illustration[curate]'`).

### *class* illustration.CurationResult(\*\*data)

Bases: `BaseModel`

The outcome of curating one beat.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.DuplicateGroup(members, signature='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Images judged to be the same subject, best first.

#### *property* best *: [ImageResult](illustration.schema.md#illustration.schema.ImageResult)*

The member a consumer should get — highest quality of the group.

### illustration.DuplicateSignature

alias of [`Signature`](illustration.duplicates.md#illustration.duplicates.Signature)

### *class* illustration.Grade(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

CRAG’s three-way retrieval grade (R2 §1).

### *exception* illustration.IllustrationError

Bases: [`Exception`](https://docs.python.org/3/builtins/exceptions.html#Exception)

Base class for every error raised by [`illustration`](#module-illustration).

### *class* illustration.ImageResult(\*\*data)

Bases: `BaseModel`

One normalized image hit from any provider.

The first eight fields plus `cacheable` are the cross-provider minimum the
design guarantees; the rest are populated when a provider supplies them.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### to_search_hit()

Adapt to an `ir.SearchHit` for Layer-2 cross-provider fusion.

Imported lazily so `import illustration` never requires `ir`.

### *class* illustration.InspectReport(\*\*data)

Bases: `BaseModel`

A VLM inspection of one candidate (caption or judge mode; R2 INSPECT).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.IterationRecord(\*\*data)

Bases: `BaseModel`

One iteration of the loop — the run-log R2 requires for observability.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *exception* illustration.MissingCredentialError(provider, , env_var=None, console_url=None)

Bases: [`IllustrationError`](illustration.errors.md#illustration.errors.IllustrationError)

A source needs an API key that could not be resolved.

The message tells the user exactly what to do; key values are never logged.

### *class* illustration.PrefilterReport(\*\*data)

Bases: `BaseModel`

Per-candidate pre-filter verdict (the R2 PREFILTER stage record).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.PrefilterResult(passed, reports)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The outcome of pre-filtering a candidate set.

#### *property* dropped *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[PrefilterReport](illustration.inspection.md#illustration.inspection.PrefilterReport)]*

Reports for the candidates that failed at least one check.

### *exception* illustration.ProviderError(provider, message, , status=None)

Bases: [`IllustrationError`](illustration.errors.md#illustration.errors.IllustrationError)

A provider’s HTTP API returned an error or an unusable response.

### *exception* illustration.RateLimitError(provider, message, , status=None)

Bases: [`ProviderError`](illustration.errors.md#illustration.errors.ProviderError)

A provider returned HTTP 429 (rate limit exceeded).

### *exception* illustration.RerankDependencyError(missing=None)

Bases: [`IllustrationError`](illustration.errors.md#illustration.errors.IllustrationError), [`ImportError`](https://docs.python.org/3/builtins/exceptions.html#ImportError)

The optional local-rerank dependencies are not installed.

The message names the missing packages and the extra that provides them.

### *class* illustration.RetrievalSource(, session=None)

Bases: [`ABC`](https://docs.python.org/3/library/abc.html#abc.ABC)

Abstract base for a pure image-search provider.

Subclasses set the class attributes below and implement `_items()` and
`_normalize()` (and `_auth_headers()` if the provider needs a key).
[`search()`](#illustration.search) and [`raw_search()`](#illustration.RetrievalSource.raw_search) are \*\*template methods — do not
override them\*\*: they enforce credential checks, canonical→native
translation, pagination (capped by `MAX_PAGES`), and per-item normalization
that skips rather than fails on a malformed item. Override a hook, not the
template, so a provider can never silently lose those guarantees.

#### endpoint *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= ''*

Search endpoint URL. Required.

#### fixed_params *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= mappingproxy({})*

Constant native params sent on every request (e.g. an API mode/format).

#### info *: [SourceInfo](illustration.base.md#illustration.base.SourceInfo)* *= SourceInfo(name='', description='', requires_key=False, homepage=None, default_cacheable=True, license_note='', rate_limit='', tags=())*

Static metadata (a per-instance one is synthesized in \_\_init_\_ if unset).

#### max_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 20*

Hard cap on results per page this provider allows.

#### min_per_page *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 1*

Floor on results per page this provider allows. Default 1 (no floor);
raise it for a provider that *rejects* a small page (Pixabay’s documented
minimum is 3), so `search(q, n=1)` asks for a page the API accepts and
the extra rows are trimmed by the `n` slice rather than 400-ing.

#### name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= ''*

Registry key, e.g. `"openverse"`. Required.

#### page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page'*

Native name of the page-number parameter.

#### param_map *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Any](https://docs.python.org/3/library/typing.html#typing.Any)]* *= mappingproxy({})*

Canonical→native parameter spec (see [`illustration.translation`](illustration.translation.md#module-illustration.translation)).
Immutable empty default so subclasses never share one mutable dict.

#### per_page_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'page_size'*

Native name of the results-per-page parameter.

#### query_param *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'q'*

Native name of the free-text query parameter.

#### raw_search(, api_key=None, \*\*native_params)

Hit the endpoint with zero translation — the deepest escape hatch.

`native_params` are passed through verbatim as the provider’s own
query parameters; the raw decoded JSON response is returned.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

#### search(query, , n=10, api_key=None, native_params=None, \*\*canonical)

Search `query` and return up to `n` normalized [`ImageResult`](#illustration.ImageResult).

`canonical` are façade-canonical filters (see the façade `search` and
the design doc §2); each is translated to the provider’s native param via
`param_map`, degrading gracefully where unsupported. `native_params`
are raw provider-native params (the escape hatch) merged last, overriding
translated ones.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

### *class* illustration.RubricScore(\*\*data)

Bases: `BaseModel`

A pointwise VLM judgement of one candidate (R2 §4 rubric dimensions).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### recompute_overall()

Set `overall` to the mean of the six rubric dimensions.

* **Return type:**
  [`RubricScore`](illustration.inspection.md#illustration.inspection.RubricScore)

### *class* illustration.SearchCache(store=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A thin read/write facade over an injectable `MutableMapping` store.

Values are stored as a small JSON envelope
`{schema, source, query, stored_at, results: [ImageResult.model_dump(), ...]}`.

#### get(source, query, params)

Return cached results for the key, or `None` on a miss.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### put(source, query, params, results)

Store `results` under the key; return the key.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### *class* illustration.SelectionBody(\*\*data)

Bases: `BaseModel`

The typed body of an illustration selection annotation (lacing body schema).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.SequenceResult(\*\*data)

Bases: `BaseModel`

The result of curating a whole sequence of beats.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.SequenceSelection(\*\*data)

Bases: `BaseModel`

One image chosen per beat, optimized for the cross-shot objective.

#### *property* chosen *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[ImageResult](illustration.schema.md#illustration.schema.ImageResult) | [None](https://docs.python.org/3/builtins/constants.html#None)]*

The chosen image per beat, in order (`None` where a beat was empty).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.SourceInfo(name, description='', requires_key=False, homepage=None, default_cacheable=True, license_note='', rate_limit='', tags=<factory>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Static, human-facing metadata about a source (for discovery + the gate).

### *class* illustration.SourcesView

Bases: [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)

A live `Mapping` over the registry with dict- *and* attribute-access.

Attribute access (`sources.openverse`) is a convenience; dict access
(`sources["openverse"]`) is the canonical form and the only one that works
for a source whose name collides with a `Mapping` method (`get`,
`keys`, `values`, …).

### *exception* illustration.UnknownSourceError(name, known=None)

Bases: [`IllustrationError`](illustration.errors.md#illustration.errors.IllustrationError), [`KeyError`](https://docs.python.org/3/builtins/exceptions.html#KeyError)

A source name was requested that is not in the registry.

### illustration.blur_check(, min_variance=100.0)

Reject blurry images via variance of the Laplacian (R2 §3; OpenCV-free).

The 3x3 Laplacian is applied with NumPy (no OpenCV) on the grayscale image;
a low response variance means few sharp edges, i.e. blur.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](illustration.inspection.md#illustration.inspection.CheckOutcome)]

### illustration.brightness_check(, min_brightness=0.1, max_brightness=0.95)

Reject near-black / blown-out images. Mean luminance, normalized to [0, 1].

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](illustration.inspection.md#illustration.inspection.CheckOutcome)]

### illustration.cache_dir(, ensure=False)

Directory for regenerable caches (the default search-result store).

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### illustration.check_attributions(results)

Return the results whose `attribution` does not visibly name a licence.

`license_allowlist` gates on the *machine-readable* `license` field;
this is the companion audit for the *human-readable* `attribution`
string a credit roll actually renders. CC BY / CC BY-SA require the
licence to be identified in the credit — a licensed result with a
populated, correct `license` can still carry an `attribution` that is
just an author’s name (illustration#22, seen on ~4% of one Wikimedia
session’s hits), which silently breaches that condition if a consumer
renders `attribution` verbatim, as the package’s own guide tells them
to. This never rewrites or drops a result — it is read-only, for a
pipeline to review, log, or compose a fallback credit from `author` /
`license` / `license_url` for exactly the results it returns.

A result with no `license` at all is not flagged: there is nothing to
name, and it should already have been dropped by `license_allowlist` if
that matters to the caller.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

```pycon
>>> a = ImageResult(provider="p", id="1", url="u", license="by-sa", attribution="Jane Doe")
>>> b = ImageResult(provider="p", id="2", url="u", license="by-sa",
...                  attribution="Jane Doe / CC BY-SA 4.0, via Wikimedia Commons")
>>> c = ImageResult(provider="p", id="3", url="u", license=None, attribution=None)
>>> [r.id for r in check_attributions([a, b, c])]
['1']
```

### illustration.check_requirements(provider, , api_key=None)

Return the key for `provider`, raising if a *required* key is missing.

A provider with no entry in `PROVIDER_ENV_VARS` needs no key and
returns `None`. Otherwise a missing key raises
[`MissingCredentialError`](illustration.errors.md#illustration.errors.MissingCredentialError).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.check_rerank_requirements()

Raise [`RerankDependencyError`](#illustration.RerankDependencyError) if the rerank extra isn’t installed.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.curate(beat, , sources=None, n=12, budget=None, expander=None, refiner=None, grader=None, describe=None, scorer=None, checks=None, model=None, search_fn=None, fetch=None)

Curate the single best image for a narration `beat` via the CRAG loop.

* **Parameters:**
  * **beat** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The narration beat / scene description to illustrate.
  * **sources** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Source name(s) to search, or `None` for the default set.
  * **n** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Candidates requested per source per query (recall width).
  * **budget** ([`Budget`](illustration.curation.md#illustration.curation.Budget) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Hard loop bounds (defaults to [`Budget`](#illustration.Budget)).
  * **refiner** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – Query generation / refinement seams (default: `aix`).
  * **grader** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)], [`Grade`](illustration.curation.md#illustration.curation.Grade)]]) – `(results, selection) -> Grade` (default [`score_grade()`](#illustration.score_grade)).
  * **describe** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – VLM `(image, prompt) -> text` seam (default: `aix`).
  * **scorer** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – SigLIP-style `(beat, results) -> scores` reranker. `None` uses
    the local SigLIP scorer when its deps are present, else falls back to
    the rank-fused order.
  * **checks** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](illustration.inspection.md#illustration.inspection.CheckOutcome)]]]) – Classical-CV pre-filter checks (default: dependency-aware set).
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – LLM model id passed to the default expander / refiner / describe.
  * **search_fn** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – `(query, *, source, n, ...) -> [ImageResult]` (default:
    [`illustration.search()`](#illustration.search)). Inject a stub to test offline.
  * **fetch** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – Image fetch override for the pre-filters (test double).
* **Return type:**
  [`CurationResult`](illustration.curation.md#illustration.curation.CurationResult)
* **Returns:**
  A [`CurationResult`](#illustration.CurationResult) — the accepted (or best-so-far) candidate, the
  full candidate set, the per-iteration trace, and the spend accounting.

### illustration.curate_sequence(beats, , sources=None, n=12, per_beat=None, \*\*select_kwargs)

Curate a whole sequence: gather a candidate pool per beat, then select.

`per_beat` produces the candidate pool for one beat — a sequence of
[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult) (default: a recall + SigLIP rerank
via [`illustration.search()`](#illustration.search), so pools carry relevance `.score`). For
the full per-beat CRAG loop, unwrap the loop’s `Candidate` envelopes:
`per_beat=lambda b: [c.result for c in illustration.curate(b).candidates]`.
Remaining keyword args pass through to [`select_sequence()`](#illustration.select_sequence).

* **Return type:**
  [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult)

### illustration.dedupe(results, \*, strategy='best', signature=None, threshold=None, quality=<function quality_key>)

`results` with same-subject duplicates collapsed, original order kept.

`strategy` is `"best"` (default — one image per subject, the largest),
`"all"` (group but keep everything, so a caller can choose), `"first"`
(keep the provider’s own pick), or any callable taking a
[`DuplicateGroup`](#illustration.DuplicateGroup).

Order is the order of first appearance, so the top hit stays the top hit
even when a lower-ranked member of its group is the one kept.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

### illustration.dedupe_paths(paths, \*, strategy='best', signature=None, threshold=None, quality=<function quality_key>)

The paths in `paths` with same-subject duplicates collapsed, order kept.

[`dedupe()`](#illustration.dedupe) for a folder: same `strategy` vocabulary (`"best"`,
`"all"`, `"first"`, or a callable), same first-appearance ordering, and
the same no-fetch default as [`group_duplicate_paths()`](#illustration.group_duplicate_paths). `"best"` keeps
the largest reproduction of each subject, which for a pool of stills is the
one a pan-and-zoom render can actually use.

Returns [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) objects, not [`ImageResult`](#illustration.ImageResult) wrappers —
a caller who handed in paths wants paths back, and the wrapper carries no
information the file does not.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)]

```pycon
>>> import pathlib, tempfile
>>> from PIL import Image
>>> tmp = pathlib.Path(tempfile.mkdtemp())
>>> picture = Image.linear_gradient("L").convert("RGB")
>>> picture.save(tmp / "small.png")
>>> picture.resize((512, 512)).save(tmp / "big.png")  # same picture, rescaled
>>> kept = dedupe_paths(
...     sorted(tmp.glob("*.png")), signature=local_signature(phash_signature)
... )
>>> [p.name for p in kept]
['big.png']
```

### illustration.default_search_store()

A `JsonFiles` store under `<cache_dir>/search` (created on demand).

* **Return type:**
  [`MutableMapping`](https://docs.python.org/3/library/typing.html#typing.MutableMapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### illustration.default_signature(\*\*kwargs)

The strongest signature whose dependencies are installed.

DINOv2 when `[dedupe]` is installed, pHash otherwise. pHash is always
available, so this never raises; check `Signature.subject_level` if
you need to know whether you got subject-level grouping or only raster
matching. `kwargs` (`field`, `fetch`) reach whichever tier is chosen,
so a caller can redirect *where the pixels come from* without knowing which
tier they got — see [`local_signature()`](#illustration.local_signature).

[`siglip_signature()`](#illustration.siglip_signature) is deliberately not in this chain. It needs the
same torch wheels as DINOv2 and is weaker at this job, so it can only ever
be chosen for a reason this function cannot see (the reranker has already
paid for its embeddings). It also has no `fetch` seam — it reads network
URLs only — so auto-selecting it would silently put [`local_signature()`](#illustration.local_signature)
back on the network and drop the `kwargs` on the floor. Ask for it by name.

* **Return type:**
  [`Signature`](illustration.duplicates.md#illustration.duplicates.Signature)

### illustration.default_sources()

The default source set (config `DFLT_SOURCES`), filtered to registered.

Falls back to all registered sources if none of the configured defaults are
present, so the façade always has something to query.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.dinov2_signature(model='facebook/dinov2-small', , field='thumbnail_url', fetch=None)

DINOv2 embeddings — the preferred tier for “is this the same thing?”.

Self-supervised, trained for invariance to crop and perturbation, and
stronger than caption-aligned encoders at fine-grained instance retrieval.
Uses the pooled CLS embedding and compares by cosine.

* **Return type:**
  [`Signature`](illustration.duplicates.md#illustration.duplicates.Signature)

### illustration.display_license(value)

The conventional human spelling of a licence, for on-screen credit.

Unlike [`normalize_license()`](#illustration.normalize_license) (a canonical code for *comparison*, with
the version stripped by design), this is for *display* — a credit line, a
video description, an attribution card — and works on the **recorded**
spelling rather than the normalised one, because the version is
information a normalised code deliberately drops and a credit arguably
should keep: `cc-by-sa-4.0` and a hypothetical `cc-by-sa-3.0` compare
equal under [`normalize_license()`](#illustration.normalize_license) but are not the same licence to name
on screen.

Recognised Creative Commons / public-domain codes (the same vocabulary
[`normalize_license()`](#illustration.normalize_license) produces) get the conventional spelling —
`"by-sa"` → `"CC BY-SA"`, `"cc0"` → `"CC0"`, `"pdm"` →
`"Public Domain Mark"` — with the recorded version appended if the input
carried one. This is presentation only: an input that does not resolve to
a known permission code is title-cased and returned as-is, never
reinterpreted — it must still fail [`normalize_license()`](#illustration.normalize_license)’s consumers
(e.g. [`illustration.schema.license_allowlist()`](illustration.schema.md#illustration.schema.license_allowlist)) exactly as before.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

```pycon
>>> display_license("cc-by-sa-4.0")
'CC BY-SA 4.0'
>>> display_license("CC BY-SA 4.0")
'CC BY-SA 4.0'
>>> display_license("by-sa")           # no version in the recorded spelling
'CC BY-SA'
>>> display_license("cc0"), display_license("CC0 1.0")
('CC0', 'CC0 1.0')
>>> display_license("pd"), display_license("public domain")
('Public Domain Mark', 'Public Domain Mark')
>>> display_license("cc-by-nc-nd-4.0")  # restrictions survive, same as normalize_license
'CC BY-NC-ND 4.0'
>>> display_license("Pixabay License")  # not a CC/PD code -- shown, not invented
'Pixabay License'
>>> display_license(None) is None
True
```

### illustration.expand_query(beat, , n=3, expander=None, model=None, include_verbatim=True)

Expand a narration `beat` into a deduped list of image-search queries.

The verbatim beat is included first by default (so the literal phrasing is
never lost), followed by the expander’s suggestions. `expander` defaults to
an `aix.prompt_func()`-backed generator (built lazily); inject a
`beat -> [query, ...]` callable to override it or to test offline.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.export_otio(store, target=None)

Export the annotation store to OpenTimelineIO (needs `lacing[otio]`).

Thin passthrough to lacing’s OTIO adapter, so selections can flow into video
tools. Returns the bytes when `target` is None, else writes the file.

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.get_source(name)

Return the registered source named `name` (raises if unknown).

* **Return type:**
  [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

### illustration.group_duplicate_paths(paths, \*, signature=None, threshold=None, quality=<function quality_key>)

Partition image files on disk into groups of the same subject.

[`group_duplicates()`](#illustration.group_duplicates) for a folder rather than a search — “here are 200
stills, which of them are the same picture?”. The motivating case is a
Ken Burns still pool assembled from several searches, where the same image
arrives twice under two provider ids and the film shows it twice.

The default `signature` is [`local_signature()`](#illustration.local_signature), so \*\*nothing is
fetched\*\*: the strongest installed tier is wired to open the files directly.
That is a correctness property, not an optimisation — the generic path would
treat each `url` as an address and hand every image back as `None`,
which grouping reads as “unembeddable”, so a silently-networked default
would report *no duplicates at all* rather than failing.

Groups come back in first-appearance order, members best-first. Each member
is an [`ImageResult`](#illustration.ImageResult) whose `url` is the path it came from
(`Path(member.url)`); use [`dedupe_paths()`](#illustration.dedupe_paths) if you only want the
survivors.

Two copies of one picture and one different picture:

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`DuplicateGroup`](illustration.duplicates.md#illustration.duplicates.DuplicateGroup)]

```pycon
>>> import pathlib, tempfile
>>> from PIL import Image
>>> tmp = pathlib.Path(tempfile.mkdtemp())
>>> stripes = Image.linear_gradient("L").convert("RGB")
>>> rings = Image.radial_gradient("L").convert("RGB")
>>> for name, image in [("a.png", stripes), ("a_copy.png", stripes),
...                     ("b.png", rings)]:
...     image.save(tmp / name)
>>> paths = sorted(tmp.glob("*.png"))
```

Pinning the pHash tier keeps this example offline and torch-free; drop the
`signature=` argument to get the strongest tier you have installed.

```pycon
>>> groups = group_duplicate_paths(
...     paths, signature=local_signature(phash_signature)
... )
>>> [sorted(pathlib.Path(m.url).name for m in g.members) for g in groups]
[['a.png', 'a_copy.png'], ['b.png']]
```

### illustration.group_duplicates(results, \*, signature=None, threshold=None, quality=<function quality_key>)

Partition `results` into groups of the same subject.

Single-linkage: A groups with C if A~B and B~C, even when A and C fall just
under the threshold themselves. That is the right shape here, because a run
of reproductions of one painting forms a chain — a colour original, an
engraving after it, and a re-scan of the engraving — where the ends can be
further apart than either is from the middle.

Groups come back in the order their best member first appears, and each
group’s members are sorted best-first by `quality`. An image whose
signature could not be computed is never grouped, so a fetch failure loses a
duplicate rather than silently merging two different pictures.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`DuplicateGroup`](illustration.duplicates.md#illustration.duplicates.DuplicateGroup)]

### illustration.hamming_distance(a, b)

Number of differing bits between two perceptual hashes.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### illustration.inspect_candidate(query, result, , mode='caption', describe=None, model=None, max_tokens=None)

Inspect one candidate: a cheap caption (default) or a full rubric judge.

`mode="caption"` (the *Correct*-grade path) produces a one-sentence
caption from the thumbnail; `mode="judge"` (the *Ambiguous* path) delegates
to [`judge_candidate()`](#illustration.judge_candidate). `describe` defaults to a lazy
`aix.describe_image()` bound to `model` and capped at
`max_tokens` (default `DFLT_CAPTION_MAX_TOKENS`).

* **Return type:**
  [`InspectReport`](illustration.inspection.md#illustration.inspection.InspectReport)

### illustration.judge_candidate(query, result, , describe=None, model=None, max_tokens=None)

Score one candidate against `query` with a pointwise VLM rubric.

Uses the full-resolution image for accuracy. `describe` defaults to a lazy
`aix.describe_image()` capped at `max_tokens` (default
`DFLT_JUDGE_MAX_TOKENS`). The reply is parsed into a
[`RubricScore`](#illustration.RubricScore) (`overall` = mean of the six dimensions); an
unparseable reply yields a neutral score flagged `parsed=False` so the loop
can treat it as ambiguous rather than wrongly accept or reject.

* **Return type:**
  [`InspectReport`](illustration.inspection.md#illustration.inspection.InspectReport)

### illustration.license_allowlist(results, , allow=None)

Keep only results whose license is on the allowlist (R3’s license gate).

The mandatory per-file license-verification gate for commercial-adjacent
use: aggregators disclaim license accuracy, so callers should gate on a
known-good set. Both sides are run through
[`illustration.licensing.normalize_license()`](illustration.licensing.md#illustration.licensing.normalize_license) first, so a provider’s own
spelling (`cc-by-sa-4.0` from Commons, `Pixabay License`) matches the
canonical code without the allowlist having to enumerate every dialect —
and without ever dropping an `nc`/`nd` restriction. Results with no
`license` are dropped (unknown == not allowed).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

```pycon
>>> a = ImageResult(provider="p", id="1", url="u", license="cc0")
>>> b = ImageResult(provider="p", id="2", url="u", license="by-nc")
>>> c = ImageResult(provider="p", id="3", url="u", license=None)
>>> [r.id for r in license_allowlist([a, b, c])]
['1']
>>> [r.id for r in license_allowlist([a, b, c], allow={"by-nc"})]
['2']
```

Provider dialects pass the same gate:

```pycon
>>> w = ImageResult(provider="wikimedia", id="4", url="u", license="cc-by-sa-4.0")
>>> p = ImageResult(provider="pixabay", id="5", url="u", license="Pixabay License")
>>> nd = ImageResult(provider="wikimedia", id="6", url="u", license="cc-by-nd-4.0")
>>> [r.id for r in license_allowlist([w, p, nd])]
['4', '5']
```

### illustration.list_sources()

Sorted names of all registered sources.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### illustration.local_signature(tier=<function default_signature>, \*\*kwargs)

A signature that reads its pixels off the filesystem instead of the network.

The one seam the local-file entry points need. `tier` is the signature
factory to wire up — [`default_signature()`](#illustration.default_signature) (strongest installed),
or name one to pin it (`local_signature(phash_signature)` for the
always-available raster tier, no model download).

Wiring rather than a new tier, because the *comparison* is identical for a
local file and a fetched one; only the byte source differs. That is already
a parameter — `field="url"` points the loader at the path we stored, and
`fetch=local_image` opens it — so there is no second code path to keep in
step, and no way for one image in a batch to be fetched over HTTP.

* **Return type:**
  [`Signature`](illustration.duplicates.md#illustration.duplicates.Signature)

### illustration.make_param_translator(param_map, , on_unsupported='ignore', source_name='')

Build a translator from a `param_map` (see module docstring).

`on_unsupported` governs what happens when a canonical param has no native
equivalent: `'ignore'` (drop silently, the graceful default), `'warn'`
(drop + [`warnings.warn()`](https://docs.python.org/3/library/warnings.html#warnings.warn)), or `'raise'` (raise `ValueError`).
Parameters whose value is `None` are skipped entirely (an unset filter).

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]

### illustration.make_phash_hasher(, field='thumbnail_url', fetch=None)

A pHash hasher that fetches each result’s image once (cached for the pass).

Returns `result -> int | None` (None when the image can’t be fetched or
Pillow/NumPy aren’t installed), suitable as [`select_sequence()`](#illustration.select_sequence)’s
`hasher` seam. The fetch is content-deduped within the pass.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)], [`int`](https://docs.python.org/3/builtins/functions.html#int) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]

### illustration.make_siglip_scorer(, model='google/siglip2-base-patch16-224', cache=None, device=None, image_field='thumbnail_url')

Build a SigLIP `SiglipScorer` (raises if the extra is missing).

* **Return type:**
  [`SiglipScorer`](illustration.reranking.md#illustration.reranking.SiglipScorer)

### illustration.normalize_license(value)

Fold a provider’s licence spelling onto one canonical, comparable code.

Lower-cases, unifies separators to `-`, strips a trailing version and a
leading `cc-`, then applies `LICENSE_ALIASES`. Returns `None` for
`None`/blank — an absent licence is never a code.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

```pycon
>>> normalize_license("by-sa"), normalize_license("cc0"), normalize_license("CC0 1.0")
('by-sa', 'cc0', 'cc0')
>>> normalize_license("Pexels License"), normalize_license("  BY  ")
('pexels-license', 'by')
>>> normalize_license("public domain"), normalize_license("cc-by-3.0")
('pdm', 'by')
>>> normalize_license("cc-0")  # the version strip would otherwise eat "-0"
'cc0'
>>> normalize_license("")  is None
True
```

### illustration.nsfw_check(, max_prob=0.5, classifier=None)

Hard-drop unsafe images (R2: NSFW is a non-negotiable drop).

`classifier` is `image -> nsfw_probability`; it defaults to the
Apache-2.0 `Falconsai/nsfw_image_detection` ViT (torch/transformers — the
`[rerank]` extra). Fails **closed**: a candidate whose image can’t be
fetched or classified is dropped, never passed.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](illustration.inspection.md#illustration.inspection.CheckOutcome)]

### illustration.package_version()

The installed package version, or `'0+unknown'` if not installed.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

```pycon
>>> isinstance(package_version(), str)
True
```

### illustration.persist_sequence(result, , store=None, actor='agent:illustration-curate', activity='infer', at_time=None)

Persist a [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult) as lacing annotations.

One `selections`-tier annotation per beat (machine choices), keyed on the
ordinal beat timeline. Returns the store (a fresh `lacing.MemoryStore` when
`store` is None). `at_time` (a `lacing.RationalTime`) overrides the
provenance timestamp — pass it for deterministic ordering in tests; defaults
to wall-clock `RationalTime.now()`.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.phash(image, , hash_size=8, highfreq_factor=4)

A DCT perceptual hash of a PIL image, as a `hash_size**2`-bit integer.

The standard pHash: resize to grayscale, take the low-frequency DCT block,
threshold against its median (excluding the DC term), pack into bits.
Implemented with a NumPy DCT matrix so it needs only Pillow + NumPy.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)

### illustration.phash_signature(, field='thumbnail_url', fetch=None)

Perceptual hash as ±1 bits — the always-available tier.

**Not subject-level.** It finds the same raster re-encoded, rescaled or
lightly cropped, and will not group two engravings after the same painting.
The threshold is the cosine image of `sequence.DFLT_PHASH_THRESHOLD`.

* **Return type:**
  [`Signature`](illustration.duplicates.md#illustration.duplicates.Signature)

### illustration.prefilter(results, , checks=None, field='thumbnail_url', fetch=None)

Run `checks` over `results`, keeping only candidates that pass all.

Checks run cheapest-first and **short-circuit** on the first failure, so a
candidate dropped on its (free) metadata never triggers an image fetch.
Images are fetched at most once per URL (in-memory, for this call only);
`fetch` overrides the fetch function (a test double avoids the network).
`checks` defaults to `default_checks()` (core CV + NSFW where its deps
are available).

Returns a [`PrefilterResult`](#illustration.PrefilterResult) with the surviving `passed` results and
a [`PrefilterReport`](#illustration.PrefilterReport) per input candidate.

* **Return type:**
  [`PrefilterResult`](illustration.inspection.md#illustration.inspection.PrefilterResult)

### illustration.record_override(store, beat_index, chosen, , beat=None, actor='user:director', reason=None, at_time=None)

Append a director override for `beat_index` (a new, superseding annotation).

Never mutates the machine’s annotation — the override is a fresh annotation on
the same beat, with `provenance.was_derived_from` pointing at the most-recent
prior selection (STAM-style append-only layering). Returns the new annotation.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.refine_query(beat, critique, , refiner=None, model=None)

Refine a query for `beat` given a short `critique` of the last round.

`refiner` defaults to an `aix.prompt_func()`-backed refiner (lazy);
inject a `(beat, critique) -> query` callable to override or test offline.
Falls back to the verbatim beat if the refiner errors or returns nothing.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### illustration.register_source(source, , name=None)

Register a source instance under `name` (default `source.name`).

Returns the source, so it can be used as `SRC = register_source(MySource())`.

* **Return type:**
  [`RetrievalSource`](illustration.base.md#illustration.base.RetrievalSource)

### illustration.render_sequence_video(selections, , saveas, durations=4.0, narration_audio=None, fps=30, style='push', output_aspect=None, image_loader=None, render=None)

Render chosen images into a single Ken-Burns film via `burns`.

`selections` may be a [`SequenceResult`](illustration.sequence.md#illustration.sequence.SequenceResult), a
[`SequenceSelection`](illustration.sequence.md#illustration.sequence.SequenceSelection), or a plain list of
[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult). Each image gets an auto motion
path (`burns.ken_burns_path`, alternating push/pull for rhythm) and its
`durations` slice; `narration_audio` (a pre-built track) is muxed in.
Beats with no chosen image are skipped.

Seams: `image_loader` fetches an image to a PIL image (default: the shared
cached fetch — `burns` decodes PIL, not URLs); `render` is the renderer
(default: `burns.ken_burns_film`) — inject a stub to test without ffmpeg.
Returns whatever `render` returns (the output path for the default).

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.requires_credentials(provider)

Decorator separating credential-checking from a function’s business logic.

Runs [`check_requirements()`](#illustration.check_requirements) for `provider` before the wrapped function
body, so the function never inlines key handling. (The built-in sources call
[`check_requirements()`](#illustration.check_requirements) directly; this decorator is the functional-style
equivalent for Layer-2 helpers.)

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)

```pycon
>>> @requires_credentials("pexels")
... def fetch(): return "ok"
>>> with using_credentials(pexels="k"):
...     fetch()
'ok'
```

### illustration.rerank(query, results, , scorer=None, descending=True)

Re-score `results` against `query` and return them sorted by score.

Each returned [`ImageResult`](#illustration.ImageResult) is a copy with `.score` populated.
`scorer` defaults to the SigLIP scorer (needs the `[rerank]` extra);
inject any `(query, results) -> scores` callable to use a different model
or a test double. An empty `results` returns `[]` without loading a model.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

### illustration.resolve_api_key(provider, , api_key=None)

Resolve the API key for `provider` by precedence, or `None` if absent.

Does not raise — callers that *require* a key use [`check_requirements()`](#illustration.check_requirements).
Reads are non-interactive (never prompts).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.resolve_selection(store, beat_index)

The *active* selection body for a beat — the latest annotation wins.

Resolves machine choice vs. director override by provenance timestamp, so a
later override supersedes the machine’s choice without deleting it.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.resolved_selections(store)

The active selection body per beat index (resolved over all overrides).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### illustration.score_grade(results, selection)

The default, model-free grader — scale-robust via `ir.select` structure.

Maps the conservative selection’s *shape* (not an absolute score) onto CRAG’s
grade: nothing/abstained → Incorrect; a single dominant pick → Correct;
several comparable picks → Ambiguous. Because it reads relative structure, it
works regardless of the reranker’s score magnitude — the absolute quality bar
lives in the rubric (0-1), applied only on the Ambiguous path.

* **Return type:**
  [`Grade`](illustration.curation.md#illustration.curation.Grade)

### illustration.search(query, , n=10, source=None, orientation=None, size=None, safe=True, license_type=None, color=None, content_type=None, license_allow=False, rerank=False, dedupe='auto', provider_params=None, api_key=None, cache=True, refresh=False, \*\*provider_kwargs)

Search for up to `n` images matching `query` from one or more sources.

* **Parameters:**
  * **query** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The free-text query (first positional; required).
  * **n** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of results wanted **per source** (default `DFLT_N`).
  * **source** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – A source name, list of names, or `None` for the default set.
  * **orientation** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `landscape` | `portrait` | `square`.
  * **size** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `large` | `medium` | `small` (minimum-size filter).
  * **safe** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Exclude mature content where the provider supports it (default True).
  * **license_type** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `commercial` | `all-cc` | `modification` | `all`
    (honored by providers with license filtering, e.g. Openverse).
  * **color** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – A named color or `#hex` (Pexels, Pixabay).
  * **content_type** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `photo` | `illustration` | `vector` (Openverse,
    Pixabay; providers map/skip values they don’t support).
  * **license_allow** (`Union`[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – License gate (R3). `False` (default) = no gate; `True`
    = keep only commercial-safe licenses (CC0/PD/BY/BY-SA + Pexels);
    an iterable of license codes = keep only those. Aggregators disclaim
    license accuracy, so gate when commercial use matters.
  * **dedupe** (`Union`[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – Collapse same-subject duplicates (R4), keeping the best image
    of each subject. `"auto"` (default) dedupes only when the call
    already fetches images — i.e. when `rerank` is on — so a bare
    metadata search stays offline. `True` forces it and accepts a
    thumbnail fetch per result; `False` switches it off; a strategy
    name (`"best"` | `"all"` | `"first"`) or a
    `DuplicateGroup -> [ImageResult]` callable chooses what to keep.
    See [`illustration.duplicates`](illustration.duplicates.md#module-illustration.duplicates).
  * **rerank** (`Union`[[`bool`](https://docs.python.org/3/builtins/functions.html#bool), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – Local cross-modal precision rerank (R1). `False` (default) =
    off; `True` = SigLIP-2 (needs the `illustration[rerank]` extra);
    a `(query, results) -> scores` callable = a custom scorer. Applied
    to the assembled results, which it re-scores (populating `.score`)
    and sorts. Use the recall→rerank pattern: `search(q, n=50,
    rerank=True)[:10]`.
  * **provider_params** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]]) – Per-source native params, e.g.
    `{"pexels": {"color": "blue"}}` — used when fanning out to multiple
    sources so each gets the right native overrides.
  * **api_key** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – An explicit API key. **Single-source only** — raises if combined
    with multiple sources; use
    [`using_credentials()`](illustration.credentials.md#illustration.credentials.using_credentials) for keyed fan-out.
  * **cache** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool) | [`SearchCache`](illustration.caching.md#illustration.caching.SearchCache)) – `True` to use the default cache, `False` to bypass, or a
    [`SearchCache`](illustration.caching.md#illustration.caching.SearchCache) instance to inject one.
  * **refresh** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True, ignore any cached entry and re-fetch (then re-store).
  * **\*\*provider_kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Flat native params (escape-hatch rung 3a). \*\*Single-
    source only\*\* — raises if combined with multiple sources; use
    `provider_params={source: {...}}` for fan-out.
* **Returns:**
  for multiple
  sources the per-source lists are concatenated (up to `n × len(sources)`)
  and Layer-2 adds rank fusion via `ir`.
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult)]

```pycon
>>> isinstance(search.__doc__, str)
True
```

### illustration.search_cache_key(source, query, params)

Content-addressed SHA-256 key for `(source, query, params)`.

`params` should be the *normalized* request parameters (the canonical args
actually sent, including `n`), so two calls that differ only cosmetically
share a key.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### illustration.select_sequence(per_beat_candidates, , relevance=None, embed=None, hasher=None, shortlist=None, alpha=0.3, beta=0.5, phash_threshold=6, signature=None)

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
subject\* ([`illustration.duplicates`](illustration.duplicates.md#module-illustration.duplicates)). pHash cannot tell that four
nineteenth-century engravings after one portrait are one picture, and a
sequence that spends four beats on them is the failure this guards. When
given, it replaces the pHash test entirely — it strictly subsumes it.

* **Return type:**
  [`SequenceSelection`](illustration.sequence.md#illustration.sequence.SequenceSelection)

### illustration.siglip_signature(model=None)

SigLIP image embeddings, reusing the reranker’s on-disk embedding cache.

Free if the pass already reranked — the vectors are the same ones. Looser
than DINOv2 for this job: a caption-aligned space puts “portrait of a woman
in eighteenth-century dress” close together whether or not it is the same
woman, so the threshold is set higher to compensate.

Network-only: the embeddings come from the reranker’s URL-keyed cache, so
unlike the other two tiers there is no `fetch` seam and this cannot read a
local file. That is why [`default_signature()`](#illustration.default_signature) never returns it.

* **Return type:**
  [`Signature`](illustration.duplicates.md#illustration.duplicates.Signature)

### illustration.to_search_hit(result)

Map an [`ImageResult`](#illustration.ImageResult) to an `ir.SearchHit` for Layer-2 fusion.

The bridge into the `ir` retrieval substrate so the agentic layer can
`ir.fuse_hits` across providers. `ir` is imported here, not at module
top, to keep the base façade dependency-light. Identity follows ir’s
`(source, artifact_id)` keying: `source` is the provider and
`artifact_id` is the provider-native id. The image URL is placed under the
`path` metadata key so `SearchHit.pointer` (which scans
`ir.base.POINTER_KEYS`) resolves to it; the full normalized result rides
along in `metadata` too.

`score` is `0.0` for any hit not yet reranked (Layer 1 leaves
`ImageResult.score` as `None`) — rely on *rank*, not magnitude, until a
Layer-2 reranker populates it; `ir.fuse_hits` (RRF) is rank-based, so this
is correct for fusion.

### illustration.to_walkthru_document(selections, , narration=None, durations=4.0, doc_id='illustration-storyboard', title=None)

Build a `walkthru.DemoDocument` from the selections (pure data, no render).

Emits one b-roll beat per chosen image (`poster` = the image URL,
`timing` from `durations`) and, if `narration` is given (one string per
beat), a narration track anchored to each beat. The consumer then runs
`walkthru.realize_narration` / `pace_steps_to_narration` / its renderer.
Beats with no chosen image are skipped. Needs the `[video]` extra.

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)

### illustration.unregister_source(name)

Remove a source from the registry (no error if absent).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### illustration.using_credentials(\*\*provider_keys)

Bind per-request provider API keys for the duration of the `with` block.

Falsy values are ignored (so an optional request header passes straight
through). Bindings nest: an inner block overlays the outer.

```pycon
>>> with using_credentials(pexels="k1"):
...     with using_credentials(pexels="k2"):
...         inner = resolve_api_key("pexels")
...     outer = resolve_api_key("pexels")
>>> inner, outer
('k2', 'k1')
```

### Modules

| [`base`](illustration.base.md#module-illustration.base)               | The provider plugin contract: [`RetrievalSource`](#illustration.RetrievalSource).                   |
|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| [`caching`](illustration.caching.md#module-illustration.caching)         | SHA-256 content-addressed caching of search results (the `falaw` recipe).                                         |
| [`cli`](illustration.cli.md#module-illustration.cli)                 | Command-line surface (thin `cw` wrappers over the library functions).                                             |
| [`config`](illustration.config.md#module-illustration.config)           | Configuration: XDG directories and package-wide defaults (the SSOT).                                              |
| [`credentials`](illustration.credentials.md#module-illustration.credentials) | API-key resolution (the `aix` credentials idiom + `falaw` BYO-key seam).                                          |
| [`curation`](illustration.curation.md#module-illustration.curation)       | The bounded corrective-retrieval (CRAG) loop — Layer 2's heart (R2 §1).                                           |
| [`duplicates`](illustration.duplicates.md#module-illustration.duplicates)   | Group images that are the same **subject**, and keep the best one of each group.                                  |
| [`errors`](illustration.errors.md#module-illustration.errors)           | The package exception hierarchy.                                                                                  |
| [`expansion`](illustration.expansion.md#module-illustration.expansion)     | Query expansion & refinement — the first node of the curation loop (R2 §1).                                       |
| [`facade`](illustration.facade.md#module-illustration.facade)           | The façade: [`search()`](#illustration.search) — one call over any registered provider(s). |
| [`inspection`](illustration.inspection.md#module-illustration.inspection)   | Candidate inspection — classical-CV pre-filters + VLM caption/judge (R2 §2-3).                                    |
| [`licensing`](illustration.licensing.md#module-illustration.licensing)     | Licence-code normalisation — one vocabulary for four provider vocabularies.                                       |
| [`persistence`](illustration.persistence.md#module-illustration.persistence) | Persist curation/selection decisions as `lacing` standoff annotations (R2 §6).                                    |
| [`providers`](illustration.providers.md#module-illustration.providers)     | Built-in provider sources, registered on import.                                                                  |
| [`registry`](illustration.registry.md#module-illustration.registry)       | The open-closed source registry and the `sources` view.                                                           |
| [`reranking`](illustration.reranking.md#module-illustration.reranking)     | Local cross-modal rerank — the precision stage (research report R1 §3).                                           |
| [`schema`](illustration.schema.md#module-illustration.schema)           | The normalized result schema — the single source of truth (Pydantic v2).                                          |
| [`sequence`](illustration.sequence.md#module-illustration.sequence)       | Sequence-level selection — the M4 domain core (research report R2 §5).                                            |
| [`translation`](illustration.translation.md#module-illustration.translation) | Canonical → native parameter translation (the `denote` `param_map` idiom).                                        |
| [`video`](illustration.video.md#module-illustration.video)             | Narration → Ken-Burns video hook — the M4 integration seam.                                                       |
