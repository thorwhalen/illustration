"""Tests for same-subject duplicate grouping.

The observed failure: a search for one person returned a colour painting, three
nineteenth-century engravings after it, and a re-scan of one engraving. Five
ids, five byte-streams, five rasters — one picture of one woman. A film used
four of them and looked like it had run out of pictures.

Measured on those exact files, the perceptual hash already in ``sequence`` found
**one** of the four; DINOv2 found all four, plus three portraits of the husband
and two near-identical genre paintings, while keeping the subject's *sister*
correctly separate. That gap is the reason this module exists, and
``test_phash_is_not_subject_level`` documents it rather than papering over it.

Most tests here inject a fake signature: the grouping, ordering, quality and
strategy logic is what needs pinning, and it must be testable without a model
download. The two model tiers are covered by their construction and by their
declared capability flags.

Run: ``PYTHONPATH="$PWD" python -m pytest tests/test_duplicates.py -q``
"""

from __future__ import annotations

import pytest

from illustration.duplicates import (
    DUPLICATE_STRATEGIES,
    DuplicateGroup,
    Signature,
    dedupe,
    default_signature,
    group_duplicates,
    phash_signature,
    quality_key,
)
from illustration.schema import ImageResult


def result(rid, *, w=800, h=600, license="cc0", author="A", subject=None):
    """An ImageResult carrying its intended subject in ``title``."""
    return ImageResult(
        provider="test", id=rid, url=f"http://x/{rid}.jpg",
        thumbnail_url=f"http://x/{rid}_t.jpg",
        width=w, height=h, license=license, author=author,
        title=subject or rid,
    )


#: Dimension of the stub subject space. Must be wide enough that two different
#: titles do not collide by hash.
_FAKE_DIM = 4096


