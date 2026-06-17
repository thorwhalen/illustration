"""Tests for the Openverse source adapter (offline, injected session)."""

from illustration.providers.openverse import OpenverseSource


def test_normalize_first_result(make_session, openverse_payload):
    src = OpenverseSource(session=make_session({1: openverse_payload}))
    results = src.search("stormy harbour", n=2)
    assert len(results) == 2
    r = results[0]
    assert r.provider == "openverse"
    assert r.id == "uuid-1"
    assert r.url == "https://img.example/full1.jpg"
    assert r.thumbnail_url.endswith("/thumb/")
    assert r.width == 1024 and r.height == 768
    assert r.license == "by-sa"
    assert r.license_url.endswith("/by-sa/2.0/")
    assert r.attribution.startswith('"Stormy Harbour"')
    assert r.source_page_url == "https://flickr.example/photos/jane/1"
    assert r.author == "Jane Doe"
    assert r.cacheable is True
    assert r.query == "stormy harbour"
    # tags: objects with .name only; the one without a name is dropped
    assert r.tags == ["harbour", "storm"]
    # raw payload preserved (escape hatch)
    assert r.raw["provider"] == "flickr"


def test_cc0_has_null_license_url(make_session, openverse_payload):
    src = OpenverseSource(session=make_session({1: openverse_payload}))
    results = src.search("dusk", n=2)
    cc0 = results[1]
    assert cc0.license == "cc0"
    assert cc0.license_url is None


def test_orientation_and_safe_translation(make_session, openverse_payload):
    sess = make_session({1: openverse_payload})
    src = OpenverseSource(session=sess)
    src.search("x", n=1, orientation="landscape", safe=True, size="large")
    sent = sess.calls[0]["params"]
    assert sent["aspect_ratio"] == "wide"  # landscape -> wide
    assert sent["mature"] is False  # safe=True -> mature=False
    assert sent["size"] == "large"
    assert sent["q"] == "x"


def test_no_api_key_header(make_session, openverse_payload):
    sess = make_session({1: openverse_payload})
    OpenverseSource(session=sess).search("x", n=1)
    assert "Authorization" not in sess.calls[0]["headers"]
    assert sess.calls[0]["headers"]["User-Agent"].startswith("illustration/")


def test_content_type_translation(make_session, openverse_payload):
    sess = make_session({1: openverse_payload})
    src = OpenverseSource(session=sess)
    # photo -> category=photograph
    src.search("x", n=1, content_type="photo")
    assert sess.calls[0]["params"]["category"] == "photograph"
    # vector is unsupported by Openverse's category -> dropped (not sent)
    src.search("x", n=1, content_type="vector")
    assert "category" not in sess.calls[1]["params"]
