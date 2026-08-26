"""Tests for illustration.persistence — lacing standoff persistence (offline).

Needs the [persist] extra (lacing); gated with importorskip. Uses explicit
RationalTime timestamps so the machine-vs-override resolution is deterministic.
"""

import pytest

pytest.importorskip("lacing")

from lacing import RationalTime  # noqa: E402

from illustration.persistence import (  # noqa: E402
    _CandidateRef,
    persist_sequence,
    record_override,
    resolve_selection,
    resolved_selections,
)
from illustration.schema import RIGHTS_FIELDS, ImageResult  # noqa: E402
from illustration.sequence import BeatSelection, SequenceResult, SequenceSelection  # noqa: E402


def _result():
    return SequenceResult(
        beats=["dawn harbour", "dusk pier"],
        selection=SequenceSelection(
            selections=[
                BeatSelection(
                    beat_index=0,
                    chosen=ImageResult(provider="p", id="m0", url="u0", score=0.9),
                ),
                BeatSelection(
                    beat_index=1,
                    chosen=ImageResult(provider="p", id="m1", url="u1", score=0.8),
                ),
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
        store,
        0,
        ImageResult(provider="p", id="picked", url="up"),
        reason="better composition",
        at_time=RationalTime(2, 1),  # later -> wins
    )
    body = resolve_selection(store, 0)
    assert body["source"] == "director"
    assert body["selected"]["id"] == "picked"
    assert body["reason"] == "better composition"
    # beat 1 still resolves to its machine choice (override only touched beat 0)
    assert resolve_selection(store, 1)["selected"]["id"] == "m1"


def test_override_is_append_only_with_provenance_link():
    store = persist_sequence(_result(), at_time=RationalTime(1, 1))
    record_override(
        store,
        0,
        ImageResult(provider="p", id="picked", url="up"),
        at_time=RationalTime(2, 1),
    )
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


# --- the rights record must survive the persistence boundary (issue #14) ----


def _licensed_image(**overrides):
    """An ImageResult with every rights field populated."""
    fields = dict(
        provider="wikimedia",
        id="12345",
        url="https://upload.wikimedia.example/Stormy_Harbour.jpg",
        score=0.77,
        license="cc-by-sa-4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0",
        attribution="Alice / CC BY-SA 4.0, via Wikimedia Commons",
        source_page_url="https://commons.wikimedia.org/wiki/File:Stormy_Harbour.jpg",
        author="Alice",
        author_url="https://commons.wikimedia.org/wiki/User:Alice",
        cacheable=True,
    )
    fields.update(overrides)
    return ImageResult(**fields)


def _licensed_sequence():
    return SequenceResult(
        beats=["dawn harbour"],
        selection=SequenceSelection(
            selections=[BeatSelection(beat_index=0, chosen=_licensed_image())]
        ),
    )


#: The rights record, spelled out. Pinned as a **literal** rather than derived
#: from ``RIGHTS_FIELDS``, because a guard parameterised by the thing it guards
#: guards nothing: trimming ``"source_page_url"`` out of the SSOT tuple used to
#: leave the whole suite green while every subsequently persisted selection lost
#: its link to the licence page. With the pin, a trim (or an addition) is a
#: deliberate two-place edit and shows up in review.
EXPECTED_RIGHTS_FIELDS = {
    "license",
    "license_url",
    "attribution",
    "source_page_url",
    "author",
    "author_url",
    "cacheable",
}

#: Every field :class:`ImageResult` declares, pinned for the same reason from
#: the other side. ``RIGHTS_FIELDS`` cannot be *derived* from this model — no
#: structural property says which fields answer "may we ship this?" — so the
#: only way a rights field added upstream cannot silently fail to be persisted
#: is to make **any** addition to the contract model a decision someone records
#: here, classifying it as rights-bearing or not.
EXPECTED_IMAGE_RESULT_FIELDS = {
    # identity / payload
    "provider",
    "id",
    "url",
    "thumbnail_url",
    "width",
    "height",
    "title",
    "description",
    "tags",
    "avg_color",
    # rights record (must equal EXPECTED_RIGHTS_FIELDS)
    "license",
    "license_url",
    "attribution",
    "source_page_url",
    "author",
    "author_url",
    "cacheable",
    # provenance / forward-compatibility
    "query",
    "score",
    "raw",
}


def test_rights_fields_tuple_matches_its_literal_pin():
    """Trimming the SSOT tuple must be a deliberate edit, not a silent loss.

    ``_candidate_ref`` copies exactly ``RIGHTS_FIELDS``, so a field removed from
    the tuple simply stops being persisted — with every other test in this file
    (which all iterate the same tuple) still green.
    """
    assert set(RIGHTS_FIELDS) == EXPECTED_RIGHTS_FIELDS, (
        "RIGHTS_FIELDS changed. If that is intended, update "
        "EXPECTED_RIGHTS_FIELDS here too — and check whether the new shape "
        "needs a lacing migration for annot://schema/illustration-selection/v1."
    )
    assert len(RIGHTS_FIELDS) == len(set(RIGHTS_FIELDS))  # no duplicates


def test_image_result_gained_no_unclassified_field():
    """A field added to the contract model must be classified, not ignored.

    ``RIGHTS_FIELDS`` is hand-written twenty lines above ``ImageResult`` and is
    easy to miss; a new rights-bearing field left out of it is never copied by
    ``_candidate_ref``, so every persisted selection loses it. Nothing about a
    pydantic field says whether it answers "may we ship this, and whom must we
    credit?" — so the classification is made here, by a human, once per field.
    """
    actual = set(ImageResult.model_fields)
    added = actual - EXPECTED_IMAGE_RESULT_FIELDS
    removed = EXPECTED_IMAGE_RESULT_FIELDS - actual
    assert not added, (
        f"ImageResult gained {sorted(added)}. Decide, for each: does it answer "
        '"may we ship this, and whom must we credit?" If yes, add it to '
        "illustration.schema.RIGHTS_FIELDS *and* persistence._CandidateRef "
        "*and* EXPECTED_RIGHTS_FIELDS. Either way, record it in "
        "EXPECTED_IMAGE_RESULT_FIELDS."
    )
    assert not removed, (
        f"ImageResult lost {sorted(removed)} — a contract removal. Update the "
        "pin, and if a rights field went, migrate stored selection bodies."
    )


def test_every_rights_field_exists_on_image_result():
    """The tuple names fields that are really there — ``getattr`` in
    ``_candidate_ref`` would otherwise raise at persist time, at runtime.
    """
    missing = [f for f in RIGHTS_FIELDS if f not in ImageResult.model_fields]
    assert not missing, f"RIGHTS_FIELDS names non-existent ImageResult field(s): {missing}"


def test_candidate_ref_declares_every_rights_field():
    """A field in the rights record cannot silently fail to reach storage.

    The projection in ``_candidate_ref`` iterates ``RIGHTS_FIELDS`` and splats
    the result into ``_CandidateRef``, which does **not** set
    ``extra="forbid"`` (deliberately — that is what lets an old build read a
    newer body). So an undeclared key is *ignored*, i.e. lost silently, rather
    than raising. This is what makes that impossible.
    """
    missing = [f for f in RIGHTS_FIELDS if f not in _CandidateRef.model_fields]
    assert not missing, f"_CandidateRef drops rights field(s): {missing}"



def test_persisted_selection_carries_the_whole_rights_record():
    store = persist_sequence(_licensed_sequence(), at_time=RationalTime(1, 1))
    selected = resolve_selection(store, 0)["selected"]
    source = _licensed_image()
    for field in RIGHTS_FIELDS:
        assert selected[field] == getattr(source, field), field
    # and the identity half is unchanged
    assert (selected["provider"], selected["id"], selected["score"]) == (
        "wikimedia",
        "12345",
        0.77,
    )


def test_director_override_carries_the_rights_record_too():
    store = persist_sequence(_licensed_sequence(), at_time=RationalTime(1, 1))
    picked = _licensed_image(
        provider="pixabay",
        id="555",
        license="Pixabay License",
        attribution="Image by janedoe on Pixabay",
        author="janedoe",
    )
    record_override(store, 0, picked, at_time=RationalTime(2, 1))
    selected = resolve_selection(store, 0)["selected"]
    assert selected["license"] == "Pixabay License"
    assert selected["attribution"] == "Image by janedoe on Pixabay"
    assert selected["author"] == "janedoe"


def test_stored_candidates_list_carries_rights_too():
    store = persist_sequence(_licensed_sequence(), at_time=RationalTime(1, 1))
    (candidate,) = resolve_selection(store, 0)["candidates"]
    assert candidate["attribution"] == "Alice / CC BY-SA 4.0, via Wikimedia Commons"


def test_rights_fields_are_optional_so_a_pre_rights_body_still_validates():
    """The addition is additive: no lacing migration is owed.

    An annotation written before the rights fields existed has a body whose
    ``selected`` carries only the four identity keys; it must still validate
    against ``annot://schema/illustration-selection/v1``.
    """
    from illustration.persistence import SelectionBody

    legacy = {
        "beat": "dawn harbour",
        "beat_index": 0,
        "source": "machine",
        "selected": {"provider": "p", "id": "m0", "url": "u0", "score": 0.9},
        "candidates": [],
        "forced_duplicate": False,
        "reason": None,
    }
    body = SelectionBody.model_validate(legacy)
    # "not recorded" is distinguishable from "recorded as not cacheable"
    assert body.selected.cacheable is None
    assert body.selected.license is None


def test_unlicensed_result_records_absence_rather_than_inventing_a_licence():
    result = SequenceResult(
        beats=["b"],
        selection=SequenceSelection(
            selections=[
                BeatSelection(
                    beat_index=0, chosen=ImageResult(provider="p", id="x", url="u")
                )
            ]
        ),
    )
    store = persist_sequence(result, at_time=RationalTime(1, 1))
    selected = resolve_selection(store, 0)["selected"]
    assert selected["license"] is None
    assert (
        selected["cacheable"] is False
    )  # ImageResult's own default, carried faithfully
