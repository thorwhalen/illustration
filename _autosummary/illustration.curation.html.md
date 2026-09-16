# illustration.curation

The bounded corrective-retrieval (CRAG) loop — Layer 2’s heart (R2 §1).

Turns a high-recall provider search into a single vetted candidate for one
narration beat, self-correcting across a *hard-bounded* number of rounds. The
shape is CRAG [Yan et al. 2024]: retrieve → grade → conditionally re-query —
wrapped in a controller whose stop conditions are enforced \*\*in code, not
prompts\*\*. That distinction is the whole point: the cautionary tale R2 cites is a
multi-agent loop that ran 11 days and cost $47k because it had cost *alerts* but
no cost *enforcement*. Here, [`Budget`](#illustration.curation.Budget) caps (max iterations, per-call-type
ceilings, accept threshold, optional cost ceiling) are checked before every paid
call.

The pipeline per iteration:

```default
expand → search (fan-out) → ir.fuse_hits (provider merge/dedup, rank-based)
       → prefilter (classical CV) → rerank (SigLIP) → ir.select
       → grade {Correct | Ambiguous | Incorrect}
       → Correct: caption + accept · Ambiguous: VLM judge · Incorrect: refine
```

Cost discipline (R2, in impact order): the classical-CV prefilter gates before
any VLM token is spent; *Correct* uses a cheap caption and *Ambiguous* escalates
to the rubric judge only when the cheap signal is unsure; everything is bounded.

Every expensive seam is injectable — `search_fn`, `expander`/`refiner`,
`scorer` (SigLIP), `describe` (the VLM), `grader`, `checks` — so the loop
runs end-to-end **offline** with stubs and never spends on a paid API in a test.

```pycon
>>> # offline: stub search + scorer + a generous-enough budget -> one round
>>> from illustration.schema import ImageResult
>>> cands = [ImageResult(provider="p", id=str(i), url=f"u{i}", width=900, height=600)
...          for i in range(3)]
>>> res = curate(
...     "a stormy harbour at dusk",
...     expander=lambda beat: [],                       # no expansion
...     search_fn=lambda q, **kw: cands,                # canned recall
...     checks=[],                                      # skip CV (no fetch)
...     scorer=lambda beat, rs: [0.9, 0.4, 0.2],        # canned relevance
...     describe=lambda image, prompt: "a harbour",     # canned VLM (no API)
... )
>>> res.accepted, res.best.result.id, res.grade
(True, '0', 'correct')
```

The example is `+SKIP`-ed under `--doctest-modules` because it exercises the
`ir` fan-in, which ships in the optional `[curate]` extra (absent in the
base / CI install). `tests/test_curation.py` covers this path in full under
`importorskip("ir")`.

### Module Attributes

