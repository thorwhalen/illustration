"""Candidate inspection — classical-CV pre-filters + VLM caption/judge (R2 §2-3).

Two cost tiers, cheapest first:

1. **Classical-CV pre-filters** (R2 §3) — sub-10ms/image checks (aspect ratio,
   minimum size, brightness, blur, NSFW) that drop unusable candidates *before*
   any VLM token is spent. This is the single biggest cost lever in the loop.
   License-safe libraries only: Pillow (MIT-CMU) + NumPy for the core checks;
   the NSFW gate defaults to the Apache-2.0 ``Falconsai/nsfw_image_detection``
   ViT (the torch stack the reranker already uses) and is fully injectable.
2. **VLM inspect** (R2 §2) — a cheap one-sentence caption for the *Correct* path,
   or a full pointwise rubric judgement for the *Ambiguous* path. Both go through
   the injectable ``describe`` seam, which defaults to :func:`aix.describe_image`
   (lazy import). Judgements are **pointwise** (one image at a time) rather than
   pairwise, mitigating the position bias that plagues comparative VLM judges
   (R2 §4); use a judge model from a *different* family than any generator to
   cut self-preference bias.

Every expensive step is an injectable seam, so the whole module is testable
offline with stubs (synthetic PIL images for the CV checks, canned strings for
``describe``) — no network, no paid API.

>>> # offline: a metadata-only check needs no image fetch
>>> from illustration.schema import ImageResult
>>> r = ImageResult(provider="p", id="1", url="u", width=1200, height=800)
>>> out = aspect_ratio_check()(r, lambda: None)
>>> out.name, out.passed
('aspect_ratio', True)
"""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Sequence

from pydantic import BaseModel, Field

from illustration._imageio import DFLT_IMAGE_FIELD, memoized_image_loader
from illustration.errors import CurateDependencyError
from illustration.schema import ImageResult

__all__ = [
    # prefilter
    "CheckOutcome",
    "PrefilterReport",
    "PrefilterResult",
    "Check",
    "prefilter",
    "aspect_ratio_check",
    "min_dimension_check",
    "brightness_check",
    "blur_check",
    "nsfw_check",
    "CORE_CHECKS",
    "DEFAULT_CHECKS",
    "default_checks",
    "SafetyGateDisabledWarning",
    # VLM inspect
    "RubricScore",
    "InspectReport",
    "Describe",
    "inspect_candidate",
    "judge_candidate",
    "CAPTION_PROMPT",
    "JUDGE_PROMPT",
    "DFLT_CAPTION_MAX_TOKENS",
    "DFLT_JUDGE_MAX_TOKENS",
]


class SafetyGateDisabledWarning(UserWarning):
    """Raised when the default pre-filter set runs without the NSFW safety gate."""


# --------------------------------------------------------------------------- #
# Classical-CV pre-filters
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CheckOutcome:
    """The result of one check on one candidate."""

    name: str
    passed: bool
    value: "float | None" = None
    reason: "str | None" = None


#: A check maps (result, get_image) -> CheckOutcome. ``get_image`` is a 0-arg
#: thunk returning the candidate's PIL image (cached) or ``None`` if unfetchable;
#: metadata-only checks ignore it (so a metadata fail never triggers a fetch).
Check = Callable[[ImageResult, "Callable[[], Any]"], CheckOutcome]


class PrefilterReport(BaseModel):
    """Per-candidate pre-filter verdict (the R2 PREFILTER stage record)."""

    provider: str
    id: str
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    values: dict[str, float] = Field(default_factory=dict)


@dataclass
class PrefilterResult:
    """The outcome of pre-filtering a candidate set."""

    passed: list[ImageResult]
    reports: list[PrefilterReport]

    @property
    def dropped(self) -> list[PrefilterReport]:
        """Reports for the candidates that failed at least one check."""
        return [r for r in self.reports if not r.passed]


def prefilter(
    results: Sequence[ImageResult],
    *,
    checks: "Sequence[Check] | None" = None,
    field: str = DFLT_IMAGE_FIELD,
    fetch: "Callable | None" = None,
) -> PrefilterResult:
    """Run ``checks`` over ``results``, keeping only candidates that pass all.

    Checks run cheapest-first and **short-circuit** on the first failure, so a
    candidate dropped on its (free) metadata never triggers an image fetch.
    Images are fetched at most once per URL (in-memory, for this call only);
    ``fetch`` overrides the fetch function (a test double avoids the network).
    ``checks`` defaults to :func:`default_checks` (core CV + NSFW where its deps
    are available).

    Returns a :class:`PrefilterResult` with the surviving ``passed`` results and
    a :class:`PrefilterReport` per input candidate.
    """
    checks = list(checks if checks is not None else default_checks())
    loader = memoized_image_loader(field=field, fetch=fetch)

    passed: list[ImageResult] = []
    reports: list[PrefilterReport] = []
    for result in results:
        get_image = lambda r=result: loader(r)  # noqa: E731 - intentional per-result thunk
        ok = True
        reasons: list[str] = []
        values: dict[str, float] = {}
        for check in checks:
            outcome = check(result, get_image)
            if outcome.value is not None:
                values[outcome.name] = outcome.value
            if not outcome.passed:
                ok = False
                reasons.append(outcome.reason or f"{outcome.name} failed")
                break  # short-circuit: stop at the first failure
        reports.append(
            PrefilterReport(
                provider=result.provider, id=result.id, passed=ok,
                reasons=reasons, values=values,
            )
        )
        if ok:
            passed.append(result)
    return PrefilterResult(passed=passed, reports=reports)


