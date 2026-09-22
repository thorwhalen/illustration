# illustration.inspection

Candidate inspection — classical-CV pre-filters + VLM caption/judge (R2 §2-3).

Two cost tiers, cheapest first:

1. **Classical-CV pre-filters** (R2 §3) — sub-10ms/image checks (aspect ratio,
   minimum size, brightness, blur, NSFW) that drop unusable candidates *before*
   any VLM token is spent. This is the single biggest cost lever in the loop.
   License-safe libraries only: Pillow (MIT-CMU) + NumPy for the core checks;
   the NSFW gate defaults to the Apache-2.0 `Falconsai/nsfw_image_detection`
   ViT (the torch stack the reranker already uses) and is fully injectable.
2. **VLM inspect** (R2 §2) — a cheap one-sentence caption for the *Correct* path,
   or a full pointwise rubric judgement for the *Ambiguous* path. Both go through
   the injectable `describe` seam, which defaults to `aix.describe_image()`
   (lazy import). Judgements are **pointwise** (one image at a time) rather than
   pairwise, mitigating the position bias that plagues comparative VLM judges
   (R2 §4); use a judge model from a *different* family than any generator to
   cut self-preference bias.

Every expensive step is an injectable seam, so the whole module is testable
offline with stubs (synthetic PIL images for the CV checks, canned strings for
`describe`) — no network, no paid API.

```pycon
>>> # offline: a metadata-only check needs no image fetch
>>> from illustration.schema import ImageResult
>>> r = ImageResult(provider="p", id="1", url="u", width=1200, height=800)
>>> out = aspect_ratio_check()(r, lambda: None)
>>> out.name, out.passed
('aspect_ratio', True)
```

### Module Attributes

