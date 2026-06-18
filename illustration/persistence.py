"""Persist curation/selection decisions as ``lacing`` standoff annotations (R2 §6).

Per R2 §6, a director's curation decisions should be **standoff annotations**, not
destructive edits: a beat → its chosen image, layered so a human override is a
*new* annotation that supersedes (never overwrites) the machine's choice, with
full provenance. The ecosystem already has exactly this — ``lacing`` (the
standoff annotation system: typed ``Annotation`` envelope, W3C PROV-O provenance,
append-only, OTIO export). This module is the thin adapter that maps an
illustration :class:`~illustration.sequence.SequenceResult` onto lacing — it does
**not** reinvent an annotation store.

One deliberate modeling choice: a "best image for beat *i*" selection is a *graph*
relation (beat → candidate), not inherently time-keyed — but ``lacing`` is
interval-keyed, and at selection time the storyboard has no rendered timeline
yet. So selections are keyed on an **ordinal beat-index timeline**
(``RationalTime(i, rate=1)`` = "beat *i*"), which is honest (a storyboard *is* an
ordered sequence) and lets the real render timeline stay a separate concern. If a
general "selection track" facade proves worth sharing, it belongs upstream in
``lacing``; this stays a domain-specific adapter.

Behind the optional ``[persist]`` extra (``lacing``); imported lazily so base
``illustration`` never requires it.

>>> # offline doctest needs lacing; skipped if the extra isn't installed
>>> import importlib.util
>>> if importlib.util.find_spec("lacing"):                       # doctest: +SKIP
...     from illustration.sequence import SequenceResult, SequenceSelection, BeatSelection
...     from illustration.schema import ImageResult
...     r = SequenceResult(beats=["dawn harbour"], selection=SequenceSelection(
...         selections=[BeatSelection(beat_index=0,
...             chosen=ImageResult(provider="p", id="x", url="u", score=0.9))]))
...     store = persist_sequence(r)
...     resolve_selection(store, 0)["selected"]["id"]
"""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, Field

from illustration.schema import ImageResult

__all__ = [
    "persist_sequence",
    "record_override",
    "resolve_selection",
    "resolved_selections",
    "export_otio",
    "SelectionBody",
    "SELECTION_SCHEMA_URI",
    "SELECTIONS_TIER",
]

#: The lacing body-schema URI for an illustration selection annotation.
SELECTION_SCHEMA_URI = "annot://schema/illustration-selection/v1"

#: The lacing tier selections live on.
SELECTIONS_TIER = "selections"


class _CandidateRef(BaseModel):
    """A compact candidate reference stored inside a selection body."""

    provider: str
    id: str
    url: str
    score: "float | None" = None


class SelectionBody(BaseModel):
    """The typed body of an illustration selection annotation (lacing body schema)."""

    model_config = {"extra": "forbid"}

    beat: str
    beat_index: int
    source: str  # "machine" | "director"
    selected: "_CandidateRef | None" = None
    candidates: list[_CandidateRef] = Field(default_factory=list)
    forced_duplicate: bool = False
    reason: "str | None" = None


def persist_sequence(
    result: Any,
    *,
    store: Any = None,
    actor: str = "agent:illustration-curate",
    activity: str = "infer",
    at_time: Any = None,
) -> Any:
    """Persist a :class:`~illustration.sequence.SequenceResult` as lacing annotations.

    One ``selections``-tier annotation per beat (machine choices), keyed on the
    ordinal beat timeline. Returns the store (a fresh ``lacing.MemoryStore`` when
    ``store`` is None). ``at_time`` (a ``lacing.RationalTime``) overrides the
    provenance timestamp — pass it for deterministic ordering in tests; defaults
    to wall-clock ``RationalTime.now()``.
    """
    store = _ensure_store(store)
    for bs in result.selection.selections:
        body = SelectionBody(
            beat=_beat_text(result, bs.beat_index),
            beat_index=bs.beat_index,
            source="machine",
            selected=_candidate_ref(bs.chosen),
            candidates=[_candidate_ref(bs.chosen)] if bs.chosen is not None else [],
            forced_duplicate=bool(getattr(bs, "forced_duplicate", False)),
        )
        _add_selection(
            store, bs.beat_index, body, actor=actor, activity=activity, at_time=at_time
        )
    return store


