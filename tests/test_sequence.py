"""Tests for illustration.sequence — cross-shot selection (fully offline).

The embed / hasher / relevance seams are injected with canned values so the
selection math is exercised deterministically with no network and no model.
The pHash + hamming tests need Pillow/NumPy (importorskip), like the rerank tests.
"""

import pytest

from illustration.schema import ImageResult
from illustration.sequence import (
    curate_sequence,
    hamming_distance,
    select_sequence,
)


def _img(id, score=None):
    return ImageResult(provider="p", id=id, url=f"u{id}", score=score)


_NO_EMBED = lambda rs: [None] * len(list(rs))  # noqa: E731
_NO_HASH = lambda r: None  # noqa: E731


class TestRelevanceOnly:
    def test_picks_highest_score_per_beat(self):
        beats = [
            [_img("a", 0.9), _img("b", 0.3)],
            [_img("c", 0.2), _img("d", 0.8)],
        ]
        sel = select_sequence(beats, embed=_NO_EMBED, hasher=_NO_HASH)
        assert [bs.chosen.id for bs in sel.selections] == ["a", "d"]
        assert all(not bs.forced_duplicate for bs in sel.selections)

    def test_empty_beat_yields_none_and_note(self):
        sel = select_sequence([[], [_img("a", 0.5)]], embed=_NO_EMBED, hasher=_NO_HASH)
        assert sel.selections[0].chosen is None
        assert sel.selections[1].chosen.id == "a"
        assert any("no candidates" in n for n in sel.notes)

    def test_shortlist_seam_restricts_candidates(self):
        beats = [[_img("a", 0.1), _img("b", 0.9)]]
        # shortlist keeps only the first candidate -> "a" wins despite lower score
        sel = select_sequence(
            beats, embed=_NO_EMBED, hasher=_NO_HASH, shortlist=lambda cs: list(cs)[:1]
        )
        assert sel.selections[0].chosen.id == "a"


class TestCoherenceAndDiversity:
    @pytest.fixture(autouse=True)
    def _need_numpy(self):
        # coherence/redundancy go through _cosine, which uses NumPy (a
        # [curate]/[rerank]-extra dep, absent in the base/CI install).
        pytest.importorskip("numpy")

    def _beats(self):
        # beat0 fixes the previous embedding to [1,0]; beat1 chooses between a
        # coherent+redundant candidate (same embedding) and an orthogonal one.
        return [
            [_img("anchor", 0.5)],
            [_img("same", 0.5), _img("ortho", 0.5)],
        ]

    _EMB = {"anchor": [1.0, 0.0], "same": [1.0, 0.0], "ortho": [0.0, 1.0]}

    def test_coherence_reward_picks_similar_when_redundancy_off(self):
        sel = select_sequence(
            self._beats(), embed=lambda rs: [self._EMB[r.id] for r in rs],
            hasher=_NO_HASH, alpha=0.3, beta=0.0,  # coherence on, redundancy off
        )
        assert sel.selections[1].chosen.id == "same"
        assert sel.selections[1].coherence == pytest.approx(1.0)

    def test_redundancy_penalty_picks_diverse_when_coherence_off(self):
        sel = select_sequence(
            self._beats(), embed=lambda rs: [self._EMB[r.id] for r in rs],
            hasher=_NO_HASH, alpha=0.0, beta=0.5,  # coherence off, redundancy on
        )
        assert sel.selections[1].chosen.id == "ortho"
        assert sel.selections[1].redundancy == pytest.approx(0.0)

    def test_combined_objective_value(self):
        # both weights on (the shipped defaults): same -> 0.5+0.3-0.5=0.3,
        # ortho -> 0.5 -> ortho wins; objective = 0.5 (beat0) + 0.5 (beat1) = 1.0
        sel = select_sequence(
            self._beats(), embed=lambda rs: [self._EMB[r.id] for r in rs],
            hasher=_NO_HASH, alpha=0.3, beta=0.5,
        )
        assert sel.selections[1].chosen.id == "ortho"
        assert sel.objective == pytest.approx(1.0)


