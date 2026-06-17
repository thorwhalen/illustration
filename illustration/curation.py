"""The bounded corrective-retrieval (CRAG) loop — Layer 2's heart (R2 §1).

Turns a high-recall provider search into a single vetted candidate for one
narration beat, self-correcting across a *hard-bounded* number of rounds. The
shape is CRAG [Yan et al. 2024]: retrieve → grade → conditionally re-query —
wrapped in a controller whose stop conditions are enforced **in code, not
prompts**. That distinction is the whole point: the cautionary tale R2 cites is a
multi-agent loop that ran 11 days and cost $47k because it had cost *alerts* but
no cost *enforcement*. Here, :class:`Budget` caps (max iterations, per-call-type
ceilings, accept threshold, optional cost ceiling) are checked before every paid
call.

The pipeline per iteration::

    expand → search (fan-out) → ir.fuse_hits (provider merge/dedup, rank-based)
           → prefilter (classical CV) → rerank (SigLIP) → ir.select
           → grade {Correct | Ambiguous | Incorrect}
           → Correct: caption + accept · Ambiguous: VLM judge · Incorrect: refine

Cost discipline (R2, in impact order): the classical-CV prefilter gates before
any VLM token is spent; *Correct* uses a cheap caption and *Ambiguous* escalates
to the rubric judge only when the cheap signal is unsure; everything is bounded.

Every expensive seam is injectable — ``search_fn``, ``expander``/``refiner``,
``scorer`` (SigLIP), ``describe`` (the VLM), ``grader``, ``checks`` — so the loop
runs end-to-end **offline** with stubs and never spends on a paid API in a test.

>>> # offline: stub search + scorer + a generous-enough budget -> one round
>>> from illustration.schema import ImageResult
>>> cands = [ImageResult(provider="p", id=str(i), url=f"u{i}", width=900, height=600)
...          for i in range(3)]
>>> res = curate(
...     "a stormy harbour at dusk",
...     expander=lambda beat: [],                       # no expansion
...     search_fn=lambda q, **kw: cands,                # canned recall
...     checks=[],                                      # skip CV (no fetch)
...     scorer=lambda beat, rs: [0.9, 0.4, 0.2],        # canned relevance
...     describe=lambda image, prompt: "a harbour",     # canned VLM (no API)
... )
>>> res.accepted, res.best.result.id, res.grade
(True, '0', 'correct')
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence

from pydantic import BaseModel, Field

from illustration.config import DFLT_SOURCES
from illustration.expansion import Expander, Refiner, expand_query, refine_query
from illustration.inspection import (
    Check,
    Describe,
    InspectReport,
    RubricScore,
    inspect_candidate,
    prefilter,
)
from illustration.schema import ImageResult, to_search_hit

__all__ = [
    "curate",
    "Grade",
    "Budget",
    "Candidate",
    "IterationRecord",
    "CurationResult",
    "score_grade",
    "Grader",
    "DFLT_CURATE_N",
]

#: Default candidates requested *per source* for the recall stage.
DFLT_CURATE_N = 12


class Grade(str, Enum):
    """CRAG's three-way retrieval grade (R2 §1)."""

    CORRECT = "correct"      # a dominant relevant candidate -> caption + accept
    AMBIGUOUS = "ambiguous"  # several comparable candidates -> escalate to VLM judge
    INCORRECT = "incorrect"  # nothing sufficient -> refine the query and retry


#: A grader maps (reranked results, ir.Selection) -> a :class:`Grade`.
Grader = Callable[[Sequence[ImageResult], Any], Grade]


