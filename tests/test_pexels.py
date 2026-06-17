"""Tests for the Pexels source adapter (offline, injected session)."""

import pytest

from illustration.credentials import using_credentials
from illustration.errors import MissingCredentialError
from illustration.providers.pexels import PexelsSource


def test_normalize(make_session, pexels_payload):
    src = PexelsSource(session=make_session({1: pexels_payload}))
    results = src.search("harbour", n=1, api_key="test-key")
    assert len(results) == 1
    r = results[0]
    assert r.provider == "pexels"
    assert r.id == "123"  # coerced to str
    # url is the full-res image, NOT the web page
    assert r.url == "https://images.pexels.example/123/orig.jpg"
    assert r.thumbnail_url == "https://images.pexels.example/123/tiny.jpg"
    assert r.source_page_url == "https://www.pexels.com/photo/123/"  # the page
    assert r.description == "A stormy harbour at dusk"
    assert r.tags == []  # Pexels returns none
    assert r.license == "Pexels License"
    assert r.attribution == "Photo by John Smith on Pexels"
    assert r.author == "John Smith"
    assert r.avg_color == "#5A6B7C"
    assert r.cacheable is True


def test_authorization_header_is_raw_key_no_bearer(make_session, pexels_payload):
    sess = make_session({1: pexels_payload})
    PexelsSource(session=sess).search("x", n=1, api_key="RAWKEY")
    auth = sess.calls[0]["headers"]["Authorization"]
    assert auth == "RAWKEY"
    assert not auth.startswith("Bearer ")


def test_missing_key_raises(make_session, pexels_payload, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.setattr("illustration.credentials._config_store_get", lambda key: None)
    src = PexelsSource(session=make_session({1: pexels_payload}))
    with pytest.raises(MissingCredentialError):
        src.search("x", n=1)


def test_key_via_using_credentials(make_session, pexels_payload):
    sess = make_session({1: pexels_payload})
    src = PexelsSource(session=sess)
    with using_credentials(pexels="CTXKEY"):
        results = src.search("x", n=1)
    assert results[0].provider == "pexels"
    assert sess.calls[0]["headers"]["Authorization"] == "CTXKEY"
