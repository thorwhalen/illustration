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

__all__ = ["search", "curate", "curate_sequence", "sources", "info", "COMMANDS"]


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


def curate(
    beat: str,
    *,
    source: "str | None" = None,
    n: int = 12,
    max_iter: int = 3,
    model: "str | None" = None,
    json: bool = False,
):
    """Curate the best image for a narration BEAT via the bounded CRAG loop.

    Needs the optional ``[curate]`` extra (aix + ir) and provider/LLM API keys;
    see the agentic-curation docs. Prints the accepted candidate (or the
    best-so-far) and a one-line spend summary, or the full result with ``--json``.
    """
    from illustration.curation import Budget

    result = illustration.curate(
        beat,
        sources=source,
        n=n,
        budget=Budget(max_iter=max_iter),
        model=model,
    )
    if json:
        return _json.dumps(result.model_dump(), indent=2, default=str)
    best = result.best
    head = (
        f"{'ACCEPTED' if result.accepted else 'BEST-SO-FAR'} "
        f"(grade={result.grade}, reason={result.reason})"
    )
    if best is None:
        return f"{head}\n(no candidate found)\nspend: {result.spend}"
    lines = [
        head,
        f"  [{best.result.provider}] {best.result.url}",
        f"  license: {best.result.license or 'unknown'}"
        + (f"  rubric: {best.rubric.overall:.2f}" if best.rubric else "")
        + (f"  score: {best.score:.3f}" if best.score is not None else ""),
    ]
    if best.caption:
        lines.append(f"  caption: {best.caption}")
    if best.rationale:
        lines.append(f"  rationale: {best.rationale}")
    lines.append(f"  spend: {result.spend}")
    return "\n".join(lines)


def curate_sequence(
    *beats: str,
    source: "str | None" = None,
    n: int = 12,
    json: bool = False,
):
    """Choose the best image per narration BEAT across a sequence (cross-shot).

    Pass one quoted beat per argument. Optimizes relevance + cross-shot coherence
    − redundancy with near-duplicate suppression (the M4 selection layer); needs
    the [curate]/[rerank] extras for the full signal. Prints the chosen image per
    beat, or the full result with --json.
    """
    from illustration.sequence import curate_sequence as _cs

    if not beats:
        return "(no beats given; pass one quoted beat per argument)"
    result = _cs(list(beats), sources=source, n=n)
    if json:
        return _json.dumps(result.model_dump(), indent=2, default=str)
    lines = []
    for bs in result.selection.selections:
        if bs.chosen is None:
            lines.append(f"[beat {bs.beat_index}] (no image)")
            continue
        dup = " [forced-dup]" if bs.forced_duplicate else ""
        lines.append(
            f"[beat {bs.beat_index}] {bs.chosen.url}  "
            f"(rel={bs.relevance:.3f} coh={bs.coherence:.2f} red={bs.redundancy:.2f}){dup}"
        )
    if result.selection.notes:
        lines.append("notes: " + "; ".join(result.selection.notes))
    return "\n".join(lines)


def sources():
    """List the registered image sources."""
    return "\n".join(illustration.list_sources())


def info(name: str):
    """Show metadata for one source."""
    src = illustration.get_source(name)
    return _json.dumps(src.info.to_dict(), indent=2, default=str)


#: Commands exposed by the CLI (consumed by ``illustration/__main__.py``).
COMMANDS = [search, curate, curate_sequence, sources, info]