def record_override(
    store: Any,
    beat_index: int,
    chosen: "ImageResult | None",
    *,
    beat: "str | None" = None,
    actor: str = "user:director",
    reason: "str | None" = None,
    at_time: Any = None,
) -> Any:
    """Append a director override for ``beat_index`` (a new, superseding annotation).

    Never mutates the machine's annotation — the override is a fresh annotation on
    the same beat, with ``provenance.was_derived_from`` pointing at the most-recent
    prior selection (STAM-style append-only layering). Returns the new annotation.
    """
    prior = _latest_annotation(store, beat_index)
    derived = [prior.id] if prior is not None else []
    beat_text = (
        beat if beat is not None else (prior.body.get("beat", "") if prior else "")
    )
    body = SelectionBody(
        beat=beat_text,
        beat_index=beat_index,
        source="director",
        selected=_candidate_ref(chosen),
        candidates=[_candidate_ref(chosen)] if chosen is not None else [],
        reason=reason,
    )
    return _add_selection(
        store,
        beat_index,
        body,
        actor=actor,
        activity="derive",
        was_derived_from=derived,
        at_time=at_time,
    )


def resolve_selection(store: Any, beat_index: int) -> "dict | None":
    """The *active* selection body for a beat — the latest annotation wins.

    Resolves machine choice vs. director override by provenance timestamp, so a
    later override supersedes the machine's choice without deleting it.
    """
    ann = _latest_annotation(store, beat_index)
    return dict(ann.body) if ann is not None else None


def resolved_selections(store: Any) -> "dict[int, dict]":
    """The active selection body per beat index (resolved over all overrides)."""
    out: dict[int, dict] = {}
    for ann in store.by_tier(SELECTIONS_TIER):
        idx = int(ann.body.get("beat_index"))
        cur = out.get(idx)
        if cur is None or _gen_seconds(ann) >= cur[0]:
            out[idx] = (_gen_seconds(ann), dict(ann.body))
    return {idx: body for idx, (_, body) in out.items()}


def export_otio(store: Any, target: "str | None" = None) -> "bytes | None":
    """Export the annotation store to OpenTimelineIO (needs ``lacing[otio]``).

    Thin passthrough to lacing's OTIO adapter, so selections can flow into video
    tools. Returns the bytes when ``target`` is None, else writes the file.
    """
    import lacing.adapters.otio  # noqa: F401 - self-registers the "otio" adapter
    from lacing.adapters import dump

    return dump(store, target, format="otio")


# --- internals --------------------------------------------------------------

_REGISTERED = False


def _ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    from lacing import register_body_schema

    # register_body_schema overwrites idempotently; the _REGISTERED guard keeps
    # this a once-per-process call, and a real error (bad URI/type) surfaces.
    register_body_schema(SELECTION_SCHEMA_URI, SelectionBody)
    _REGISTERED = True


def _ensure_store(store: Any) -> Any:
    _ensure_registered()
    from lacing import MemoryStore, Tier

    if store is None:
        store = MemoryStore()
    if store.get_tier(SELECTIONS_TIER) is None:
        store.add_tier(Tier(SELECTIONS_TIER))
    return store


def _add_selection(
    store,
    beat_index,
    body: SelectionBody,
    *,
    actor,
    activity,
    was_derived_from=None,
    at_time=None,
):
    from uuid import uuid4

    from lacing import Annotation, NodeRef, Provenance, RationalTime, TimeInterval

    when = at_time if at_time is not None else RationalTime.now()
    interval = TimeInterval(
        RationalTime(beat_index, rate=1), RationalTime(beat_index + 1, rate=1)
    )
    ann = Annotation(
        id=uuid4(),
        tier=SELECTIONS_TIER,
        reference=NodeRef(scene_path=f"beat/{beat_index}", interval=interval),
        body=body.model_dump(),
        body_schema_uri=SELECTION_SCHEMA_URI,
        provenance=Provenance(
            was_generated_by=actor,
            was_attributed_to=actor,
            was_derived_from=list(was_derived_from or []),
            generated_at_time=when,
            activity=activity,
        ),
    )
    store.add(ann)
    return ann


def _latest_annotation(store, beat_index: int):
    # by_tier yields in append (insertion) order; tie-break a timestamp draw
    # toward the later-inserted annotation, so resolve_selection and
    # resolved_selections agree on "the latest override wins".
    anns = [
        a
        for a in store.by_tier(SELECTIONS_TIER)
        if int(a.body.get("beat_index", -1)) == beat_index
    ]
    if not anns:
        return None
    return max(enumerate(anns), key=lambda t: (_gen_seconds(t[1]), t[0]))[1]


def _gen_seconds(ann) -> float:
    return float(ann.provenance.generated_at_time.to_seconds())


def _candidate_ref(result: "ImageResult | None") -> "_CandidateRef | None":
    if result is None:
        return None
    return _CandidateRef(
        provider=result.provider, id=result.id, url=result.url, score=result.score
    )


def _beat_text(result: Any, beat_index: int) -> str:
    beats = getattr(result, "beats", None) or []
    return beats[beat_index] if 0 <= beat_index < len(beats) else ""
