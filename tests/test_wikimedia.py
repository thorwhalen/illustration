"""Tests for the Wikimedia Commons source adapter (offline, injected session)."""

from illustration.providers.wikimedia import WikimediaSource


def test_normalize_and_mime_filter(make_session, wikimedia_payload):
    src = WikimediaSource(session=make_session({1: wikimedia_payload}))
    results = src.search("stormy harbour", n=10)
    # the audio file (mime audio/ogg) is dropped; only the image remains
    assert len(results) == 1
    r = results[0]
    assert r.provider == "wikimedia"
    assert r.id == "12345"
    assert r.title == "Stormy Harbour.jpg"  # "File:" prefix stripped
    assert r.url == "https://upload.wikimedia.example/Stormy_Harbour.jpg"
    assert r.thumbnail_url.endswith("330px-Stormy_Harbour.jpg")
    assert r.width == 1024 and r.height == 768
    assert r.license == "cc-by-sa-4.0"
    assert r.license_url.endswith("/by-sa/4.0")
    assert r.author == "Alice"  # HTML stripped from Artist
    assert r.author_url == "https://commons.wikimedia.org/wiki/User:Alice"  # href lifted, // -> https
    assert r.description == "A stormy harbour at dusk."  # HTML stripped
    assert r.attribution == "Alice / CC BY-SA 4.0, via Wikimedia Commons"
    assert r.source_page_url.endswith("File:Stormy_Harbour.jpg")
    assert r.cacheable is True


def test_fixed_params_and_offset_pagination(make_session, wikimedia_payload):
    sess = make_session({1: wikimedia_payload})
    WikimediaSource(session=sess).search("harbour", n=5)
    sent = sess.calls[0]["params"]
    # fixed params are present
    assert sent["action"] == "query"
    assert sent["generator"] == "search"
    assert sent["gsrnamespace"] == "6"
    assert sent["prop"] == "imageinfo"
    # query goes to gsrsearch; pagination is offset-based
    assert sent["gsrsearch"] == "harbour"
    assert sent["gsrlimit"] == 5
    assert sent["gsroffset"] == 0


def test_offset_advances_on_page_two(make_session):
    # page 1 full (== per_page) forces a second page; assert gsroffset advances
    def img_page(idx):
        return {"query": {"pages": {str(idx): {
            "pageid": idx, "index": idx, "title": f"File:img{idx}.jpg",
            "imageinfo": [{"mime": "image/jpeg", "url": f"u{idx}", "width": 1, "height": 1,
                           "descriptionurl": "d", "extmetadata": {}}],
        }}}}
    # per_page becomes 1 (n=2, but we cap via max_per_page on the instance)
    src = WikimediaSource(session=make_session({1: img_page(1), 2: img_page(2)}))
    src.max_per_page = 1
    results = src.search("q", n=2)
    # page 2 must serve DIFFERENT content (the offset-aware fake honors gsroffset)
    assert [r.id for r in results] == ["1", "2"]
    offsets = [c["params"]["gsroffset"] for c in src._session.calls]
    assert offsets == [0, 1]


def test_no_key_needed(make_session, wikimedia_payload):
    sess = make_session({1: wikimedia_payload})
    WikimediaSource(session=sess).search("x", n=1)  # no api_key, no raise
    assert "Authorization" not in sess.calls[0]["headers"]


def test_raw_search_carries_fixed_params(make_session, wikimedia_payload):
    sess = make_session({1: wikimedia_payload})
    WikimediaSource(session=sess).raw_search(gsrsearch="harbour")
    sent = sess.calls[0]["params"]
    assert sent["action"] == "query"  # fixed_params present even in raw_search
    assert sent["gsrsearch"] == "harbour"


def test_nonempty_attribution_used_verbatim(make_session):
    payload = {"query": {"pages": {"1": {
        "pageid": 1, "index": 1, "title": "File:X.jpg",
        "imageinfo": [{"mime": "image/jpeg", "url": "u", "width": 1, "height": 1,
                       "descriptionurl": "d",
                       "extmetadata": {"Attribution": {"value": "Use freely, credit ACME"},
                                       "Artist": {"value": "ACME"},
                                       "LicenseShortName": {"value": "CC BY 4.0"}}}],
    }}}}
    r = WikimediaSource(session=make_session({1: payload})).search("x", n=1)[0]
    assert r.attribution == "Use freely, credit ACME"  # verbatim, not the built fallback


def test_image_with_empty_extmetadata_normalizes(make_session):
    payload = {"query": {"pages": {"1": {
        "pageid": 1, "index": 1, "title": "File:X.jpg",
        "imageinfo": [{"mime": "image/png", "url": "u", "width": 1, "height": 1,
                       "descriptionurl": "d", "extmetadata": {}}],
    }}}}
    r = WikimediaSource(session=make_session({1: payload})).search("x", n=1)[0]
    assert r.license is None and r.author is None and r.attribution is None  # no crash


def test_attribution_and_href_helpers():
    from illustration.providers.wikimedia import _build_attribution, _first_href, _strip_html

    # attribution fallbacks
    assert _build_attribution("Bob", "CC0") == "Bob / CC0, via Wikimedia Commons"
    assert _build_attribution("Bob", None) == "Bob, via Wikimedia Commons"
    assert _build_attribution(None, "CC0") == "CC0, via Wikimedia Commons"
    assert _build_attribution(None, None) is None
    # href: absolute https stays, protocol-relative gets https:, none -> None
    assert _first_href('<a href="https://x/u">n</a>') == "https://x/u"
    assert _first_href('<a href="//x/u">n</a>') == "https://x/u"
    assert _first_href("no link here") is None
    assert _strip_html(None) is None and _strip_html("<b>x</b>") == "x"
