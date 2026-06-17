"""Tests for illustration._imageio (offline — fetch is stubbed)."""

from illustration._imageio import (
    fetch_image_bytes,
    image_for_result,
    memoized_image_loader,
)
from illustration.schema import ImageResult


def test_fetch_bytes_empty_url_returns_none():
    assert fetch_image_bytes("") is None


def test_image_for_result_no_url_returns_none():
    assert image_for_result(ImageResult(provider="p", id="1", url="")) is None


def test_memoized_loader_fetches_each_url_once():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return f"img:{url}"

    load = memoized_image_loader(fetch=fake_fetch)
    r1 = ImageResult(provider="p", id="1", url="u1", thumbnail_url="t1")
    r1b = ImageResult(provider="p", id="1b", url="u1b", thumbnail_url="t1")  # same thumb URL

    assert load(r1) == "img:t1"  # prefers thumbnail_url
    assert load(r1b) == "img:t1"  # same URL -> cached, not re-fetched
    assert load(r1) == "img:t1"
    assert calls == ["t1"]  # fetched exactly once


def test_memoized_loader_falls_back_to_url_when_field_missing():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return f"img:{url}"

    load = memoized_image_loader(fetch=fake_fetch)
    r = ImageResult(provider="p", id="1", url="full", thumbnail_url=None)
    assert load(r) == "img:full"
    assert calls == ["full"]