@dataclass(frozen=True)
class Budget:
    """Hard loop bounds — the safety net, enforced in controller code (R2).

    Counts and iterations are the deterministic, provider-independent caps. The
    optional ``cost_estimator`` / ``max_cost`` overlay lets a caller add a money
    ceiling on top; with no estimator the call/iteration caps alone bound spend.
    """

    max_iter: int = 3
    #: Cap on individual ``(query, source)`` search requests across the whole run.
    max_search_calls: int = 8
    max_caption_calls: int = 12
    max_judge_calls: int = 8
    #: Rubric ``overall`` (0-1) at/above which a judged candidate is accepted.
    accept_threshold: float = 0.62
    #: Optional absolute relevance floor below which a *Correct*-graded dominant
    #: candidate is escalated to the VLM judge instead of auto-accepted. ``None``
    #: (default) keeps the cheap fast-path; set it (on the reranker's score scale)
    #: when a dominant-but-weak top must still be rubric-verified.
    correct_min_score: "float | None" = None
    #: ``ir.select`` tuning for the grade (conservative selector).
    select_max_k: int = 3
    select_rel: float = 0.9
    #: Optional absolute relevance floor for ``ir.select`` abstention. ``None`` =
    #: relative-only (the loop's quality bar lives in the rubric, which is 0-1).
    min_score: "float | None" = None
    #: Optional money ceiling overlay. The count/iteration caps above are the
    #: strict hard bound; ``max_cost`` is a *soft* ceiling — the run halts once
    #: accrued ``est_cost`` reaches it, so the one call already decided upon may
    #: push the total slightly past ``max_cost`` (effective bound ≈ ``max_cost`` +
    #: one call's estimate).
    max_cost: "float | None" = None
    #: ``(call_type, info) -> cost`` estimate; ``call_type`` in
    #: {"search", "caption", "judge"}.
    cost_estimator: "Callable[[str, dict], float] | None" = None


@dataclass
class _Spend:
    """Mutable run accounting (the basis for every hard stop)."""

    iterations: int = 0
    search_calls: int = 0
    caption_calls: int = 0
    judge_calls: int = 0
    est_cost: float = 0.0

    def as_dict(self) -> dict:
        return {
            "iterations": self.iterations,
            "search_calls": self.search_calls,
            "caption_calls": self.caption_calls,
            "judge_calls": self.judge_calls,
            "est_cost": round(self.est_cost, 6),
        }


class Candidate(BaseModel):
    """One scored (and optionally inspected) candidate."""

    result: ImageResult
    score: "float | None" = None
    caption: "str | None" = None
    rubric: "RubricScore | None" = None
    rationale: "str | None" = None

    @property
    def quality(self) -> float:
        """A 0-1 comparable quality: the rubric overall if judged, else 0."""
        return self.rubric.overall if self.rubric is not None else 0.0


class IterationRecord(BaseModel):
    """One iteration of the loop — the run-log R2 requires for observability."""

    iteration: int
    queries: list[str]
    n_candidates: int
    n_passed: int
    grade: str
    action: str
    best_score: "float | None" = None
    search_calls: int = 0
    caption_calls: int = 0
    judge_calls: int = 0
    notes: str = ""


class CurationResult(BaseModel):
    """The outcome of curating one beat."""

    beat: str
    best: "Candidate | None"
    accepted: bool
    grade: str
    reason: str
    candidates: list[Candidate] = Field(default_factory=list)
    trace: list[IterationRecord] = Field(default_factory=list)
    spend: dict = Field(default_factory=dict)


def score_grade(results: "Sequence[ImageResult]", selection: Any) -> Grade:
    """The default, model-free grader — scale-robust via ``ir.select`` structure.

    Maps the conservative selection's *shape* (not an absolute score) onto CRAG's
    grade: nothing/abstained → Incorrect; a single dominant pick → Correct;
    several comparable picks → Ambiguous. Because it reads relative structure, it
    works regardless of the reranker's score magnitude — the absolute quality bar
    lives in the rubric (0-1), applied only on the Ambiguous path.
    """
    if not results or getattr(selection, "abstained", False):
        return Grade.INCORRECT
    if len(getattr(selection, "selected", [])) <= 1:
        return Grade.CORRECT
    return Grade.AMBIGUOUS