class TestDefaultSeams:
    def test_default_embed_degrades_gracefully_without_rerank(self, monkeypatch):
        # the real _default_embed path: if reranking.embed_images raises (no torch),
        # coherence/redundancy fall back to 0 and selection is pure relevance.
        import illustration.reranking as rr

        def boom(results):
            raise RuntimeError("no torch")

        monkeypatch.setattr(rr, "embed_images", boom)
        beats = [[_img("a", 0.5)], [_img("b", 0.9), _img("c", 0.1)]]
        sel = select_sequence(beats, hasher=_NO_HASH)  # embed seam left at default
        assert sel.selections[1].chosen.id == "b"  # highest relevance
        assert all(bs.coherence == 0.0 and bs.redundancy == 0.0 for bs in sel.selections)

    def test_make_phash_hasher_uses_injected_fetch(self):
        np = pytest.importorskip("numpy")
        Image = pytest.importorskip("PIL.Image")
        from illustration.sequence import make_phash_hasher, phash

        img = Image.fromarray(np.random.RandomState(5).randint(0, 256, (64, 64, 3), dtype="uint8"))
        assert make_phash_hasher(fetch=lambda url: img)(_img("x")) == phash(img)
        assert make_phash_hasher(fetch=lambda url: None)(_img("x")) is None


class TestPhashDedup:
    def test_near_duplicate_of_prior_beat_is_excluded(self):
        beats = [
            [_img("a", 0.5)],
            [_img("dup", 0.9), _img("fresh", 0.1)],  # dup near-duplicates "a"
        ]
        hashes = {"a": 0b100, "dup": 0b100, "fresh": 0b111000}  # dup == a; fresh far
        sel = select_sequence(
            beats, embed=_NO_EMBED, hasher=lambda r: hashes[r.id], phash_threshold=2
        )
        # "dup" excluded by the hard constraint -> "fresh" chosen despite lower score
        assert sel.selections[1].chosen.id == "fresh"
        assert sel.selections[1].forced_duplicate is False

    def test_all_near_duplicates_relaxes_and_flags(self):
        beats = [
            [_img("a", 0.5)],
            [_img("dup1", 0.9), _img("dup2", 0.4)],  # both near-duplicate "a"
        ]
        hashes = {"a": 0b100, "dup1": 0b100, "dup2": 0b100}
        sel = select_sequence(
            beats, embed=_NO_EMBED, hasher=lambda r: hashes[r.id], phash_threshold=2
        )
        assert sel.selections[1].forced_duplicate is True
        assert sel.selections[1].chosen.id == "dup1"  # best by objective
        assert any("near-duplicate" in n for n in sel.notes)


class TestCurateSequence:
    def test_orchestrates_per_beat_pool_then_selects(self):
        pools = {
            "dawn": [_img("d1", 0.9), _img("d2", 0.2)],
            "dusk": [_img("k1", 0.3), _img("k2", 0.8)],
        }
        result = curate_sequence(
            ["dawn", "dusk"],
            per_beat=lambda b: pools[b],
            embed=_NO_EMBED, hasher=_NO_HASH,
        )
        assert result.beats == ["dawn", "dusk"]
        assert [bs.chosen.id for bs in result.selection.selections] == ["d1", "k2"]
        assert result.selection.chosen[0].id == "d1"


class TestPhashPrimitive:
    def test_phash_is_deterministic(self):
        pytest.importorskip("numpy")  # phash uses a NumPy DCT internally
        Image = pytest.importorskip("PIL.Image")
        from illustration.sequence import phash

        flat = Image.new("RGB", (64, 64), (128, 128, 128))
        assert phash(flat) == phash(flat)
        assert hamming_distance(phash(flat), phash(flat)) == 0

    def test_dct_concentrates_low_frequency_energy(self):
        # Pins the DCT-II orientation: a smooth gradient must put almost all of
        # its energy in the low-frequency top-left block. A transposed basis
        # (the bug this guards) scatters it (~0.57) and breaks discrimination.
        np = pytest.importorskip("numpy")
        from illustration.sequence import _dct2

        grad = np.tile(np.linspace(0, 255, 32), (32, 1))
        coefs = np.abs(_dct2(grad))
        assert coefs[:8, :8].sum() / coefs.sum() > 0.9

    def test_phash_discriminates_distinct_images(self):
        # The behavioral guarantee the near-duplicate constraint depends on:
        # two distinct images must be well ABOVE the dedup threshold (the
        # transposed-DCT bug collapsed this to ~1.5, flagging everything a dup).
        np = pytest.importorskip("numpy")
        Image = pytest.importorskip("PIL.Image")
        from illustration.sequence import DFLT_PHASH_THRESHOLD, phash

        a = Image.fromarray(np.random.RandomState(2).randint(0, 256, (96, 96, 3), dtype="uint8"))
        b = Image.fromarray(np.random.RandomState(3).randint(0, 256, (96, 96, 3), dtype="uint8"))
        assert hamming_distance(phash(a), phash(b)) > DFLT_PHASH_THRESHOLD

    def test_hamming_distance(self):
        assert hamming_distance(0b1010, 0b1010) == 0
        assert hamming_distance(0b1010, 0b0000) == 2
