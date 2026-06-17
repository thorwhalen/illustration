"""Shared image fetching — used by the rerank and curation layers.

Both the precision reranker (:mod:`illustration.reranking`) and the Layer-2
classical-CV prefilters (:mod:`illustration.inspection`) need to pull image
bytes off the network and decode them. That logic lives here so there is one
fetch path (one User-Agent, one timeout policy, one fail-soft contract) rather
than a copy per consumer.

Everything here lazily imports ``requests`` / ``Pillow`` so ``import
illustration`` stays dependency-light; the heavy bits ride the optional
``[rerank]`` / ``[curate]`` extras.

>>> # offline doctest: a candidate with no fetchable URL yields None, never raises
>>> from illustration.schema import ImageResult
>>> image_for_result(ImageResult(provider="p", id="1", url="")) is None
True
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from illustration.config import HTTP_TIMEOUT, user_agent
from illustration.schema import ImageResult

__all__ = ["fetch_image", "fetch_image_bytes", "image_for_result", "DFLT_IMAGE_FIELD"]

#: Which result field to fetch by default — the thumbnail is smaller/faster than
#: the full image and sufficient for both relevance scoring and CV pre-filters.
DFLT_IMAGE_FIELD = "thumbnail_url"


def fetch_image_bytes(
    url: str, *, timeout: "int | float" = HTTP_TIMEOUT, session: Any = None
) -> "bytes | None":
    """Download ``url`` and return the raw bytes, or ``None`` on any failure.

    Never raises on a network/HTTP error — a candidate that can't be fetched is
    simply skipped by the caller (fail-soft).
    """
    if not url:
        return None
    try:
        import requests

        getter = session.get if session is not None else requests.get
        resp = getter(url, headers={"User-Agent": user_agent()}, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception:  # network / HTTP / decode failure -> skip
        return None


def fetch_image(
    url: str, *, timeout: "int | float" = HTTP_TIMEOUT, session: Any = None
):
    """Download ``url`` into an RGB :class:`PIL.Image.Image`, or ``None`` on failure."""
    data = fetch_image_bytes(url, timeout=timeout, session=session)
    if data is None:
        return None
    try:
        import io

        from PIL import Image

        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # decode failure -> skip this candidate
        return None


def image_for_result(
    result: ImageResult,
    *,
    field: str = DFLT_IMAGE_FIELD,
    timeout: "int | float" = HTTP_TIMEOUT,
    session: Any = None,
):
    """Fetch the best image for ``result``: the chosen ``field``, then ``url``.

    Returns a PIL image, or ``None`` if neither URL is fetchable/decodable.
    """
    url = getattr(result, field, None) or result.url
    return fetch_image(url, timeout=timeout, session=session) if url else None


def memoized_image_loader(
    *, field: str = DFLT_IMAGE_FIELD, fetch: "Callable | None" = None
) -> "Callable[[ImageResult], Any]":
    """A per-call, cache-once image loader for one curation/prefilter pass.

    Returns ``load(result) -> PIL image | None`` that fetches each distinct image
    URL at most once (in-memory LRU keyed by URL). ``fetch`` overrides the fetch
    function (a test double avoids the network entirely). The cache is local to
    the returned closure, so it's discarded when the pass ends.
    """
    _fetch = fetch if fetch is not None else fetch_image

    @lru_cache(maxsize=None)
    def _load(url: str):
        return _fetch(url)

    def load(result: ImageResult):
        url = getattr(result, field, None) or result.url
        return _load(url) if url else None

    return load