def aspect_ratio_check(*, min_ratio: float = 0.2, max_ratio: float = 5.0) -> Check:
    """Reject degenerate aspect ratios (extreme slivers/panoramas). Metadata-only.

    Uses the result's ``width``/``height``; passes when either is missing (can't
    assess). ``ratio = width / height``.
    """

    def check(result: ImageResult, get_image: "Callable[[], Any]") -> CheckOutcome:
        if not result.width or not result.height:
            return CheckOutcome("aspect_ratio", passed=True, reason="no dimensions")
        ratio = result.width / result.height
        ok = min_ratio <= ratio <= max_ratio
        reason = None if ok else f"aspect ratio {ratio:.2f} outside [{min_ratio}, {max_ratio}]"
        return CheckOutcome("aspect_ratio", passed=ok, value=round(ratio, 3), reason=reason)

    return check


def min_dimension_check(*, min_width: int = 200, min_height: int = 200) -> Check:
    """Reject tiny images. Metadata-only (passes when dimensions are unknown)."""

    def check(result: ImageResult, get_image: "Callable[[], Any]") -> CheckOutcome:
        if not result.width or not result.height:
            return CheckOutcome("min_dimension", passed=True, reason="no dimensions")
        ok = result.width >= min_width and result.height >= min_height
        reason = None if ok else f"{result.width}x{result.height} below {min_width}x{min_height}"
        return CheckOutcome(
            "min_dimension", passed=ok, value=float(min(result.width, result.height)), reason=reason
        )

    return check


def brightness_check(*, min_brightness: float = 0.10, max_brightness: float = 0.95) -> Check:
    """Reject near-black / blown-out images. Mean luminance, normalized to [0, 1]."""

    def check(result: ImageResult, get_image: "Callable[[], Any]") -> CheckOutcome:
        image = get_image()
        if image is None:
            return CheckOutcome("brightness", passed=False, reason="image unavailable")
        from PIL import ImageStat

        mean = ImageStat.Stat(image.convert("L")).mean[0] / 255.0
        ok = min_brightness <= mean <= max_brightness
        reason = None if ok else f"brightness {mean:.2f} outside [{min_brightness}, {max_brightness}]"
        return CheckOutcome("brightness", passed=ok, value=round(mean, 3), reason=reason)

    return check


def blur_check(*, min_variance: float = 100.0) -> Check:
    """Reject blurry images via variance of the Laplacian (R2 §3; OpenCV-free).

    The 3x3 Laplacian is applied with NumPy (no OpenCV) on the grayscale image;
    a low response variance means few sharp edges, i.e. blur.
    """

    def check(result: ImageResult, get_image: "Callable[[], Any]") -> CheckOutcome:
        image = get_image()
        if image is None:
            return CheckOutcome("blur", passed=False, reason="image unavailable")
        variance = _laplacian_variance(image)
        ok = variance >= min_variance
        reason = None if ok else f"blur variance {variance:.0f} below {min_variance:.0f}"
        return CheckOutcome("blur", passed=ok, value=round(variance, 1), reason=reason)

    return check


def nsfw_check(
    *, max_prob: float = 0.5, classifier: "Callable[[Any], float] | None" = None
) -> Check:
    """Hard-drop unsafe images (R2: NSFW is a non-negotiable drop).

    ``classifier`` is ``image -> nsfw_probability``; it defaults to the
    Apache-2.0 ``Falconsai/nsfw_image_detection`` ViT (torch/transformers — the
    ``[rerank]`` extra). Fails **closed**: a candidate whose image can't be
    fetched or classified is dropped, never passed.
    """

    def check(result: ImageResult, get_image: "Callable[[], Any]") -> CheckOutcome:
        clf = classifier if classifier is not None else _default_nsfw_classifier()
        image = get_image()
        if image is None:
            return CheckOutcome("nsfw", passed=False, reason="image unavailable (safety fails closed)")
        try:
            prob = float(clf(image))
        except Exception as e:
            return CheckOutcome("nsfw", passed=False, reason=f"nsfw check errored: {e}")
        ok = prob <= max_prob
        reason = None if ok else f"nsfw probability {prob:.2f} > {max_prob}"
        return CheckOutcome("nsfw", passed=ok, value=round(prob, 3), reason=reason)

    return check


