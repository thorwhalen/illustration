"""Openverse source — 800M+ openly-licensed / public-domain images, **no key**.

Openverse (``https://api.openverse.org/v1/images/``) aggregates Creative-Commons
and public-domain media from Flickr, Wikimedia, museums, and more. The anonymous
tier needs no credentials, which makes it the package's out-of-the-box default
(``illustration.search("...")`` works with zero setup). Every result carries a
license code, a canonical license URL (except CC0/PDM, where it is ``None``), and
a ready-to-render attribution sentence — so licensing is populated from day one.

Quirks handled here (from the live-API survey): ``tags`` are *objects*
(``{"name": ...}``), ``url`` is the real image while ``thumbnail`` is an
Openverse proxy, and the anonymous tier caps ``page_size`` at 20.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from illustration.base import RetrievalSource, SourceInfo
from illustration.schema import ImageResult

__all__ = ["OpenverseSource"]

# canonical aspect-ratio vocabulary -> Openverse's aspect_ratio vocabulary
_ORIENTATION_TO_ASPECT = {"landscape": "wide", "portrait": "tall", "square": "square"}


class OpenverseSource(RetrievalSource):
    """Pure-search adapter for the Openverse image API (anonymous tier)."""

    name = "openverse"
    endpoint = "https://api.openverse.org/v1/images/"
    query_param = "q"
    page_param = "page"
    per_page_param = "page_size"
    max_per_page = 20  # anonymous-tier hard cap
    param_map = {
        "orientation": {
            "name": "aspect_ratio",
            "coerce": lambda o: _ORIENTATION_TO_ASPECT.get(o, o),
        },
        "size": {"name": "size", "choices": {"large", "medium", "small"}},
        "safe": {"name": "mature", "coerce": lambda safe: not safe},
        "license_type": "license_type",
        # content_type: Openverse `category` has no 'vector' → only photo/illustration
        "content_type": {
            "name": "category",
            "choices": {"photo", "illustration"},
            "coerce": lambda ct: {
                "photo": "photograph",
                "illustration": "illustration",
            }[ct],
        },
        "color": None,  # Openverse has no color filter (explicitly unsupported)
    }
    info = SourceInfo(
        name="openverse",
        description="800M+ CC / public-domain images aggregated from 50+ sources.",
        requires_key=False,
        homepage="https://openverse.org",
        default_cacheable=True,
        license_note="Per-result CC/PD license; preserve attribution for BY-family.",
        rate_limit="anonymous: 20/min, 200/day",
        tags=("open", "cc", "public-domain", "breadth"),
    )

    def _items(self, response: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        return response.get("results") or []

    def _normalize(self, item: Mapping[str, Any], *, query: str) -> ImageResult:
        tags = [
            t["name"]
            for t in (item.get("tags") or [])
            if isinstance(t, Mapping) and t.get("name")
        ]
        title = item.get("title")
        return ImageResult(
            provider=self.name,
            id=str(item["id"]),
            url=item["url"],
            thumbnail_url=item.get("thumbnail"),
            width=item.get("width"),
            height=item.get("height"),
            title=title,
            description=title,  # Openverse exposes no separate description
            tags=tags,
            license=item.get("license"),
            license_url=item.get("license_url"),
            attribution=item.get("attribution"),
            source_page_url=item.get("foreign_landing_url"),
            author=item.get("creator"),
            author_url=item.get("creator_url"),
            cacheable=True,  # CC / public-domain media is cacheable (preserve attribution)
            avg_color=None,
            query=query,
            raw=dict(item),
        )
