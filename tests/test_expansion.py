"""Tests for illustration.expansion (offline — LLM seams are stubbed)."""

from illustration.expansion import (
    _parse_lines,
    expand_query,
    make_query_expander,
    refine_query,
)


def test_expand_includes_verbatim_first():
    out = expand_query("a stormy harbour", expander=lambda beat: ["harbour storm", "rough sea"])
    assert out == ["a stormy harbour", "harbour storm", "rough sea"]


def test_expand_can_exclude_verbatim():
    out = expand_query("beat", expander=lambda b: ["x"], include_verbatim=False)
    assert out == ["x"]


def test_expand_dedupes_case_insensitively():
    out = expand_query("Harbour", expander=lambda b: ["harbour", "HARBOUR", "pier"])
    assert out == ["Harbour", "pier"]


def test_expand_falls_back_to_verbatim_on_expander_error():
    def boom(beat):
        raise RuntimeError("llm down")

    assert expand_query("the beat", expander=boom) == ["the beat"]


def test_refine_uses_refiner():
    out = refine_query("beat", "too generic", refiner=lambda b, c: "harbour at dusk")
    assert out == "harbour at dusk"


def test_refine_falls_back_to_beat_on_empty():
    assert refine_query("beat", "crit", refiner=lambda b, c: "  ") == "beat"


def test_refine_falls_back_to_beat_on_error():
    def boom(b, c):
        raise RuntimeError

    assert refine_query("beat", "crit", refiner=boom) == "beat"


def test_parse_lines_strips_bullets_and_numbers():
    text = "1. harbour storm\n- rough sea\n* dusk pier\n\n  \n2) fishing boats"
    assert _parse_lines(text) == ["harbour storm", "rough sea", "dusk pier", "fishing boats"]


def test_make_query_expander_returns_callable():
    # Building the expander must not import aix (lazy on call only).
    assert callable(make_query_expander(n=2))
