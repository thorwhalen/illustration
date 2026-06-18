"""Sequence-level selection — the M4 domain core (research report R2 §5).

M3's :func:`illustration.curate` picks the best image for *one* beat in isolation.
A storyboard is a *sequence*, so the right image for beat *i* depends on its
neighbours: consecutive shots should cohere visually, the set should stay
diverse, and no two beats should land on near-duplicate images. This module adds
that cross-shot layer — the one piece of M4 the ecosystem doesn't already own
(``burns`` renders, ``walkthru`` orchestrates time + narration, ``lacing``
persists; none of them *choose* images).

The objective, greedily optimized left-to-right (an MMR-style pass, R2 §5)::

    J(s) = Σ_i  rel(s_i)                          # per-beat relevance
         + α Σ_i  coherence(s_i, s_{i-1})         # consecutive-shot visual coherence
         − β Σ_i  redundancy(s_i, {s_j : j<i})    # diversity / anti-repetition
      subject to  phash_distance(s_i, s_j) ≥ τ    # hard near-duplicate constraint

Everything heavy is an **injectable seam**, and the defaults stay dependency-light
on purpose (the no-bloat directive): relevance defaults to the candidate's
existing rerank ``.score``; coherence/redundancy reuse the **SigLIP image
embeddings illustration already caches in M2b** (via
:func:`illustration.reranking.embed_images`, behind the ``[rerank]`` extra);
near-duplicate detection is an **in-house NumPy DCT perceptual hash** (no new
dep). When the embedding deps are absent the loop degrades gracefully to
relevance + dedup. Optional upgrades — ``apricot`` (submodular shortlisting) and
``imagededup`` (CNN dedup) — plug in through the ``shortlist`` / ``hasher`` seams,
exactly like M3's ``Scorer`` seam.

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
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from pydantic import BaseModel, Field

from illustration.schema import ImageResult

__all__ = [
    "select_sequence",
    "curate_sequence",
    "SequenceSelection",
    "BeatSelection",
    "SequenceResult",
    "phash",
    "hamming_distance",
    "make_phash_hasher",
    "DFLT_ALPHA",
    "DFLT_BETA",
    "DFLT_PHASH_THRESHOLD",
    "DFLT_SEQUENCE_N",
]

#: Coherence reward weight (α) — how much consecutive-shot similarity is favored.
DFLT_ALPHA = 0.30
#: Redundancy penalty weight (β) — how much repetition across the set is punished.
DFLT_BETA = 0.50
#: Perceptual-hash Hamming distance below which two images are "near-duplicate".
DFLT_PHASH_THRESHOLD = 6
#: Default candidate-pool width requested per beat by :func:`curate_sequence`.
DFLT_SEQUENCE_N = 12

#: An embed seam maps a list of results to aligned L2-normalized vectors (or None).
Embed = Callable[[Sequence[ImageResult]], Sequence[Any]]
#: A hasher seam maps one result to a perceptual hash int (or None if unhashable).
Hasher = Callable[[ImageResult], "int | None"]
#: A relevance seam maps one result to a scalar score.
Relevance = Callable[[ImageResult], float]


class BeatSelection(BaseModel):
    """The chosen image (and why) for one beat in a sequence."""

    beat_index: int
    chosen: "ImageResult | None"
    relevance: float = 0.0
    coherence: float = 0.0
    redundancy: float = 0.0
    forced_duplicate: bool = False  # True if the pHash constraint had to be relaxed
    n_candidates: int = 0


class SequenceSelection(BaseModel):
    """One image chosen per beat, optimized for the cross-shot objective."""

    selections: list[BeatSelection] = Field(default_factory=list)
    objective: float = 0.0
    notes: list[str] = Field(default_factory=list)

    @property
    def chosen(self) -> "list[ImageResult | None]":
        """The chosen image per beat, in order (``None`` where a beat was empty)."""
        return [s.chosen for s in self.selections]


class SequenceResult(BaseModel):
    """The result of curating a whole sequence of beats."""

    beats: list[str]
    selection: SequenceSelection


def select_sequence(
    per_beat_candidates: "Sequence[Sequence[ImageResult]]",
    *,
    relevance: "Relevance | None" = None,
    embed: "Embed | None" = None,
    hasher: "Hasher | None" = None,
    shortlist: "Callable[[Sequence[ImageResult]], Sequence[ImageResult]] | None" = None,
    alpha: float = DFLT_ALPHA,
    beta: float = DFLT_BETA,
    phash_threshold: int = DFLT_PHASH_THRESHOLD,
) -> SequenceSelection:
    """Choose one image per beat optimizing relevance + coherence − redundancy.

    A greedy left-to-right pass: at each beat, pick the candidate maximizing
    ``rel + α·coherence(prev) − β·max_redundancy(chosen)``, excluding any
    near-duplicate (pHash Hamming < ``phash_threshold``) of an already-chosen
    image. If *every* candidate for a beat is a near-duplicate, the constraint is
    relaxed for that beat and the choice is flagged ``forced_duplicate``.

    Seams (all default to the lean in-house / M2b path, injectable for tests or
    upgrades): ``relevance`` (default: candidate ``.score`` or 0), ``embed``
    (default: cached SigLIP embeddings via ``[rerank]``; coherence/redundancy are
    skipped when unavailable), ``hasher`` (default: in-house DCT pHash; dedup is
    skipped when Pillow/NumPy are unavailable), ``shortlist`` (optional per-beat
    pre-filter, e.g. an ``apricot`` submodular representative set).
    """
    rel_fn = relevance if relevance is not None else _default_relevance
    embed_fn = embed if embed is not None else _default_embed
    hash_fn = hasher if hasher is not None else make_phash_hasher()

    selections: list[BeatSelection] = []
    notes: list[str] = []
    chosen_embs: list[Any] = []
    chosen_hashes: list[Any] = []
    total = 0.0

    for i, raw in enumerate(per_beat_candidates):
        cands = list(raw)
        if shortlist is not None and cands:
            cands = list(shortlist(cands))
        if not cands:
            selections.append(BeatSelection(beat_index=i, chosen=None, n_candidates=0))
            notes.append(f"beat {i}: no candidates")
            continue

        embs = list(embed_fn(cands))
        hashes = [hash_fn(c) for c in cands]
        prev_emb = chosen_embs[-1] if chosen_embs else None

        scored = []
        for c, e, h in zip(cands, embs, hashes):
            near_dup = h is not None and any(
                ch is not None and hamming_distance(h, ch) < phash_threshold
                for ch in chosen_hashes
            )
            coh = _cosine(e, prev_emb)
            red = max((_cosine(e, ce) for ce in chosen_embs), default=0.0)
            j = rel_fn(c) + alpha * coh - beta * red
            scored.append(
                {
                    "j": j,
                    "near_dup": near_dup,
                    "c": c,
                    "e": e,
                    "h": h,
                    "coh": coh,
                    "red": red,
                }
            )

        valid = [s for s in scored if not s["near_dup"]]
        pool = valid if valid else scored
        forced = not valid
        best = max(pool, key=lambda s: s["j"])
        if forced:
            notes.append(
                f"beat {i}: every candidate near-duplicates an earlier beat; "
                "relaxed the constraint and kept the best by objective"
            )

        selections.append(
            BeatSelection(
                beat_index=i,
                chosen=best["c"],
                relevance=rel_fn(best["c"]),
                coherence=round(best["coh"], 4),
                redundancy=round(best["red"], 4),
                forced_duplicate=forced,
                n_candidates=len(cands),
            )
        )
        chosen_embs.append(best["e"])
        chosen_hashes.append(best["h"])
        total += best["j"]

    return SequenceSelection(
        selections=selections, objective=round(total, 4), notes=notes
    )


def curate_sequence(
    beats: "Sequence[str]",
    *,
    sources: "str | list[str] | None" = None,
    n: int = DFLT_SEQUENCE_N,
    per_beat: "Callable[[str], Sequence[ImageResult]] | None" = None,
    **select_kwargs: Any,
) -> SequenceResult:
    """Curate a whole sequence: gather a candidate pool per beat, then select.

    ``per_beat`` produces the candidate pool for one beat (default: a recall +
    SigLIP rerank via :func:`illustration.search`, so pools carry relevance
    ``.score``). Inject ``per_beat=lambda b: illustration.curate(b).candidates``
    for the full per-beat CRAG loop, or any other pool source. Remaining keyword
    args pass through to :func:`select_sequence`.
    """
    fn = per_beat if per_beat is not None else _default_per_beat(sources, n)
    pools = [list(fn(beat)) for beat in beats]
    selection = select_sequence(pools, **select_kwargs)
    return SequenceResult(beats=list(beats), selection=selection)


# --- perceptual hash (in-house, NumPy-only — no new dependency) --------------


def phash(image, *, hash_size: int = 8, highfreq_factor: int = 4) -> int:
    """A DCT perceptual hash of a PIL image, as a ``hash_size**2``-bit integer.

    The standard pHash: resize to grayscale, take the low-frequency DCT block,
    threshold against its median (excluding the DC term), pack into bits.
    Implemented with a NumPy DCT matrix so it needs only Pillow + NumPy.
    """
    import numpy as np

    img_size = hash_size * highfreq_factor
    gray = np.asarray(image.convert("L").resize((img_size, img_size)), dtype="float64")
    coefs = _dct2(gray)[:hash_size, :hash_size]
    flat = coefs.flatten()
    med = np.median(flat[1:])  # exclude the DC coefficient
    bits = flat > med
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    return value


def hamming_distance(a: int, b: int) -> int:
    """Number of differing bits between two perceptual hashes."""
    return bin(a ^ b).count("1")


def make_phash_hasher(
    *, field: str = "thumbnail_url", fetch: "Callable | None" = None
) -> Hasher:
    """A pHash hasher that fetches each result's image once (cached for the pass).

    Returns ``result -> int | None`` (None when the image can't be fetched or
    Pillow/NumPy aren't installed), suitable as :func:`select_sequence`'s
    ``hasher`` seam. The fetch is content-deduped within the pass.
    """
    from illustration._imageio import memoized_image_loader

    load = memoized_image_loader(field=field, fetch=fetch)

    def hasher(result: ImageResult) -> "int | None":
        image = load(result)
        if image is None:
            return None
        try:
            return phash(image)
        except Exception:  # pragma: no cover - decode/transform failure
            return None

    return hasher


# --- internals --------------------------------------------------------------


def _default_relevance(result: ImageResult) -> float:
    return result.score if result.score is not None else 0.0


def _default_embed(results: Sequence[ImageResult]) -> list:
    """Default coherence/redundancy embeddings: cached SigLIP, else all-None."""
    try:
        from illustration.reranking import embed_images

        return embed_images(results)
    except Exception:
        # rerank deps missing (or a transient embed failure) -> coherence off
        return [None] * len(list(results))


def _default_per_beat(sources, n) -> "Callable[[str], list[ImageResult]]":
    def per_beat(beat: str) -> list[ImageResult]:
        import illustration  # lazy: avoid an import cycle at module load

        from illustration.reranking import _importable

        use_rerank = all(
            _importable(m) for m in ("torch", "transformers", "PIL", "numpy")
        )
        return illustration.search(beat, source=sources, n=n, rerank=use_rerank)

    return per_beat


def _cosine(a, b) -> float:
    if a is None or b is None:
        return 0.0
    import numpy as np

    av, bv = np.asarray(a, dtype="float64"), np.asarray(b, dtype="float64")
    na, nb = float(np.linalg.norm(av)), float(np.linalg.norm(bv))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(av, bv) / (na * nb))


def _dct2(matrix):
    """2-D DCT-II of a square matrix via a NumPy basis matrix (no SciPy)."""
    import numpy as np

    n = matrix.shape[0]
    k = np.arange(n)
    # D[freq, sample] = cos(pi/n * (sample + 0.5) * freq): frequency is the ROW
    # index so the [:hash_size, :hash_size] slice in phash() is the true
    # low-frequency block (a transpose here silently destroys discrimination).
    basis = np.cos(np.pi / n * (k[None, :] + 0.5) * k[:, None])
    return basis @ matrix @ basis.T