#: Core checks — need only Pillow + NumPy (the ``[curate]`` extra), no model.
CORE_CHECKS: tuple = (
    aspect_ratio_check(),
    min_dimension_check(),
    brightness_check(),
    blur_check(),
)


#: The recommended set: core CV + the NSFW gate. The NSFW check needs the
#: classifier deps (``[rerank]`` extra); see :func:`default_checks` for the
#: dependency-aware default actually used when ``checks`` is omitted.
DEFAULT_CHECKS: tuple = CORE_CHECKS + (nsfw_check(),)


def default_checks() -> tuple:
    """The default check set, chosen by what's installed.

    Returns :data:`DEFAULT_CHECKS` (core + NSFW) when the NSFW classifier deps
    are importable, else :data:`CORE_CHECKS` — and **emits a
    :class:`SafetyGateDisabledWarning`** so the absence of the safety screen is
    never silent (install ``illustration[rerank]`` to enable it). Passing
    ``checks=`` to :func:`prefilter` explicitly always overrides this.
    """
    if _nsfw_available():
        return DEFAULT_CHECKS
    warnings.warn(
        "The NSFW safety gate is disabled: its classifier deps (transformers, "
        "torch) are not installed, so pre-filtering runs core CV checks only. "
        "Install illustration[rerank] to enable the safety screen, or pass an "
        "explicit `checks=` (e.g. with your own nsfw_check classifier).",
        SafetyGateDisabledWarning,
        stacklevel=2,
    )
    return CORE_CHECKS


# --------------------------------------------------------------------------- #
# VLM inspect (caption + pointwise rubric judge)
# --------------------------------------------------------------------------- #


#: The six pointwise rubric dimensions (R2 §4), in display order.
RUBRIC_DIMENSIONS = ("subject", "action", "setting", "mood", "style", "quality")


class RubricScore(BaseModel):
    """A pointwise VLM judgement of one candidate (R2 §4 rubric dimensions)."""

    subject: float = 0.0
    action: float = 0.0
    setting: float = 0.0
    mood: float = 0.0
    style: float = 0.0
    quality: float = 0.0
    overall: float = 0.0
    rationale: str = ""
    parsed: bool = True

    def recompute_overall(self) -> "RubricScore":
        """Set ``overall`` to the mean of the six rubric dimensions."""
        dims = [getattr(self, d) for d in RUBRIC_DIMENSIONS]
        self.overall = round(sum(dims) / len(dims), 4)
        return self


class InspectReport(BaseModel):
    """A VLM inspection of one candidate (caption or judge mode; R2 INSPECT)."""

    provider: str
    id: str
    mode: str  # "caption" | "judge"
    caption: "str | None" = None
    rubric: "RubricScore | None" = None
    rationale: "str | None" = None


#: A describe seam maps (image_ref, prompt) -> text. ``image_ref`` is anything
#: :func:`aix.describe_image` accepts (URL / path / bytes / PIL / data URI).
Describe = Callable[[Any, str], str]

#: Token caps for the default VLM seam — a soft cost bound on the paid path. A
#: one-sentence caption and a compact JSON rubric both need very few tokens.
DFLT_CAPTION_MAX_TOKENS = 80
DFLT_JUDGE_MAX_TOKENS = 220

CAPTION_PROMPT = (
    "In one concise sentence, describe what this image shows. Then, in a few "
    "words, say how well it fits this scene: {query}"
)

JUDGE_PROMPT = (
    "You are scoring how well an image matches a narration beat for a storyboard.\n"
    "Beat/scene: {query}\n\n"
    "Score each dimension from 0.0 (no match) to 1.0 (perfect match):\n"
    "- subject: are the key subjects present?\n"
    "- action: does the depicted action/pose match?\n"
    "- setting: does the location/environment match?\n"
    "- mood: does the lighting/mood match?\n"
    "- style: is the visual style appropriate?\n"
    "- quality: is it technically good (sharp, well-exposed, well-composed)?\n\n"
    "Respond with ONLY a compact JSON object with numeric keys subject, action, "
    "setting, mood, style, quality (each 0-1) and a 'rationale' string (one short "
    "sentence). No markdown, no code fence."
)


