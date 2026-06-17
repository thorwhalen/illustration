"""The normalized result schema — the single source of truth (Pydantic v2).

:class:`ImageResult` is the stable contract that every provider normalizes into
and that the (future) agentic curation layer consumes. License, attribution,
``source_page_url`` and ``cacheable`` are first-class and populated from day one,
because licensing/cacheability is a primary concern for commercial-adjacent
video (see ``misc/docs/design/illustration_design.md`` §3).

>>> r = ImageResult(provider="openverse", id="abc", url="https://x/img.jpg",
...                  license="by-sa", cacheable=True)
>>> r.provider, r.cacheable, r.tags
('openverse', True, [])
>>> r.model_dump()["license"]
'by-sa'

The ``raw`` field carries the untranslated provider payload (the escape-hatch
"nothing is lost" convention), so a downstream consumer can always reach a
provider-specific field the normalized schema doesn't name.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from pydantic import BaseModel, Field

from illustration.config import DFLT_LICENSE_ALLOWLIST

__all__ = ["ImageResult", "license_allowlist", "to_search_hit"]


class ImageResult(BaseModel):
    """One normalized image hit from any provider.

    The first eight fields plus ``cacheable`` are the cross-provider minimum the
    design guarantees; the rest are populated when a provider supplies them.
    """

    provider: str = Field(description="Source/provider name, e.g. 'openverse'.")
    id: str = Field(description="Provider-native identifier.")
    url: str = Field(description="Full-resolution image URL.")
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    title: str | None = None
    description: str | None = Field(default=None, description="Alt text / longer description.")
    tags: list[str] = Field(default_factory=list)
    license: str | None = Field(default=None, description="License code or name (e.g. 'by-sa').")
    license_url: str | None = None
    attribution: str | None = Field(default=None, description="Ready-to-render attribution sentence.")
    source_page_url: str | None = None
    author: str | None = None
    author_url: str | None = None
    cacheable: bool = Field(default=False, description="May the bytes be downloaded/cached to our server?")
    avg_color: str | None = Field(default=None, description="Dominant-color hint where available.")
    # provenance / forward-compatibility
    query: str | None = Field(default=None, description="Canonical query that produced this hit.")
    score: float | None = Field(default=None, description="Reserved for Layer-2 rerank; None at Layer 1.")
    raw: dict[str, Any] = Field(default_factory=dict, description="Untranslated provider payload.")

    def to_search_hit(self):
        """Adapt to an ``ir.SearchHit`` for Layer-2 cross-provider fusion.

        Imported lazily so ``import illustration`` never requires ``ir``.
        """
        return to_search_hit(self)


def to_search_hit(result: "ImageResult"):
    """Map an :class:`ImageResult` to an ``ir.SearchHit`` for Layer-2 fusion.

    The bridge into the ``ir`` retrieval substrate so the agentic layer can
    ``ir.fuse_hits`` across providers. ``ir`` is imported here, not at module
    top, to keep the base façade dependency-light. Identity follows ir's
    ``(source, artifact_id)`` keying: ``source`` is the provider and
    ``artifact_id`` is the provider-native id. The image URL is placed under the
    ``path`` metadata key so ``SearchHit.pointer`` (which scans
    ``ir.base.POINTER_KEYS``) resolves to it; the full normalized result rides
    along in ``metadata`` too.

    ``score`` is ``0.0`` for any hit not yet reranked (Layer 1 leaves
    ``ImageResult.score`` as ``None``) — rely on *rank*, not magnitude, until a
    Layer-2 reranker populates it; ``ir.fuse_hits`` (RRF) is rank-based, so this
    is correct for fusion.
    """
    from ir import SearchHit  # lazy: Layer-2 dependency only

    return SearchHit(
        artifact_id=result.id,
        surface_kind="image",
        score=result.score if result.score is not None else 0.0,
        text=result.description or result.title or "",
        metadata={**result.model_dump(), "path": result.url},
        source=result.provider,
    )


def license_allowlist(
    results: Iterable["ImageResult"],
    *,
    allow: "Iterable[str] | None" = None,
) -> list["ImageResult"]:
    """Keep only results whose license is on the allowlist (R3's license gate).

    The mandatory per-file license-verification gate for commercial-adjacent
    use: aggregators disclaim license accuracy, so callers should gate on a
    known-good set. Matching is case-insensitive on the license code/name.
    Results with no ``license`` are dropped (unknown == not allowed).

    >>> a = ImageResult(provider="p", id="1", url="u", license="cc0")
    >>> b = ImageResult(provider="p", id="2", url="u", license="by-nc")
    >>> c = ImageResult(provider="p", id="3", url="u", license=None)
    >>> [r.id for r in license_allowlist([a, b, c])]
    ['1']
    >>> [r.id for r in license_allowlist([a, b, c], allow={"by-nc"})]
    ['2']
    """
    allowed = {s.lower() for s in (allow if allow is not None else DFLT_LICENSE_ALLOWLIST)}
    return [r for r in results if r.license and r.license.lower() in allowed]


def _coerce_results(items: Iterable[Mapping[str, Any]]) -> list[ImageResult]:
    """Validate a sequence of dicts back into :class:`ImageResult` (cache reads)."""
    return [ImageResult.model_validate(d) for d in items]
