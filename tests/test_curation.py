"""Tests for illustration.curation — the bounded CRAG loop (fully offline).

Every paid seam is injected (search_fn / scorer / describe / expander / refiner)
and CV is skipped (checks=[]), so the loop runs end-to-end with zero network and
zero API spend. ``ir`` (fuse_hits + select) is a real dependency, gated here.
"""

import pytest

pytest.importorskip("ir")

from illustration.curation import Budget, Grade, curate, score_grade
from illustration.schema import ImageResult


def _cands(n=3):
    return [
        ImageResult(provider="p", id=str(i), url=f"u{i}", width=900, height=600)
        for i in range(n)
    ]


def _rubric_json(value):
    return (
        f'{{"subject":{value},"action":{value},"setting":{value},'
        f'"mood":{value},"style":{value},"quality":{value},"rationale":"r"}}'
    )


# A loop config that touches no network / API: stub everything paid.
_OFFLINE = dict(
    expander=lambda beat: [],
    refiner=lambda beat, critique: "refined " + beat,
    checks=[],
    describe=lambda image, prompt: _rubric_json(0.9),
)


class TestScoreGrade:
    """The default grader is a pure function over (results, selection)."""

    class _Sel:
        def __init__(self, abstained, selected):
            self.abstained = abstained
            self.selected = selected

    def test_no_results_is_incorrect(self):
        assert score_grade([], self._Sel(False, [])) == Grade.INCORRECT

    def test_abstained_is_incorrect(self):
        assert score_grade(_cands(1), self._Sel(True, [])) == Grade.INCORRECT

    def test_single_selected_is_correct(self):
        assert score_grade(_cands(2), self._Sel(False, ["one"])) == Grade.CORRECT

    def test_multiple_selected_is_ambiguous(self):
        assert score_grade(_cands(3), self._Sel(False, ["a", "b"])) == Grade.AMBIGUOUS


class TestCurateHappyPaths:
    def test_correct_grade_captions_and_accepts(self):
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.9, 0.4, 0.2],  # one dominant -> CORRECT
            **_OFFLINE,
        )
        assert res.accepted is True
        assert res.grade == "correct"
        assert res.best.result.id == "0"
        assert res.best.caption is not None  # captioned via the stub describe
        assert res.spend["judge_calls"] == 0  # CORRECT path never judges
        assert len(res.trace) == 1

    def test_ambiguous_grade_judges_and_accepts(self):
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.90, 0.88, 0.86],  # close -> AMBIGUOUS
            **_OFFLINE,  # describe returns 0.9 rubric -> over accept_threshold
        )
        assert res.accepted is True
        assert res.grade == "ambiguous"
        assert res.best.rubric is not None
        assert res.best.rubric.overall == pytest.approx(0.9)
        assert res.spend["judge_calls"] >= 1


class TestCurateCorrectivePaths:
    def test_ambiguous_below_threshold_refines_then_exhausts(self):
        cands = _cands(3)
        seen_queries = []

        def search_fn(q, **kw):
            seen_queries.append(q)
            return cands

        res = curate(
            "a stormy harbour",
            budget=Budget(max_iter=2),
            search_fn=search_fn,
            scorer=lambda beat, rs: [0.90, 0.88, 0.86],
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined harbour",
            checks=[],
            describe=lambda image, prompt: _rubric_json(0.30),  # below 0.62
        )
        assert res.accepted is False
        assert res.best is not None
        assert res.best.rubric.overall == pytest.approx(0.30)  # best-so-far kept
        assert res.reason in {"no_progress", "max_iter"}
        # the refiner steered the second round's query
        assert "refined harbour" in seen_queries

    def test_incorrect_when_no_candidates_then_max_iter(self):
        res = curate(
            "a stormy harbour",
            budget=Budget(max_iter=2),
            search_fn=lambda q, **kw: [],  # empty recall -> INCORRECT every round
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined",
            checks=[],
        )
        assert res.accepted is False
        assert res.best is None
        # empty recall both rounds -> stops on no_progress (cheaper) or max_iter
        assert res.reason in {"no_progress", "max_iter"}
        assert res.spend["iterations"] >= 1

    def test_min_score_abstention_grades_incorrect(self):
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            budget=Budget(max_iter=1, min_score=99.0),  # nothing clears the floor
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.9, 0.4, 0.2],
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined",
            checks=[],
        )
        assert res.accepted is False
        assert res.trace[0].grade == "incorrect"


