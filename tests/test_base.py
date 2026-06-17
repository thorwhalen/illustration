"""Tests for the RetrievalSource base: pagination, escape hatch, error handling."""

import pytest

from illustration.base import RetrievalSource
from illustration.errors import ProviderError, RateLimitError
from illustration.schema import ImageResult


class _FakeSource(RetrievalSource):
    name = "fake"
    endpoint = "http://example/api"
    query_param = "q"
    page_param = "page"
    per_page_param = "pp"
    max_per_page = 2  # small, to force pagination
    param_map = {"size": "size"}

    def _items(self, response):
        return response.get("items", [])

    def _normalize(self, item, *, query):
        if item.get("bad"):
            raise ValueError("malformed item")
        return ImageResult(provider="fake", id=str(item["id"]), url=item["u"], query=query)


def _page(ids):
    return {"items": [{"id": i, "u": f"u{i}"} for i in ids]}


def test_pagination_across_pages(make_session):
    sess = make_session({1: _page([1, 2]), 2: _page([3])})
    src = _FakeSource(session=sess)
    results = src.search("q", n=3)
    assert [r.id for r in results] == ["1", "2", "3"]
    # page 1 was full (2 == pp) so it fetched page 2; page 2 short -> stop
    assert [c["params"]["page"] for c in sess.calls] == [1, 2]


def test_truncates_to_n(make_session):
    sess = make_session({1: _page([1, 2]), 2: _page([3, 4])})
    src = _FakeSource(session=sess)
    results = src.search("q", n=3)
    assert len(results) == 3


def test_stops_on_empty_page(make_session):
    sess = make_session({1: _page([1, 2]), 2: {"items": []}})
    src = _FakeSource(session=sess)
    results = src.search("q", n=10)
    assert [r.id for r in results] == ["1", "2"]


def test_bad_item_is_skipped_not_fatal(make_session):
    sess = make_session({1: {"items": [{"id": 1, "u": "u1"}, {"bad": True}]}})
    src = _FakeSource(session=sess)
    results = src.search("q", n=2)
    assert [r.id for r in results] == ["1"]


def test_native_params_override_escape_hatch(make_session):
    sess = make_session({1: _page([1])})
    src = _FakeSource(session=sess)
    src.search("q", n=1, size="large", native_params={"color": "blue", "size": "small"})
    sent = sess.calls[0]["params"]
    assert sent["color"] == "blue"
    assert sent["size"] == "small"  # native override wins over translated canonical


def test_empty_query_rejected(make_session):
    src = _FakeSource(session=make_session({1: _page([1])}))
    with pytest.raises(ValueError):
        src.search("", n=1)


def test_rate_limit_error(make_session):
    sess = make_session(response={"items": []}, status_code=429)
    with pytest.raises(RateLimitError):
        _FakeSource(session=sess).search("q", n=1)


def test_auth_error(make_session):
    sess = make_session(response={"items": []}, status_code=401)
    with pytest.raises(ProviderError):
        _FakeSource(session=sess).search("q", n=1)


def test_raw_search_passthrough(make_session):
    sess = make_session(response={"items": [{"id": 9, "u": "u9"}]})
    src = _FakeSource(session=sess)
    raw = src.raw_search(q="anything", custom_native="x")
    assert raw["items"][0]["id"] == 9
    assert sess.calls[0]["params"] == {"q": "anything", "custom_native": "x"}