def curate(
    beat: str,
    *,
    sources: "str | list[str] | None" = None,
    n: int = DFLT_CURATE_N,
    budget: "Budget | None" = None,
    expander: "Expander | None" = None,
    refiner: "Refiner | None" = None,
    grader: "Grader | None" = None,
    describe: "Describe | None" = None,
    scorer: "Callable | None" = None,
    checks: "Sequence[Check] | None" = None,
    model: "str | None" = None,
    search_fn: "Callable | None" = None,
    fetch: "Callable | None" = None,
) -> CurationResult:
    """Curate the single best image for a narration ``beat`` via the CRAG loop.

    Args:
        beat: The narration beat / scene description to illustrate.
        sources: Source name(s) to search, or ``None`` for the default set.
        n: Candidates requested per source per query (recall width).
        budget: Hard loop bounds (defaults to :class:`Budget`).
        expander / refiner: Query generation / refinement seams (default: ``aix``).
        grader: ``(results, selection) -> Grade`` (default :func:`score_grade`).
        describe: VLM ``(image, prompt) -> text`` seam (default: ``aix``).
        scorer: SigLIP-style ``(beat, results) -> scores`` reranker. ``None`` uses
            the local SigLIP scorer when its deps are present, else falls back to
            the rank-fused order.
        checks: Classical-CV pre-filter checks (default: dependency-aware set).
        model: LLM model id passed to the default expander / refiner / describe.
        search_fn: ``(query, *, source, n, ...) -> [ImageResult]`` (default:
            :func:`illustration.search`). Inject a stub to test offline.
        fetch: Image fetch override for the pre-filters (test double).

    Returns:
        A :class:`CurationResult` — the accepted (or best-so-far) candidate, the
        full candidate set, the per-iteration trace, and the spend accounting.
    """
    budget = budget or Budget()
    grader = grader or score_grade
    search = search_fn if search_fn is not None else _default_search
    source_list = _resolve_sources(sources)

    spend = _Spend()
    trace: list[IterationRecord] = []
    pool: dict[tuple, Candidate] = {}  # (provider, id) -> best-known Candidate

    queries = expand_query(beat, expander=expander, model=model)
    best_judged: "Candidate | None" = None
    fallback_best: "Candidate | None" = None
    prev_keyset: "frozenset | None" = None
    stop_reason: "str | None" = None

    while True:
        # --- termination, checked BEFORE the next (paid) search round (R2 T1/T2) ---
        if spend.iterations >= budget.max_iter:
            stop_reason = "max_iter"
            break
        if budget.max_cost is not None and spend.est_cost >= budget.max_cost:
            stop_reason = "budget_cost"
            break
        spend.iterations += 1
        searched_queries = list(queries)  # the queries this round actually searched

        # --- R2: search -> fuse -> prefilter -> rerank -> select -> grade ---
        results = _run_search(queries, source_list, n, search, spend, budget)
        candidates = _fuse(results)
        pf = prefilter(candidates, checks=checks, fetch=fetch)
        scored = _rerank(beat, pf.passed, scorer)
        _absorb(pool, scored)
        selection = _select(scored, budget)
        grade = grader(scored, selection)

        # Optional absolute floor: a dominant-but-weak top is escalated to the
        # rubric judge rather than auto-accepted on the cheap Correct path.
        if grade == Grade.CORRECT and budget.correct_min_score is not None:
            top_score = scored[0].score if scored else None
            if top_score is None or top_score < budget.correct_min_score:
                grade = Grade.AMBIGUOUS

        iter_caption_calls = iter_judge_calls = 0
        action = ""
        notes = ""
        best_score = scored[0].score if scored else None

        if grade == Grade.CORRECT:
            top = scored[0]
            cand = pool[(top.provider, top.id)]
            cand.score = top.score
            if _can_caption(spend, budget):
                _charge(spend, budget, "caption", {"id": top.id})
                spend.caption_calls += 1
                iter_caption_calls = 1
                report = inspect_candidate(beat, top, mode="caption", describe=describe, model=model)
                cand.caption = report.caption
            action = "caption+accept"
            trace.append(_record(spend.iterations, searched_queries, candidates, pf, grade, action,
                                  best_score, 0, iter_caption_calls, 0, notes))
            return _finish(beat, cand, pool, trace, spend, accepted=True,
                           grade=grade, reason="correct")

        if grade == Grade.AMBIGUOUS:
            judged = _judge_selection(beat, scored, selection, pool, describe, model, spend, budget)
            iter_judge_calls = len(judged)
            for cand in judged:
                if best_judged is None or cand.quality > best_judged.quality:
                    best_judged = cand
            if best_judged is not None and best_judged.quality >= budget.accept_threshold:
                action = "judge+accept"
                trace.append(_record(spend.iterations, searched_queries, candidates, pf, grade, action,
                                     best_judged.quality, 0, 0, iter_judge_calls, notes))
                return _finish(beat, best_judged, pool, trace, spend, accepted=True,
                               grade=grade, reason="accept_threshold")
            action = "judge+refine"
            critique = _critique_from_judgements(judged, budget)
            queries = [refine_query(beat, critique, refiner=refiner, model=model)]
            notes = critique

        else:  # INCORRECT
            action = "refine"
            if scored and fallback_best is None:
                fallback_best = pool[(scored[0].provider, scored[0].id)]
            critique = (
                "no candidates survived pre-filtering"
                if not pf.passed
                else "no sufficiently relevant candidate"
            )
            queries = [refine_query(beat, critique, refiner=refiner, model=model)]
            notes = critique

        trace.append(_record(spend.iterations, searched_queries, candidates, pf, grade, action,
                             best_score, 0, iter_caption_calls, iter_judge_calls, notes))

        # --- no-progress stop (R2 T4): same candidate set as last round ---
        keyset = frozenset((r.provider, r.id) for r in scored)
        if prev_keyset is not None and keyset == prev_keyset:
            stop_reason = "no_progress"
            break
        prev_keyset = keyset

    # --- loop ended without acceptance: return best-so-far ---
    best = best_judged or fallback_best or _top_of_pool(pool)
    return _finish(
        beat, best, pool, trace, spend, accepted=False,
        grade=(trace[-1].grade if trace else Grade.INCORRECT.value),
        reason=stop_reason or "exhausted",
    )


