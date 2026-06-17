"""The open-closed source registry and the ``sources`` view.

Providers register their :class:`~illustration.base.RetrievalSource` instance by
name into a module-level mapping; the façade dispatches through it. Adding a
provider never touches the façade. The :data:`sources` view offers both
dict-style (``sources["pexels"]``) and attribute-style (``sources.pexels``)
access — the ``denote`` idiom — and is a *live view* over the SSOT registry, so
"what providers exist" can never drift from what is queryable.

>>> from illustration.registry import list_sources
>>> "openverse" in list_sources()
True
"""

from __future__ import annotations

from typing import Iterator, Mapping

from illustration.base import RetrievalSource
from illustration.config import DFLT_SOURCES
from illustration.errors import UnknownSourceError

__all__ = [
    "register_source",
    "unregister_source",
    "get_source",
    "list_sources",
    "default_sources",
    "sources",
    "SourcesView",
]

_SOURCES: "dict[str, RetrievalSource]" = {}


def register_source(source: RetrievalSource, *, name: "str | None" = None) -> RetrievalSource:
    """Register a source instance under ``name`` (default ``source.name``).

    Returns the source, so it can be used as ``SRC = register_source(MySource())``.
    """
    key = name or source.name
    if not key:
        raise ValueError("source has no name; pass name=... or set .name")
    _SOURCES[key] = source
    return source


def unregister_source(name: str) -> None:
    """Remove a source from the registry (no error if absent)."""
    _SOURCES.pop(name, None)


def get_source(name: str) -> RetrievalSource:
    """Return the registered source named ``name`` (raises if unknown)."""
    try:
        return _SOURCES[name]
    except KeyError:
        raise UnknownSourceError(name, known=list(_SOURCES)) from None


def list_sources() -> list[str]:
    """Sorted names of all registered sources."""
    return sorted(_SOURCES)


def default_sources() -> list[str]:
    """The default source set (config ``DFLT_SOURCES``), filtered to registered.

    Falls back to all registered sources if none of the configured defaults are
    present, so the façade always has something to query.
    """
    defaults = [name for name in DFLT_SOURCES if name in _SOURCES]
    return defaults or list_sources()


class SourcesView(Mapping):
    """A live ``Mapping`` over the registry with dict- *and* attribute-access.

    Attribute access (``sources.openverse``) is a convenience; dict access
    (``sources["openverse"]``) is the canonical form and the only one that works
    for a source whose name collides with a ``Mapping`` method (``get``,
    ``keys``, ``values``, …).
    """

    def __getitem__(self, name: str) -> RetrievalSource:
        return get_source(name)

    def __getattr__(self, name: str) -> RetrievalSource:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return get_source(name)
        except UnknownSourceError as e:
            raise AttributeError(str(e)) from None

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(_SOURCES))

    def __len__(self) -> int:
        return len(_SOURCES)

    def __repr__(self) -> str:
        return f"SourcesView({list_sources()})"


#: Singleton view: ``illustration.sources["openverse"]`` or ``.openverse``.
sources = SourcesView()
