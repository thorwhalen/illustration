"""Group images that are the same **subject**, and keep the best one of each group.

The failure this exists for: a search for "Elizabeth Schuyler Hamilton" returns
five different files — a colour painting, three nineteenth-century engravings
after it, and a library's re-scan of one of the engravings. Five distinct ids,
five distinct byte-streams, five distinct pixel layouts. To a viewer they are
*the same picture of the same woman*, and a film that uses four of them looks
like it ran out of pictures. Exactly that shipped in a real episode.

``sequence`` already suppresses near-duplicates with a DCT perceptual hash, and
that is the right tool for a different job: pHash catches a re-encode, a rescale,
a re-crop — images that are the same *raster*. It does not catch two engravings
made by different hands after the same sitting, because those genuinely differ
pixel by pixel. Telling those apart needs a model that has learned what a picture
is *of*.

Three signature tiers, strongest first
--------------------------------------

===================== ==================================== ==================
signature             what it recognises                   cost
===================== ==================================== ==================
:func:`dinov2_signature`  same subject / instance, across   ``[dedupe]``
                      medium, crop, palette, engraving      (torch)
:func:`siglip_signature`  same subject, a little looser —   ``[rerank]``
                      reuses the reranker's cached          (already paid if
                      image embeddings                      you rerank)
:func:`phash_signature`   same raster only                  numpy + Pillow
===================== ==================================== ==================

:func:`default_signature` picks the strongest one whose dependencies are
actually installed, so the behaviour degrades rather than breaking. Only the
first two are ``subject_level``; a caller that needs the real thing can check
:attr:`Signature.subject_level` and say so rather than silently getting less.

Self-supervised descriptors beat text-aligned ones here — DINOv2 is trained to
be invariant to crop and perturbation and is consistently better at fine-grained
instance retrieval than CLIP-family encoders, which are optimised to match
*captions* and therefore pull "any portrait of a woman in period dress" close
together. That is why DINOv2 is the preferred tier and SigLIP the fallback.

One similarity measure
----------------------

Every signature produces an L2-normalised vector and everything is compared by
**cosine**, including the perceptual hash — its bits become ±1, for which cosine
is an exact affine image of Hamming distance (``cos = 1 - 2·d/bits``). So one
threshold semantic covers all three tiers, and each :class:`Signature` carries
the threshold that is right for *it* rather than leaving the caller to guess.

Usage::

    from illustration.duplicates import dedupe, group_duplicates

    keep = dedupe(results)                  # best of each group, order preserved
    groups = group_duplicates(results)      # or inspect the grouping yourself
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from illustration.schema import ImageResult

__all__ = [
    "DFLT_STRATEGY",
    "DUPLICATE_STRATEGIES",
    "DuplicateGroup",
    "Signature",
    "dedupe",
    "default_signature",
    "shared_signature",
    "dinov2_signature",
    "group_duplicates",
    "phash_signature",
    "quality_key",
    "siglip_signature",
]

#: Default DINOv2 checkpoint. The small ViT-S/14 is enough to separate subjects
#: and is a ~22M-parameter download; a caller wanting more can name a larger one.
DFLT_DINOV2_MODEL = "facebook/dinov2-small"

#: What to do with a group by default.
DFLT_STRATEGY = "best"

#: Which result field to fetch. Thumbnails are small, already cached by the
#: rerank path, and carry more than enough signal to tell two subjects apart.
DFLT_IMAGE_FIELD = "thumbnail_url"

#: Licence preference when two images of the same subject are otherwise equal.
#: An unconditional licence is worth more than a conditional one, because the
#: credit it avoids is a credit that cannot later be got wrong.
_LICENCE_RANK = {
    "pdm": 3,
    "cc0": 3,
    "public domain": 3,
    "by": 2,
    "cc-by": 2,
    "by-sa": 1,
    "cc-by-sa": 1,
}


@dataclass(frozen=True)
class Signature:
    """A way of turning images into comparable vectors, and when to call it a match.

    ``threshold`` is cosine similarity at or above which two images are the same
    subject. It belongs to the signature rather than to the caller because the
    right value is a property of the embedding space, not of the task.

    ``subject_level`` is the honest capability flag: ``False`` means this
    signature can only find the same raster, so a caller relying on subject
    grouping should treat it as unavailable rather than as a weak yes.
    """

    name: str
    embed: Callable[[Sequence[ImageResult]], "list[Any | None]"]
    threshold: float
    subject_level: bool = True


@dataclass(frozen=True)
class DuplicateGroup:
    """Images judged to be the same subject, best first."""

    members: tuple[ImageResult, ...]
    signature: str = ""

    def __len__(self) -> int:
        return len(self.members)

    @property
    def best(self) -> ImageResult:
        """The member a consumer should get — highest quality of the group."""
        return self.members[0]

    @property
    def is_duplicate(self) -> bool:
        return len(self.members) > 1


# --------------------------------------------------------------------------- #
# quality — which member of a group wins
# --------------------------------------------------------------------------- #


def quality_key(result: ImageResult) -> tuple:
    """Sort key for "best of the group", descending.

    Pixel area first, because for the same subject a bigger reproduction is
    strictly more useful to a renderer that will crop and pan over it. Then
    licence permissiveness, then whether an author is even recorded — a file
    with provenance is a safer thing to publish than an equivalent one without.
    """
    area = (result.width or 0) * (result.height or 0)
    licence = _LICENCE_RANK.get((result.license or "").strip().lower(), 0)
    has_author = bool(result.author)
    return (area, licence, has_author)


# --------------------------------------------------------------------------- #
# signatures
# --------------------------------------------------------------------------- #


def _l2_normalize(vec):
    import numpy as np

    arr = np.asarray(vec, dtype="float32").ravel()
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


def phash_signature(
    *, field: str = DFLT_IMAGE_FIELD, fetch: "Callable | None" = None
) -> Signature:
    """Perceptual hash as ±1 bits — the always-available tier.

    **Not subject-level.** It finds the same raster re-encoded, rescaled or
    lightly cropped, and will not group two engravings after the same painting.
    The threshold is the cosine image of ``sequence.DFLT_PHASH_THRESHOLD``.
    """
    from illustration.sequence import DFLT_PHASH_THRESHOLD, phash
    from illustration._imageio import memoized_image_loader

    bits = 64
    load = memoized_image_loader(field=field, fetch=fetch)

    def embed(results: Sequence[ImageResult]) -> "list[Any | None]":
        import numpy as np

        out: "list[Any | None]" = []
        for result in results:
            image = load(result)
            if image is None:
                out.append(None)
                continue
            try:
                value = phash(image)
            except Exception:
                out.append(None)
                continue
            unpacked = [(1.0 if (value >> i) & 1 else -1.0) for i in range(bits)]
            out.append(_l2_normalize(np.asarray(unpacked, dtype="float32")))
        return out

    return Signature(
        name="phash",
        embed=embed,
        threshold=1.0 - 2.0 * DFLT_PHASH_THRESHOLD / bits,
        subject_level=False,
    )


def siglip_signature(model: "str | None" = None) -> Signature:
    """SigLIP image embeddings, reusing the reranker's on-disk embedding cache.

    Free if the pass already reranked — the vectors are the same ones. Looser
    than DINOv2 for this job: a caption-aligned space puts "portrait of a woman
    in eighteenth-century dress" close together whether or not it is the same
    woman, so the threshold is set higher to compensate.
    """
    from illustration.reranking import DFLT_RERANK_MODEL, SiglipScorer

    scorer = SiglipScorer(model=model or DFLT_RERANK_MODEL)

    def embed(results: Sequence[ImageResult]) -> "list[Any | None]":
        vectors = scorer.image_embeddings(results)
        return [None if v is None else _l2_normalize(v) for v in vectors]

    return Signature(name="siglip", embed=embed, threshold=0.92)


def dinov2_signature(
    model: str = DFLT_DINOV2_MODEL,
    *,
    field: str = DFLT_IMAGE_FIELD,
    fetch: "Callable | None" = None,
) -> Signature:
    """DINOv2 embeddings — the preferred tier for "is this the same thing?".

    Self-supervised, trained for invariance to crop and perturbation, and
    stronger than caption-aligned encoders at fine-grained instance retrieval.
    Uses the pooled CLS embedding and compares by cosine.
    """
    from illustration._imageio import memoized_image_loader

    load = memoized_image_loader(field=field, fetch=fetch)
    state: dict = {}

    def _model_and_processor():
        if not state:
            from transformers import AutoImageProcessor, AutoModel

            state["processor"] = AutoImageProcessor.from_pretrained(model)
            state["model"] = AutoModel.from_pretrained(model).eval()
        return state["model"], state["processor"]

    def embed(results: Sequence[ImageResult]) -> "list[Any | None]":
        import torch

        net, processor = _model_and_processor()
        out: "list[Any | None]" = []
        for result in results:
            image = load(result)
            if image is None:
                out.append(None)
                continue
            try:
                inputs = processor(images=image, return_tensors="pt")
                with torch.no_grad():
                    pooled = net(**inputs).last_hidden_state[:, 0]
                out.append(_l2_normalize(pooled[0].numpy()))
            except Exception:
                out.append(None)
        return out

    return Signature(name="dinov2", embed=embed, threshold=0.86)


def _importable(*modules: str) -> bool:
    from importlib.util import find_spec

    try:
        return all(find_spec(m) is not None for m in modules)
    except (ImportError, ValueError):
        return False


def default_signature(**kwargs) -> Signature:
    """The strongest signature whose dependencies are installed.

    DINOv2 -> SigLIP -> pHash. The last is always available, so this never
    raises; check :attr:`Signature.subject_level` if you need to know whether
    you actually got subject-level grouping or only raster matching.
    """
    if _importable("torch", "transformers"):
        return dinov2_signature(**kwargs)
    if _importable("torch", "transformers", "PIL"):  # pragma: no cover - same gate
        return siglip_signature()
    return phash_signature(**kwargs)


#: Process-wide default, built once. The model weights and the closure's image
#: cache are the expensive parts, and rebuilding a signature per ``search()``
#: call would pay for both every time.
_DEFAULT_SIGNATURE: "Signature | None" = None


def shared_signature() -> Signature:
    """:func:`default_signature`, constructed once per process.

    This is what the façade uses, so repeated searches share one loaded model
    and one image cache. Call :func:`default_signature` directly for an
    independent one (a test, or a different field/fetch).
    """
    global _DEFAULT_SIGNATURE
    if _DEFAULT_SIGNATURE is None:
        _DEFAULT_SIGNATURE = default_signature()
    return _DEFAULT_SIGNATURE


# --------------------------------------------------------------------------- #
# grouping
# --------------------------------------------------------------------------- #


def _union_find(n: int):
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    return find, union


def group_duplicates(
    results: Sequence[ImageResult],
    *,
    signature: "Signature | None" = None,
    threshold: "float | None" = None,
    quality: Callable[[ImageResult], Any] = quality_key,
) -> list[DuplicateGroup]:
    """Partition ``results`` into groups of the same subject.

    Single-linkage: A groups with C if A~B and B~C, even when A and C fall just
    under the threshold themselves. That is the right shape here, because a run
    of reproductions of one painting forms a chain — a colour original, an
    engraving after it, and a re-scan of the engraving — where the ends can be
    further apart than either is from the middle.

    Groups come back in the order their best member first appears, and each
    group's members are sorted best-first by ``quality``. An image whose
    signature could not be computed is never grouped, so a fetch failure loses a
    duplicate rather than silently merging two different pictures.
    """
    results = list(results)
    if len(results) < 2:
        return [DuplicateGroup(members=(r,)) for r in results]

    signature = signature or default_signature()
    cutoff = signature.threshold if threshold is None else threshold
    vectors = signature.embed(results)

    find, union = _union_find(len(results))
    usable = [i for i, v in enumerate(vectors) if v is not None]
    for position, i in enumerate(usable):
        for j in usable[position + 1 :]:
            if float(vectors[i] @ vectors[j]) >= cutoff:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(len(results)):
        clusters.setdefault(find(i), []).append(i)

    groups = []
    for indices in clusters.values():
        members = sorted((results[i] for i in indices), key=quality, reverse=True)
        first_seen = min(indices)
        groups.append((first_seen, DuplicateGroup(tuple(members), signature.name)))
    return [group for _, group in sorted(groups, key=lambda pair: pair[0])]


# --------------------------------------------------------------------------- #
# strategies
# --------------------------------------------------------------------------- #


def _strategy_best(group: DuplicateGroup) -> list[ImageResult]:
    return [group.best]


def _strategy_all(group: DuplicateGroup) -> list[ImageResult]:
    return list(group.members)


def _strategy_first(group: DuplicateGroup) -> list[ImageResult]:
    """Keep whichever member the provider ranked highest, not the biggest."""
    return [group.members[0]]


#: Named reductions of a group to the images a consumer receives. Add to this
#: mapping to register another, or pass a callable directly to :func:`dedupe`.
DUPLICATE_STRATEGIES: Mapping[str, Callable[[DuplicateGroup], list[ImageResult]]] = {
    "best": _strategy_best,
    "all": _strategy_all,
    "first": _strategy_first,
}


def dedupe(
    results: Sequence[ImageResult],
    *,
    strategy: "str | Callable[[DuplicateGroup], list[ImageResult]]" = DFLT_STRATEGY,
    signature: "Signature | None" = None,
    threshold: "float | None" = None,
    quality: Callable[[ImageResult], Any] = quality_key,
) -> list[ImageResult]:
    """``results`` with same-subject duplicates collapsed, original order kept.

    ``strategy`` is ``"best"`` (default — one image per subject, the largest),
    ``"all"`` (group but keep everything, so a caller can choose), ``"first"``
    (keep the provider's own pick), or any callable taking a
    :class:`DuplicateGroup`.

    Order is the order of first appearance, so the top hit stays the top hit
    even when a lower-ranked member of its group is the one kept.
    """
    if isinstance(strategy, str):
        try:
            reduce = DUPLICATE_STRATEGIES[strategy]
        except KeyError:
            raise ValueError(
                f"unknown duplicate strategy {strategy!r}; "
                f"known: {sorted(DUPLICATE_STRATEGIES)}"
            ) from None
    else:
        reduce = strategy

    groups = group_duplicates(
        results, signature=signature, threshold=threshold, quality=quality
    )
    kept: list[ImageResult] = []
    for group in groups:
        kept.extend(reduce(group))
    return kept