| [`DFLT_CURATE_N`](#illustration.curation.DFLT_CURATE_N)   | Default candidates requested *per source* for the recall stage.                                             |
|------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| [`Grader`](#illustration.curation.Grader)          | A grader maps (reranked results, ir.Selection) -> a [`Grade`](#illustration.curation.Grade). |

### Functions

| [`curate`](#illustration.curation.curate)(beat, \*[, sources, n, budget, ...])   | Curate the single best image for a narration `beat` via the CRAG loop.   |
|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`score_grade`](#illustration.curation.score_grade)(results, selection)               | The default, model-free grader — scale-robust via `ir.select` structure. |

### Classes

| [`Grade`](#illustration.curation.Grade)(\*values)                           | CRAG's three-way retrieval grade (R2 §1).                              |
|--------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`Budget`](#illustration.curation.Budget)([max_iter, max_search_calls, ...]) | Hard loop bounds — the safety net, enforced in controller code (R2).   |
| [`Candidate`](#illustration.curation.Candidate)(\*\*data)                       | One scored (and optionally inspected) candidate.                       |
| [`IterationRecord`](#illustration.curation.IterationRecord)(\*\*data)                 | One iteration of the loop — the run-log R2 requires for observability. |
| [`CurationResult`](#illustration.curation.CurationResult)(\*\*data)                  | The outcome of curating one beat.                                      |

### *class* illustration.curation.Budget(max_iter=3, max_search_calls=8, max_caption_calls=12, max_judge_calls=8, accept_threshold=0.62, correct_min_score=None, select_max_k=3, select_rel=0.9, min_score=None, max_cost=None, cost_estimator=None)

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

### *class* illustration.curation.Candidate(\*\*data)

Bases: `BaseModel`

One scored (and optionally inspected) candidate.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### *property* quality *: [float](https://docs.python.org/3/builtins/functions.html#float)*

the rubric overall if judged, else 0.

* **Type:**
  A 0-1 comparable quality

### *class* illustration.curation.CurationResult(\*\*data)

Bases: `BaseModel`

The outcome of curating one beat.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### illustration.curation.DFLT_CURATE_N *= 12*

Default candidates requested *per source* for the recall stage.

### *class* illustration.curation.Grade(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

CRAG’s three-way retrieval grade (R2 §1).

### illustration.curation.Grader

A grader maps (reranked results, ir.Selection) -> a [`Grade`](#illustration.curation.Grade).

alias of `Callable`[[[`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)], [`Grade`](#illustration.curation.Grade)]

### *class* illustration.curation.IterationRecord(\*\*data)

Bases: `BaseModel`

One iteration of the loop — the run-log R2 requires for observability.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### illustration.curation.curate(beat, , sources=None, n=12, budget=None, expander=None, refiner=None, grader=None, describe=None, scorer=None, checks=None, model=None, search_fn=None, fetch=None)

Curate the single best image for a narration `beat` via the CRAG loop.

* **Parameters:**
  * **beat** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The narration beat / scene description to illustrate.
  * **sources** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Source name(s) to search, or `None` for the default set.
  * **n** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Candidates requested per source per query (recall width).
  * **budget** ([`Budget`](#illustration.curation.Budget) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Hard loop bounds (defaults to [`Budget`](#illustration.curation.Budget)).
  * **refiner** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – Query generation / refinement seams (default: `aix`).
  * **grader** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)], [`Grade`](#illustration.curation.Grade)]]) – `(results, selection) -> Grade` (default [`score_grade()`](#illustration.curation.score_grade)).
  * **describe** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – VLM `(image, prompt) -> text` seam (default: `aix`).
  * **scorer** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – SigLIP-style `(beat, results) -> scores` reranker. `None` uses
    the local SigLIP scorer when its deps are present, else falls back to
    the rank-fused order.
  * **checks** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](illustration.inspection.html.md#illustration.inspection.CheckOutcome)]]]) – Classical-CV pre-filter checks (default: dependency-aware set).
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – LLM model id passed to the default expander / refiner / describe.
  * **search_fn** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – `(query, *, source, n, ...) -> [ImageResult]` (default:
    [`illustration.search()`](illustration.html.md#illustration.search)). Inject a stub to test offline.
  * **fetch** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – Image fetch override for the pre-filters (test double).
* **Return type:**
  [`CurationResult`](#illustration.curation.CurationResult)
* **Returns:**
  A [`CurationResult`](#illustration.curation.CurationResult) — the accepted (or best-so-far) candidate, the
  full candidate set, the per-iteration trace, and the spend accounting.

### illustration.curation.score_grade(results, selection)

The default, model-free grader — scale-robust via `ir.select` structure.

Maps the conservative selection’s *shape* (not an absolute score) onto CRAG’s
grade: nothing/abstained → Incorrect; a single dominant pick → Correct;
several comparable picks → Ambiguous. Because it reads relative structure, it
works regardless of the reranker’s score magnitude — the absolute quality bar
lives in the rubric (0-1), applied only on the Ambiguous path.

* **Return type:**
  [`Grade`](#illustration.curation.Grade)