# --- internals --------------------------------------------------------------


def _default_search(query: str, **kwargs: Any) -> list[ImageResult]:
    import illustration  # lazy to avoid an import cycle at module load

    return illustration.search(query, **kwargs)


def _resolve_sources(sources: "str | list[str] | None") -> list[str]:
    if sources is None:
        return list(DFLT_SOURCES)
    return [sources] if isinstance(sources, str) else list(sources)


def _run_search(queries, source_list, n, search, spend: _Spend, budget: Budget) -> list[ImageResult]:
    """Search each (query, source) request, honoring the per-request search cap.

    Each provider request is gated and charged individually, so the cap bounds
    real provider HTTP requests (not just logical queries) and the cost overlay
    can price each source's request separately.
    """
    out: list[ImageResult] = []
    for query in queries:
        for source in source_list:
            if spend.search_calls >= budget.max_search_calls:
                return out
            if budget.max_cost is not None and spend.est_cost >= budget.max_cost:
                return out
            _charge(spend, budget, "search", {"query": query, "source": source})
            spend.search_calls += 1
            try:
                out.extend(search(query, source=source, n=n))
            except Exception:  # one provider hiccup mustn't sink the round
                continue
    return out


def _fuse(results: Sequence[ImageResult]) -> list[ImageResult]:
    """Merge per-provider hits with ``ir.fuse_hits`` (rank-based; dedup by id).

    Returns the fused-ordered :class:`ImageResult` list (provider-balanced via
    Reciprocal Rank Fusion; raw scores never cross a source boundary).
    """
    if not results:
        return []
    by_key: dict[tuple, ImageResult] = {}
    hits_by_source: dict[str, list] = {}
    for r in results:
        key = (r.provider, r.id)
        by_key.setdefault(key, r)
        hits_by_source.setdefault(r.provider, []).append(to_search_hit(r))

    from ir import fuse_hits

    ordered: list[ImageResult] = []
    seen: set = set()
    for hit in fuse_hits(hits_by_source):
        key = (hit.source, hit.artifact_id)
        if key in by_key and key not in seen:
            seen.add(key)
            ordered.append(by_key[key])
    return ordered


def _rerank(beat, results, scorer) -> list[ImageResult]:
    """SigLIP rerank when available/injected; else score by the fused rank.

    The fallback derives a strictly-positive, rank-descending score from the
    already-fused order rather than copying the fused scores: ``fuse_hits``
    preserves raw scores for a single source, which are ``0.0`` for un-reranked
    Layer-1 results — and an all-zero set would collapse ``ir.select`` to a
    degenerate case, flattening the grade. Synthesizing from rank keeps the
    relative structure the grader reads.
    """
    if not results:
        return []
    if scorer is not None or _rerank_available():
        from illustration.reranking import rerank as _rk

        return _rk(beat, results, scorer=scorer)
    total = len(results)
    return [
        r.model_copy(update={"score": (total - i) / total})
        for i, r in enumerate(results)
    ]