def inspect_candidate(
    query: str,
    result: ImageResult,
    *,
    mode: str = "caption",
    describe: "Describe | None" = None,
    model: "str | None" = None,
    max_tokens: "int | None" = None,
) -> InspectReport:
    """Inspect one candidate: a cheap caption (default) or a full rubric judge.

    ``mode="caption"`` (the *Correct*-grade path) produces a one-sentence
    caption from the thumbnail; ``mode="judge"`` (the *Ambiguous* path) delegates
    to :func:`judge_candidate`. ``describe`` defaults to a lazy
    :func:`aix.describe_image` bound to ``model`` and capped at
    ``max_tokens`` (default :data:`DFLT_CAPTION_MAX_TOKENS`).
    """
    if mode == "judge":
        return judge_candidate(query, result, describe=describe, model=model, max_tokens=max_tokens)
    cap = max_tokens if max_tokens is not None else DFLT_CAPTION_MAX_TOKENS
    fn = describe if describe is not None else _default_describe(model, max_tokens=cap)
    image_ref = result.thumbnail_url or result.url
    caption = fn(image_ref, CAPTION_PROMPT.format(query=query))
    return InspectReport(
        provider=result.provider, id=result.id, mode="caption",
        caption=(caption or "").strip() or None,
    )


def judge_candidate(
    query: str,
    result: ImageResult,
    *,
    describe: "Describe | None" = None,
    model: "str | None" = None,
    max_tokens: "int | None" = None,
) -> InspectReport:
    """Score one candidate against ``query`` with a pointwise VLM rubric.

    Uses the full-resolution image for accuracy. ``describe`` defaults to a lazy
    :func:`aix.describe_image` capped at ``max_tokens`` (default
    :data:`DFLT_JUDGE_MAX_TOKENS`). The reply is parsed into a
    :class:`RubricScore` (``overall`` = mean of the six dimensions); an
    unparseable reply yields a neutral score flagged ``parsed=False`` so the loop
    can treat it as ambiguous rather than wrongly accept or reject.
    """
    cap = max_tokens if max_tokens is not None else DFLT_JUDGE_MAX_TOKENS
    fn = describe if describe is not None else _default_describe(model, max_tokens=cap)
    image_ref = result.url or result.thumbnail_url
    text = fn(image_ref, JUDGE_PROMPT.format(query=query))
    rubric = _parse_rubric(text)
    return InspectReport(
        provider=result.provider, id=result.id, mode="judge",
        rubric=rubric, rationale=rubric.rationale or None,
    )


# --- internals --------------------------------------------------------------


def _default_describe(model: "str | None", *, max_tokens: "int | None" = None) -> Describe:
    """The default describe seam, backed by ``aix.describe_image`` (lazy)."""

    def describe(image_ref: Any, prompt: str) -> str:
        try:
            import aix  # lazy: Layer-2 dependency only
        except ImportError as e:  # pragma: no cover - exercised only without aix
            raise CurateDependencyError(["aix"]) from e
        return aix.describe_image(image_ref, prompt=prompt, model=model, max_tokens=max_tokens)

    return describe


def _parse_rubric(text: str) -> RubricScore:
    """Extract a :class:`RubricScore` from a VLM reply; neutral on parse failure."""
    blob = _extract_json_object(text)
    if blob is not None:
        try:
            data = json.loads(blob)
            data = {k: data[k] for k in data if k in {*RUBRIC_DIMENSIONS, "rationale"}}
            return RubricScore(**data).recompute_overall()
        except Exception:  # malformed numbers / structure
            pass
    return RubricScore(
        overall=0.5, parsed=False, rationale=f"unparsed VLM reply: {(text or '')[:160]}"
    )


def _extract_json_object(text: str) -> "str | None":
    """Return the first ``{...}`` JSON object substring in ``text``, if any."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else None


def _laplacian_variance(image) -> float:
    """Variance of the Laplacian of the grayscale image (sharpness; NumPy-only)."""
    import numpy as np

    gray = np.asarray(image.convert("L"), dtype="float64")
    if gray.ndim != 2 or min(gray.shape) < 3:
        return 0.0
    # 3x3 Laplacian via interior finite differences (no SciPy/OpenCV).
    lap = (
        -4.0 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    return float(lap.var())


@lru_cache(maxsize=2)
def _default_nsfw_classifier(
    model: str = "Falconsai/nsfw_image_detection",
) -> "Callable[[Any], float]":
    """Build the default NSFW classifier (Falconsai ViT, Apache-2.0; cached)."""
    if not _nsfw_available():
        raise CurateDependencyError(
            ["transformers", "torch", "pillow"], extra="rerank", purpose="the NSFW safety gate"
        )
    import os

    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_FLAX", "0")
    from transformers import pipeline

    pipe = pipeline("image-classification", model=model)

    def classify(image) -> float:
        for pred in pipe(image):
            if str(pred.get("label", "")).lower() == "nsfw":
                return float(pred.get("score", 0.0))
        return 0.0

    return classify


def _nsfw_available() -> bool:
    import importlib.util

    return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch", "PIL"))