def subject_signature(threshold: float = 0.86) -> Signature:
    """A stand-in that embeds each result's ``title`` as a one-hot subject.

    Two results with the same title are the same subject and nothing else is,
    which is precisely the judgement a real encoder is approximating.

    The index is derived from a **stable hash of the title**, not from the
    subjects present in the call. An earlier version indexed by call contents and
    was subtly wrong: ``select_sequence`` embeds one beat at a time, so two
    different subjects in different beats landed on the same one-hot, every
    candidate looked like a repeat, and the constraint relaxed. A real encoder is
    stable across calls; a stub that is not tests something else.
    """
    import hashlib

    import numpy as np

    def index_of(title: str) -> int:
        digest = hashlib.blake2b(title.encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") % _FAKE_DIM

    def embed(results):
        out = []
        for r in results:
            vec = np.zeros(_FAKE_DIM, dtype="float32")
            vec[index_of(r.title)] = 1.0
            out.append(vec)
        return out

    return Signature(name="fake", embed=embed, threshold=threshold)


ELIZA = [
    result("eliza-nypl", w=1920, h=2802, subject="eliza"),
    result("eliza-earl", w=1920, h=2632, subject="eliza"),
    result("eliza-nara", w=1920, h=2573, subject="eliza"),
    result("eliza-nypl2", w=1920, h=2516, subject="eliza"),
    result("angelica", w=1920, h=2322, subject="angelica"),
    result("philip", w=760, h=1000, subject="philip"),
]


class TestGrouping:
    def test_the_reported_failure_collapses_to_one_group(self):
        groups = group_duplicates(ELIZA, signature=subject_signature())
        assert len(groups) == 3
        biggest = max(groups, key=len)
        assert {m.id for m in biggest.members} == {
            "eliza-nypl", "eliza-earl", "eliza-nara", "eliza-nypl2"
        }

    def test_different_subjects_are_never_merged(self):
        """The hard negative: two period portraits of two different women."""
        groups = group_duplicates(ELIZA, signature=subject_signature())
        by_id = {m.id: g for g in groups for m in g.members}
        assert by_id["angelica"] is not by_id["eliza-earl"]

    def test_a_singleton_is_still_a_group(self):
        groups = group_duplicates([result("only")], signature=subject_signature())
        assert len(groups) == 1 and not groups[0].is_duplicate

    def test_empty_input(self):
        assert group_duplicates([], signature=subject_signature()) == []

    def test_groups_keep_first_appearance_order(self):
        ordered = [ELIZA[4], ELIZA[0], ELIZA[1], ELIZA[5]]  # angelica, eliza, eliza, philip
        groups = group_duplicates(ordered, signature=subject_signature())
        assert [g.members[0].title for g in groups] == ["angelica", "eliza", "philip"]

    def test_an_unembeddable_image_is_never_grouped(self):
        """A fetch failure must lose a duplicate, not merge two subjects."""
        import numpy as np

        def embed(results):
            return [None] * len(results)

        sig = Signature(name="broken", embed=embed, threshold=0.5)
        groups = group_duplicates(ELIZA, signature=sig)
        assert len(groups) == len(ELIZA)

    def test_single_linkage_chains_through_a_middle_image(self):
        """A colour original and a re-scan of an engraving after it can each be
        near the engraving while further from each other."""
        import numpy as np

        vectors = {
            "a": np.asarray([1.0, 0.0], dtype="float32"),
            "b": np.asarray([0.7071, 0.7071], dtype="float32"),
            "c": np.asarray([0.0, 1.0], dtype="float32"),
        }
        sig = Signature(
            name="chain",
            embed=lambda rs: [vectors[r.id] for r in rs],
            threshold=0.70,  # a~b and b~c, but a·c == 0
        )
        groups = group_duplicates(
            [result("a"), result("b"), result("c")], signature=sig
        )
        assert len(groups) == 1


class TestBestOfGroup:
    def test_the_largest_reproduction_wins(self):
        groups = group_duplicates(ELIZA, signature=subject_signature())
        biggest = max(groups, key=len)
        assert biggest.best.id == "eliza-nypl"  # 1920x2802, the tallest

    def test_an_unconditional_licence_breaks_a_size_tie(self):
        same = [
            result("bysa", w=100, h=100, license="by-sa"),
            result("cc0", w=100, h=100, license="cc0"),
        ]
        groups = group_duplicates(same, signature=subject_signature(threshold=0.0))
        assert groups[0].best.id == "cc0"

    def test_a_recorded_author_breaks_a_remaining_tie(self):
        same = [
            result("anon", w=100, h=100, license="cc0", author=""),
            result("named", w=100, h=100, license="cc0", author="Ralph Earl"),
        ]
        groups = group_duplicates(same, signature=subject_signature(threshold=0.0))
        assert groups[0].best.id == "named"

    def test_quality_key_is_a_seam(self):
        groups = group_duplicates(
            ELIZA, signature=subject_signature(), quality=lambda r: r.id
        )
        biggest = max(groups, key=len)
        assert biggest.best.id == "eliza-nypl2"  # last alphabetically


class TestStrategies:
    def test_best_is_the_default_and_gives_one_per_subject(self):
        kept = dedupe(ELIZA, signature=subject_signature())
        assert [r.id for r in kept] == ["eliza-nypl", "angelica", "philip"]

    def test_all_keeps_everything_but_grouped(self):
        kept = dedupe(ELIZA, signature=subject_signature(), strategy="all")
        assert len(kept) == len(ELIZA)

    def test_first_keeps_the_providers_own_pick(self):
        """`first` is the group's own member order, which is quality order."""
        kept = dedupe(ELIZA, signature=subject_signature(), strategy="first")
        assert len(kept) == 3

    def test_a_callable_strategy_is_accepted(self):
        kept = dedupe(
            ELIZA,
            signature=subject_signature(),
            strategy=lambda g: list(g.members[:2]),
        )
        assert len(kept) == 2 + 1 + 1

    def test_an_unknown_strategy_names_the_known_ones(self):
        with pytest.raises(ValueError, match="unknown duplicate strategy"):
            dedupe(ELIZA, signature=subject_signature(), strategy="nope")

    def test_order_of_first_appearance_is_preserved(self):
        ordered = [ELIZA[5], ELIZA[1], ELIZA[4]]  # philip, eliza, angelica
        kept = dedupe(ordered, signature=subject_signature())
        assert [r.title for r in kept] == ["philip", "eliza", "angelica"]

    def test_every_named_strategy_returns_results(self):
        group = DuplicateGroup(members=(ELIZA[0], ELIZA[1]))
        for name, reduce in DUPLICATE_STRATEGIES.items():
            kept = reduce(group)
            assert kept and all(isinstance(r, ImageResult) for r in kept), name


class TestSignatureCapability:
    def test_phash_declares_that_it_is_not_subject_level(self):
        """Documents the gap: it finds the same raster, not the same subject."""
        assert phash_signature().subject_level is False

    def test_phash_threshold_matches_the_sequence_hamming_default(self):
        from illustration.sequence import DFLT_PHASH_THRESHOLD

        assert phash_signature().threshold == pytest.approx(
            1.0 - 2.0 * DFLT_PHASH_THRESHOLD / 64
        )

    def test_default_signature_always_returns_something(self):
        assert isinstance(default_signature(), Signature)

    def test_threshold_can_be_overridden_per_call(self):
        loose = group_duplicates(
            ELIZA, signature=subject_signature(), threshold=0.0
        )
        assert len(loose) == 1  # everything is the same subject at threshold 0


class TestQualityKey:
    def test_missing_dimensions_do_not_raise(self):
        assert quality_key(ImageResult(provider="p", id="i", url="u")) == (0, 0, False)

    def test_area_dominates(self):
        big = quality_key(result("b", w=4000, h=3000, license="by-sa", author=""))
        small = quality_key(result("s", w=100, h=100, license="cc0", author="A"))
        assert big > small


# --------------------------------------------------------------------------- #
# Wikimedia category routing (a curated list beats a filename guess)
# --------------------------------------------------------------------------- #

class TestWikimediaCategoryQueries:
    """A Commons category is maintained by people who looked at the pictures.

    Free-text search is a guess at filename and description — which is how
    "Hamilton Grange" returns a branch library of that name instead of the
    house. Detected from MediaWiki's own namespace prefix so it survives the
    façade, the cache key and the CLI without a new parameter.
    """

    def source(self):
        from illustration.providers.wikimedia import WikimediaSource

        return WikimediaSource()

    def test_a_plain_query_uses_the_search_generator(self):
        params = self.source()._query_params("eliza hamilton", page=1, per_page=20)
        assert params["gsrsearch"] == "eliza hamilton"
        assert "gcmtitle" not in params

    def test_a_category_query_uses_the_categorymembers_generator(self):
        params = self.source()._query_params(
            "Category:Elizabeth Schuyler Hamilton", page=1, per_page=20
        )
        assert params["generator"] == "categorymembers"
        assert params["gcmtitle"] == "Category:Elizabeth Schuyler Hamilton"
        assert params["gcmtype"] == "file"
        assert "gsrsearch" not in params

    def test_the_prefix_is_case_insensitive_and_trimmed(self):
        params = self.source()._query_params(
            "category:  Trinity Church (Manhattan) ", page=1, per_page=5
        )
        assert params["gcmtitle"] == "Category:Trinity Church (Manhattan)"

    def test_the_page_size_is_carried_through(self):
        params = self.source()._query_params("Category:X", page=1, per_page=7)
        assert params["gcmlimit"] == 7

    def test_other_providers_are_untouched_by_the_new_hook(self):
        from illustration.providers.openverse import OpenverseSource

        params = OpenverseSource()._query_params("harbour", page=2, per_page=10)
        assert params["q"] == "harbour"


# --------------------------------------------------------------------------- #
# sequence-level: the same subject must not win two beats
# --------------------------------------------------------------------------- #

class TestSequenceUsesSubjects:
    """The cross-beat version of the reported failure.

    pHash lets four engravings of one sitter win four different beats, because
    to it they are four different rasters. A subject signature spends one beat
    on the subject and moves on.
    """

    def beats(self):
        # Every beat offers an Eliza engraving first and something else second.
        return [
            [result(f"eliza-{i}", w=1000 + i, h=1000, subject="eliza"),
             result(f"other-{i}", w=900, h=900, subject=f"other-{i}")]
            for i in range(3)
        ]

    def test_without_a_signature_the_same_subject_wins_every_beat(self):
        from illustration.sequence import select_sequence

        sel = select_sequence(
            self.beats(),
            relevance=lambda r: 1.0 if r.title == "eliza" else 0.0,
            embed=lambda rs: [None] * len(rs),
            hasher=lambda r: None,  # pHash unavailable -> no constraint at all
        )
        assert [s.chosen.title for s in sel.selections] == ["eliza"] * 3

    def test_with_a_signature_the_subject_is_used_once(self):
        from illustration.sequence import select_sequence

        sel = select_sequence(
            self.beats(),
            relevance=lambda r: 1.0 if r.title == "eliza" else 0.0,
            embed=lambda rs: [None] * len(rs),
            signature=subject_signature(),
        )
        titles = [s.chosen.title for s in sel.selections]
        assert titles.count("eliza") == 1, titles

    def test_a_beat_with_only_duplicates_is_flagged_not_dropped(self):
        from illustration.sequence import select_sequence

        only_eliza = [
            [result("a", subject="eliza")],
            [result("b", subject="eliza")],
        ]
        sel = select_sequence(
            only_eliza,
            embed=lambda rs: [None] * len(rs),
            signature=subject_signature(),
        )
        assert all(s.chosen is not None for s in sel.selections)
        assert sel.selections[1].forced_duplicate is True
