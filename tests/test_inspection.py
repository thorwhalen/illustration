"""Tests for illustration.inspection — CV pre-filters + VLM inspect (offline).

CV checks run on synthetic PIL images (no network); VLM inspect uses a stubbed
``describe`` (no paid API). PIL/NumPy gate the CV tests, like the rerank tests.
"""

import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

import numpy as np
from PIL import Image

from illustration.inspection import (
    RubricScore,
    _parse_rubric,
    aspect_ratio_check,
    blur_check,
    brightness_check,
    inspect_candidate,
    judge_candidate,
    min_dimension_check,
    nsfw_check,
    prefilter,
)
from illustration.schema import ImageResult


def _sharp_image(size=64):
    arr = np.random.RandomState(0).randint(0, 256, (size, size, 3), dtype="uint8")
    return Image.fromarray(arr)


def _flat_image(value=128, size=64):
    return Image.new("RGB", (size, size), (value, value, value))


def _result(id="1", **kw):
    return ImageResult(provider="p", id=id, url=f"u{id}", **kw)


class TestMetadataChecks:
    def test_aspect_ratio_pass(self):
        out = aspect_ratio_check()(_result(width=1200, height=800), lambda: None)
        assert out.passed and out.name == "aspect_ratio"

    def test_aspect_ratio_reject_sliver(self):
        out = aspect_ratio_check(min_ratio=0.5)( _result(width=100, height=1000), lambda: None)
        assert not out.passed

    def test_aspect_ratio_passes_when_dims_missing(self):
        assert aspect_ratio_check()(_result(), lambda: None).passed

    def test_min_dimension_reject_small(self):
        out = min_dimension_check(min_width=500, min_height=500)(
            _result(width=100, height=100), lambda: None
        )
        assert not out.passed

    def test_metadata_check_never_calls_get_image(self):
        sentinel = {"called": False}

        def get_image():
            sentinel["called"] = True
            return None

        aspect_ratio_check()(_result(width=10, height=10), get_image)
        assert sentinel["called"] is False


class TestImageChecks:
    def test_blur_rejects_flat_accepts_sharp(self):
        assert not blur_check()(_result(), lambda: _flat_image()).passed
        assert blur_check(min_variance=50)(_result(), lambda: _sharp_image()).passed

    def test_blur_fails_closed_when_image_missing(self):
        out = blur_check()(_result(), lambda: None)
        assert not out.passed and "unavailable" in out.reason

    def test_brightness_rejects_dark_and_blown(self):
        assert not brightness_check()(_result(), lambda: _flat_image(2)).passed
        assert not brightness_check()(_result(), lambda: _flat_image(252)).passed
        assert brightness_check()(_result(), lambda: _flat_image(128)).passed


class TestNsfwCheck:
    def test_pass_with_injected_classifier(self):
        out = nsfw_check(classifier=lambda img: 0.01)(_result(), lambda: _flat_image())
        assert out.passed and out.value == 0.01

    def test_reject_high_probability(self):
        out = nsfw_check(max_prob=0.5, classifier=lambda img: 0.9)(_result(), lambda: _flat_image())
        assert not out.passed

    def test_fails_closed_when_image_missing(self):
        out = nsfw_check(classifier=lambda img: 0.0)(_result(), lambda: None)
        assert not out.passed  # safety gate never passes an unfetchable image

    def test_fails_closed_when_classifier_errors(self):
        def boom(img):
            raise RuntimeError("model boom")

        out = nsfw_check(classifier=boom)(_result(), lambda: _flat_image())
        assert not out.passed and "errored" in out.reason


class TestDefaultChecks:
    def test_warns_when_nsfw_unavailable(self, monkeypatch):
        import illustration.inspection as insp

        monkeypatch.setattr(insp, "_nsfw_available", lambda: False)
        with pytest.warns(insp.SafetyGateDisabledWarning):
            checks = insp.default_checks()
        assert checks == insp.CORE_CHECKS  # NSFW dropped, but loudly

    def test_includes_nsfw_when_available(self, monkeypatch):
        import illustration.inspection as insp

        monkeypatch.setattr(insp, "_nsfw_available", lambda: True)
        assert insp.default_checks() == insp.DEFAULT_CHECKS


class TestPrefilter:
    def test_keeps_passing_drops_failing_short_circuit(self):
        good = _result("good", width=1000, height=700)
        bad_meta = _result("bad", width=10, height=10)  # fails aspect/min_dim first
        images = {"ugood": _sharp_image(), "ubad": _flat_image()}
        res = prefilter(
            [good, bad_meta],
            checks=[aspect_ratio_check(), min_dimension_check(), blur_check(min_variance=50)],
            fetch=lambda url: images.get(url),
        )
        assert [r.id for r in res.passed] == ["good"]
        assert len(res.dropped) == 1
        assert res.dropped[0].id == "bad"

    def test_empty_checks_passes_all_without_fetch(self):
        called = {"n": 0}

        def fetch(url):
            called["n"] += 1
            return None

        res = prefilter([_result("a"), _result("b")], checks=[], fetch=fetch)
        assert len(res.passed) == 2
        assert called["n"] == 0  # no check needed an image


class TestVlmInspect:
    def test_caption_mode(self):
        report = inspect_candidate(
            "a harbour", _result(), mode="caption",
            describe=lambda image, prompt: "A misty harbour at dawn.",
        )
        assert report.mode == "caption"
        assert report.caption == "A misty harbour at dawn."
        assert report.rubric is None

    def test_judge_mode_parses_rubric(self):
        blob = (
            '{"subject":0.9,"action":0.8,"setting":0.7,"mood":0.6,"style":0.5,'
            '"quality":0.4,"rationale":"decent"}'
        )
        report = judge_candidate("a harbour", _result(), describe=lambda image, prompt: blob)
        assert report.mode == "judge"
        assert report.rubric is not None
        assert report.rubric.parsed is True
        assert report.rubric.overall == pytest.approx((0.9 + 0.8 + 0.7 + 0.6 + 0.5 + 0.4) / 6)
        assert report.rationale == "decent"

    def test_judge_handles_code_fenced_json(self):
        blob = '```json\n{"subject":1,"action":1,"setting":1,"mood":1,"style":1,"quality":1}\n```'
        report = judge_candidate("x", _result(), describe=lambda image, prompt: blob)
        assert report.rubric.parsed is True
        assert report.rubric.overall == pytest.approx(1.0)


class TestParseRubric:
    def test_unparseable_is_neutral_and_flagged(self):
        rubric = _parse_rubric("I cannot score this image, sorry.")
        assert rubric.parsed is False
        assert rubric.overall == 0.5

    def test_valid_json_with_nonnumeric_value_is_neutral(self):
        # A structurally-valid object whose values fail validation -> the except
        # branch fires, falling safe to a neutral, flagged score.
        rubric = _parse_rubric('{"subject":"high","action":1}')
        assert rubric.parsed is False
        assert rubric.overall == 0.5

    def test_ignores_unknown_keys(self):
        rubric = _parse_rubric('{"subject":1,"action":1,"setting":1,"mood":1,"style":1,"quality":1,"bogus":42}')
        assert rubric.parsed is True
        assert isinstance(rubric, RubricScore)
