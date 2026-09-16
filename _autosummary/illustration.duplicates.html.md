# illustration.duplicates

Group images that are the same **subject**, and keep the best one of each group.

The failure this exists for: a search for “Elizabeth Schuyler Hamilton” returns
five different files — a colour painting, three nineteenth-century engravings
after it, and a library’s re-scan of one of the engravings. Five distinct ids,
five distinct byte-streams, five distinct pixel layouts. To a viewer they are
*the same picture of the same woman*, and a film that uses four of them looks
like it ran out of pictures. Exactly that shipped in a real episode.

`sequence` already suppresses near-duplicates with a DCT perceptual hash, and
that is the right tool for a different job: pHash catches a re-encode, a rescale,
a re-crop — images that are the same *raster*. It does not catch two engravings
made by different hands after the same sitting, because those genuinely differ
pixel by pixel. Telling those apart needs a model that has learned what a picture
is *of*.

## Three signature tiers, strongest first

[`default_signature()`](#illustration.duplicates.default_signature) picks the strongest *automatic* one whose dependencies
are actually installed — DINOv2, else pHash — so the behaviour degrades rather
than breaking. Only the first two are `subject_level`; a caller that needs the
real thing can check `Signature.subject_level` and say so rather than
silently getting less. SigLIP is opt-in by name: it needs the same wheels as
DINOv2 and is weaker here, so it is worth asking for only when the reranker has
already paid for its embeddings — and it reads network URLs only.

Self-supervised descriptors beat text-aligned ones here — DINOv2 is trained to
be invariant to crop and perturbation and is consistently better at fine-grained
instance retrieval than CLIP-family encoders, which are optimised to match
*captions* and therefore pull “any portrait of a woman in period dress” close
together. That is why DINOv2 is the preferred tier and SigLIP only a fallback
for a caller who already has its vectors.

## One similarity measure

Every signature produces an L2-normalised vector and everything is compared by
**cosine**, including the perceptual hash — its bits become ±1, for which cosine
is an exact affine image of Hamming distance (`cos = 1 - 2·d/bits`). So one
threshold semantic covers all three tiers, and each [`Signature`](#illustration.duplicates.Signature) carries
the threshold that is right for *it* rather than leaving the caller to guess.

## Search results or files on disk

The same question gets asked of a folder — “here are 200 stills, which of them
are the same picture?” — so the path pair mirrors the result pair exactly, and
the only difference is where the pixels are read from. That difference is a
parameter, not a code path: [`local_signature()`](#illustration.duplicates.local_signature) points the chosen tier’s
loader at the file instead of at a URL, so a local dedupe touches no network.

Usage:

```default
from illustration.duplicates import dedupe, group_duplicates
from illustration.duplicates import dedupe_paths, group_duplicate_paths

keep = dedupe(results)                  # best of each group, order preserved
groups = group_duplicates(results)      # or inspect the grouping yourself

keep = dedupe_paths(folder.glob("*.jpg"))       # -> the surviving Paths
groups = group_duplicate_paths(folder.glob("*.jpg"))
```

### Module Attributes

| [`DFLT_STRATEGY`](#illustration.duplicates.DFLT_STRATEGY)        | What to do with a group by default.                            |
|-----------------------------------------------------------------------|----------------------------------------------------------------|
| [`DUPLICATE_STRATEGIES`](#illustration.duplicates.DUPLICATE_STRATEGIES) | Named reductions of a group to the images a consumer receives. |

### Functions

| [`dedupe`](#illustration.duplicates.dedupe)(results, \*[, strategy, signature, ...])    | `results` with same-subject duplicates collapsed, original order kept.                              |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| [`dedupe_paths`](#illustration.duplicates.dedupe_paths)(paths, \*[, strategy, ...])           | The paths in `paths` with same-subject duplicates collapsed, order kept.                            |
| [`default_signature`](#illustration.duplicates.default_signature)(\*\*kwargs)                      | The strongest signature whose dependencies are installed.                                           |
| [`shared_signature`](#illustration.duplicates.shared_signature)()                                 | [`default_signature()`](#illustration.duplicates.default_signature), constructed once per process. |
| [`dinov2_signature`](#illustration.duplicates.dinov2_signature)([model, field, fetch])            | DINOv2 embeddings — the preferred tier for "is this the same thing?".                               |
| [`group_duplicates`](#illustration.duplicates.group_duplicates)(results, \*[, signature, ...])    | Partition `results` into groups of the same subject.                                                |
| [`group_duplicate_paths`](#illustration.duplicates.group_duplicate_paths)(paths, \*[, signature, ...]) | Partition image files on disk into groups of the same subject.                                      |
| [`local_signature`](#illustration.duplicates.local_signature)([tier])                            | A signature that reads its pixels off the filesystem instead of the network.                        |
| [`phash_signature`](#illustration.duplicates.phash_signature)(\*[, field, fetch])                | Perceptual hash as ±1 bits — the always-available tier.                                             |
| [`quality_key`](#illustration.duplicates.quality_key)(result)                                | Sort key for "best of the group", descending.                                                       |
| [`siglip_signature`](#illustration.duplicates.siglip_signature)([model])                          | SigLIP image embeddings, reusing the reranker's on-disk embedding cache.                            |

### Classes

| [`DuplicateGroup`](#illustration.duplicates.DuplicateGroup)(members[, signature])     | Images judged to be the same subject, best first.                             |
|-------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`Signature`](#illustration.duplicates.Signature)(name, embed, threshold[, ...]) | A way of turning images into comparable vectors, and when to call it a match. |

### illustration.duplicates.DFLT_STRATEGY *= 'best'*

What to do with a group by default.

### illustration.duplicates.DUPLICATE_STRATEGIES *: [Mapping](https://docs.python.org/3/library/typing.html#typing.Mapping)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [Callable](https://docs.python.org/3/library/typing.html#typing.Callable)[[[DuplicateGroup](#illustration.duplicates.DuplicateGroup)], [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[ImageResult](illustration.schema.html.md#illustration.schema.ImageResult)]]]* *= {'all': <function \_strategy_all>, 'best': <function \_strategy_best>, 'first': <function \_strategy_first>}*

Named reductions of a group to the images a consumer receives. Add to this
mapping to register another, or pass a callable directly to [`dedupe()`](#illustration.duplicates.dedupe).

### *class* illustration.duplicates.DuplicateGroup(members, signature='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Images judged to be the same subject, best first.

#### *property* best *: [ImageResult](illustration.schema.html.md#illustration.schema.ImageResult)*

The member a consumer should get — highest quality of the group.

### *class* illustration.duplicates.Signature(name, embed, threshold, subject_level=True)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A way of turning images into comparable vectors, and when to call it a match.

`threshold` is cosine similarity at or above which two images are the same
subject. It belongs to the signature rather than to the caller because the
right value is a property of the embedding space, not of the task.

`subject_level` is the honest capability flag: `False` means this
signature can only find the same raster, so a caller relying on subject
grouping should treat it as unavailable rather than as a weak yes.

### illustration.duplicates.dedupe(results, \*, strategy='best', signature=None, threshold=None, quality=<function quality_key>)

`results` with same-subject duplicates collapsed, original order kept.

`strategy` is `"best"` (default — one image per subject, the largest),
`"all"` (group but keep everything, so a caller can choose), `"first"`
(keep the provider’s own pick), or any callable taking a
[`DuplicateGroup`](#illustration.duplicates.DuplicateGroup).

Order is the order of first appearance, so the top hit stays the top hit
even when a lower-ranked member of its group is the one kept.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`ImageResult`](illustration.schema.html.md#illustration.schema.ImageResult)]

### illustration.duplicates.dedupe_paths(paths, \*, strategy='best', signature=None, threshold=None, quality=<function quality_key>)

The paths in `paths` with same-subject duplicates collapsed, order kept.

[`dedupe()`](#illustration.duplicates.dedupe) for a folder: same `strategy` vocabulary (`"best"`,
`"all"`, `"first"`, or a callable), same first-appearance ordering, and
the same no-fetch default as [`group_duplicate_paths()`](#illustration.duplicates.group_duplicate_paths). `"best"` keeps
the largest reproduction of each subject, which for a pool of stills is the
one a pan-and-zoom render can actually use.

Returns [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) objects, not `ImageResult` wrappers —
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

### illustration.duplicates.default_signature(\*\*kwargs)

The strongest signature whose dependencies are installed.

DINOv2 when `[dedupe]` is installed, pHash otherwise. pHash is always
available, so this never raises; check `Signature.subject_level` if
you need to know whether you got subject-level grouping or only raster
matching. `kwargs` (`field`, `fetch`) reach whichever tier is chosen,
so a caller can redirect *where the pixels come from* without knowing which
tier they got — see [`local_signature()`](#illustration.duplicates.local_signature).

[`siglip_signature()`](#illustration.duplicates.siglip_signature) is deliberately not in this chain. It needs the
same torch wheels as DINOv2 and is weaker at this job, so it can only ever
be chosen for a reason this function cannot see (the reranker has already
paid for its embeddings). It also has no `fetch` seam — it reads network
URLs only — so auto-selecting it would silently put [`local_signature()`](#illustration.duplicates.local_signature)
back on the network and drop the `kwargs` on the floor. Ask for it by name.

* **Return type:**
  [`Signature`](#illustration.duplicates.Signature)

### illustration.duplicates.dinov2_signature(model='facebook/dinov2-small', , field='thumbnail_url', fetch=None)

DINOv2 embeddings — the preferred tier for “is this the same thing?”.

Self-supervised, trained for invariance to crop and perturbation, and
stronger than caption-aligned encoders at fine-grained instance retrieval.
Uses the pooled CLS embedding and compares by cosine.

* **Return type:**
  [`Signature`](#illustration.duplicates.Signature)

### illustration.duplicates.group_duplicate_paths(paths, \*, signature=None, threshold=None, quality=<function quality_key>)

Partition image files on disk into groups of the same subject.

[`group_duplicates()`](#illustration.duplicates.group_duplicates) for a folder rather than a search — “here are 200
stills, which of them are the same picture?”. The motivating case is a
Ken Burns still pool assembled from several searches, where the same image
arrives twice under two provider ids and the film shows it twice.

The default `signature` is [`local_signature()`](#illustration.duplicates.local_signature), so \*\*nothing is
fetched\*\*: the strongest installed tier is wired to open the files directly.
That is a correctness property, not an optimisation — the generic path would
treat each `url` as an address and hand every image back as `None`,
which grouping reads as “unembeddable”, so a silently-networked default
would report *no duplicates at all* rather than failing.

Groups come back in first-appearance order, members best-first. Each member
is an `ImageResult` whose `url` is the path it came from
(`Path(member.url)`); use [`dedupe_paths()`](#illustration.duplicates.dedupe_paths) if you only want the
survivors.

Two copies of one picture and one different picture:

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`DuplicateGroup`](#illustration.duplicates.DuplicateGroup)]

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

### illustration.duplicates.group_duplicates(results, \*, signature=None, threshold=None, quality=<function quality_key>)

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
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`DuplicateGroup`](#illustration.duplicates.DuplicateGroup)]

### illustration.duplicates.local_signature(tier=<function default_signature>, \*\*kwargs)

A signature that reads its pixels off the filesystem instead of the network.

The one seam the local-file entry points need. `tier` is the signature
factory to wire up — [`default_signature()`](#illustration.duplicates.default_signature) (strongest installed),
or name one to pin it (`local_signature(phash_signature)` for the
always-available raster tier, no model download).

Wiring rather than a new tier, because the *comparison* is identical for a
local file and a fetched one; only the byte source differs. That is already
a parameter — `field="url"` points the loader at the path we stored, and
`fetch=local_image` opens it — so there is no second code path to keep in
step, and no way for one image in a batch to be fetched over HTTP.

* **Return type:**
  [`Signature`](#illustration.duplicates.Signature)

### illustration.duplicates.phash_signature(, field='thumbnail_url', fetch=None)

Perceptual hash as ±1 bits — the always-available tier.

**Not subject-level.** It finds the same raster re-encoded, rescaled or
lightly cropped, and will not group two engravings after the same painting.
The threshold is the cosine image of `sequence.DFLT_PHASH_THRESHOLD`.

* **Return type:**
  [`Signature`](#illustration.duplicates.Signature)

### illustration.duplicates.quality_key(result)

Sort key for “best of the group”, descending.

Pixel area first, because for the same subject a bigger reproduction is
strictly more useful to a renderer that will crop and pan over it. Then
licence permissiveness, then whether an author is even recorded — a file
with provenance is a safer thing to publish than an equivalent one without.

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)

### illustration.duplicates.shared_signature()

[`default_signature()`](#illustration.duplicates.default_signature), constructed once per process.

This is what the façade uses, so repeated searches share one loaded model
and one image cache. Call [`default_signature()`](#illustration.duplicates.default_signature) directly for an
independent one (a test, or a different field/fetch).

* **Return type:**
  [`Signature`](#illustration.duplicates.Signature)

### illustration.duplicates.siglip_signature(model=None)

SigLIP image embeddings, reusing the reranker’s on-disk embedding cache.

Free if the pass already reranked — the vectors are the same ones. Looser
than DINOv2 for this job: a caption-aligned space puts “portrait of a woman
in eighteenth-century dress” close together whether or not it is the same
woman, so the threshold is set higher to compensate.

Network-only: the embeddings come from the reranker’s URL-keyed cache, so
unlike the other two tiers there is no `fetch` seam and this cannot read a
local file. That is why [`default_signature()`](#illustration.duplicates.default_signature) never returns it.

* **Return type:**
  [`Signature`](#illustration.duplicates.Signature)
