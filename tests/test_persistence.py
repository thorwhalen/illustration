"""Tests for illustration.persistence — lacing standoff persistence (offline).

Needs the [persist] extra (lacing); gated with importorskip. Uses explicit
RationalTime timestamps so the machine-vs-override resolution is deterministic.
"""

import pytest

pytest.importorskip("lacing")

from lacing import RationalTime  # noqa: E402

from illustration.persistence import (  # noqa: E402
    persist_sequence,
    record_override,
    resolve_selection,
    resolved_selections,
)
from illustration.schema import ImageResult  # noqa: E402
from illustration.sequence import BeatSelection, SequenceResult, SequenceSelection  # noqa: E402


def _result():
    return SequenceResult(
        beats=["dawn harbour", "dusk pier"],
        selection=SequenceSelection(
            selections=[
                BeatSelection(beat_index=0, chosen=ImageResult(provider="p", id="m0", url="u0", score=0.9)),
                BeatSelection(beat_index=1, chosen=ImageResult(provider="p", id="m1", url="u1", score=0.8)),
            ]
        ),
    )


def test_persist_then_resolve_machine_choice():
    store = persist_sequence(_result(), at_time=RationalTime(1, 1))
    body = resolve_selection(store, 0)
    assert body is not None
    assert body["source"] == "machine"
    assert body["selected"]["id"] == "m0"
    assert body["beat"] == "dawn harbour"


def test_director_override_supersedes_machine():
    store = persist_sequence(_result(), at_time=RationalTime(1, 1))
    record_override(
        store, 0, ImageResult(provider="p", id="picked", url="up"),
        reason="better composition", at_time=RationalTime(2, 1),  # later -> wins
    )
    body = resolve_selection(store, 0)
    assert body["source"] == "director"
    assert body["selected"]["id"] == "picked"
    assert body["reason"] == "better composition"
    # beat 1 still resolves to its machine choice (override only touched beat 0)
    assert resolve_selection(store, 1)["selected"]["id"] == "m1"


def test_override_is_append_only_with_provenance_link():
    store = persist_sequence(_result(), at_time=RationalTime(1, 1))
    record_override(store, 0, ImageResult(provider="p", id="picked", url="up"), at_time=RationalTime(2, 1))
    anns = [a for a in store.by_tier("selections") if a.body.get("beat_index") == 0]
    assert len(anns) == 2  # machine choice NOT overwritten — both annotations coexist
    director = next(a for a in anns if a.body["source"] == "director")
    machine = next(a for a in anns if a.body["source"] == "machine")
    assert director.provenance.was_derived_from == [machine.id]  # STAM-style lineage
    assert director.provenance.activity == "derive"


def test_resolved_selections_maps_every_beat():
    store = persist_sequence(_result(), at_time=RationalTime(1, 1))
    resolved = resolved_selections(store)
    assert set(resolved) == {0, 1}
    assert resolved[0]["selected"]["id"] == "m0"
    assert resolved[1]["selected"]["id"] == "m1"


def test_export_otio_roundtrips():
    # export_otio must register the 'otio' adapter before dumping (the lacing
    # adapter registry is import-side-effect driven). Gated on the [otio] extra.
    pytest.importorskip("opentimelineio")
    from illustration.persistence import export_otio

    store = persist_sequence(_result(), at_time=RationalTime(1, 1))
    data = export_otio(store)
    assert isinstance(data, (bytes, bytearray)) and len(data) > 0
