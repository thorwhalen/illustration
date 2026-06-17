"""Tests for the ImageResult schema and helpers."""

import pytest

from illustration.schema import ImageResult, license_allowlist


def test_defaults():
    r = ImageResult(provider="p", id="1", url="u")
    assert r.tags == []
    assert r.raw == {}
    assert r.cacheable is False
    assert r.score is None


def test_roundtrip_dump_validate():
    r = ImageResult(provider="p", id="1", url="u", license="cc0", tags=["a"], raw={"x": 1})
    again = ImageResult.model_validate(r.model_dump())
    assert again == r


def test_license_allowlist_default():
    a = ImageResult(provider="p", id="1", url="u", license="cc0")
    b = ImageResult(provider="p", id="2", url="u", license="by-nc")
    c = ImageResult(provider="p", id="3", url="u", license=None)
    kept = license_allowlist([a, b, c])
    assert [r.id for r in kept] == ["1"]


def test_license_allowlist_custom_and_case_insensitive():
    a = ImageResult(provider="p", id="1", url="u", license="BY-NC")
    kept = license_allowlist([a], allow={"by-nc"})
    assert [r.id for r in kept] == ["1"]


def test_to_search_hit_bridges_to_ir():
    ir = pytest.importorskip("ir")
    r = ImageResult(provider="openverse", id="abc", url="https://x/i.jpg",
                    description="a harbour", score=0.5)
    hit = r.to_search_hit()
    assert isinstance(hit, ir.SearchHit)
    assert hit.source == "openverse"
    assert hit.artifact_id == "abc"  # provider-native id; source carries provenance
    assert hit.score == 0.5
    assert hit.metadata["url"] == "https://x/i.jpg"  # full result rides in metadata
    # the disclosure pointer must resolve to the image URL (ir scans POINTER_KEYS)
    assert hit.pointer == "https://x/i.jpg"
