"""Pixabay source — free commercial-use images, **API key required (query param)**.

Pixabay (``https://pixabay.com/api/``) is a second keyed provider whose license
explicitly permits **downloading, caching, and self-hosting** the files — the
download-to-your-own-server model a production pipeline wants (so ``cacheable``
is ``True``). Its key is sent as a **query parameter** (``key=``), not a header
— exercised here via the base ``_auth_params`` hook.

It is also the second provider for two canonical params: it supports ``color``
(native ``colors``, alongside Pexels) and ``content_type`` (native ``image_type``
= photo/illustration/vector, alongside Openverse's ``category``), which is what
promotes both to first-class façade arguments under the ≥2-provider rule.

Quirks handled here: ``tags`` is a comma-separated string; the usable image URLs
are ``largeImageURL`` / ``webformatURL`` (``imageURL`` needs full API access);
there is no per-result license (the single Pixabay Content License).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from illustration.base import RetrievalSource, SourceInfo
from illustration.schema import ImageResult

__all__ = ["PixabaySource"]

_PIXABAY_LICENSE = "Pixabay License"
_PIXABAY_LICENSE_URL = "https://pixabay.com/service/license-summary/"
# canonical orientation → Pixabay's orientation vocabulary (no 'square' → 'all')
_ORIENTATION = {"landscape": "horizontal", "portrait": "vertical", "square": "all"}
# canonical size → Pixabay min_width (no size tier; approximate with a width floor)
_SIZE_MIN_WIDTH = {"large": 1920, "medium": 1280, "small": 640}


class PixabaySource(RetrievalSource):
    """Pure-search adapter for the Pixabay image API."""

    name = "pixabay"
    endpoint = "https://pixabay.com/api/"
    query_param = "q"
    page_param = "page"
    per_page_param = "per_page"
    max_per_page = 200
    param_map = {
        # choices guards drop an unrecognized value (matching sibling providers)
        # rather than silently neutralizing it via the coerce default.
        "orientation": {
            "name": "orientation",
            "choices": {"landscape", "portrait", "square"},
            "coerce": lambda o: _ORIENTATION[o],
        },
        "size": {
            "name": "min_width",
            "choices": {"large", "medium", "small"},
            "coerce": lambda s: _SIZE_MIN_WIDTH[s],
        },
        "safe": {
            "name": "safesearch",
            "coerce": lambda safe: "true" if safe else "false",
        },
        "license_type": None,  # single Pixabay License
        "color": "colors",
        "content_type": {
            "name": "image_type",
            "choices": {"photo", "illustration", "vector"},
        },
    }
    info = SourceInfo(
        name="pixabay",
        description="Free commercial-use images; license permits caching + self-hosting.",
        requires_key=True,
        homepage="https://pixabay.com",
        default_cacheable=True,
        license_note="Single Pixabay Content License; download-to-own-server (no hotlink).",
        rate_limit="100/60s (raisable); responses must be cached 24h",
        tags=("stock", "free-commercial", "keyed", "cacheable"),
    )

    def _auth_params(self, api_key: "str | None") -> dict:
        # Pixabay takes the key as a query param, not a header.
        return {"key": api_key} if api_key else {}

    def _items(self, response: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        return response.get("hits") or []

    def _normalize(self, item: Mapping[str, Any], *, query: str) -> ImageResult:
        user = item.get("user")
        tags = [t.strip() for t in (item.get("tags") or "").split(",") if t.strip()]
        return ImageResult(
            provider=self.name,
            id=str(item["id"]),
            url=item.get("largeImageURL")
            or item.get("webformatURL")
            or item.get("imageURL"),
            thumbnail_url=item.get("previewURL"),
            width=item.get("imageWidth"),
            height=item.get("imageHeight"),
            title=None,
            description=None,
            tags=tags,
            license=_PIXABAY_LICENSE,
            license_url=_PIXABAY_LICENSE_URL,
            attribution=f"Image by {user} on Pixabay" if user else "Image from Pixabay",
            source_page_url=item.get("pageURL"),
            author=user,
            author_url=None,
            cacheable=True,  # license permits caching / self-hosting
            avg_color=None,
            query=query,
            raw=dict(item),
        )
