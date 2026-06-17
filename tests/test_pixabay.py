"""Tests for the Pixabay source adapter (offline, injected session)."""

import pytest

from illustration.credentials import using_credentials
from illustration.errors import MissingCredentialError
from illustration.providers.pixabay import PixabaySource


def test_normalize(make_session, pixabay_payload):
    src = PixabaySource(session=make_session({1: pixabay_payload}))
    results = src.search("harbour", n=1, api_key="test-key")
    assert len(results) == 1
    r = results[0]
    assert r.provider == "pixabay"
    assert r.id == "555"
    assert r.url == "https://cdn.pixabay.example/555_1280.jpg"  # largeImageURL
    assert r.thumbnail_url == "https://cdn.pixabay.example/555_150.jpg"
    assert r.width == 4000 and r.height == 3000
    assert r.tags == ["harbour", "boats", "dusk"]  # comma string split
    assert r.license == "Pixabay License"
    assert r.attribution == "Image by janedoe on Pixabay"
    assert r.author == "janedoe"
    assert r.source_page_url == "https://pixabay.com/photos/harbour-555/"
    assert r.cacheable is True


def test_key_is_query_param_not_header(make_session, pixabay_payload):
    sess = make_session({1: pixabay_payload})
    PixabaySource(session=sess).search("x", n=1, api_key="SECRETKEY")
    call = sess.calls[0]
    assert call["params"]["key"] == "SECRETKEY"  # key rides in the query params
    assert "Authorization" not in call["headers"]


def test_param_translation(make_session, pixabay_payload):
    sess = make_session({1: pixabay_payload})
    PixabaySource(session=sess).search(
        "x", n=1, api_key="k",
        orientation="landscape", safe=True, content_type="illustration",
        native_params={"colors": "blue"},
    )
    sent = sess.calls[0]["params"]
    assert sent["orientation"] == "horizontal"  # landscape -> horizontal
    assert sent["safesearch"] == "true"  # safe -> safesearch
    assert sent["image_type"] == "illustration"  # content_type -> image_type
    assert sent["colors"] == "blue"


def test_missing_key_raises(make_session, pixabay_payload, monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.setattr("illustration.credentials._config_store_get", lambda key: None)
    src = PixabaySource(session=make_session({1: pixabay_payload}))
    with pytest.raises(MissingCredentialError):
        src.search("x", n=1)


def test_key_via_using_credentials(make_session, pixabay_payload):
    sess = make_session({1: pixabay_payload})
    with using_credentials(pixabay="CTX"):
        PixabaySource(session=sess).search("x", n=1)
    assert sess.calls[0]["params"]["key"] == "CTX"


def test_raw_search_carries_key(make_session, pixabay_payload):
    sess = make_session({1: pixabay_payload})
    PixabaySource(session=sess).raw_search(api_key="K", q="x")
    sent = sess.calls[0]["params"]
    assert sent["key"] == "K"  # _auth_params injects the key for raw_search too
    assert sent["q"] == "x"


def test_invalid_size_or_orientation_dropped(make_session, pixabay_payload):
    sess = make_session({1: pixabay_payload})
    PixabaySource(session=sess).search("x", n=1, api_key="k", size="huge", orientation="sideways")
    sent = sess.calls[0]["params"]
    assert "min_width" not in sent  # invalid size dropped (choices guard), not min_width=0
    assert "orientation" not in sent  # invalid orientation dropped
