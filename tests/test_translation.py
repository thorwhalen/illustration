"""Tests for canonical->native parameter translation."""

import warnings

import pytest

from illustration.translation import make_param_translator


def test_rename_and_passthrough():
    t = make_param_translator({"size": "size", "orientation": "orient"})
    native, dropped = t({"size": "large", "orientation": "portrait"})
    assert native == {"size": "large", "orient": "portrait"}
    assert dropped == []


def test_coerce_and_named_spec():
    t = make_param_translator(
        {"orientation": {"name": "aspect_ratio", "coerce": lambda o: {"landscape": "wide"}.get(o, o)}}
    )
    native, dropped = t({"orientation": "landscape"})
    assert native == {"aspect_ratio": "wide"}
    assert dropped == []


def test_none_value_is_skipped_not_dropped():
    t = make_param_translator({"size": "size"})
    native, dropped = t({"size": None})
    assert native == {} and dropped == []


def test_explicitly_unsupported_is_dropped():
    t = make_param_translator({"license_type": None})
    native, dropped = t({"license_type": "commercial"})
    assert native == {} and dropped == ["license_type"]


def test_absent_key_is_dropped():
    t = make_param_translator({"size": "size"})
    native, dropped = t({"color": "blue"})
    assert native == {} and dropped == ["color"]


def test_choices_validation_drops_under_ignore():
    t = make_param_translator({"size": {"name": "size", "choices": {"large", "small"}}})
    native, dropped = t({"size": "gigantic"})
    assert native == {} and dropped == ["size"]


def test_on_unsupported_raise():
    t = make_param_translator({"size": None}, on_unsupported="raise")
    with pytest.raises(ValueError):
        t({"size": "large"})


def test_on_unsupported_warn():
    t = make_param_translator({}, on_unsupported="warn", source_name="x")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        native, dropped = t({"color": "blue"})
    assert dropped == ["color"]
    assert any("color" in str(w.message) for w in caught)


def test_invalid_on_unsupported():
    with pytest.raises(ValueError):
        make_param_translator({}, on_unsupported="explode")


def test_callable_spec():
    t = make_param_translator({"orientation": str.upper})
    native, dropped = t({"orientation": "landscape"})
    assert native == {"orientation": "LANDSCAPE"} and dropped == []


def test_choices_raise_policy():
    t = make_param_translator(
        {"size": {"name": "size", "choices": {"large"}}}, on_unsupported="raise"
    )
    with pytest.raises(ValueError):
        t({"size": "gigantic"})


def test_choices_warn_policy():
    t = make_param_translator(
        {"size": {"name": "size", "choices": {"large"}}}, on_unsupported="warn"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        native, dropped = t({"size": "gigantic"})
    assert native == {} and dropped == ["size"]
    assert any("gigantic" in str(w.message) for w in caught)


def test_invalid_spec_type_raises():
    t = make_param_translator({"size": 123})  # not str/dict/callable/None
    with pytest.raises(TypeError):
        t({"size": "large"})
