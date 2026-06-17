"""Command-line surface (thin ``argh`` wrappers over the library functions).

Business logic lives in the library; these functions only adapt it to the shell
and format output — the dispatch-to-interface pattern. Examples::

    illustration search "a stormy harbour at dusk" --n 10
    illustration search "rusty bicycle" --source openverse --size large --json
    illustration sources
    illustration info openverse
"""

from __future__ import annotations

import json as _json

import illustration

__all__ = ["search", "sources", "info", "COMMANDS"]


def search(
    query: str,
    *,
    n: int = 10,
    source: "str | None" = None,
    orientation: "str | None" = None,
    size: "str | None" = None,
    safe: bool = True,
    license_type: "str | None" = None,
    json: bool = False,
):
    """Search for images and print the results (one per line, or ``--json``)."""
    results = illustration.search(
        query,
        n=n,
        source=source,
        orientation=orientation,
        size=size,
        safe=safe,
        license_type=license_type,
    )
    if json:
        return _json.dumps([r.model_dump() for r in results], indent=2, default=str)
    if not results:
        return "(no results)"
    lines = []
    for r in results:
        label = r.title or r.description or "(untitled)"
        label = label if len(label) <= 60 else label[:57] + "..."
        lines.append(f"[{r.provider}] {label}\n    {r.url}  ({r.license or 'unknown license'})")
    return "\n".join(lines)


def sources():
    """List the registered image sources."""
    return "\n".join(illustration.list_sources())


def info(name: str):
    """Show metadata for one source."""
    src = illustration.get_source(name)
    return _json.dumps(src.info.to_dict(), indent=2, default=str)


#: Commands exposed by the CLI (consumed by ``illustration/__main__.py``).
COMMANDS = [search, sources, info]
