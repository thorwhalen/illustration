"""Local cross-modal rerank — the precision stage (research report R1 §3).

Provider lexical/tag search is a cheap, high-recall *recall* stage; this module
is the expensive, high-precision *rerank* stage that re-scores the candidates by
true cross-modal (text↔image) similarity using a local CLIP-family model. The
default is **SigLIP 2** (Apache-2.0, commercially safe; R1's recommended open
encoder).

The design is a clean seam: :func:`rerank` is a torch-free orchestrator over an
injectable :data:`Scorer` (``(query, results) -> per-result scores``). The
default scorer (:func:`make_siglip_scorer`) loads SigLIP via ``transformers`` +
``torch`` + ``pillow`` — all behind the optional ``illustration[rerank]`` extra
and imported lazily, so ``import illustration`` (and this module) stay light and
the scorer can later be swapped for an ``ef``-hosted embedder with no call-site
change.

Typical recall→rerank→top-k use::

    hits = illustration.search("a stormy harbour at dusk", n=50)   # recall
    top = illustration.rerank("a stormy harbour at dusk", hits)[:10]  # precision

or the convenience ``illustration.search("...", n=50, rerank=True)[:10]``.

>>> # orchestration is testable with a stub scorer (no model needed)
>>> from illustration.schema import ImageResult
>>> rs = [ImageResult(provider="p", id=str(i), url=f"u{i}") for i in range(3)]
>>> ranked = rerank("q", rs, scorer=lambda q, results: [0.1, 0.9, 0.5])
>>> [r.id for r in ranked], [round(r.score, 1) for r in ranked]
(['1', '2', '0'], [0.9, 0.5, 0.1])
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any, Callable, MutableMapping, Sequence

from illustration.config import cache_dir
from illustration.errors import RerankDependencyError
from illustration.schema import ImageResult

__all__ = [
    "rerank",
    "make_siglip_scorer",
    "default_scorer",
    "embed_images",
    "check_rerank_requirements",
    "Scorer",
    "SiglipScorer",
    "DFLT_RERANK_MODEL",
]

#: A scorer maps (query, results) -> one relevance score per result (parallel).
Scorer = Callable[[str, Sequence[ImageResult]], Sequence[float]]

#: Default encoder: SigLIP 2 base (Apache-2.0). Smaller/faster than So400m; set a
#: larger model (e.g. ``google/siglip2-so400m-patch16-384``) for higher quality.
DFLT_RERANK_MODEL = "google/siglip2-base-patch16-224"

#: Which result field to fetch+embed (the thumbnail is smaller/faster than the
#: full image and sufficient for relevance scoring).
DFLT_IMAGE_FIELD = "thumbnail_url"

_RERANK_DEPS = ("torch", "transformers", "PIL", "numpy")


def rerank(
    query: str,
    results: Sequence[ImageResult],
    *,
    scorer: "Scorer | None" = None,
    descending: bool = True,
) -> list[ImageResult]:
    """Re-score ``results`` against ``query`` and return them sorted by score.

    Each returned :class:`ImageResult` is a copy with ``.score`` populated.
    ``scorer`` defaults to the SigLIP scorer (needs the ``[rerank]`` extra);
    inject any ``(query, results) -> scores`` callable to use a different model
    or a test double. An empty ``results`` returns ``[]`` without loading a model.
    """
    items = list(results)
    if not items:
        return []
    score_fn = scorer if scorer is not None else default_scorer()
    scores = list(score_fn(query, items))
    if len(scores) != len(items):
        raise ValueError(
            f"scorer returned {len(scores)} scores for {len(items)} results"
        )
    scored = [r.model_copy(update={"score": float(s)}) for r, s in zip(items, scores)]
    return sorted(
        scored,
        key=lambda r: r.score if r.score is not None else 0.0,
        reverse=descending,
    )


@lru_cache(maxsize=4)
def default_scorer(model: str = DFLT_RERANK_MODEL) -> "Scorer":
    """The default (cached) SigLIP scorer for ``model`` — built once per model."""
    return make_siglip_scorer(model=model)


def embed_images(
    results: Sequence[ImageResult], *, model: str = DFLT_RERANK_MODEL
) -> "list":
    """L2-normalized SigLIP image embeddings for ``results`` (``None`` per unfetchable).

    Reuses the same content-addressed embedding cache the reranker populates, so
    embedding candidates a second time (e.g. for Layer-2 sequence coherence) is
    cheap. Needs the ``[rerank]`` extra; raises :class:`RerankDependencyError` if
    it's missing. The returned list is aligned 1:1 with ``results``.
    """
    items = list(results)
    if not items:
        return []
    scorer = default_scorer(model)
    return scorer.image_embeddings(items)


def make_siglip_scorer(
    *,
    model: str = DFLT_RERANK_MODEL,
    cache: "MutableMapping[str, Any] | None" = None,
    device: "str | None" = None,
    image_field: str = DFLT_IMAGE_FIELD,
) -> "SiglipScorer":
    """Build a SigLIP :class:`SiglipScorer` (raises if the extra is missing)."""
    check_rerank_requirements()
    return SiglipScorer(
        model=model, cache=cache, device=device, image_field=image_field
    )


def check_rerank_requirements() -> None:
    """Raise :class:`RerankDependencyError` if the rerank extra isn't installed."""
    missing = [m for m in _RERANK_DEPS if not _importable(m)]
    if missing:
        raise RerankDependencyError(missing)


