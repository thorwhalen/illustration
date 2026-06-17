"""illustration — find existing images to illustrate narrated video.

A façade + (future) agentic layer for **cross-modal text-to-image retrieval**:
given narration text, retrieve fitting images from stock / open-media corpora.
It is *not* an image generator.

Quick start (no API key needed — Openverse is the default source):

>>> import illustration                                   # doctest: +SKIP
>>> hits = illustration.search("a stormy harbour at dusk", n=10)   # doctest: +SKIP
>>> hits[0].url, hits[0].license, hits[0].cacheable       # doctest: +SKIP
('https://...', 'by-sa', True)

The first argument is the query; everything else is keyword. ``search`` returns
a list of :class:`~illustration.schema.ImageResult` (the normalized,
license-carrying result schema). Results are cached (SHA-256 content-addressed),
so an identical second call is free.

Adding a provider is open-closed — subclass
:class:`~illustration.base.RetrievalSource` and
:func:`~illustration.register_source` it; the façade is untouched.

See ``misc/docs/design/illustration_design.md`` for the full design.
"""

from __future__ import annotations

# Public API ----------------------------------------------------------------
from illustration.base import RetrievalSource, SourceInfo
from illustration.caching import SearchCache, default_search_store, search_cache_key
from illustration.config import (
    DFLT_LICENSE_ALLOWLIST,
    DFLT_N,
    DFLT_SOURCES,
    cache_dir,
)
from illustration.credentials import (
    PROVIDER_CONSOLE_URLS,
    PROVIDER_ENV_VARS,
    check_requirements,
    requires_credentials,
    resolve_api_key,
    using_credentials,
)
from illustration.errors import (
    IllustrationError,
    MissingCredentialError,
    ProviderError,
    RateLimitError,
    UnknownSourceError,
)
from illustration.facade import search
from illustration.registry import (
    SourcesView,
    default_sources,
    get_source,
    list_sources,
    register_source,
    sources,
    unregister_source,
)
from illustration.schema import ImageResult, license_allowlist, to_search_hit
from illustration.translation import make_param_translator

# Importing the providers subpackage registers the built-in sources as a side
# effect. Named `providers` so it does not shadow the public `sources` registry
# view imported above.
from illustration import providers as _builtin_providers  # noqa: F401,E402  (side-effect import)

__all__ = [
    # façade
    "search",
    # schema + helpers
    "ImageResult",
    "license_allowlist",
    "to_search_hit",
    # registry / sources
    "RetrievalSource",
    "SourceInfo",
    "register_source",
    "unregister_source",
    "get_source",
    "list_sources",
    "default_sources",
    "sources",
    "SourcesView",
    # caching
    "SearchCache",
    "search_cache_key",
    "default_search_store",
    # credentials
    "using_credentials",
    "resolve_api_key",
    "check_requirements",
    "requires_credentials",
    "PROVIDER_ENV_VARS",
    "PROVIDER_CONSOLE_URLS",
    # translation
    "make_param_translator",
    # config
    "DFLT_N",
    "DFLT_SOURCES",
    "DFLT_LICENSE_ALLOWLIST",
    "cache_dir",
    # errors
    "IllustrationError",
    "UnknownSourceError",
    "MissingCredentialError",
    "ProviderError",
    "RateLimitError",
]

__version__ = "0.0.2"