def _select(scored: Sequence[ImageResult], budget: Budget):
    from ir import select

    hits = [to_search_hit(r) for r in scored]
    return select(
        hits, strategy="conservative", max_k=budget.select_max_k,
        rel=budget.select_rel, min_score=budget.min_score,
    )


def _judge_selection(beat, scored, selection, pool, describe, model, spend, budget) -> list[Candidate]:
    """VLM-judge the selected (ambiguous) candidates, honoring the judge cap."""
    selected_ids = {(h.source, h.artifact_id) for h in getattr(selection, "selected", [])}
    targets = [r for r in scored if (r.provider, r.id) in selected_ids] or list(scored[:budget.select_max_k])
    judged: list[Candidate] = []
    for r in targets:
        if not _can_judge(spend, budget):
            break
        _charge(spend, budget, "judge", {"id": r.id})
        spend.judge_calls += 1
        report: InspectReport = inspect_candidate(beat, r, mode="judge", describe=describe, model=model)
        cand = pool[(r.provider, r.id)]
        cand.score = r.score
        cand.rubric = report.rubric
        cand.rationale = report.rationale
        judged.append(cand)
    return judged


def _critique_from_judgements(judged: Sequence[Candidate], budget: Budget) -> str:
    """Summarize why the best judged candidate fell short, to steer the refine."""
    if not judged:
        return "the candidates did not match the scene"
    best = max(judged, key=lambda c: c.quality)
    rubric = best.rubric
    if rubric is None:
        return "the candidates did not match the scene"
    dims = {
        "subject": rubric.subject, "action": rubric.action, "setting": rubric.setting,
        "mood": rubric.mood, "style": rubric.style, "quality": rubric.quality,
    }
    weakest = min(dims, key=dims.get)
    return (
        f"best match scored {rubric.overall:.2f} (< {budget.accept_threshold:.2f}); "
        f"weakest on {weakest}"
    )


def _absorb(pool: dict, scored: Sequence[ImageResult]) -> None:
    for r in scored:
        key = (r.provider, r.id)
        if key not in pool:
            pool[key] = Candidate(result=r, score=r.score)
        else:
            pool[key].score = r.score


def _top_of_pool(pool: dict) -> "Candidate | None":
    if not pool:
        return None
    return max(pool.values(), key=lambda c: (c.score if c.score is not None else 0.0))


def _record(iteration, queries, candidates, pf, grade, action, best_score,
            sc, cc, jc, notes) -> IterationRecord:
    return IterationRecord(
        iteration=iteration, queries=list(queries), n_candidates=len(candidates),
        n_passed=len(pf.passed), grade=grade.value if isinstance(grade, Grade) else str(grade),
        action=action, best_score=best_score, search_calls=sc, caption_calls=cc,
        judge_calls=jc, notes=notes,
    )


def _finish(beat, best, pool, trace, spend, *, accepted, grade, reason) -> CurationResult:
    candidates = sorted(
        pool.values(), key=lambda c: (c.quality, c.score if c.score is not None else 0.0),
        reverse=True,
    )
    return CurationResult(
        beat=beat, best=best, accepted=accepted,
        grade=grade.value if isinstance(grade, Grade) else str(grade),
        reason=reason, candidates=candidates, trace=trace, spend=spend.as_dict(),
    )


def _can_caption(spend: _Spend, budget: Budget) -> bool:
    return spend.caption_calls < budget.max_caption_calls and not _over_cost(spend, budget)


def _can_judge(spend: _Spend, budget: Budget) -> bool:
    return spend.judge_calls < budget.max_judge_calls and not _over_cost(spend, budget)


def _over_cost(spend: _Spend, budget: Budget) -> bool:
    return budget.max_cost is not None and spend.est_cost >= budget.max_cost


def _charge(spend: _Spend, budget: Budget, call_type: str, info: dict) -> None:
    if budget.cost_estimator is not None:
        spend.est_cost += float(budget.cost_estimator(call_type, info))


def _rerank_available() -> bool:
    import importlib.util

    return all(
        importlib.util.find_spec(m) is not None
        for m in ("torch", "transformers", "PIL", "numpy")
    )