class SiglipScorer:
    """Scores (query, image) pairs by SigLIP cross-modal cosine similarity.

    The model is loaded lazily on first call; image embeddings are content-
    addressed (keyed by model + image URL) in an injectable ``dol`` store, so a
    re-rank of overlapping candidates is cheap. A candidate whose image can't be
    fetched/embedded scores ``-1.0`` (sorted to the bottom) rather than failing.
    """

    def __init__(
        self,
        *,
        model: str = DFLT_RERANK_MODEL,
        cache: "MutableMapping[str, Any] | None" = None,
        device: "str | None" = None,
        image_field: str = DFLT_IMAGE_FIELD,
    ):
        if image_field not in ImageResult.model_fields:
            raise ValueError(
                f"image_field {image_field!r} is not a field of ImageResult "
                f"(choose e.g. 'thumbnail_url' or 'url')"
            )
        self.model_id = model
        self.device = device
        self.image_field = image_field
        self._cache = cache if cache is not None else default_embedding_store(model)
        self._loaded: Any = None

    def __call__(self, query: str, results: Sequence[ImageResult]) -> list[float]:
        import numpy as np

        model, processor = self._model_and_processor()
        text_vec = self._embed_text(query, model, processor)
        scores: list[float] = []
        for r in results:
            img_vec = self._image_embedding(r, model, processor)
            scores.append(
                float(np.dot(text_vec, img_vec)) if img_vec is not None else -1.0
            )
        return scores

    def image_embeddings(self, results: Sequence[ImageResult]) -> list:
        """L2-normalized image embeddings (cached) for ``results``; ``None`` per failure.

        The image half of :meth:`__call__`, exposed so Layer-2 sequence selection
        can reuse the cached embeddings for cross-shot coherence/redundancy
        without re-fetching or re-embedding.
        """
        model, processor = self._model_and_processor()
        return [self._image_embedding(r, model, processor) for r in results]

    # -- internals -----------------------------------------------------------

    def _model_and_processor(self):
        if self._loaded is None:
            import os

            # this is a torch-based reranker; never let transformers auto-import
            # TensorFlow/Flax (which can be broken or unwanted in a torch env)
            os.environ.setdefault("USE_TF", "0")
            os.environ.setdefault("USE_FLAX", "0")
            import torch  # noqa: F401  (ensure present; used by transformers)
            from transformers import AutoModel, AutoProcessor

            model = AutoModel.from_pretrained(self.model_id)
            model.eval()
            if self.device:
                model.to(self.device)
            self._loaded = (model, AutoProcessor.from_pretrained(self.model_id))
        return self._loaded

    def _embed_text(self, text: str, model, processor):
        import torch

        inputs = processor(
            text=[text], return_tensors="pt", padding="max_length", truncation=True
        )
        if self.device:
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            feats = model.get_text_features(**inputs)
        return _l2_normalize(feats[0].cpu().numpy())

    def _image_embedding(self, result: ImageResult, model, processor):
        url = getattr(result, self.image_field, None) or result.url
        if not url:
            return None
        key = _embedding_key(self.model_id, url)
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        vec = self._embed_image_url(url, model, processor)
        if vec is not None:
            self._cache_put(key, vec)
        return vec

    def _embed_image_url(self, url: str, model, processor):
        import torch

        from illustration._imageio import fetch_image

        image = fetch_image(url)
        if image is None:
            return None
        inputs = processor(images=[image], return_tensors="pt")
        if self.device:
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            feats = model.get_image_features(**inputs)
        return _l2_normalize(feats[0].cpu().numpy())

    def _cache_get(self, key: str):
        import numpy as np

        try:
            raw = self._cache[key]
        except KeyError:
            return None
        try:
            return np.asarray(raw, dtype="float32")
        except Exception:  # pragma: no cover - corrupt entry
            return None

    def _cache_put(self, key: str, vec) -> None:
        self._cache[key] = [float(x) for x in vec]


# --- module helpers ---------------------------------------------------------


def default_embedding_store(model: str) -> "MutableMapping[str, Any]":
    """A ``JsonFiles`` store for image embeddings under the cache dir, per model."""
    from dol import JsonFiles

    root = cache_dir(ensure=True) / "embeddings" / _slug(model)
    root.mkdir(parents=True, exist_ok=True)
    return JsonFiles(str(root))


def _embedding_key(model_id: str, url: str) -> str:
    # model is part of the key (not only the per-model store dir) so a single
    # store injected across multiple models still separates their embeddings.
    blob = f"{model_id}\x00{url}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _l2_normalize(vec):
    import numpy as np

    arr = np.asarray(vec, dtype="float32")
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


def _importable(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)