class TestBudgetEnforcement:
    def test_judge_call_cap_is_respected(self):
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            budget=Budget(max_iter=1, max_judge_calls=1, select_max_k=3),
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.90, 0.89, 0.88],  # all selected -> AMBIGUOUS
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined",
            checks=[],
            describe=lambda image, prompt: _rubric_json(0.10),  # never accepts
        )
        assert res.spend["judge_calls"] == 1  # capped despite >1 selected

    def test_cost_cap_halts_the_loop(self):
        # AMBIGUOUS + below-threshold rubric would keep refining forever; the cost
        # cap must STOP the run (not merely tally) — reason == 'budget_cost'.
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            budget=Budget(
                max_iter=5, max_cost=2.0,
                cost_estimator=lambda call_type, info: 1.0,
            ),
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.90, 0.88, 0.86],  # AMBIGUOUS
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined",
            checks=[],
            describe=lambda image, prompt: _rubric_json(0.30),  # never accepts
        )
        assert res.accepted is False
        assert res.reason == "budget_cost"
        assert res.spend["iterations"] < 5  # halted by cost, not by max_iter

    def test_caption_skipped_when_over_cost(self):
        # CORRECT auto-accepts, but the (paid) caption must be skipped once the
        # cost overlay is exhausted — proves the _over_cost gate actually fires.
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            budget=Budget(
                max_iter=3, max_cost=0.5,
                cost_estimator=lambda call_type, info: 1.0,  # search alone exceeds it
            ),
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.9, 0.4, 0.2],  # CORRECT
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined",
            checks=[],
            describe=lambda image, prompt: "should-not-be-called",
        )
        assert res.accepted is True and res.grade == "correct"
        assert res.spend["caption_calls"] == 0
        assert res.best.caption is None


class TestRerankAndFusion:
    def test_no_reranker_fallback_uses_positive_rank_scores(self, monkeypatch):
        # Force the no-scorer + no-deps fallback. With a single provider, fuse_hits
        # preserves raw (zero) scores; the fallback must synthesize POSITIVE
        # rank-descending scores so ir.select doesn't collapse the grade.
        monkeypatch.setattr("illustration.curation._rerank_available", lambda: False)
        cands = _cands(3)  # single provider "p"
        res = curate(
            "a stormy harbour",
            search_fn=lambda q, **kw: cands,
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined",
            checks=[],
            describe=lambda image, prompt: "a caption",
        )
        assert res.best is not None
        assert res.best.score is not None and res.best.score > 0.0  # not all-zero
        assert res.grade == "correct"  # dominant top distinguished, not degenerate

    def test_fuse_merges_providers_and_dedups_by_identity(self):
        from illustration.curation import _fuse

        hits = [
            ImageResult(provider="a", id="1", url="ua1"),
            ImageResult(provider="b", id="1", url="ub1"),    # same id, diff provider -> distinct
            ImageResult(provider="a", id="1", url="ua1dup"),  # dup (a,1) -> merged away
        ]
        keys = [(r.provider, r.id) for r in _fuse(hits)]
        assert ("a", "1") in keys and ("b", "1") in keys
        assert len(keys) == 2  # (a,1) deduped; (b,1) is a different artifact


class TestRecovery:
    def test_incorrect_then_recovers_and_accepts(self):
        # iter 1: empty recall -> INCORRECT -> refine; iter 2 (refined query):
        # a dominant candidate -> CORRECT -> accept. The full corrective arc.
        def search_fn(q, **kw):
            return [] if q == "a stormy harbour" else _cands(3)

        res = curate(
            "a stormy harbour",
            budget=Budget(max_iter=3),
            search_fn=search_fn,
            scorer=lambda beat, rs: [0.9, 0.4, 0.2],
            expander=lambda beat: [],
            refiner=lambda beat, critique: "refined harbour",
            checks=[],
            describe=lambda image, prompt: "a caption",
        )
        assert res.accepted is True
        assert res.grade == "correct"
        assert len(res.trace) >= 2
        assert res.trace[0].grade == "incorrect"  # recovered from a bad first round


class TestTrace:
    def test_trace_is_a_runlog(self):
        cands = _cands(3)
        res = curate(
            "a stormy harbour",
            search_fn=lambda q, **kw: cands,
            scorer=lambda beat, rs: [0.9, 0.4, 0.2],
            **_OFFLINE,
        )
        rec = res.trace[0]
        assert rec.iteration == 1
        assert rec.n_candidates == 3
        assert rec.grade == "correct"
        assert rec.action == "caption+accept"
        assert rec.queries  # the verbatim beat at minimum
