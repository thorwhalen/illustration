"""Configuration: XDG directories and package-wide defaults (the SSOT).

All tunable constants live here so the rest of the package never hardcodes a
magic number. Directories follow the XDG base-directory convention with
per-package environment overrides, mirroring the ecosystem's ``ir``/``aix``
idiom:

================  ===================================  ============================
Purpose           Environment override                 Fallback
================  ===================================  ============================
config            ``ILLUSTRATION_CONFIG_DIR``           ``$XDG_CONFIG_HOME``/illustration
data (durable)    ``ILLUSTRATION_DATA_DIR``             ``$XDG_DATA_HOME``/illustration
cache (regen.)    ``ILLUSTRATION_CACHE_DIR``            ``$XDG_CACHE_HOME``/illustration
================  ===================================  ============================

>>> p = cache_dir()                          # doctest: +ELLIPSIS
>>> p.name
'illustration'
"""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

__all__ = [
    "config_dir",
    "data_dir",
    "cache_dir",
    "package_version",
    "user_agent",
    "DFLT_N",
    "DFLT_SOURCES",
    "DFLT_LICENSE_ALLOWLIST",
    "HTTP_TIMEOUT",
    "MAX_PAGES",
    "SEARCH_CACHE_SCHEMA",
]

# --- Defaults (no magic numbers anywhere else) ------------------------------

#: Default number of results requested *per source*.
DFLT_N = 10

#: Default source set used when ``search(..., source=None)``. Openverse first
#: because it needs no API key (works out of the box).
DFLT_SOURCES = ("openverse",)

#: Conservative default license allowlist for the (opt-in) license gate.
#: CC0 / public-domain / CC-BY / CC-BY-SA are commercial-safe (BY-SA imposes
#: share-alike — flagged, not rejected). NC/ND and unknowns are excluded.
DFLT_LICENSE_ALLOWLIST = frozenset({"cc0", "pdm", "by", "by-sa", "pexels license"})

#: HTTP request timeout, seconds.
HTTP_TIMEOUT = 30

#: Hard safety cap on how many pages a single ``search`` will fetch, so an
#: unbounded ``n`` (or a misbehaving provider) can never loop forever.
MAX_PAGES = 25

#: Version token folded into every cache key, so a result-schema change
#: invalidates the cache *structurally* (a new key) rather than by deletion.
SEARCH_CACHE_SCHEMA = "illustration.search/v1"


# --- Directories ------------------------------------------------------------


def _base_dir(env_var: str, xdg_var: str, home_subpath: str) -> Path:
    """Resolve a base dir: explicit env var > XDG var > ``~`` fallback."""
    explicit = os.environ.get(env_var)
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get(xdg_var)
    if xdg:
        return Path(xdg).expanduser() / "illustration"
    return Path.home() / home_subpath / "illustration"


def config_dir(*, ensure: bool = False) -> Path:
    """Directory for durable configuration (e.g. registered sources)."""
    return _ensure(
        _base_dir("ILLUSTRATION_CONFIG_DIR", "XDG_CONFIG_HOME", ".config"), ensure
    )


def data_dir(*, ensure: bool = False) -> Path:
    """Directory for durable data."""
    return _ensure(
        _base_dir("ILLUSTRATION_DATA_DIR", "XDG_DATA_HOME", ".local/share"), ensure
    )


def cache_dir(*, ensure: bool = False) -> Path:
    """Directory for regenerable caches (the default search-result store)."""
    return _ensure(
        _base_dir("ILLUSTRATION_CACHE_DIR", "XDG_CACHE_HOME", ".cache"), ensure
    )


def _ensure(path: Path, ensure: bool) -> Path:
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


# --- Identity ---------------------------------------------------------------


def package_version() -> str:
    """The installed package version, or ``'0+unknown'`` if not installed.

    >>> isinstance(package_version(), str)
    True
    """
    try:
        return version("illustration")
    except PackageNotFoundError:
        return "0+unknown"


def user_agent() -> str:
    """A descriptive User-Agent string (some providers throttle default UAs).

    >>> user_agent().startswith('illustration/')
    True
    """
    return f"illustration/{package_version()} (+https://github.com/thorwhalen/illustration)"