| [`Check`](#illustration.inspection.Check)                   | A check maps (result, get_image) -> CheckOutcome.                         |
|--------------------------------------------------------------------------|---------------------------------------------------------------------------|
| [`CORE_CHECKS`](#illustration.inspection.CORE_CHECKS)             | Core checks — need only Pillow + NumPy (the `[curate]` extra), no model.  |
| [`DEFAULT_CHECKS`](#illustration.inspection.DEFAULT_CHECKS)          | core CV + the NSFW gate.                                                  |
| [`Describe`](#illustration.inspection.Describe)                | A describe seam maps (image_ref, prompt) -> text.                         |
| [`DFLT_CAPTION_MAX_TOKENS`](#illustration.inspection.DFLT_CAPTION_MAX_TOKENS) | Token caps for the default VLM seam — a soft cost bound on the paid path. |

### Functions

| [`prefilter`](#illustration.inspection.prefilter)(results, \*[, checks, field, fetch])    | Run `checks` over `results`, keeping only candidates that pass all.      |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`aspect_ratio_check`](#illustration.inspection.aspect_ratio_check)(\*[, min_ratio, max_ratio])    | Reject degenerate aspect ratios (extreme slivers/panoramas).             |
| [`min_dimension_check`](#illustration.inspection.min_dimension_check)(\*[, min_width, min_height])  | Reject tiny images.                                                      |
| [`brightness_check`](#illustration.inspection.brightness_check)(\*[, min_brightness, ...])       | Reject near-black / blown-out images.                                    |
| [`blur_check`](#illustration.inspection.blur_check)(\*[, min_variance])                    | Reject blurry images via variance of the Laplacian (R2 §3; OpenCV-free). |
| [`nsfw_check`](#illustration.inspection.nsfw_check)(\*[, max_prob, classifier])            | Hard-drop unsafe images (R2: NSFW is a non-negotiable drop).             |
| [`default_checks`](#illustration.inspection.default_checks)()                                  | The default check set, chosen by what's installed.                       |
| [`inspect_candidate`](#illustration.inspection.inspect_candidate)(query, result, \*[, mode, ...]) | Inspect one candidate: a cheap caption (default) or a full rubric judge. |
| [`judge_candidate`](#illustration.inspection.judge_candidate)(query, result, \*[, ...])         | Score one candidate against `query` with a pointwise VLM rubric.         |

### Classes

| [`CheckOutcome`](#illustration.inspection.CheckOutcome)(name, passed[, value, reason])   | The result of one check on one candidate.                              |
|------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`PrefilterReport`](#illustration.inspection.PrefilterReport)(\*\*data)                     | Per-candidate pre-filter verdict (the R2 PREFILTER stage record).      |
| [`PrefilterResult`](#illustration.inspection.PrefilterResult)(passed, reports)              | The outcome of pre-filtering a candidate set.                          |
| [`RubricScore`](#illustration.inspection.RubricScore)(\*\*data)                         | A pointwise VLM judgement of one candidate (R2 §4 rubric dimensions).  |
| [`InspectReport`](#illustration.inspection.InspectReport)(\*\*data)                       | A VLM inspection of one candidate (caption or judge mode; R2 INSPECT). |

### Exceptions

| [`SafetyGateDisabledWarning`](#illustration.inspection.SafetyGateDisabledWarning)   | Raised when the default pre-filter set runs without the NSFW safety gate.   |
|------------------------------------------------------------------------------|-----------------------------------------------------------------------------|

### illustration.inspection.CORE_CHECKS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)* *= (<function aspect_ratio_check.<locals>.check>, <function min_dimension_check.<locals>.check>, <function brightness_check.<locals>.check>, <function blur_check.<locals>.check>)*

Core checks — need only Pillow + NumPy (the `[curate]` extra), no model.

### illustration.inspection.Check

A check maps (result, get_image) -> CheckOutcome. `get_image` is a 0-arg
thunk returning the candidate’s PIL image (cached) or `None` if unfetchable;
metadata-only checks ignore it (so a metadata fail never triggers a fetch).

alias of `Callable`[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), `Callable[[], Any]`], [`CheckOutcome`](#illustration.inspection.CheckOutcome)]

### *class* illustration.inspection.CheckOutcome(name, passed, value=None, reason=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The result of one check on one candidate.

### illustration.inspection.DEFAULT_CHECKS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)* *= (<function aspect_ratio_check.<locals>.check>, <function min_dimension_check.<locals>.check>, <function brightness_check.<locals>.check>, <function blur_check.<locals>.check>, <function nsfw_check.<locals>.check>)*

core CV + the NSFW gate. The NSFW check needs the
classifier deps (`[rerank]` extra); see [`default_checks()`](#illustration.inspection.default_checks) for the
dependency-aware default actually used when `checks` is omitted.

* **Type:**
  The recommended set

### illustration.inspection.DFLT_CAPTION_MAX_TOKENS *= 80*

Token caps for the default VLM seam — a soft cost bound on the paid path. A
one-sentence caption and a compact JSON rubric both need very few tokens.

### illustration.inspection.Describe

A describe seam maps (image_ref, prompt) -> text. `image_ref` is anything
`aix.describe_image()` accepts (URL / path / bytes / PIL / data URI).

alias of `Callable`[[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### *class* illustration.inspection.InspectReport(\*\*data)

Bases: `BaseModel`

A VLM inspection of one candidate (caption or judge mode; R2 INSPECT).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.inspection.PrefilterReport(\*\*data)

Bases: `BaseModel`

Per-candidate pre-filter verdict (the R2 PREFILTER stage record).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* illustration.inspection.PrefilterResult(passed, reports)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The outcome of pre-filtering a candidate set.

#### *property* dropped *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[PrefilterReport](#illustration.inspection.PrefilterReport)]*

Reports for the candidates that failed at least one check.

### *class* illustration.inspection.RubricScore(\*\*data)

Bases: `BaseModel`

A pointwise VLM judgement of one candidate (R2 §4 rubric dimensions).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

#### recompute_overall()

Set `overall` to the mean of the six rubric dimensions.

* **Return type:**
  [`RubricScore`](#illustration.inspection.RubricScore)

### *exception* illustration.inspection.SafetyGateDisabledWarning

Bases: [`UserWarning`](https://docs.python.org/3/builtins/exceptions.html#UserWarning)

Raised when the default pre-filter set runs without the NSFW safety gate.

### illustration.inspection.aspect_ratio_check(, min_ratio=0.2, max_ratio=5.0)

Reject degenerate aspect ratios (extreme slivers/panoramas). Metadata-only.

Uses the result’s `width`/`height`; passes when either is missing (can’t
assess). `ratio = width / height`.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](#illustration.inspection.CheckOutcome)]

### illustration.inspection.blur_check(, min_variance=100.0)

Reject blurry images via variance of the Laplacian (R2 §3; OpenCV-free).

The 3x3 Laplacian is applied with NumPy (no OpenCV) on the grayscale image;
a low response variance means few sharp edges, i.e. blur.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](#illustration.inspection.CheckOutcome)]

### illustration.inspection.brightness_check(, min_brightness=0.1, max_brightness=0.95)

Reject near-black / blown-out images. Mean luminance, normalized to [0, 1].

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](#illustration.inspection.CheckOutcome)]

### illustration.inspection.default_checks()

The default check set, chosen by what’s installed.

Returns [`DEFAULT_CHECKS`](#illustration.inspection.DEFAULT_CHECKS) (core + NSFW) when the NSFW classifier deps
are importable, else [`CORE_CHECKS`](#illustration.inspection.CORE_CHECKS) — and \*\*emits a
`SafetyGateDisabledWarning`** so the absence of the safety screen is
never silent (install ``illustration[rerank]`` to enable it). Passing
`checks=` to [`prefilter()`](#illustration.inspection.prefilter) explicitly always overrides this.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)

### illustration.inspection.inspect_candidate(query, result, , mode='caption', describe=None, model=None, max_tokens=None)

Inspect one candidate: a cheap caption (default) or a full rubric judge.

`mode="caption"` (the *Correct*-grade path) produces a one-sentence
caption from the thumbnail; `mode="judge"` (the *Ambiguous* path) delegates
to [`judge_candidate()`](#illustration.inspection.judge_candidate). `describe` defaults to a lazy
`aix.describe_image()` bound to `model` and capped at
`max_tokens` (default [`DFLT_CAPTION_MAX_TOKENS`](#illustration.inspection.DFLT_CAPTION_MAX_TOKENS)).

* **Return type:**
  [`InspectReport`](#illustration.inspection.InspectReport)

### illustration.inspection.judge_candidate(query, result, , describe=None, model=None, max_tokens=None)

Score one candidate against `query` with a pointwise VLM rubric.

Uses the full-resolution image for accuracy. `describe` defaults to a lazy
`aix.describe_image()` capped at `max_tokens` (default
`DFLT_JUDGE_MAX_TOKENS`). The reply is parsed into a
[`RubricScore`](#illustration.inspection.RubricScore) (`overall` = mean of the six dimensions); an
unparseable reply yields a neutral score flagged `parsed=False` so the loop
can treat it as ambiguous rather than wrongly accept or reject.

* **Return type:**
  [`InspectReport`](#illustration.inspection.InspectReport)

### illustration.inspection.min_dimension_check(, min_width=200, min_height=200)

Reject tiny images. Metadata-only (passes when dimensions are unknown).

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](#illustration.inspection.CheckOutcome)]

### illustration.inspection.nsfw_check(, max_prob=0.5, classifier=None)

Hard-drop unsafe images (R2: NSFW is a non-negotiable drop).

`classifier` is `image -> nsfw_probability`; it defaults to the
Apache-2.0 `Falconsai/nsfw_image_detection` ViT (torch/transformers — the
`[rerank]` extra). Fails **closed**: a candidate whose image can’t be
fetched or classified is dropped, never passed.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`ImageResult`](illustration.schema.md#illustration.schema.ImageResult), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[], [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`CheckOutcome`](#illustration.inspection.CheckOutcome)]

### illustration.inspection.prefilter(results, , checks=None, field='thumbnail_url', fetch=None)

Run `checks` over `results`, keeping only candidates that pass all.

Checks run cheapest-first and **short-circuit** on the first failure, so a
candidate dropped on its (free) metadata never triggers an image fetch.
Images are fetched at most once per URL (in-memory, for this call only);
`fetch` overrides the fetch function (a test double avoids the network).
`checks` defaults to [`default_checks()`](#illustration.inspection.default_checks) (core CV + NSFW where its deps
are available).

Returns a [`PrefilterResult`](#illustration.inspection.PrefilterResult) with the surviving `passed` results and
a [`PrefilterReport`](#illustration.inspection.PrefilterReport) per input candidate.

* **Return type:**
  [`PrefilterResult`](#illustration.inspection.PrefilterResult)
