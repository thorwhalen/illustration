"""Query expansion & refinement — the first node of the curation loop (R2 §1).

A narration *beat* ("a stormy harbour at dusk, fishermen hauling nets") is not a
good stock-image query verbatim. This module turns a beat into a small set of
concrete, visual search queries, and — when a search round comes back empty or
off — refines a query given a short critique. These are the ``generate_query``
and ``refine_query`` steps of the bounded CRAG loop.

The default generator is built on :func:`aix.prompt_func` (the multi-provider
LLM facade) and is imported **lazily**, so ``import illustration`` never requires
``aix``. Every entry point takes an injectable seam (a plain
``beat -> queries`` / ``(beat, critique) -> query`` callable) so the loop is
fully testable offline with a stub — the same string-or-callable + lazy-LLM
idiom ``ir`` uses for its formulators.

>>> # offline: inject a stub expander (no LLM, no network)
>>> expand_query("a stormy harbour", expander=lambda beat: ["harbour storm", "rough sea"])
['a stormy harbour', 'harbour storm', 'rough sea']
>>> refine_query("a stormy harbour", "too generic", refiner=lambda b, c: "harbour at dusk in a gale")
'harbour at dusk in a gale'
"""

from __future__ import annotations

from typing import Callable, Sequence

__all__ = [
    "expand_query",
    "refine_query",
    "make_query_expander",
    "make_query_refiner",
    "Expander",
    "Refiner",
    "DFLT_N_EXPANSIONS",
    "EXPANSION_PROMPT",
    "REFINEMENT_PROMPT",
]

#: An expander maps a beat to a list of candidate image-search queries.
Expander = Callable[[str], Sequence[str]]

#: A refiner maps (beat, critique) to one improved query.
Refiner = Callable[[str, str], str]

#: Default number of expansions the LLM generator is asked for.
DFLT_N_EXPANSIONS = 3

EXPANSION_PROMPT = (
    "You turn a narration beat into concrete, visual stock-image search queries.\n"
    "Beat: {beat}\n\n"
    "Write {n} short queries (3-7 words each), one per line, no numbering. Each must "
    "name concrete, depictable subjects/scenes/lighting a photographer could shoot — "
    "not abstract narration. Vary the angle (subject, setting, mood) across the lines."
)

REFINEMENT_PROMPT = (
    "A stock-image search for a narration beat did not return good matches.\n"
    "Beat: {beat}\n"
    "What went wrong: {critique}\n\n"
    "Write ONE improved search query (3-7 words) that is more concrete and more "
    "likely to match real photographs. Output only the query, nothing else."
)


def expand_query(
    beat: str,
    *,
    n: int = DFLT_N_EXPANSIONS,
    expander: "Expander | None" = None,
    model: "str | None" = None,
    include_verbatim: bool = True,
) -> list[str]:
    """Expand a narration ``beat`` into a deduped list of image-search queries.

    The verbatim beat is included first by default (so the literal phrasing is
    never lost), followed by the expander's suggestions. ``expander`` defaults to
    an :func:`aix.prompt_func`-backed generator (built lazily); inject a
    ``beat -> [query, ...]`` callable to override it or to test offline.
    """
    fn = expander if expander is not None else make_query_expander(n=n, model=model)
    queries: list[str] = [beat] if include_verbatim else []
    try:
        queries.extend(fn(beat))
    except Exception:  # an LLM hiccup must not sink the loop — fall back to verbatim
        if not queries:
            queries = [beat]
    return _dedupe_nonempty(queries)


def refine_query(
    beat: str,
    critique: str,
    *,
    refiner: "Refiner | None" = None,
    model: "str | None" = None,
) -> str:
    """Refine a query for ``beat`` given a short ``critique`` of the last round.

    ``refiner`` defaults to an :func:`aix.prompt_func`-backed refiner (lazy);
    inject a ``(beat, critique) -> query`` callable to override or test offline.
    Falls back to the verbatim beat if the refiner errors or returns nothing.
    """
    fn = refiner if refiner is not None else make_query_refiner(model=model)
    try:
        refined = fn(beat, critique)
    except Exception:
        refined = ""
    refined = (refined or "").strip()
    return refined or beat


def make_query_expander(
    *,
    n: int = DFLT_N_EXPANSIONS,
    prompt: str = EXPANSION_PROMPT,
    model: "str | None" = None,
) -> Expander:
    """Build the default LLM expander on ``aix`` (lazy import on first call)."""

    def expander(beat: str) -> list[str]:
        import aix  # lazy: Layer-2 dependency only

        fn = aix.prompt_func(prompt, egress=_parse_lines, name="expand_query", model=model)
        return list(fn(beat=beat, n=n))

    return expander


def make_query_refiner(
    *, prompt: str = REFINEMENT_PROMPT, model: "str | None" = None
) -> Refiner:
    """Build the default LLM refiner on ``aix`` (lazy import on first call)."""

    def refiner(beat: str, critique: str) -> str:
        import aix  # lazy

        fn = aix.prompt_func(prompt, egress=_first_line, name="refine_query", model=model)
        return fn(beat=beat, critique=critique)

    return refiner


# --- internals --------------------------------------------------------------


def _parse_lines(text: str) -> list[str]:
    """Parse an LLM list reply into clean query strings (strip bullets/numbers)."""
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*•").strip()
        # drop a leading "1." / "2)" enumerator
        if line[:2].rstrip(".)").isdigit():
            line = line.split(".", 1)[-1].split(")", 1)[-1].strip()
        line = line.strip().strip('"').strip()
        if line:
            out.append(line)
    return out


def _first_line(text: str) -> str:
    lines = _parse_lines(text)
    return lines[0] if lines else (text or "").strip()


def _dedupe_nonempty(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = (it or "").strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out
