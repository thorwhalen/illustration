"""Wikimedia Commons source — 140M+ free media, **no key**, deep file metadata.

Wikimedia Commons (the MediaWiki Action API at
``https://commons.wikimedia.org/w/api.php``) adds breadth and historical /
editorial / fine-art / scientific reference imagery to the no-key default set.
It uses a ``generator=search`` query feeding ``prop=imageinfo`` so each hit
carries the full image URL, a thumbnail, and ``extmetadata`` (license, license
URL, artist, attribution).

This adapter exercises the base's general extension hooks (no per-provider hacks
in the façade): :attr:`fixed_params` (the constant ``action=query`` / ``format``
/ ``generator`` / ``gsrnamespace`` / ``prop`` / ``iiprop`` params) and
:meth:`_page_params` (Wikimedia paginates by ``gsroffset``, not page number).

Quirks handled here: the response's ``query.pages`` is a **dict keyed by
pageid** (sorted here by the search ``index`` to preserve relevance order);
licenses **vary per file** (so pair with the ``license_allow`` gate for
commercial use); the ``Artist`` field is **HTML** (stripped for ``author``,
with the first ``href`` lifted into ``author_url``); the File namespace includes
non-images (PDF/audio/video) which are dropped during normalization by MIME.

It supports **none** of the canonical search-time filters (orientation/size/
safe/license_type/color/content_type) — they degrade gracefully.
"""

from __future__ import annotations

import html
import re
from typing import Any, Iterable, Mapping

from illustration.base import RetrievalSource, SourceInfo
from illustration.schema import ImageResult

__all__ = ["WikimediaSource"]

_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def _strip_html(value: "str | None") -> "str | None":
    """Strip tags + unescape entities from an extmetadata HTML value."""
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub("", value)).strip()
    return text or None


def _first_href(value: "str | None") -> "str | None":
    if not value:
        return None
    m = _HREF_RE.search(value)
    if not m:
        return None
    url = m.group(1)
    return ("https:" + url) if url.startswith("//") else url


class WikimediaSource(RetrievalSource):
    """Pure-search adapter for Wikimedia Commons (MediaWiki Action API)."""

    name = "wikimedia"
    endpoint = "https://commons.wikimedia.org/w/api.php"
    query_param = "gsrsearch"
    max_per_page = 50  # anonymous search-generator limit
    fixed_params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",  # the File namespace
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime|user",
        "iiurlwidth": "320",  # produces a thumbnail URL
    }
    # param_map left empty: Commons exposes no canonical search-time filters here.
    info = SourceInfo(
        name="wikimedia",
        description="140M+ free media files with deep per-file metadata; no key.",
        requires_key=False,
        homepage="https://commons.wikimedia.org",
        default_cacheable=True,
        license_note="Per-file license varies (CC/PD; some share-alike) — gate for commercial use.",
        rate_limit="etiquette-bound (descriptive User-Agent required)",
        tags=("open", "historical", "editorial", "breadth", "no-key"),
    )

    def _page_params(self, *, page: int, per_page: int) -> dict:
        # offset-based pagination, not page-number based
        return {"gsrlimit": per_page, "gsroffset": (page - 1) * per_page}

    def _items(self, response: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        pages = (response.get("query") or {}).get("pages") or {}
        # `pages` is a dict keyed by pageid; sort by search index for relevance order
        return sorted(pages.values(), key=lambda p: p.get("index", 0))

    def _normalize(self, item: Mapping[str, Any], *, query: str) -> ImageResult:
        info = (item.get("imageinfo") or [{}])[0]
        if not str(info.get("mime", "")).startswith("image/"):
            raise ValueError("not an image file")  # dropped by _safe_normalize
        em = info.get("extmetadata") or {}

        def _em(key: str) -> "str | None":
            v = em.get(key)
            return v.get("value") if isinstance(v, dict) else None

        artist_html = _em("Artist")
        title = item.get("title") or ""
        if title.startswith("File:"):
            title = title[len("File:"):]
        license_short = _em("LicenseShortName")
        return ImageResult(
            provider=self.name,
            id=str(item.get("pageid")),
            url=info.get("url"),
            thumbnail_url=info.get("thumburl"),
            width=info.get("width"),
            height=info.get("height"),
            title=title or None,
            description=_strip_html(_em("ImageDescription")),
            tags=[],  # Commons categories are noisy/HTML; omitted at this layer
            license=_em("License") or license_short,
            license_url=_em("LicenseUrl"),
            attribution=_strip_html(_em("Attribution"))
            or _build_attribution(_strip_html(artist_html), license_short),
            source_page_url=info.get("descriptionurl"),
            author=_strip_html(artist_html),
            author_url=_first_href(artist_html),
            cacheable=True,  # free content; preserve attribution (gate per-file license)
            avg_color=None,
            query=query,
            raw=dict(item),
        )


def _build_attribution(author: "str | None", license_short: "str | None") -> "str | None":
    if author and license_short:
        return f"{author} / {license_short}, via Wikimedia Commons"
    if author:
        return f"{author}, via Wikimedia Commons"
    if license_short:
        return f"{license_short}, via Wikimedia Commons"
    return None
