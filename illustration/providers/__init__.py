"""Built-in provider sources, registered on import.

Importing :mod:`illustration` imports this package, which instantiates and
registers each built-in :class:`~illustration.base.RetrievalSource`. A
third-party provider registers itself the same way:
``illustration.register_source(MySource())``.

(This subpackage is named ``providers`` rather than ``sources`` so it does not
shadow the public :data:`illustration.sources` registry view.)
"""

from __future__ import annotations

from illustration.providers.openverse import OpenverseSource
from illustration.providers.pexels import PexelsSource
from illustration.providers.pixabay import PixabaySource
from illustration.providers.wikimedia import WikimediaSource
from illustration.registry import register_source

__all__ = ["OpenverseSource", "PexelsSource", "PixabaySource", "WikimediaSource"]

# Register the built-ins (idempotent: re-registering overwrites the same key).
register_source(OpenverseSource())
register_source(PexelsSource())
register_source(PixabaySource())
register_source(WikimediaSource())
