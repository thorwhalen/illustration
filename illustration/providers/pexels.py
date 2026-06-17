"""Pexels source — high-quality stock photos, **API key required**.

Pexels (``https://api.pexels.com/v1/search``) is the package's reference *keyed*
provider: it proves the registry is a true drop-in and exercises the credentials
/ ``check_requirements`` path. The key is sent as the **raw** value of the
``Authorization`` header (no ``Bearer`` prefix — a prefix yields 401).

Quirks handled here (from the live-API survey): ``photos[].url`` is the Pexels
web *page*, not the image (the image is under ``photos[].src.*``); there are no
tags and no per-result license (all content is the single Pexels License).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from illustration.base import RetrievalSource, SourceInfo
from illustration.schema import ImageResult

__all__ = ["PexelsSource"]

_PEXELS_LICENSE = "Pexels License"
_PEXELS_LICENSE_URL = "https://www.pexels.com/license/"


class PexelsSource(RetrievalSource):
    """Pure-search adapter for the Pexels photo API."""

    name = "pexels"
    endpoint = "https://api.pexels.com/v1/search"
    query_param = "query"
    page_param = "page"
    per_page_param = "per_page"
    max_per_page = 80
    param_map = {
        "orientation": {
            "name": "orientation",
            "choices": {"landscape", "portrait", "square"},
        },
        "size": {"name": "size", "choices": {"large", "medium", "small"}},
        # `safe` is a no-op (the Pexels corpus is curated); `license_type` has no
        # equivalent (single license). Both are explicitly unsupported -> degrade.
        "safe": None,
        "license_type": None,
        "color": "color",  # Pexels supports a named or #hex color
        "content_type": None,  # Pexels is photos only
    }
    info = SourceInfo(
        name="pexels",
        description="Curated high-quality stock photos under the Pexels License.",
        requires_key=True,
        homepage="https://www.pexels.com",
        default_cacheable=True,
        license_note="Single Pexels License (commercial OK); credit photographer + backlink.",
        rate_limit="200/hour, 20,000/month",
        tags=("stock", "photos", "keyed"),
    )

    def _auth_headers(self, api_key: "str | None") -> dict:
        # Raw key, no "Bearer " prefix. check_requirements has already ensured
        # a key is present before we get here.
        return {"Authorization": api_key} if api_key else {}

    def _items(self, response: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        return response.get("photos") or []

    def _normalize(self, item: Mapping[str, Any], *, query: str) -> ImageResult:
        src = item.get("src") or {}
        photographer = item.get("photographer")
        attribution = (
            f"Photo by {photographer} on Pexels" if photographer else "Photo from Pexels"
        )
        return ImageResult(
            provider=self.name,
            id=str(item["id"]),
            url=src.get("original") or src.get("large2x") or src.get("large"),
            thumbnail_url=src.get("tiny") or src.get("medium"),
            width=item.get("width"),
            height=item.get("height"),
            title=None,
            description=item.get("alt") or None,
            tags=[],  # Pexels returns no tags
            license=_PEXELS_LICENSE,
            license_url=_PEXELS_LICENSE_URL,
            attribution=attribution,
            source_page_url=item.get("url"),  # the Pexels web page
            author=photographer,
            author_url=item.get("photographer_url"),
            cacheable=True,  # Pexels License permits caching for display
            avg_color=item.get("avg_color"),
            query=query,
            raw=dict(item),
        )
